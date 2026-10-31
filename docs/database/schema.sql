-- =====================================================================
-- 해외고객향 C/S 대응 AI Agent — 생성 SQL (테이블 정의서 v1.3)
-- 근거: 테이블 정의서 v1.3 (기능 요구사항 명세서 v1.5, 기술 명세서 v1.4)
-- DB: PostgreSQL 16 + pgvector · 작성일 2026-10-22
--
-- 실행: psql -v ON_ERROR_STOP=1 -d <DB> -f 00_create_all_v1.3.sql
--       빈 DB에서 한 번 실행한다. 전체가 한 트랜잭션이라 중간에 실패하면 아무것도 남지 않는다.
-- 데이터 적재(ref CSV 12개 + doc_index, tickets.csv, resolution_cases.csv)는 이 파일에 없다.
--
-- 순서
--   0. 확장·스키마
--   1. ref   기준정보·규칙표 25개            (정의서 §2)
--   2. gold  운영진 정답지 원본 2개 + v_inputs (정의서 §3)
--   3. svc   서비스 표 11개 + 트리거 + 함수 2개 (정의서 §4)
--   4. scoring  svc와 같은 표·함수, 채점 배치 전용 (정의서 §5)
--   5. eval  팀 정답지·채점·자체 검사 8개     (정의서 §6)
--   6. 뷰    svc·scoring의 v_ticket_summary, v_inquiry_inbox
--   7. 권한  서비스 계정(cs_service)
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 0. 확장·스키마
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector (ref.doc_chunk.embedding)

CREATE SCHEMA ref;
CREATE SCHEMA gold;
CREATE SCHEMA svc;
CREATE SCHEMA scoring;
CREATE SCHEMA eval;

COMMENT ON SCHEMA ref     IS '기준정보·규칙표. 적재 작업만 쓰고 서비스와 채점은 읽기만 한다';
COMMENT ON SCHEMA gold    IS '운영진 정답지 원본(tickets.csv, resolution_cases.csv). 서비스는 v_inputs만 읽는다';
COMMENT ON SCHEMA svc     IS '서비스 표';
COMMENT ON SCHEMA scoring IS 'svc와 같은 모양. 채점 배치 전용, 실행마다 비우고 다시 채운다';
COMMENT ON SCHEMA eval    IS '팀 정답지, 채점 결과, 자체 검사, 상담원 기록';

-- =====================================================================
-- 1. ref 스키마 (정의서 §2)
-- =====================================================================

-- ---- 2-1. 코드 표 7개 ----
CREATE TABLE ref.department (
  dept_code    text PRIMARY KEY,
  dept_name_ko text NOT NULL,
  dept_name_en text NOT NULL,
  level        text NOT NULL CHECK (level IN ('L1','L2','L3')),
  scope        text
);
COMMENT ON TABLE ref.department IS '부서 (departments.csv, 13행)';

CREATE TABLE ref.product_family (
  family            text PRIMARY KEY,
  family_name       text NOT NULL,
  tech_support_dept text NOT NULL REFERENCES ref.department (dept_code)
);
COMMENT ON TABLE ref.product_family IS '제품군 (product_master.csv의 family, family_name, tech_support_dept, 11행)';

CREATE TABLE ref.inquiry_category (
  category              text PRIMARY KEY,
  resolution_definition text NOT NULL,
  sla_resolution_coef   numeric
);
COMMENT ON TABLE ref.inquiry_category IS '문의 유형 (sla_policy.csv의 category, resolution_definition, 10행)';

CREATE TABLE ref.priority_level (
  priority   text PRIMARY KEY CHECK (priority IN ('P1','P2','P3','P4')),
  definition text NOT NULL
);
COMMENT ON TABLE ref.priority_level IS '우선순위 (priority_rules.csv의 priority, priority_definition, 4행)';

CREATE TABLE ref.customer_tier (
  tier text PRIMARY KEY
);
COMMENT ON TABLE ref.customer_tier IS '고객 등급 (customers.csv tier, 3행)';

CREATE TABLE ref.urgency (
  urgency     text PRIMARY KEY,
  description text NOT NULL
);
COMMENT ON TABLE ref.urgency IS '긴급도 (urgency_codebook.csv, 6행)';

CREATE TABLE ref.info_field (
  field text PRIMARY KEY,
  label text NOT NULL
);
COMMENT ON TABLE ref.info_field IS '정보 항목 (info_field_codebook.csv, 32행)';

-- ---- 2-2. 마스터 표 ----
CREATE TABLE ref.customer (
  customer_id    text PRIMARY KEY,
  company_masked text NOT NULL,
  country        text NOT NULL,
  tier           text NOT NULL REFERENCES ref.customer_tier (tier),
  segment        text NOT NULL,
  account_since  date,
  contact_count  integer,
  -- 대표 연락처(v1.3, 가-7). customers.csv에는 값이 없어 비어 있다
  primary_contact_name  text,
  primary_contact_email text,
  primary_contact_phone text
);
COMMENT ON TABLE ref.customer IS '고객사 (customers.csv, 600행)';

CREATE TABLE ref.product (
  product_code        text PRIMARY KEY,
  product_name        text NOT NULL,
  family              text NOT NULL REFERENCES ref.product_family (family),
  description         text,
  has_firmware        boolean NOT NULL,
  warranty_months     integer NOT NULL,
  lifecycle_status    text NOT NULL,
  std_lead_time_weeks integer NOT NULL,
  moq                 integer NOT NULL,
  list_price_usd      integer NOT NULL,
  weight_kg           text,
  dimensions_mm       text,
  ip_rating           text,
  operating_temp      text
);
COMMENT ON TABLE ref.product IS '제품 (product_master.csv, 23행). family_name·tech_support_dept → product_family, standards·certifications → 두 표, fw_latest → firmware_release.is_latest, doc_ids → document';

-- ---- 2-5. 문서 목록 (product_spec, firmware_release가 가리키므로 먼저 만든다) ----
CREATE TABLE ref.document (
  doc_id       text PRIMARY KEY,
  title        text NOT NULL,
  doc_type     text NOT NULL CHECK (doc_type IN ('DS','IG','TG','RN','MG','FAQ','POL')),
  product_code text REFERENCES ref.product (product_code),
  family       text REFERENCES ref.product_family (family),
  revision     text,
  path         text NOT NULL,
  chars        integer NOT NULL
);
COMMENT ON TABLE ref.document IS '문서 목록 (docs/doc_index.csv, 107행). 정책·FAQ는 product_code, 정책은 family가 비어 있다';

CREATE TABLE ref.product_standard (
  product_code text NOT NULL REFERENCES ref.product (product_code),
  standard     text NOT NULL,
  PRIMARY KEY (product_code, standard)
);
COMMENT ON TABLE ref.product_standard IS '제품 규격 (product_master.csv standards를 행으로 펼침, 39행)';

CREATE TABLE ref.product_certification (
  product_code  text NOT NULL REFERENCES ref.product (product_code),
  certification text NOT NULL,
  PRIMARY KEY (product_code, certification)
);
COMMENT ON TABLE ref.product_certification IS '제품 인증 (product_master.csv certifications를 행으로 펼침, 61행)';

CREATE TABLE ref.product_spec (
  product_code text NOT NULL REFERENCES ref.product (product_code),
  attribute    text NOT NULL,
  value        text NOT NULL,
  doc_id       text REFERENCES ref.document (doc_id),
  section      text,                       -- '2.10' 보존
  PRIMARY KEY (product_code, attribute)
);
COMMENT ON TABLE ref.product_spec IS '제품 사양값 (product_spec_facts.csv, 169행)';

CREATE TABLE ref.firmware_release (
  product_code text NOT NULL REFERENCES ref.product (product_code),
  fw_version   text NOT NULL,              -- '3.10' 보존
  release_date date NOT NULL,
  is_latest    boolean NOT NULL,
  changes      text,
  doc_id       text REFERENCES ref.document (doc_id),
  PRIMARY KEY (product_code, fw_version)
);
COMMENT ON TABLE ref.firmware_release IS '펌웨어 이력 (firmware_history.csv, 39행)';

-- ---- 2-3. 진단 지식 ----
CREATE TABLE ref.fault (
  fault_id                 text PRIMARY KEY,
  family                   text NOT NULL REFERENCES ref.product_family (family),
  error_code               text,
  symptom                  text NOT NULL,
  root_cause               text NOT NULL,
  diagnosis                text NOT NULL,
  action                   text NOT NULL,
  severity_hint            text NOT NULL REFERENCES ref.priority_level (priority),
  needs_onsite             boolean NOT NULL,
  needs_rma                boolean NOT NULL,
  replacement_part         text,
  typical_resolution_hours integer NOT NULL
);
COMMENT ON TABLE ref.fault IS '고장 유형 (fault_catalog.csv, 97행)';

CREATE TABLE ref.fault_product (
  fault_id       text NOT NULL REFERENCES ref.fault (fault_id),
  product_code   text NOT NULL REFERENCES ref.product (product_code),
  fw_fix_version text,
  PRIMARY KEY (fault_id, product_code)
);
COMMENT ON TABLE ref.fault_product IS '고장-제품 (fault_catalog.csv applies_to를 행으로 펼침, 156행). fw_fix_version은 고장 × 제품마다 다르다';

-- ---- 2-4. 운영 규칙 ----
CREATE TABLE ref.priority_rule (
  rule_id    text PRIMARY KEY,
  rule_order integer NOT NULL UNIQUE,       -- 원본 order
  condition  text NOT NULL,
  priority   text NOT NULL REFERENCES ref.priority_level (priority)
);
COMMENT ON TABLE ref.priority_rule IS '우선순위 규칙 (priority_rules.csv, 7행). rule_order가 작은 규칙부터 보고 처음 맞는 규칙을 쓴다(FR-011)';

CREATE TABLE ref.priority_rule_urgency (
  rule_id text NOT NULL REFERENCES ref.priority_rule (rule_id),
  urgency text NOT NULL REFERENCES ref.urgency (urgency),
  PRIMARY KEY (rule_id, urgency)
);
COMMENT ON TABLE ref.priority_rule_urgency IS '규칙의 긴급도 조건 (6행). 행이 없으면 모든 긴급도';

CREATE TABLE ref.priority_rule_category (
  rule_id  text NOT NULL REFERENCES ref.priority_rule (rule_id),
  category text NOT NULL REFERENCES ref.inquiry_category (category),
  PRIMARY KEY (rule_id, category)
);
COMMENT ON TABLE ref.priority_rule_category IS '규칙의 유형 조건 (20행). 행이 없으면 모든 유형';

CREATE TABLE ref.routing_rule (
  rule_id              text PRIMARY KEY,
  family               text REFERENCES ref.product_family (family),       -- 원본 ALL → NULL
  category             text REFERENCES ref.inquiry_category (category),
  rule_source          text NOT NULL CHECK (rule_source IN ('CATEGORY_DEFAULT','FAMILY_OVERRIDE','SUBTYPE_OVERRIDE','ESCALATION')),
  primary_dept         text REFERENCES ref.department (dept_code),       -- 원본 '(제품군 기술지원)' → NULL
  escalation_dept      text REFERENCES ref.department (dept_code),
  escalation_condition text
);
COMMENT ON TABLE ref.routing_rule IS '부서 규칙 (routing_rules.csv, 111행). primary_dept가 비어 있으면 product_family.tech_support_dept (FR-012)';

CREATE TABLE ref.required_info_rule (
  family   text NOT NULL REFERENCES ref.product_family (family),
  category text NOT NULL REFERENCES ref.inquiry_category (category),
  PRIMARY KEY (family, category)
);
COMMENT ON TABLE ref.required_info_rule IS '필수정보 규칙 (required_info.csv, 110행, FR-013)';

CREATE TABLE ref.required_info_field (
  family      text NOT NULL,
  category    text NOT NULL,
  field       text NOT NULL REFERENCES ref.info_field (field),
  field_order smallint NOT NULL,
  is_blocking boolean NOT NULL,
  PRIMARY KEY (family, category, field),
  FOREIGN KEY (family, category) REFERENCES ref.required_info_rule (family, category)
);
COMMENT ON TABLE ref.required_info_field IS '필수 항목 (required_fields, blocking_fields를 행으로 펼침, 437행). 표시 이름은 info_field.label';

CREATE TABLE ref.sla_policy (
  sla_id               text PRIMARY KEY,
  category             text NOT NULL REFERENCES ref.inquiry_category (category),
  customer_tier        text NOT NULL REFERENCES ref.customer_tier (tier),
  priority             text NOT NULL REFERENCES ref.priority_level (priority),
  first_response_hours integer NOT NULL CHECK (first_response_hours > 0),
  resolution_hours     integer NOT NULL CHECK (resolution_hours > 0),
  UNIQUE (category, customer_tier, priority)
);
COMMENT ON TABLE ref.sla_policy IS 'SLA 정책 (sla_policy.csv, 120행, FR-014)';

CREATE TABLE ref.sla_setting (
  key   text PRIMARY KEY,
  value text NOT NULL
);
COMMENT ON TABLE ref.sla_setting IS 'SLA 설정 3행: clock = 24x7, at_risk_threshold = 75%, pause_rule = WAITING_CUSTOMER 시간 제외 (FR-026)';

-- ---- 2-5. 문서 검색 청크 ----
CREATE TABLE ref.doc_chunk (
  chunk_id      text PRIMARY KEY,           -- {doc_id}§{section_no}
  doc_id        text NOT NULL REFERENCES ref.document (doc_id),
  doc_type      text NOT NULL,              -- 검색 필터용 복사
  product_code  text REFERENCES ref.product (product_code),
  family        text REFERENCES ref.product_family (family),
  section_no    text NOT NULL,              -- '2.10' 보존, FAQ는 'Q3'
  section_title text NOT NULL,
  text          text NOT NULL,
  embedding     vector,                     -- gemini-embedding-2(T38). 차원과 벡터 색인은 W2 시작 때 정한다
  UNIQUE (doc_id, section_no)
);
COMMENT ON TABLE ref.doc_chunk IS '문서 검색 청크. ##, ### 절 하나 = 한 행(T35). 색인 작업이 채운다';
CREATE INDEX doc_chunk_product_type ON ref.doc_chunk (product_code, doc_type);
CREATE INDEX doc_chunk_family_type  ON ref.doc_chunk (family, doc_type);

-- =====================================================================
-- 2. gold 스키마 (정의서 §3)
-- 원본 열 이름 그대로, 모두 TEXT(원본 보존, 형 변환은 읽을 때). 서비스 계정은 v_inputs만 읽는다.
-- =====================================================================
CREATE TABLE gold.ticket_gold (
  ticket_id                   text PRIMARY KEY,
  received_at_utc             text,
  channel                     text,
  country                     text,
  country_name                text,
  language                    text,
  body_language               text,
  locale                      text,
  customer_id                 text,
  company_masked              text,
  customer_tier               text,
  customer_segment            text,
  contact_email_masked        text,
  product_code                text,
  product_name                text,
  product_family              text,
  category_code               text,
  secondary_category          text,
  urgency_flag                text,
  inquiry_subject             text,
  inquiry_body                text,
  error_code_reported         text,
  fw_version_reported         text,
  priority                    text,
  priority_rule_id            text,
  priority_adjusted_by_agent  text,
  routing_rule_id             text,
  assigned_dept               text,
  assignee_masked             text,
  escalated                   text,
  escalated_to                text,
  escalation_reason           text,
  required_info               text,
  provided_info               text,
  missing_info                text,
  missing_blocking_info       text,
  info_request_sent           text,
  info_request_message        text,
  status                      text,
  first_response_at_utc       text,
  resolved_at_utc             text,
  first_response_hours        text,
  customer_wait_hours         text,
  customer_followups          text,
  sla_first_response_target_h text,
  sla_resolution_target_h     text,
  sla_elapsed_hours           text,
  sla_first_response_status   text,
  sla_resolution_status       text,
  expected_action             text,
  final_action                text,
  final_reply                 text,
  rma_no                      text,
  reference_doc_id            text,
  reference_section           text,
  resolution_case_id          text,
  data_split                  text,
  source                      text
);
COMMENT ON TABLE gold.ticket_gold IS 'tickets.csv 4,000행, 58열 원본 그대로. data_split 열은 남지만 쓰지 않는다(D30)';

CREATE TABLE gold.resolution_case_gold (
  case_id               text PRIMARY KEY,
  ticket_id             text,
  category_code         text,
  product_code          text,
  product_name          text,
  product_family        text,
  fw_version_at_issue   text,
  fault_id              text,
  error_code            text,
  symptom               text,
  initial_hypothesis    text,
  hypothesis_correct    text,
  root_cause            text,
  root_cause_type       text,
  diagnosis_method      text,
  action_taken          text,
  replacement_part      text,
  onsite_visit          text,
  rma_no                text,
  fw_fixed_version      text,
  resolution_result     text,
  time_to_resolve_hours text,
  resolved_by_dept      text,
  reference_doc_id      text,
  reference_section     text,
  recurrence_prevention text,
  case_summary          text
);
COMMENT ON TABLE gold.resolution_case_gold IS 'resolution_cases.csv 800행, 27열 원본 그대로';

-- 서비스가 정답지를 읽는 유일한 창구(FR-003). 정답 열과 제목(inquiry_subject)은 없다
CREATE VIEW gold.v_inputs AS
SELECT ticket_id,
       channel,
       customer_id,
       product_code,
       language,
       inquiry_body,
       nullif(received_at_utc, '')::timestamptz AS received_at_utc
  FROM gold.ticket_gold;
COMMENT ON VIEW gold.v_inputs IS '입력 열만 보이는 창구(4,000행)';

-- =====================================================================
-- 3. svc 스키마 — 서비스 표 (정의서 §4)
-- =====================================================================
-- ---------------------------------------------------------------------
-- 공통 규칙 (정의서 §4)
-- - 상태와 SLA는 문의(sub_ticket) 단위(D16). 상한 없이 여러 문의로 나눈다(D18).
-- - 시각 열은 timestamptz(UTC 저장), 이름 끝 _utc.
-- - *_by 열 = 상담원 ID(API 머리 X-Agent-Id) 또는 SYSTEM (D23, T43).
-- - 넣기만 하는 기록: ticket_message, message_gloss, ticket_status_history,
--   priority_adjustment, sla_alert, agent_run, agent_step, eval.self_check.
--   표마다 허용하는 예외는 트리거 인자로 적었다.
-- ---------------------------------------------------------------------

-- 넣기만 하는 표의 수정·삭제 막기.
-- 인자: 첫째 = 'allow_delete' 또는 'no_delete', 둘째부터 = 수정을 허락하는 열 이름
CREATE FUNCTION svc.guard_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  allowed text[] := TG_ARGV[1:];
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF TG_ARGV[0] = 'allow_delete' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION '%.%: 삭제할 수 없는 기록이다', TG_TABLE_SCHEMA, TG_TABLE_NAME;
  END IF;
  IF (to_jsonb(OLD) - allowed) IS DISTINCT FROM (to_jsonb(NEW) - allowed) THEN
    IF cardinality(allowed) = 0 THEN
      RAISE EXCEPTION '%.%: 고칠 수 없는 기록이다', TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    RAISE EXCEPTION '%.%: 바꿀 수 있는 열은 % 뿐이다', TG_TABLE_SCHEMA, TG_TABLE_NAME, array_to_string(allowed, ', ');
  END IF;
  RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- 4-1. status_transition 허용 전이표 (FR-025)
-- ---------------------------------------------------------------------
CREATE TABLE svc.status_transition (
  from_status text,                          -- 접수(INTAKE)는 NULL
  to_status   text NOT NULL,
  event_kind  text NOT NULL,
  actor_kind  text NOT NULL CHECK (actor_kind IN ('SYSTEM','AGENT')),
  note        text,
  CONSTRAINT status_transition_uq UNIQUE NULLS NOT DISTINCT (from_status, to_status, event_kind)
);
COMMENT ON TABLE svc.status_transition IS '허용 전이표 13행. transition()이 이 표에 있는 전이만 허락한다. 자동 발송 전이 없음(D32), 상담원 직접 종료 없음(D20)';

INSERT INTO svc.status_transition (from_status, to_status, event_kind, actor_kind, note) VALUES
  (NULL,               'NEW',              'INTAKE',                       'SYSTEM', '접수'),
  ('NEW',              'IN_PROGRESS',      'PIPELINE_DONE',                'SYSTEM', '처리 흐름 종료(T6)'),
  ('NEW',              'WAITING_CUSTOMER', 'INFO_REQUEST_SENT',            'AGENT',  '정보 요청 승인·발송'),
  ('IN_PROGRESS',      'WAITING_CUSTOMER', 'INFO_REQUEST_SENT',            'AGENT',  '정보 요청 승인·발송'),
  ('WAITING_CUSTOMER', 'IN_PROGRESS',      'CUSTOMER_REPLY',               'AGENT',  '고객 회신 입력(대리 입력)'),
  ('IN_PROGRESS',      'ESCALATED',        'ESCALATE',                     'AGENT',  '이관 확정(사유 필수, FR-033)'),
  ('ESCALATED',        'IN_PROGRESS',      'DEPT_REPLY',                   'AGENT',  '이관 부서 회신 등록(메일 아님). Q8부터 재처리(FR-033 처리 8)'),
  ('ESCALATED',        'IN_PROGRESS',      'DEPT_MAIL_SENT',               'AGENT',  '예외 부서(FIELD_SVC, SALES_OPS) 고객 메일 발송(D34)'),
  ('IN_PROGRESS',      'RESOLVED',         'FINAL_REPLY_SENT',             'AGENT',  '최종 답변 승인·발송(답한 문의만)'),
  ('ESCALATED',        'RESOLVED',         'FINAL_REPLY_SENT',             'AGENT',  '최종 답변 승인·발송'),
  ('RESOLVED',         'CLOSED',           'NO_REPLY_168H_AFTER_RESOLVED', 'SYSTEM', '최종 답변 뒤 168시간 회신 없음(D20)'),
  ('RESOLVED',         'IN_PROGRESS',      'CUSTOMER_REPLY',               'AGENT',  '168시간 안에 고객 회신(D20, FR-032)'),
  ('WAITING_CUSTOMER', 'CLOSED',           'NO_REPLY_168H',                'SYSTEM', '무응답 168시간(D22). final_action = CLOSED_NO_RESPONSE');

-- ---------------------------------------------------------------------
-- 4-2. ticket 접수 (FR-001·003·004·006)
-- ---------------------------------------------------------------------
-- 새 접수 번호: 'CSV1-' || lpad(nextval('svc.ticket_new_no')::text, 6, '0') → CSV1-004001부터.
-- 시연 재생(REPLAY)은 원본 번호를 그대로 쓴다.
CREATE SEQUENCE svc.ticket_new_no START 4001;

CREATE TABLE svc.ticket (
  ticket_id               text PRIMARY KEY,
  received_at_utc         timestamptz NOT NULL,
  channel                 text NOT NULL CHECK (channel IN ('EMAIL','CHAT','PHONE','WEB_FORM','PARTNER_PORTAL')),
  language                text NOT NULL CHECK (language IN ('ar','de','en','es','fr','id','it','ja','pl','pt','ru','th','tr','vi','zh')),
  body_language           text CHECK (body_language IN ('ar','de','en','es','fr','id','it','ja','pl','pt','ru','th','tr','vi','zh')),
  body_language_uncertain boolean NOT NULL DEFAULT false,
  locale                  text,
  customer_id             text NOT NULL REFERENCES ref.customer (customer_id),
  customer_tier           text NOT NULL REFERENCES ref.customer_tier (tier),   -- 접수 당시 스냅샷
  contact_email_masked    text,                                                -- 운영진 데이터 재생 행만
  contact_name            text,                                                -- 보낸 사람 연락처 원문(v1.3, 가-7). 시뮬레이터 입력만
  contact_email           text,                                                --   LLM 입력·실행 로그에 넣지 않는다
  contact_phone           text,
  inquiry_subject         text,                                                -- 저장만, 처리 흐름에 넣지 않음
  inquiry_body            text NOT NULL CHECK (char_length(inquiry_body) BETWEEN 1 AND 2000),  -- 원문(FR-038)
  multi_yn                boolean NOT NULL DEFAULT false,
  source                  text NOT NULL CHECK (source IN ('SIMULATOR','LOAD','REPLAY')),
  source_ticket_id        text,                                                -- FK 없음. eval.gold_set.source_ticket_id와 맞대 본다
  created_at_utc          timestamptz NOT NULL DEFAULT now(),
  CHECK (source = 'SIMULATOR' OR source_ticket_id IS NOT NULL)
);
COMMENT ON TABLE svc.ticket IS '접수. 한 행 = 고객이 한 번 보낸 글';
CREATE INDEX ticket_received ON svc.ticket (received_at_utc);
CREATE INDEX ticket_source_ticket ON svc.ticket (source_ticket_id);

-- ---------------------------------------------------------------------
-- 4-3. sub_ticket 문의
-- ---------------------------------------------------------------------
CREATE TABLE svc.sub_ticket (
  -- 식별
  sub_ticket_id               text PRIMARY KEY,                   -- ticket_id-seq (T42)
  ticket_id                   text NOT NULL REFERENCES svc.ticket (ticket_id),
  seq                         smallint NOT NULL CHECK (seq >= 1),
  -- 분류·추출 (FR-005~008)
  category_code               text REFERENCES ref.inquiry_category (category),
  evidence_sentences          text[] NOT NULL DEFAULT '{}',
  summary_ko                 text,                                   -- 접수함·상세에 보이는 한국어 한 줄 요약(add-summary-ko). 처리 때 한 번 저장하고 다시 처리해도 새 값이 있을 때만 바꾼다
  urgency_flag                text NOT NULL DEFAULT 'NONE' REFERENCES ref.urgency (urgency),
  product_code                text REFERENCES ref.product (product_code),
  error_code_reported         text,
  fw_version_reported         text,
  -- 규칙 결과 (FR-011·012·014)
  priority                    text REFERENCES ref.priority_level (priority),
  priority_rule_id            text REFERENCES ref.priority_rule (rule_id),
  priority_adjusted_by_agent  boolean NOT NULL DEFAULT false,
  routing_rule_id             text REFERENCES ref.routing_rule (rule_id),
  assigned_dept               text REFERENCES ref.department (dept_code),
  return_kind                 text CHECK (return_kind IN ('DEFECT','NON_DEFECT','UNKNOWN')),
  sla_id                      text REFERENCES ref.sla_policy (sla_id),
  -- 담당 (FR-047, T43)
  assignee_masked             text,
  -- 이관 (FR-020·033)
  escalated                   boolean NOT NULL DEFAULT false,
  escalated_to                text REFERENCES ref.department (dept_code),
  escalation_reason           text CHECK (escalation_reason IN ('ONSITE_REQUIRED','QUALITY_RETURN','RMA_REQUIRED','COMMERCIAL_TERMS','CAUSE_ANALYSIS','FW_UPDATE_FAILURE','SPEC_INTERPRETATION','P1','OUT_OF_SCOPE_TEST','CUSTOM_SPEC','SAFETY')),
  -- 필수정보 (FR-013·015)
  required_info               text[] NOT NULL DEFAULT '{}',
  provided_info               text[] NOT NULL DEFAULT '{}',
  missing_info                text[] NOT NULL DEFAULT '{}',
  missing_blocking_info       text[] NOT NULL DEFAULT '{}',
  info_request_sent           boolean NOT NULL DEFAULT false,
  -- 상태·시각 (FR-025)
  status                      text NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','IN_PROGRESS','WAITING_CUSTOMER','ESCALATED','RESOLVED','CLOSED')),
  first_response_at_utc       timestamptz,
  resolved_at_utc             timestamptz,
  -- SLA (FR-014·026)
  sla_first_response_target_h integer CHECK (sla_first_response_target_h > 0),
  sla_resolution_target_h     integer CHECK (sla_resolution_target_h > 0),
  first_response_hours        numeric(8,2),                       -- 파생 열(아래 inquiry_sla 참고)
  customer_wait_hours         numeric(8,2),                       -- 파생 열
  sla_elapsed_hours           numeric(8,2),                       -- 파생 열. customer_wait_hours를 이미 뺀 값
  sla_first_response_status   text CHECK (sla_first_response_status IN ('MET','BREACHED','ON_TRACK')),
  sla_resolution_status       text CHECK (sla_resolution_status IN ('MET','BREACHED','AT_RISK','ON_TRACK','N/A')),
  -- 답변 결과 (FR-016·021·024)
  evidence_json               jsonb NOT NULL DEFAULT '[]',        -- [{doc_id, section, quote, score}, …] (T42)
  reference_doc_id            text REFERENCES ref.document (doc_id),
  reference_section           text,
  resolution_case_id          text,
  final_action                text,
  rma_no                      text,
  no_evidence_flag            boolean NOT NULL DEFAULT false,
  pipeline_error              text,
  -- 동시 수정
  version                     integer NOT NULL DEFAULT 1,
  UNIQUE (ticket_id, seq),
  CHECK (sub_ticket_id = ticket_id || '-' || seq),
  CHECK (escalated_to IS NULL OR escalation_reason IS NOT NULL),   -- 이관 부서가 있으면 사유 필수. 사유만 있는 행은 허용(1차 담당이 이미 FIELD_SVC인 ONSITE_REQUIRED)
  CHECK (return_kind IS NULL OR category_code = 'RETURN'),
  CHECK (jsonb_typeof(evidence_json) = 'array')
);
COMMENT ON TABLE svc.sub_ticket IS '문의. 한 행 = 접수 안에서 나눈 문의 1개(단일 문의도 seq = 1). status는 transition()으로만 바꾼다';
CREATE INDEX sub_ticket_assigned_dept ON svc.sub_ticket (assigned_dept);
CREATE INDEX sub_ticket_assignee      ON svc.sub_ticket (assignee_masked);
CREATE INDEX sub_ticket_escalated_to  ON svc.sub_ticket (escalated_to);

-- status는 transition()으로만 바꾼다
CREATE FUNCTION svc.guard_sub_ticket_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status
     AND coalesce(current_setting('app.in_transition', true), '') <> 'on' THEN
    RAISE EXCEPTION 'sub_ticket.status는 transition()으로만 바꾼다 (%)', OLD.sub_ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER sub_ticket_status_guard BEFORE UPDATE OF status ON svc.sub_ticket
  FOR EACH ROW EXECUTE FUNCTION svc.guard_sub_ticket_status();

CREATE FUNCTION svc.guard_sub_ticket_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status <> 'NEW' AND coalesce(current_setting('app.in_transition', true), '') <> 'on' THEN
    RAISE EXCEPTION '새 문의는 NEW로 시작한다. 시연 재생은 transition()으로 이력을 쌓는다 (%)', NEW.sub_ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER sub_ticket_insert_guard BEFORE INSERT ON svc.sub_ticket
  FOR EACH ROW EXECUTE FUNCTION svc.guard_sub_ticket_insert();

-- ---------------------------------------------------------------------
-- 4-4. ticket_message 메시지 이력 (FR-023·031·035)
-- ---------------------------------------------------------------------
CREATE TABLE svc.ticket_message (
  message_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticket_id         text NOT NULL REFERENCES svc.ticket (ticket_id),
  sub_ticket_id     text REFERENCES svc.sub_ticket (sub_ticket_id),     -- 티켓 전체 글(INQUIRY)은 NULL
  message_no        integer NOT NULL,                                     -- 비우면 트리거가 채운다
  sender            text NOT NULL CHECK (sender IN ('CUSTOMER','SYSTEM','AGENT','DEPT')),
  message_type      text NOT NULL CHECK (message_type IN ('INQUIRY','INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE','CUSTOMER_REPLY','ESCALATION_NOTE')),
  message_status    text NOT NULL CHECK (message_status IN ('DRAFT','APPROVED','SENT','RECEIVED')),
  sent_at_utc       timestamptz NOT NULL,                                 -- 초안은 만든 시각
  language          text NOT NULL,
  body              text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 5000),
  source_draft_id   bigint REFERENCES svc.ticket_message (message_id),
  edited_yn         boolean,
  sent_by_name      text NOT NULL,                                        -- 상담원 ID(부서 글은 부서 상담원 ID), SYSTEM, CUSTOMER, DEPT
  notice_transition text CHECK (notice_transition IN ('REMINDER','ACK','ESCALATED','REPLY_RECEIVED','RESOLVED')),
  override_check    boolean NOT NULL DEFAULT false,
  mask_count        integer NOT NULL DEFAULT 0 CHECK (mask_count >= 0),
  superseded_at     timestamptz,                                          -- _utc 규칙의 예외(기술 명세서 v1.4 이름)
  created_at_utc    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ticket_id, message_no),
  -- 종류·상태·보낸 쪽 조합 (FR-035 처리 2, D29, D32)
  CONSTRAINT ticket_message_kind_combo CHECK (
    CASE message_type
      WHEN 'INQUIRY'        THEN message_status = 'RECEIVED' AND sender = 'CUSTOMER'
      WHEN 'CUSTOMER_REPLY' THEN message_status = 'RECEIVED' AND sender = 'CUSTOMER'
      WHEN 'ESCALATION_NOTE' THEN sub_ticket_id IS NOT NULL AND (
             (message_status = 'SENT' AND sender = 'AGENT')
          OR (message_status = 'RECEIVED' AND sender = 'DEPT'))
      ELSE  -- INFO_REQUEST, FINAL_REPLY, PROGRESS_NOTICE
             (message_status IN ('DRAFT','APPROVED') AND sender IN ('SYSTEM','AGENT'))
          OR (message_status = 'SENT' AND sender = 'AGENT' AND notice_transition IS DISTINCT FROM 'REMINDER')
          OR (message_status = 'SENT' AND sender = 'SYSTEM' AND notice_transition IS NOT DISTINCT FROM 'REMINDER')
          -- 예외 부서(FIELD_SVC, SALES_OPS) 고객 메일: 초안부터 발송까지 DEPT (D34, v1.3)
          OR (message_type = 'FINAL_REPLY' AND sender = 'DEPT' AND message_status IN ('DRAFT','APPROVED','SENT'))
    END),
  CONSTRAINT ticket_message_notice_kind CHECK ((message_type = 'PROGRESS_NOTICE') = (notice_transition IS NOT NULL))
);
COMMENT ON TABLE svc.ticket_message IS '메시지 이력. SENT는 AGENT만, 예외는 PROGRESS_NOTICE 중 REMINDER(SYSTEM)와 예외 부서 FINAL_REPLY(DEPT). 이관 부서 회신은 ESCALATION_NOTE RECEIVED(DEPT). 삭제 거부, SENT·RECEIVED·APPROVED 수정 거부';
CREATE INDEX ticket_message_sent_at ON svc.ticket_message (sent_at_utc);
CREATE INDEX ticket_message_sub     ON svc.ticket_message (sub_ticket_id);
-- 한 초안은 한 번만 발송
CREATE UNIQUE INDEX ticket_message_one_send ON svc.ticket_message (source_draft_id)
  WHERE message_status = 'SENT';
-- 리마인드는 문의당 한 번
CREATE UNIQUE INDEX ticket_message_one_reminder ON svc.ticket_message (sub_ticket_id)
  WHERE notice_transition = 'REMINDER';

-- message_no를 비우면 티켓 안 다음 번호를 채운다
CREATE FUNCTION svc.fill_message_no() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.message_no IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext(TG_TABLE_SCHEMA || '.ticket_message:' || NEW.ticket_id));
    EXECUTE format('SELECT coalesce(max(message_no), 0) + 1 FROM %I.ticket_message WHERE ticket_id = $1', TG_TABLE_SCHEMA)
      INTO NEW.message_no USING NEW.ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ticket_message_fill_no BEFORE INSERT ON svc.ticket_message
  FOR EACH ROW EXECUTE FUNCTION svc.fill_message_no();

-- 삭제 거부. SENT·RECEIVED·APPROVED는 수정 거부.
-- DRAFT는 body, message_status(APPROVED로만), superseded_at만 바꿀 수 있다.
CREATE FUNCTION svc.guard_ticket_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'ticket_message는 지울 수 없다 (message_id %)', OLD.message_id;
  END IF;
  IF OLD.message_status <> 'DRAFT' THEN
    RAISE EXCEPTION '% 메시지는 고칠 수 없다 (message_id %)', OLD.message_status, OLD.message_id;
  END IF;
  IF NEW.message_status NOT IN ('DRAFT','APPROVED') THEN
    RAISE EXCEPTION '초안은 APPROVED로만 바꿀 수 있다. 발송은 새 SENT 행으로 남긴다 (message_id %)', OLD.message_id;
  END IF;
  IF (to_jsonb(OLD) - ARRAY['body','message_status','superseded_at'])
     IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['body','message_status','superseded_at']) THEN
    RAISE EXCEPTION '초안은 body, message_status, superseded_at만 바꿀 수 있다 (message_id %)', OLD.message_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ticket_message_guard BEFORE UPDATE OR DELETE ON svc.ticket_message
  FOR EACH ROW EXECUTE FUNCTION svc.guard_ticket_message();

-- ---------------------------------------------------------------------
-- 4-5. message_gloss 초안 대역 (FR-039)
-- ---------------------------------------------------------------------
CREATE TABLE svc.message_gloss (
  gloss_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  message_id    bigint NOT NULL REFERENCES svc.ticket_message (message_id),
  language      text NOT NULL CHECK (language IN ('ko','en')),
  body          text NOT NULL,
  numbers_match boolean NOT NULL DEFAULT true,
  made_at_utc   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE svc.message_gloss IS '초안 대역. 화면은 같은 message_id·language의 최신 행을 보인다. 발송 본문에 넣지 않는다';
CREATE INDEX message_gloss_message ON svc.message_gloss (message_id, language, made_at_utc DESC);
CREATE TRIGGER message_gloss_guard BEFORE UPDATE OR DELETE ON svc.message_gloss
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-6. inquiry_field 제공 항목 (FR-008·013·032)
-- ---------------------------------------------------------------------
CREATE TABLE svc.inquiry_field (
  field_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id     text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  field             text NOT NULL REFERENCES ref.info_field (field),
  value_raw         text,
  value_norm        text,
  span_start        integer,
  span_end          integer,
  source            text NOT NULL CHECK (source IN ('INQUIRY','CUSTOMER_REPLY','AGENT')),
  source_message_id bigint REFERENCES svc.ticket_message (message_id),
  created_at_utc    timestamptz NOT NULL DEFAULT now(),
  CHECK (span_end >= span_start)
);
COMMENT ON TABLE svc.inquiry_field IS '제공 항목. 한 행 = 고객이 준 정보 항목 하나';
CREATE INDEX inquiry_field_sub ON svc.inquiry_field (sub_ticket_id);

-- ---------------------------------------------------------------------
-- 4-7. ticket_status_history 상태 이력 (FR-025·026·033)
-- ---------------------------------------------------------------------
CREATE TABLE svc.ticket_status_history (
  history_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id  text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  from_status    text,                       -- 접수 행은 NULL
  to_status      text NOT NULL,
  event_kind     text NOT NULL,
  changed_at_utc timestamptz NOT NULL,       -- 사건 시각(저장 시각 아님, T34)
  changed_by     text NOT NULL,
  reason         text,
  FOREIGN KEY (from_status, to_status, event_kind)
    REFERENCES svc.status_transition (from_status, to_status, event_kind),
  CHECK (from_status IS NOT NULL OR (event_kind = 'INTAKE' AND to_status = 'NEW')),
  CHECK (event_kind <> 'ESCALATE' OR nullif(btrim(reason), '') IS NOT NULL)
);
COMMENT ON TABLE svc.ticket_status_history IS '상태 이력. WAITING_CUSTOMER 구간 합 = customer_wait_hours. 이관 시각·주체는 ESCALATE 행';
CREATE INDEX ticket_status_history_sub ON svc.ticket_status_history (sub_ticket_id, changed_at_utc);
CREATE TRIGGER ticket_status_history_guard BEFORE UPDATE OR DELETE ON svc.ticket_status_history
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-8. priority_adjustment 우선순위 조정 (FR-028)
-- ---------------------------------------------------------------------
CREATE TABLE svc.priority_adjustment (
  adjust_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id     text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  from_priority     text NOT NULL REFERENCES ref.priority_level (priority),
  to_priority       text NOT NULL REFERENCES ref.priority_level (priority),
  from_sla_id       text REFERENCES ref.sla_policy (sla_id),
  to_sla_id         text REFERENCES ref.sla_policy (sla_id),
  from_fr_target_h  integer,
  from_res_target_h integer,
  to_fr_target_h    integer,
  to_res_target_h   integer,
  reason_kind       text NOT NULL CHECK (reason_kind IN ('CUSTOMER_REQUEST','IMPACT_REASSESSED','OTHER')),
  reason            text NOT NULL CHECK (btrim(reason) <> ''),
  adjusted_by       text NOT NULL,
  adjusted_at_utc   timestamptz NOT NULL,
  CHECK (from_priority <> to_priority)
);
COMMENT ON TABLE svc.priority_adjustment IS '우선순위 조정. 바꾸기 전·후 우선순위·정책 행·목표 시간(AC-028-1)';
CREATE INDEX priority_adjustment_sub ON svc.priority_adjustment (sub_ticket_id);
CREATE TRIGGER priority_adjustment_guard BEFORE UPDATE OR DELETE ON svc.priority_adjustment
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-9. sla_alert SLA 경고 (FR-027)
-- ---------------------------------------------------------------------
CREATE TABLE svc.sla_alert (
  alert_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id  text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  alert_type     text NOT NULL CHECK (alert_type IN ('FR_AT_RISK','FR_BREACHED','RES_AT_RISK','RES_BREACHED')),
  raised_at_utc  timestamptz NOT NULL,       -- 조건을 실제로 넘은 시각
  elapsed_h      numeric(8,2) NOT NULL,
  target_h       integer NOT NULL,
  cleared_at_utc timestamptz,                -- 우선순위 조정으로 풀린 시각
  notified_to    text,
  UNIQUE (sub_ticket_id, alert_type)
);
COMMENT ON TABLE svc.sla_alert IS 'SLA 경고. 같은 경고는 문의당 한 번. 나의 업무 현황은 cleared_at_utc가 빈 경고만 센다';
-- 넣은 뒤에는 cleared_at_utc, notified_to만 채울 수 있다
CREATE TRIGGER sla_alert_guard BEFORE UPDATE OR DELETE ON svc.sla_alert
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete', 'cleared_at_utc', 'notified_to');

-- ---------------------------------------------------------------------
-- 4-12. internal_note 내부 메모 (변경 add-internal-notes, 최신 목업 "내부 메모")
-- ---------------------------------------------------------------------
CREATE TABLE svc.internal_note (
  note_id         bigserial PRIMARY KEY,
  ticket_id       text NOT NULL REFERENCES svc.ticket (ticket_id),
  body            text NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 2000),
  author          text NOT NULL,                                   -- 상담원 이름(X-Agent-Id)
  created_at_utc  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE svc.internal_note IS '내부 메모. 상담원끼리만 보며 고객에게 보내지 않고 언어 모델 입력에도 넣지 않는다. 수정·삭제 API 없음';
CREATE INDEX internal_note_ticket ON svc.internal_note (ticket_id, created_at_utc);

-- ---------------------------------------------------------------------
-- 4-13. assignment_history 담당 변경 이력 (변경 add-reassign, 최신 목업 "담당 변경")
-- ---------------------------------------------------------------------
CREATE TABLE svc.assignment_history (
  assign_id       bigserial PRIMARY KEY,
  sub_ticket_id   text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  from_assignee   text,                                            -- 바꾸기 전 담당(없었으면 NULL)
  to_assignee     text NOT NULL,                                   -- 바꾼 뒤 담당(명단 이름)
  changed_by      text NOT NULL,                                   -- 바꾼 상담원(X-Agent-Id)
  changed_at_utc  timestamptz NOT NULL DEFAULT now(),
  CHECK (from_assignee IS DISTINCT FROM to_assignee)
);
COMMENT ON TABLE svc.assignment_history IS '담당 변경 이력. 자동 배정(접수 때)은 남기지 않고, 상담원이 손으로 바꾼 것만 남긴다. 넣기만 한다';
CREATE INDEX assignment_history_sub ON svc.assignment_history (sub_ticket_id, changed_at_utc);

-- ---------------------------------------------------------------------
-- 4-10. agent_run 실행 / agent_step 노드 실행 (FR-036, 보존 90일 T31)
-- ---------------------------------------------------------------------
CREATE TABLE svc.agent_run (
  run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticket_id       text NOT NULL REFERENCES svc.ticket (ticket_id),
  sub_ticket_id   text REFERENCES svc.sub_ticket (sub_ticket_id),
  trigger         text NOT NULL CHECK (trigger IN ('INTAKE','RETRY','CUSTOMER_REPLY','AGENT_EDIT','DEPT_REPLY')),
  started_at_utc  timestamptz NOT NULL,
  finished_at_utc timestamptz,
  status          text CHECK (status IN ('SUCCESS','FAILED','PARTIAL')),   -- NULL = 실행 중
  llm_model       text,                                                    -- gemini-3.8-flash(T38)
  last_step       text
);
COMMENT ON TABLE svc.agent_run IS '처리 흐름 실행 1회. 보존 90일(T31): 보존 기간이 지난 실행은 지울 수 있고 agent_step도 함께 지워진다';
CREATE INDEX agent_run_ticket ON svc.agent_run (ticket_id);
CREATE INDEX agent_run_sub    ON svc.agent_run (sub_ticket_id);
-- 실행이 끝날 때 finished_at_utc, status, last_step만 채운다. 보존 기간 삭제는 허락한다
CREATE TRIGGER agent_run_guard BEFORE UPDATE OR DELETE ON svc.agent_run
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('allow_delete', 'finished_at_utc', 'status', 'last_step');

CREATE TABLE svc.agent_step (
  step_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id          bigint NOT NULL REFERENCES svc.agent_run (run_id) ON DELETE CASCADE,
  step_name       text NOT NULL,             -- T1~T6, Q1~Q11, Q13
  step_order      smallint NOT NULL,
  started_at_utc  timestamptz NOT NULL,
  finished_at_utc timestamptz,
  latency_ms      integer,
  result          text CHECK (result IN ('SUCCESS','FAILED','SKIPPED')),
  input_json      jsonb,
  output_json     jsonb,                     -- 규칙 판정 과정·진단 후보·이관 후보·유사 사례. 왜? 화면(FR-024)이 읽는다
  error_kind      text CHECK (error_kind IN ('LLM_TIMEOUT','LLM_INVALID_OUTPUT','RULE_NOT_FOUND','DB','VALIDATION','UNKNOWN')),
  error           text,
  prompt_version  text,
  input_tokens    integer,
  output_tokens   integer,
  llm_calls       integer,
  UNIQUE (run_id, step_order)
);
COMMENT ON TABLE svc.agent_step IS '노드 실행 1회. run을 지우면 함께 지워진다';
-- 노드가 끝날 때 결과 열만 채운다
CREATE TRIGGER agent_step_guard BEFORE UPDATE OR DELETE ON svc.agent_step
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('allow_delete', 'finished_at_utc', 'latency_ms', 'result',
    'output_json', 'error_kind', 'error', 'input_tokens', 'output_tokens', 'llm_calls');

-- ---------------------------------------------------------------------
-- 4-11. 함수
-- ---------------------------------------------------------------------

-- 상태 변경은 이 함수로만 한다.
-- 허용 전이표에 없으면 거부, 이력 한 줄을 사건 시각으로 남기고 status·version을 바꾼다.
-- RESOLVED가 되면 resolved_at_utc를 쓴다. p_final_action을 주면 final_action도 쓴다.
-- 접수 이력(INTAKE)도 이 함수로 남긴다: 문의를 NEW로 넣은 뒤 transition(id, 'NEW', 'INTAKE', ...).
CREATE FUNCTION svc.transition(
  p_sub_ticket_id text,
  p_to_status     text,
  p_event_kind    text,
  p_at            timestamptz,
  p_actor         text,
  p_reason        text DEFAULT NULL,
  p_final_action  text DEFAULT NULL
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
  v_from text;
BEGIN
  SELECT status INTO v_from FROM svc.sub_ticket WHERE sub_ticket_id = p_sub_ticket_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '문의가 없다: %', p_sub_ticket_id;
  END IF;

  IF p_event_kind = 'INTAKE' THEN
    IF EXISTS (SELECT 1 FROM svc.ticket_status_history WHERE sub_ticket_id = p_sub_ticket_id) THEN
      RAISE EXCEPTION '이미 접수 이력이 있다: %', p_sub_ticket_id;
    END IF;
    v_from := NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM svc.status_transition
    WHERE from_status IS NOT DISTINCT FROM v_from
      AND to_status = p_to_status
      AND event_kind = p_event_kind
  ) THEN
    RAISE EXCEPTION '허용되지 않은 전이: % -> % (%), 문의 %', coalesce(v_from, '(없음)'), p_to_status, p_event_kind, p_sub_ticket_id;
  END IF;

  INSERT INTO svc.ticket_status_history
    (sub_ticket_id, from_status, to_status, event_kind, changed_at_utc, changed_by, reason)
  VALUES (p_sub_ticket_id, v_from, p_to_status, p_event_kind, p_at, p_actor, p_reason);

  PERFORM set_config('app.in_transition', 'on', true);
  UPDATE svc.sub_ticket
     SET status          = p_to_status,
         version         = version + 1,
         resolved_at_utc = CASE WHEN p_to_status = 'RESOLVED' THEN p_at ELSE resolved_at_utc END,
         final_action    = coalesce(p_final_action, final_action)
   WHERE sub_ticket_id = p_sub_ticket_id;
  PERFORM set_config('app.in_transition', 'off', true);
END $$;

-- 문의별 SLA 두 시계 (README.html SLA 정의, 팀 정리 §3).
-- as_of: 화면이면 now(), 채점·시연이면 스냅샷 '2026-09-30 23:59+00'.
-- - 1차 응답 시계는 멈추지 않는다. 응답했으면 목표 이내 MET, 넘으면 BREACHED.
--   아직이면 넘었을 때 BREACHED, 아니면 ON_TRACK. 1차 응답에는 AT_RISK가 없다.
-- - 해결 경과 = (해결 시각 또는 as_of) − 접수 시각 − WAITING_CUSTOMER 구간 합. ESCALATED는 멈추지 않는다.
-- - 해결 상태: final_action = CLOSED_NO_RESPONSE면 N/A. 해결했으면 MET/BREACHED.
--   아직이면 목표 초과 BREACHED, 75% 이상 AT_RISK(ref.sla_setting at_risk_threshold), 그 밖 ON_TRACK.
-- 파생 열 채우기(채점 비교·집계용) 예:
--   UPDATE svc.sub_ticket s SET first_response_hours = f.fr_elapsed_h, ... FROM svc.inquiry_sla(:as_of) f
--    WHERE s.sub_ticket_id = f.sub_ticket_id;
CREATE FUNCTION svc.inquiry_sla(as_of timestamptz)
RETURNS TABLE (
  sub_ticket_id   text,
  status          text,
  received_at_utc timestamptz,
  fr_target_h     integer,
  res_target_h    integer,
  fr_elapsed_h    numeric(8,2),
  fr_status       text,
  wait_h          numeric(8,2),
  res_elapsed_h   numeric(8,2),
  res_status      text,
  remaining_h     numeric(8,2)
)
LANGUAGE sql STABLE AS $$
  WITH thr AS (
    SELECT coalesce(
             (SELECT substring(value FROM '([0-9]+(\.[0-9]+)?)\s*%')::numeric / 100
                FROM ref.sla_setting WHERE key = 'at_risk_threshold'),
             0.75) AS at_risk
  ),
  h AS (
    SELECT sh.sub_ticket_id, sh.to_status, sh.changed_at_utc,
           lead(sh.changed_at_utc) OVER (PARTITION BY sh.sub_ticket_id
                                         ORDER BY sh.changed_at_utc, sh.history_id) AS next_at
      FROM svc.ticket_status_history sh
     WHERE sh.changed_at_utc <= as_of
  ),
  w AS (
    SELECT h.sub_ticket_id,
           sum(extract(epoch FROM (least(coalesce(h.next_at, as_of), as_of) - h.changed_at_utc))) / 3600.0 AS wait_h
      FROM h
     WHERE h.to_status = 'WAITING_CUSTOMER'
     GROUP BY h.sub_ticket_id
  ),
  base AS (
    SELECT s.sub_ticket_id, s.status, t.received_at_utc,
           s.sla_first_response_target_h AS fr_target_h,
           s.sla_resolution_target_h     AS res_target_h,
           s.final_action,
           CASE WHEN s.first_response_at_utc <= as_of THEN s.first_response_at_utc END AS fr_at,
           CASE WHEN s.resolved_at_utc       <= as_of THEN s.resolved_at_utc       END AS res_at,
           coalesce(w.wait_h, 0) AS wait_h
      FROM svc.sub_ticket s
      JOIN svc.ticket t ON t.ticket_id = s.ticket_id
      LEFT JOIN w ON w.sub_ticket_id = s.sub_ticket_id
  ),
  calc AS (
    SELECT b.*,
           extract(epoch FROM (coalesce(b.fr_at, as_of) - b.received_at_utc)) / 3600.0 AS fr_el,
           extract(epoch FROM (coalesce(b.res_at, as_of) - b.received_at_utc)) / 3600.0 - b.wait_h AS res_el
      FROM base b
  )
  SELECT c.sub_ticket_id, c.status, c.received_at_utc, c.fr_target_h, c.res_target_h,
         round(c.fr_el, 2)::numeric(8,2),
         CASE WHEN c.fr_target_h IS NULL THEN NULL
              WHEN c.fr_el > c.fr_target_h THEN 'BREACHED'
              WHEN c.fr_at IS NOT NULL THEN 'MET'
              ELSE 'ON_TRACK' END,
         round(c.wait_h, 2)::numeric(8,2),
         round(c.res_el, 2)::numeric(8,2),
         CASE WHEN c.final_action = 'CLOSED_NO_RESPONSE' THEN 'N/A'
              WHEN c.res_target_h IS NULL THEN NULL
              WHEN c.res_at IS NOT NULL THEN CASE WHEN c.res_el <= c.res_target_h THEN 'MET' ELSE 'BREACHED' END
              WHEN c.res_el > c.res_target_h THEN 'BREACHED'
              WHEN c.res_el >= c.res_target_h * thr.at_risk THEN 'AT_RISK'
              ELSE 'ON_TRACK' END,
         CASE WHEN c.res_at IS NULL AND c.res_target_h IS NOT NULL
                   AND coalesce(c.final_action, '') <> 'CLOSED_NO_RESPONSE'
              THEN round(c.res_target_h - c.res_el, 2)::numeric(8,2) END
    FROM calc c CROSS JOIN thr
$$;

-- =====================================================================
-- 4. scoring 스키마 — 채점 배치 전용 (정의서 §5)
-- svc와 표·함수가 같다(위 3번을 스키마 이름만 바꿔 다시 실행한 것). 채점 배치가 실행마다 비우고 다시 채운다.
-- 사람 승인이 없으므로 메시지는 DRAFT까지만 생긴다.
-- =====================================================================
-- ---------------------------------------------------------------------
-- 공통 규칙 (정의서 §4)
-- - 상태와 SLA는 문의(sub_ticket) 단위(D16). 상한 없이 여러 문의로 나눈다(D18).
-- - 시각 열은 timestamptz(UTC 저장), 이름 끝 _utc.
-- - *_by 열 = 상담원 ID(API 머리 X-Agent-Id) 또는 SYSTEM (D23, T43).
-- - 넣기만 하는 기록: ticket_message, message_gloss, ticket_status_history,
--   priority_adjustment, sla_alert, agent_run, agent_step, eval.self_check.
--   표마다 허용하는 예외는 트리거 인자로 적었다.
-- ---------------------------------------------------------------------

-- 넣기만 하는 표의 수정·삭제 막기.
-- 인자: 첫째 = 'allow_delete' 또는 'no_delete', 둘째부터 = 수정을 허락하는 열 이름
CREATE FUNCTION scoring.guard_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  allowed text[] := TG_ARGV[1:];
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF TG_ARGV[0] = 'allow_delete' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION '%.%: 삭제할 수 없는 기록이다', TG_TABLE_SCHEMA, TG_TABLE_NAME;
  END IF;
  IF (to_jsonb(OLD) - allowed) IS DISTINCT FROM (to_jsonb(NEW) - allowed) THEN
    IF cardinality(allowed) = 0 THEN
      RAISE EXCEPTION '%.%: 고칠 수 없는 기록이다', TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    RAISE EXCEPTION '%.%: 바꿀 수 있는 열은 % 뿐이다', TG_TABLE_SCHEMA, TG_TABLE_NAME, array_to_string(allowed, ', ');
  END IF;
  RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- 4-1. status_transition 허용 전이표 (FR-025)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.status_transition (
  from_status text,                          -- 접수(INTAKE)는 NULL
  to_status   text NOT NULL,
  event_kind  text NOT NULL,
  actor_kind  text NOT NULL CHECK (actor_kind IN ('SYSTEM','AGENT')),
  note        text,
  CONSTRAINT status_transition_uq UNIQUE NULLS NOT DISTINCT (from_status, to_status, event_kind)
);
COMMENT ON TABLE scoring.status_transition IS '허용 전이표 13행. transition()이 이 표에 있는 전이만 허락한다. 자동 발송 전이 없음(D32), 상담원 직접 종료 없음(D20)';

INSERT INTO scoring.status_transition (from_status, to_status, event_kind, actor_kind, note) VALUES
  (NULL,               'NEW',              'INTAKE',                       'SYSTEM', '접수'),
  ('NEW',              'IN_PROGRESS',      'PIPELINE_DONE',                'SYSTEM', '처리 흐름 종료(T6)'),
  ('NEW',              'WAITING_CUSTOMER', 'INFO_REQUEST_SENT',            'AGENT',  '정보 요청 승인·발송'),
  ('IN_PROGRESS',      'WAITING_CUSTOMER', 'INFO_REQUEST_SENT',            'AGENT',  '정보 요청 승인·발송'),
  ('WAITING_CUSTOMER', 'IN_PROGRESS',      'CUSTOMER_REPLY',               'AGENT',  '고객 회신 입력(대리 입력)'),
  ('IN_PROGRESS',      'ESCALATED',        'ESCALATE',                     'AGENT',  '이관 확정(사유 필수, FR-033)'),
  ('ESCALATED',        'IN_PROGRESS',      'DEPT_REPLY',                   'AGENT',  '이관 부서 회신 등록(메일 아님). Q8부터 재처리(FR-033 처리 8)'),
  ('ESCALATED',        'IN_PROGRESS',      'DEPT_MAIL_SENT',               'AGENT',  '예외 부서(FIELD_SVC, SALES_OPS) 고객 메일 발송(D34)'),
  ('IN_PROGRESS',      'RESOLVED',         'FINAL_REPLY_SENT',             'AGENT',  '최종 답변 승인·발송(답한 문의만)'),
  ('ESCALATED',        'RESOLVED',         'FINAL_REPLY_SENT',             'AGENT',  '최종 답변 승인·발송'),
  ('RESOLVED',         'CLOSED',           'NO_REPLY_168H_AFTER_RESOLVED', 'SYSTEM', '최종 답변 뒤 168시간 회신 없음(D20)'),
  ('RESOLVED',         'IN_PROGRESS',      'CUSTOMER_REPLY',               'AGENT',  '168시간 안에 고객 회신(D20, FR-032)'),
  ('WAITING_CUSTOMER', 'CLOSED',           'NO_REPLY_168H',                'SYSTEM', '무응답 168시간(D22). final_action = CLOSED_NO_RESPONSE');

-- ---------------------------------------------------------------------
-- 4-2. ticket 접수 (FR-001·003·004·006)
-- ---------------------------------------------------------------------
-- 새 접수 번호: 'CSV1-' || lpad(nextval('scoring.ticket_new_no')::text, 6, '0') → CSV1-004001부터.
-- 시연 재생(REPLAY)은 원본 번호를 그대로 쓴다.
CREATE SEQUENCE scoring.ticket_new_no START 4001;

CREATE TABLE scoring.ticket (
  ticket_id               text PRIMARY KEY,
  received_at_utc         timestamptz NOT NULL,
  channel                 text NOT NULL CHECK (channel IN ('EMAIL','CHAT','PHONE','WEB_FORM','PARTNER_PORTAL')),
  language                text NOT NULL CHECK (language IN ('ar','de','en','es','fr','id','it','ja','pl','pt','ru','th','tr','vi','zh')),
  body_language           text CHECK (body_language IN ('ar','de','en','es','fr','id','it','ja','pl','pt','ru','th','tr','vi','zh')),
  body_language_uncertain boolean NOT NULL DEFAULT false,
  locale                  text,
  customer_id             text NOT NULL REFERENCES ref.customer (customer_id),
  customer_tier           text NOT NULL REFERENCES ref.customer_tier (tier),   -- 접수 당시 스냅샷
  contact_email_masked    text,                                                -- 운영진 데이터 재생 행만
  contact_name            text,                                                -- 보낸 사람 연락처 원문(v1.3, 가-7). 시뮬레이터 입력만
  contact_email           text,                                                --   LLM 입력·실행 로그에 넣지 않는다
  contact_phone           text,
  inquiry_subject         text,                                                -- 저장만, 처리 흐름에 넣지 않음
  inquiry_body            text NOT NULL CHECK (char_length(inquiry_body) BETWEEN 1 AND 2000),  -- 원문(FR-038)
  multi_yn                boolean NOT NULL DEFAULT false,
  source                  text NOT NULL CHECK (source IN ('SIMULATOR','LOAD','REPLAY')),
  source_ticket_id        text,                                                -- FK 없음. eval.gold_set.source_ticket_id와 맞대 본다
  created_at_utc          timestamptz NOT NULL DEFAULT now(),
  CHECK (source = 'SIMULATOR' OR source_ticket_id IS NOT NULL)
);
COMMENT ON TABLE scoring.ticket IS '접수. 한 행 = 고객이 한 번 보낸 글';
CREATE INDEX ticket_received ON scoring.ticket (received_at_utc);
CREATE INDEX ticket_source_ticket ON scoring.ticket (source_ticket_id);

-- ---------------------------------------------------------------------
-- 4-3. sub_ticket 문의
-- ---------------------------------------------------------------------
CREATE TABLE scoring.sub_ticket (
  -- 식별
  sub_ticket_id               text PRIMARY KEY,                   -- ticket_id-seq (T42)
  ticket_id                   text NOT NULL REFERENCES scoring.ticket (ticket_id),
  seq                         smallint NOT NULL CHECK (seq >= 1),
  -- 분류·추출 (FR-005~008)
  category_code               text REFERENCES ref.inquiry_category (category),
  evidence_sentences          text[] NOT NULL DEFAULT '{}',
  summary_ko                 text,                                   -- 접수함·상세에 보이는 한국어 한 줄 요약(add-summary-ko). 처리 때 한 번 저장하고 다시 처리해도 새 값이 있을 때만 바꾼다
  urgency_flag                text NOT NULL DEFAULT 'NONE' REFERENCES ref.urgency (urgency),
  product_code                text REFERENCES ref.product (product_code),
  error_code_reported         text,
  fw_version_reported         text,
  -- 규칙 결과 (FR-011·012·014)
  priority                    text REFERENCES ref.priority_level (priority),
  priority_rule_id            text REFERENCES ref.priority_rule (rule_id),
  priority_adjusted_by_agent  boolean NOT NULL DEFAULT false,
  routing_rule_id             text REFERENCES ref.routing_rule (rule_id),
  assigned_dept               text REFERENCES ref.department (dept_code),
  return_kind                 text CHECK (return_kind IN ('DEFECT','NON_DEFECT','UNKNOWN')),
  sla_id                      text REFERENCES ref.sla_policy (sla_id),
  -- 담당 (FR-047, T43)
  assignee_masked             text,
  -- 이관 (FR-020·033)
  escalated                   boolean NOT NULL DEFAULT false,
  escalated_to                text REFERENCES ref.department (dept_code),
  escalation_reason           text CHECK (escalation_reason IN ('ONSITE_REQUIRED','QUALITY_RETURN','RMA_REQUIRED','COMMERCIAL_TERMS','CAUSE_ANALYSIS','FW_UPDATE_FAILURE','SPEC_INTERPRETATION','P1','OUT_OF_SCOPE_TEST','CUSTOM_SPEC','SAFETY')),
  -- 필수정보 (FR-013·015)
  required_info               text[] NOT NULL DEFAULT '{}',
  provided_info               text[] NOT NULL DEFAULT '{}',
  missing_info                text[] NOT NULL DEFAULT '{}',
  missing_blocking_info       text[] NOT NULL DEFAULT '{}',
  info_request_sent           boolean NOT NULL DEFAULT false,
  -- 상태·시각 (FR-025)
  status                      text NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','IN_PROGRESS','WAITING_CUSTOMER','ESCALATED','RESOLVED','CLOSED')),
  first_response_at_utc       timestamptz,
  resolved_at_utc             timestamptz,
  -- SLA (FR-014·026)
  sla_first_response_target_h integer CHECK (sla_first_response_target_h > 0),
  sla_resolution_target_h     integer CHECK (sla_resolution_target_h > 0),
  first_response_hours        numeric(8,2),                       -- 파생 열(아래 inquiry_sla 참고)
  customer_wait_hours         numeric(8,2),                       -- 파생 열
  sla_elapsed_hours           numeric(8,2),                       -- 파생 열. customer_wait_hours를 이미 뺀 값
  sla_first_response_status   text CHECK (sla_first_response_status IN ('MET','BREACHED','ON_TRACK')),
  sla_resolution_status       text CHECK (sla_resolution_status IN ('MET','BREACHED','AT_RISK','ON_TRACK','N/A')),
  -- 답변 결과 (FR-016·021·024)
  evidence_json               jsonb NOT NULL DEFAULT '[]',        -- [{doc_id, section, quote, score}, …] (T42)
  reference_doc_id            text REFERENCES ref.document (doc_id),
  reference_section           text,
  resolution_case_id          text,
  final_action                text,
  rma_no                      text,
  no_evidence_flag            boolean NOT NULL DEFAULT false,
  pipeline_error              text,
  -- 동시 수정
  version                     integer NOT NULL DEFAULT 1,
  UNIQUE (ticket_id, seq),
  CHECK (sub_ticket_id = ticket_id || '-' || seq),
  CHECK (escalated_to IS NULL OR escalation_reason IS NOT NULL),   -- 이관 부서가 있으면 사유 필수. 사유만 있는 행은 허용(1차 담당이 이미 FIELD_SVC인 ONSITE_REQUIRED)
  CHECK (return_kind IS NULL OR category_code = 'RETURN'),
  CHECK (jsonb_typeof(evidence_json) = 'array')
);
COMMENT ON TABLE scoring.sub_ticket IS '문의. 한 행 = 접수 안에서 나눈 문의 1개(단일 문의도 seq = 1). status는 transition()으로만 바꾼다';
CREATE INDEX sub_ticket_assigned_dept ON scoring.sub_ticket (assigned_dept);
CREATE INDEX sub_ticket_assignee      ON scoring.sub_ticket (assignee_masked);
CREATE INDEX sub_ticket_escalated_to  ON scoring.sub_ticket (escalated_to);

-- status는 transition()으로만 바꾼다
CREATE FUNCTION scoring.guard_sub_ticket_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status
     AND coalesce(current_setting('app.in_transition', true), '') <> 'on' THEN
    RAISE EXCEPTION 'sub_ticket.status는 transition()으로만 바꾼다 (%)', OLD.sub_ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER sub_ticket_status_guard BEFORE UPDATE OF status ON scoring.sub_ticket
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_sub_ticket_status();

CREATE FUNCTION scoring.guard_sub_ticket_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status <> 'NEW' AND coalesce(current_setting('app.in_transition', true), '') <> 'on' THEN
    RAISE EXCEPTION '새 문의는 NEW로 시작한다. 시연 재생은 transition()으로 이력을 쌓는다 (%)', NEW.sub_ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER sub_ticket_insert_guard BEFORE INSERT ON scoring.sub_ticket
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_sub_ticket_insert();

-- ---------------------------------------------------------------------
-- 4-4. ticket_message 메시지 이력 (FR-023·031·035)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.ticket_message (
  message_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticket_id         text NOT NULL REFERENCES scoring.ticket (ticket_id),
  sub_ticket_id     text REFERENCES scoring.sub_ticket (sub_ticket_id),     -- 티켓 전체 글(INQUIRY)은 NULL
  message_no        integer NOT NULL,                                     -- 비우면 트리거가 채운다
  sender            text NOT NULL CHECK (sender IN ('CUSTOMER','SYSTEM','AGENT','DEPT')),
  message_type      text NOT NULL CHECK (message_type IN ('INQUIRY','INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE','CUSTOMER_REPLY','ESCALATION_NOTE')),
  message_status    text NOT NULL CHECK (message_status IN ('DRAFT','APPROVED','SENT','RECEIVED')),
  sent_at_utc       timestamptz NOT NULL,                                 -- 초안은 만든 시각
  language          text NOT NULL,
  body              text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 5000),
  source_draft_id   bigint REFERENCES scoring.ticket_message (message_id),
  edited_yn         boolean,
  sent_by_name      text NOT NULL,                                        -- 상담원 ID(부서 글은 부서 상담원 ID), SYSTEM, CUSTOMER, DEPT
  notice_transition text CHECK (notice_transition IN ('REMINDER','ACK','ESCALATED','REPLY_RECEIVED','RESOLVED')),
  override_check    boolean NOT NULL DEFAULT false,
  mask_count        integer NOT NULL DEFAULT 0 CHECK (mask_count >= 0),
  superseded_at     timestamptz,                                          -- _utc 규칙의 예외(기술 명세서 v1.4 이름)
  created_at_utc    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ticket_id, message_no),
  -- 종류·상태·보낸 쪽 조합 (FR-035 처리 2, D29, D32)
  CONSTRAINT ticket_message_kind_combo CHECK (
    CASE message_type
      WHEN 'INQUIRY'        THEN message_status = 'RECEIVED' AND sender = 'CUSTOMER'
      WHEN 'CUSTOMER_REPLY' THEN message_status = 'RECEIVED' AND sender = 'CUSTOMER'
      WHEN 'ESCALATION_NOTE' THEN sub_ticket_id IS NOT NULL AND (
             (message_status = 'SENT' AND sender = 'AGENT')
          OR (message_status = 'RECEIVED' AND sender = 'DEPT'))
      ELSE  -- INFO_REQUEST, FINAL_REPLY, PROGRESS_NOTICE
             (message_status IN ('DRAFT','APPROVED') AND sender IN ('SYSTEM','AGENT'))
          OR (message_status = 'SENT' AND sender = 'AGENT' AND notice_transition IS DISTINCT FROM 'REMINDER')
          OR (message_status = 'SENT' AND sender = 'SYSTEM' AND notice_transition IS NOT DISTINCT FROM 'REMINDER')
          -- 예외 부서(FIELD_SVC, SALES_OPS) 고객 메일: 초안부터 발송까지 DEPT (D34, v1.3)
          OR (message_type = 'FINAL_REPLY' AND sender = 'DEPT' AND message_status IN ('DRAFT','APPROVED','SENT'))
    END),
  CONSTRAINT ticket_message_notice_kind CHECK ((message_type = 'PROGRESS_NOTICE') = (notice_transition IS NOT NULL))
);
COMMENT ON TABLE scoring.ticket_message IS '메시지 이력. SENT는 AGENT만, 예외는 PROGRESS_NOTICE 중 REMINDER(SYSTEM)와 예외 부서 FINAL_REPLY(DEPT). 이관 부서 회신은 ESCALATION_NOTE RECEIVED(DEPT). 삭제 거부, SENT·RECEIVED·APPROVED 수정 거부';
CREATE INDEX ticket_message_sent_at ON scoring.ticket_message (sent_at_utc);
CREATE INDEX ticket_message_sub     ON scoring.ticket_message (sub_ticket_id);
-- 한 초안은 한 번만 발송
CREATE UNIQUE INDEX ticket_message_one_send ON scoring.ticket_message (source_draft_id)
  WHERE message_status = 'SENT';
-- 리마인드는 문의당 한 번
CREATE UNIQUE INDEX ticket_message_one_reminder ON scoring.ticket_message (sub_ticket_id)
  WHERE notice_transition = 'REMINDER';

-- message_no를 비우면 티켓 안 다음 번호를 채운다
CREATE FUNCTION scoring.fill_message_no() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.message_no IS NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext(TG_TABLE_SCHEMA || '.ticket_message:' || NEW.ticket_id));
    EXECUTE format('SELECT coalesce(max(message_no), 0) + 1 FROM %I.ticket_message WHERE ticket_id = $1', TG_TABLE_SCHEMA)
      INTO NEW.message_no USING NEW.ticket_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ticket_message_fill_no BEFORE INSERT ON scoring.ticket_message
  FOR EACH ROW EXECUTE FUNCTION scoring.fill_message_no();

-- 삭제 거부. SENT·RECEIVED·APPROVED는 수정 거부.
-- DRAFT는 body, message_status(APPROVED로만), superseded_at만 바꿀 수 있다.
CREATE FUNCTION scoring.guard_ticket_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'ticket_message는 지울 수 없다 (message_id %)', OLD.message_id;
  END IF;
  IF OLD.message_status <> 'DRAFT' THEN
    RAISE EXCEPTION '% 메시지는 고칠 수 없다 (message_id %)', OLD.message_status, OLD.message_id;
  END IF;
  IF NEW.message_status NOT IN ('DRAFT','APPROVED') THEN
    RAISE EXCEPTION '초안은 APPROVED로만 바꿀 수 있다. 발송은 새 SENT 행으로 남긴다 (message_id %)', OLD.message_id;
  END IF;
  IF (to_jsonb(OLD) - ARRAY['body','message_status','superseded_at'])
     IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['body','message_status','superseded_at']) THEN
    RAISE EXCEPTION '초안은 body, message_status, superseded_at만 바꿀 수 있다 (message_id %)', OLD.message_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ticket_message_guard BEFORE UPDATE OR DELETE ON scoring.ticket_message
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_ticket_message();

-- ---------------------------------------------------------------------
-- 4-5. message_gloss 초안 대역 (FR-039)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.message_gloss (
  gloss_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  message_id    bigint NOT NULL REFERENCES scoring.ticket_message (message_id),
  language      text NOT NULL CHECK (language IN ('ko','en')),
  body          text NOT NULL,
  numbers_match boolean NOT NULL DEFAULT true,
  made_at_utc   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE scoring.message_gloss IS '초안 대역. 화면은 같은 message_id·language의 최신 행을 보인다. 발송 본문에 넣지 않는다';
CREATE INDEX message_gloss_message ON scoring.message_gloss (message_id, language, made_at_utc DESC);
CREATE TRIGGER message_gloss_guard BEFORE UPDATE OR DELETE ON scoring.message_gloss
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-6. inquiry_field 제공 항목 (FR-008·013·032)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.inquiry_field (
  field_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id     text NOT NULL REFERENCES scoring.sub_ticket (sub_ticket_id),
  field             text NOT NULL REFERENCES ref.info_field (field),
  value_raw         text,
  value_norm        text,
  span_start        integer,
  span_end          integer,
  source            text NOT NULL CHECK (source IN ('INQUIRY','CUSTOMER_REPLY','AGENT')),
  source_message_id bigint REFERENCES scoring.ticket_message (message_id),
  created_at_utc    timestamptz NOT NULL DEFAULT now(),
  CHECK (span_end >= span_start)
);
COMMENT ON TABLE scoring.inquiry_field IS '제공 항목. 한 행 = 고객이 준 정보 항목 하나';
CREATE INDEX inquiry_field_sub ON scoring.inquiry_field (sub_ticket_id);

-- ---------------------------------------------------------------------
-- 4-7. ticket_status_history 상태 이력 (FR-025·026·033)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.ticket_status_history (
  history_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id  text NOT NULL REFERENCES scoring.sub_ticket (sub_ticket_id),
  from_status    text,                       -- 접수 행은 NULL
  to_status      text NOT NULL,
  event_kind     text NOT NULL,
  changed_at_utc timestamptz NOT NULL,       -- 사건 시각(저장 시각 아님, T34)
  changed_by     text NOT NULL,
  reason         text,
  FOREIGN KEY (from_status, to_status, event_kind)
    REFERENCES scoring.status_transition (from_status, to_status, event_kind),
  CHECK (from_status IS NOT NULL OR (event_kind = 'INTAKE' AND to_status = 'NEW')),
  CHECK (event_kind <> 'ESCALATE' OR nullif(btrim(reason), '') IS NOT NULL)
);
COMMENT ON TABLE scoring.ticket_status_history IS '상태 이력. WAITING_CUSTOMER 구간 합 = customer_wait_hours. 이관 시각·주체는 ESCALATE 행';
CREATE INDEX ticket_status_history_sub ON scoring.ticket_status_history (sub_ticket_id, changed_at_utc);
CREATE TRIGGER ticket_status_history_guard BEFORE UPDATE OR DELETE ON scoring.ticket_status_history
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-8. priority_adjustment 우선순위 조정 (FR-028)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.priority_adjustment (
  adjust_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id     text NOT NULL REFERENCES scoring.sub_ticket (sub_ticket_id),
  from_priority     text NOT NULL REFERENCES ref.priority_level (priority),
  to_priority       text NOT NULL REFERENCES ref.priority_level (priority),
  from_sla_id       text REFERENCES ref.sla_policy (sla_id),
  to_sla_id         text REFERENCES ref.sla_policy (sla_id),
  from_fr_target_h  integer,
  from_res_target_h integer,
  to_fr_target_h    integer,
  to_res_target_h   integer,
  reason_kind       text NOT NULL CHECK (reason_kind IN ('CUSTOMER_REQUEST','IMPACT_REASSESSED','OTHER')),
  reason            text NOT NULL CHECK (btrim(reason) <> ''),
  adjusted_by       text NOT NULL,
  adjusted_at_utc   timestamptz NOT NULL,
  CHECK (from_priority <> to_priority)
);
COMMENT ON TABLE scoring.priority_adjustment IS '우선순위 조정. 바꾸기 전·후 우선순위·정책 행·목표 시간(AC-028-1)';
CREATE INDEX priority_adjustment_sub ON scoring.priority_adjustment (sub_ticket_id);
CREATE TRIGGER priority_adjustment_guard BEFORE UPDATE OR DELETE ON scoring.priority_adjustment
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('no_delete');

-- ---------------------------------------------------------------------
-- 4-9. sla_alert SLA 경고 (FR-027)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.sla_alert (
  alert_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id  text NOT NULL REFERENCES scoring.sub_ticket (sub_ticket_id),
  alert_type     text NOT NULL CHECK (alert_type IN ('FR_AT_RISK','FR_BREACHED','RES_AT_RISK','RES_BREACHED')),
  raised_at_utc  timestamptz NOT NULL,       -- 조건을 실제로 넘은 시각
  elapsed_h      numeric(8,2) NOT NULL,
  target_h       integer NOT NULL,
  cleared_at_utc timestamptz,                -- 우선순위 조정으로 풀린 시각
  notified_to    text,
  UNIQUE (sub_ticket_id, alert_type)
);
COMMENT ON TABLE scoring.sla_alert IS 'SLA 경고. 같은 경고는 문의당 한 번. 나의 업무 현황은 cleared_at_utc가 빈 경고만 센다';
-- 넣은 뒤에는 cleared_at_utc, notified_to만 채울 수 있다
CREATE TRIGGER sla_alert_guard BEFORE UPDATE OR DELETE ON scoring.sla_alert
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('no_delete', 'cleared_at_utc', 'notified_to');

-- ---------------------------------------------------------------------
-- 4-10. agent_run 실행 / agent_step 노드 실행 (FR-036, 보존 90일 T31)
-- ---------------------------------------------------------------------
CREATE TABLE scoring.agent_run (
  run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticket_id       text NOT NULL REFERENCES scoring.ticket (ticket_id),
  sub_ticket_id   text REFERENCES scoring.sub_ticket (sub_ticket_id),
  trigger         text NOT NULL CHECK (trigger IN ('INTAKE','RETRY','CUSTOMER_REPLY','AGENT_EDIT','DEPT_REPLY')),
  started_at_utc  timestamptz NOT NULL,
  finished_at_utc timestamptz,
  status          text CHECK (status IN ('SUCCESS','FAILED','PARTIAL')),   -- NULL = 실행 중
  llm_model       text,                                                    -- gemini-3.8-flash(T38)
  last_step       text
);
COMMENT ON TABLE scoring.agent_run IS '처리 흐름 실행 1회. 보존 90일(T31): 보존 기간이 지난 실행은 지울 수 있고 agent_step도 함께 지워진다';
CREATE INDEX agent_run_ticket ON scoring.agent_run (ticket_id);
CREATE INDEX agent_run_sub    ON scoring.agent_run (sub_ticket_id);
-- 실행이 끝날 때 finished_at_utc, status, last_step만 채운다. 보존 기간 삭제는 허락한다
CREATE TRIGGER agent_run_guard BEFORE UPDATE OR DELETE ON scoring.agent_run
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('allow_delete', 'finished_at_utc', 'status', 'last_step');

CREATE TABLE scoring.agent_step (
  step_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id          bigint NOT NULL REFERENCES scoring.agent_run (run_id) ON DELETE CASCADE,
  step_name       text NOT NULL,             -- T1~T6, Q1~Q11, Q13
  step_order      smallint NOT NULL,
  started_at_utc  timestamptz NOT NULL,
  finished_at_utc timestamptz,
  latency_ms      integer,
  result          text CHECK (result IN ('SUCCESS','FAILED','SKIPPED')),
  input_json      jsonb,
  output_json     jsonb,                     -- 규칙 판정 과정·진단 후보·이관 후보·유사 사례. 왜? 화면(FR-024)이 읽는다
  error_kind      text CHECK (error_kind IN ('LLM_TIMEOUT','LLM_INVALID_OUTPUT','RULE_NOT_FOUND','DB','VALIDATION','UNKNOWN')),
  error           text,
  prompt_version  text,
  input_tokens    integer,
  output_tokens   integer,
  llm_calls       integer,
  UNIQUE (run_id, step_order)
);
COMMENT ON TABLE scoring.agent_step IS '노드 실행 1회. run을 지우면 함께 지워진다';
-- 노드가 끝날 때 결과 열만 채운다
CREATE TRIGGER agent_step_guard BEFORE UPDATE OR DELETE ON scoring.agent_step
  FOR EACH ROW EXECUTE FUNCTION scoring.guard_append_only('allow_delete', 'finished_at_utc', 'latency_ms', 'result',
    'output_json', 'error_kind', 'error', 'input_tokens', 'output_tokens', 'llm_calls');

-- ---------------------------------------------------------------------
-- 4-11. 함수
-- ---------------------------------------------------------------------

-- 상태 변경은 이 함수로만 한다.
-- 허용 전이표에 없으면 거부, 이력 한 줄을 사건 시각으로 남기고 status·version을 바꾼다.
-- RESOLVED가 되면 resolved_at_utc를 쓴다. p_final_action을 주면 final_action도 쓴다.
-- 접수 이력(INTAKE)도 이 함수로 남긴다: 문의를 NEW로 넣은 뒤 transition(id, 'NEW', 'INTAKE', ...).
CREATE FUNCTION scoring.transition(
  p_sub_ticket_id text,
  p_to_status     text,
  p_event_kind    text,
  p_at            timestamptz,
  p_actor         text,
  p_reason        text DEFAULT NULL,
  p_final_action  text DEFAULT NULL
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
  v_from text;
BEGIN
  SELECT status INTO v_from FROM scoring.sub_ticket WHERE sub_ticket_id = p_sub_ticket_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION '문의가 없다: %', p_sub_ticket_id;
  END IF;

  IF p_event_kind = 'INTAKE' THEN
    IF EXISTS (SELECT 1 FROM scoring.ticket_status_history WHERE sub_ticket_id = p_sub_ticket_id) THEN
      RAISE EXCEPTION '이미 접수 이력이 있다: %', p_sub_ticket_id;
    END IF;
    v_from := NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM scoring.status_transition
    WHERE from_status IS NOT DISTINCT FROM v_from
      AND to_status = p_to_status
      AND event_kind = p_event_kind
  ) THEN
    RAISE EXCEPTION '허용되지 않은 전이: % -> % (%), 문의 %', coalesce(v_from, '(없음)'), p_to_status, p_event_kind, p_sub_ticket_id;
  END IF;

  INSERT INTO scoring.ticket_status_history
    (sub_ticket_id, from_status, to_status, event_kind, changed_at_utc, changed_by, reason)
  VALUES (p_sub_ticket_id, v_from, p_to_status, p_event_kind, p_at, p_actor, p_reason);

  PERFORM set_config('app.in_transition', 'on', true);
  UPDATE scoring.sub_ticket
     SET status          = p_to_status,
         version         = version + 1,
         resolved_at_utc = CASE WHEN p_to_status = 'RESOLVED' THEN p_at ELSE resolved_at_utc END,
         final_action    = coalesce(p_final_action, final_action)
   WHERE sub_ticket_id = p_sub_ticket_id;
  PERFORM set_config('app.in_transition', 'off', true);
END $$;

-- 문의별 SLA 두 시계 (README.html SLA 정의, 팀 정리 §3).
-- as_of: 화면이면 now(), 채점·시연이면 스냅샷 '2026-09-30 23:59+00'.
-- - 1차 응답 시계는 멈추지 않는다. 응답했으면 목표 이내 MET, 넘으면 BREACHED.
--   아직이면 넘었을 때 BREACHED, 아니면 ON_TRACK. 1차 응답에는 AT_RISK가 없다.
-- - 해결 경과 = (해결 시각 또는 as_of) − 접수 시각 − WAITING_CUSTOMER 구간 합. ESCALATED는 멈추지 않는다.
-- - 해결 상태: final_action = CLOSED_NO_RESPONSE면 N/A. 해결했으면 MET/BREACHED.
--   아직이면 목표 초과 BREACHED, 75% 이상 AT_RISK(ref.sla_setting at_risk_threshold), 그 밖 ON_TRACK.
-- 파생 열 채우기(채점 비교·집계용) 예:
--   UPDATE svc.sub_ticket s SET first_response_hours = f.fr_elapsed_h, ... FROM svc.inquiry_sla(:as_of) f
--    WHERE s.sub_ticket_id = f.sub_ticket_id;
CREATE FUNCTION scoring.inquiry_sla(as_of timestamptz)
RETURNS TABLE (
  sub_ticket_id   text,
  status          text,
  received_at_utc timestamptz,
  fr_target_h     integer,
  res_target_h    integer,
  fr_elapsed_h    numeric(8,2),
  fr_status       text,
  wait_h          numeric(8,2),
  res_elapsed_h   numeric(8,2),
  res_status      text,
  remaining_h     numeric(8,2)
)
LANGUAGE sql STABLE AS $$
  WITH thr AS (
    SELECT coalesce(
             (SELECT substring(value FROM '([0-9]+(\.[0-9]+)?)\s*%')::numeric / 100
                FROM ref.sla_setting WHERE key = 'at_risk_threshold'),
             0.75) AS at_risk
  ),
  h AS (
    SELECT sh.sub_ticket_id, sh.to_status, sh.changed_at_utc,
           lead(sh.changed_at_utc) OVER (PARTITION BY sh.sub_ticket_id
                                         ORDER BY sh.changed_at_utc, sh.history_id) AS next_at
      FROM scoring.ticket_status_history sh
     WHERE sh.changed_at_utc <= as_of
  ),
  w AS (
    SELECT h.sub_ticket_id,
           sum(extract(epoch FROM (least(coalesce(h.next_at, as_of), as_of) - h.changed_at_utc))) / 3600.0 AS wait_h
      FROM h
     WHERE h.to_status = 'WAITING_CUSTOMER'
     GROUP BY h.sub_ticket_id
  ),
  base AS (
    SELECT s.sub_ticket_id, s.status, t.received_at_utc,
           s.sla_first_response_target_h AS fr_target_h,
           s.sla_resolution_target_h     AS res_target_h,
           s.final_action,
           CASE WHEN s.first_response_at_utc <= as_of THEN s.first_response_at_utc END AS fr_at,
           CASE WHEN s.resolved_at_utc       <= as_of THEN s.resolved_at_utc       END AS res_at,
           coalesce(w.wait_h, 0) AS wait_h
      FROM scoring.sub_ticket s
      JOIN scoring.ticket t ON t.ticket_id = s.ticket_id
      LEFT JOIN w ON w.sub_ticket_id = s.sub_ticket_id
  ),
  calc AS (
    SELECT b.*,
           extract(epoch FROM (coalesce(b.fr_at, as_of) - b.received_at_utc)) / 3600.0 AS fr_el,
           extract(epoch FROM (coalesce(b.res_at, as_of) - b.received_at_utc)) / 3600.0 - b.wait_h AS res_el
      FROM base b
  )
  SELECT c.sub_ticket_id, c.status, c.received_at_utc, c.fr_target_h, c.res_target_h,
         round(c.fr_el, 2)::numeric(8,2),
         CASE WHEN c.fr_target_h IS NULL THEN NULL
              WHEN c.fr_el > c.fr_target_h THEN 'BREACHED'
              WHEN c.fr_at IS NOT NULL THEN 'MET'
              ELSE 'ON_TRACK' END,
         round(c.wait_h, 2)::numeric(8,2),
         round(c.res_el, 2)::numeric(8,2),
         CASE WHEN c.final_action = 'CLOSED_NO_RESPONSE' THEN 'N/A'
              WHEN c.res_target_h IS NULL THEN NULL
              WHEN c.res_at IS NOT NULL THEN CASE WHEN c.res_el <= c.res_target_h THEN 'MET' ELSE 'BREACHED' END
              WHEN c.res_el > c.res_target_h THEN 'BREACHED'
              WHEN c.res_el >= c.res_target_h * thr.at_risk THEN 'AT_RISK'
              ELSE 'ON_TRACK' END,
         CASE WHEN c.res_at IS NULL AND c.res_target_h IS NOT NULL
                   AND coalesce(c.final_action, '') <> 'CLOSED_NO_RESPONSE'
              THEN round(c.res_target_h - c.res_el, 2)::numeric(8,2) END
    FROM calc c CROSS JOIN thr
$$;

-- =====================================================================
-- 5. eval 스키마 (정의서 §6)
-- =====================================================================

-- ---- 6-1. gold_set 팀 정답지 (D30) ----
-- 건수·작성 방법·번호 형식은 D30으로 정한다. 규칙 항목(우선순위·부서·필수정보·SLA 목표)과
-- SLA 계산식은 운영진 데이터 4,000건 전체로 채점하므로 이 표에 정답 열을 두지 않는다.
CREATE TABLE eval.gold_set (
  gold_set_id           text PRIMARY KEY,
  set_version           text NOT NULL,
  source_ticket_id      text REFERENCES gold.ticket_gold (ticket_id),   -- 있으면 서비스 이력·색인·few-shot에서 뺀다
  -- 입력 열 6개 (gold.v_inputs와 같은 모양)
  channel               text,
  customer_id           text,
  product_code          text,
  language              text NOT NULL,
  inquiry_body          text NOT NULL,
  received_at_utc       timestamptz,
  -- 정답 열 (tickets.csv 열 이름)
  category_code         text,
  secondary_category    text,
  urgency_flag          text,
  provided_info         text[],
  missing_blocking_info text[],
  reference_doc_id      text,
  reference_section     text,
  expected_numbers      text,                                          -- 대표 지표 ②용, 선택. v1.3: 정답지 v1 값이 글이라 TEXT
  note                  text,
  created_by            text NOT NULL,
  created_at_utc        timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE eval.gold_set IS '팀 정답지. 한 행 = 팀이 만든 채점용 문의 1건과 정답. v1 = gold_set_v1.csv 80행(GS-001~GS-080)';
CREATE INDEX gold_set_source_ticket ON eval.gold_set (source_ticket_id);

-- ---- 6-2. 채점 표 ----
CREATE TABLE eval.exclusion (
  ticket_id  text NOT NULL,                  -- 운영진 번호 또는 gold_set_id
  item       text NOT NULL,
  reason     text,
  decided_on date,
  PRIMARY KEY (ticket_id, item)
);
COMMENT ON TABLE eval.exclusion IS '채점 제외 목록(D26): 시간 기록 이상 10건(D19, 경과 시간만) + 펌웨어 시점 모순 57건(펌웨어 숫자) + CSV1-000008(item = ALL, 나-13) = 68행';

CREATE TABLE eval.eval_run (
  eval_run_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_at_utc     timestamptz NOT NULL DEFAULT now(),
  input_source   text NOT NULL CHECK (input_source IN ('TEAM_GOLD','ALL_4000','FEEDBACK')),
  set_version    text,
  ticket_count   integer,
  prompt_version text,
  rule_version   text,
  llm_model      text,
  note           text
);
COMMENT ON TABLE eval.eval_run IS '채점 실행 1회. TEAM_GOLD = 팀 정답지, ALL_4000 = 규칙·SLA 재현, FEEDBACK = 상담원 기록(여유 시 FR-044)';

CREATE TABLE eval.eval_case (
  eval_case_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  eval_run_id      bigint NOT NULL REFERENCES eval.eval_run (eval_run_id),
  gold_set_id      text REFERENCES eval.gold_set (gold_set_id),          -- TEAM_GOLD
  source_ticket_id text REFERENCES gold.ticket_gold (ticket_id),        -- ALL_4000
  sub_ticket_id    text,                     -- scoring.sub_ticket 번호. scoring은 실행마다 비우므로 FK를 걸지 않는다
  item             text NOT NULL,
  expected_value   text,
  actual_value     text,
  match_yn         boolean,                  -- NULL = 제외
  excluded_reason  text,
  score            numeric,                  -- 초안 본문 참고 점수만
  judge_comment    text,
  CHECK (gold_set_id IS NOT NULL OR source_ticket_id IS NOT NULL)
);
COMMENT ON TABLE eval.eval_case IS '행별 결과. 한 행 = 한 건 × 한 항목';
CREATE INDEX eval_case_run ON eval.eval_case (eval_run_id, item);

CREATE TABLE eval.eval_summary (
  summary_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  eval_run_id bigint NOT NULL REFERENCES eval.eval_run (eval_run_id),
  item        text NOT NULL,
  n           integer,
  excluded_n  integer,
  matched     integer,
  accuracy    numeric,
  precision_  numeric,
  recall      numeric,
  threshold   numeric,
  passed      boolean,
  UNIQUE (eval_run_id, item)
);
COMMENT ON TABLE eval.eval_summary IS '항목별 집계(실행 × 항목). 대표 지표 3개(규칙 항목 100%, 숫자·인용 100%, 안전·설비 정지 놓침 0)를 여기서 뽑는다';

-- ---- 6-3. self_check 자체 검사 (FR-021·024, MVP) ----
CREATE TABLE eval.self_check (
  check_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id         bigint NOT NULL REFERENCES svc.agent_run (run_id),
  sub_ticket_id  text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  message_id     bigint REFERENCES svc.ticket_message (message_id),
  check_type     text NOT NULL,              -- 아래 9종. FR-045(여유 시)가 종류를 더하므로 값 목록 CHECK는 걸지 않는다
  passed_yn      boolean NOT NULL,
  detail         jsonb,
  checked_at_utc timestamptz NOT NULL DEFAULT now(),
  -- 초안 검사(DRAFT_CHECK)와 검증 에이전트(VERIFY)는 그 초안을 가리켜야 한다 (v1.3)
  CONSTRAINT self_check_draft_message CHECK (check_type NOT IN ('DRAFT_CHECK','VERIFY') OR message_id IS NOT NULL)
);
COMMENT ON TABLE eval.self_check IS '자체 검사 1건. check_type: DRAFT_CHECK / LOW_CONFIDENCE / RULE_FAILED / NO_EVIDENCE / RETURN_REASON / PRODUCT_UNKNOWN / EXTRACT_FAILED / LANG_UNCERTAIN / VERIFY(검증 에이전트, FR-049). 재처리 뒤에는 최신 run만 본다. VERIFY는 초안당 최신 행';
CREATE INDEX self_check_message ON eval.self_check (message_id, check_type, checked_at_utc DESC);
CREATE INDEX self_check_sub ON eval.self_check (sub_ticket_id, run_id);
CREATE TRIGGER self_check_guard BEFORE UPDATE OR DELETE ON eval.self_check
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete');

-- ---- 6-4. 여유 시 기능 표 (지금 만들고 MVP는 쓰지 않음, T41) ----
CREATE TABLE eval.agent_feedback (
  feedback_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sub_ticket_id   text NOT NULL REFERENCES svc.sub_ticket (sub_ticket_id),
  message_id      bigint REFERENCES svc.ticket_message (message_id),
  run_id          bigint REFERENCES svc.agent_run (run_id),
  field           text NOT NULL CHECK (field IN ('category_code','urgency_flag','priority','missing_blocking_info','message')),
  agent_value     text,                      -- 목록은 ';'로 잇는다
  final_value     text,
  changed_yn      boolean NOT NULL,
  reason          text,
  agent_id        text NOT NULL,             -- sub_ticket.assignee_masked 값
  created_at_utc  timestamptz NOT NULL DEFAULT now(),
  review_status   text NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING','ADOPTED','EXCLUDED')),
  reviewed_by     text,
  reviewed_at_utc timestamptz
);
COMMENT ON TABLE eval.agent_feedback IS '상담원 수정·승인 기록(FR-043, 여유 시). few-shot에는 ADOPTED만(D27). 팀 정답지 문의와 채점 실행 건은 쌓지 않는다(앱이 지킨다)';
-- 삭제 거부, 검토 3칸 말고는 수정 거부
CREATE TRIGGER agent_feedback_guard BEFORE UPDATE OR DELETE ON eval.agent_feedback
  FOR EACH ROW EXECUTE FUNCTION svc.guard_append_only('no_delete', 'review_status', 'reviewed_by', 'reviewed_at_utc');

CREATE TABLE eval.prompt_example (
  example_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  feedback_id   bigint NOT NULL REFERENCES eval.agent_feedback (feedback_id),
  field         text NOT NULL,
  input_excerpt text,
  correct_value text,
  active_yn     boolean NOT NULL DEFAULT true,
  added_at_utc  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE eval.prompt_example IS '교정 사례(FR-046, 여유 시). 출처는 팀 정답지 밖 문의 + ADOPTED 기록뿐(D27, D30)';

-- =====================================================================
-- 6. 뷰 — v_inquiry_inbox, v_ticket_summary (정의서 §4-11)
-- eval.gold_set을 읽으므로 eval 뒤에 만든다. svc와 scoring에 같은 뷰를 둔다.
-- 나의 업무 현황(FR-047)과 검토 표시 4개(FR-024 처리 6)는 뷰를 두지 않고 API가 계산한다.
-- =====================================================================

-- 문의 한 줄 재료: SLA(지금 기준), 풀리지 않은 경고, 승인 대기 초안, 리마인드
-- v_inquiry_inbox 접수함 한 줄 = 문의 하나 (FR-029).
-- 부서 접수함은 assigned_dept 또는 escalated_to가 그 부서인 줄(FR-033),
-- 나의 업무 현황(FR-047)은 assignee_masked = 상담원 ID로 거른다.
CREATE VIEW svc.v_inquiry_inbox AS
SELECT s.sub_ticket_id,
       s.ticket_id,
       s.seq,
       count(*) OVER (PARTITION BY s.ticket_id)                    AS inquiry_count,   -- 복합 n건 중 k (k = seq)
       t.received_at_utc,
       t.channel,
       t.language,
       t.customer_id,
       c.company_masked,
       t.customer_tier,
       s.product_code,
       s.category_code,
       s.urgency_flag,
       s.priority,
       s.assigned_dept,
       s.escalated_to,
       s.assignee_masked,
       s.status,
       f.fr_status,
       f.res_status,
       f.remaining_h,
       coalesce(a.alerts, '{}')                                    AS alerts,
       cardinality(s.missing_blocking_info) > 0                    AS needs_info,
       coalesce(d.has_unsent_draft, false)                         AS has_unsent_draft, -- 승인 대기
       coalesce(r.reminder_sent, false)                            AS reminder_sent     -- 리마인드 발송됨
  FROM svc.sub_ticket s
  JOIN svc.ticket t   ON t.ticket_id = s.ticket_id
  JOIN ref.customer c   ON c.customer_id = t.customer_id
  JOIN svc.inquiry_sla(now()) f ON f.sub_ticket_id = s.sub_ticket_id
  LEFT JOIN LATERAL (
    SELECT array_agg(al.alert_type ORDER BY al.alert_type) AS alerts
      FROM svc.sla_alert al
     WHERE al.sub_ticket_id = s.sub_ticket_id AND al.cleared_at_utc IS NULL
  ) a ON true
  LEFT JOIN LATERAL (
    SELECT true AS has_unsent_draft
      FROM svc.ticket_message m
     WHERE m.sub_ticket_id = s.sub_ticket_id
       AND m.message_status IN ('DRAFT','APPROVED')
       AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE')
       AND m.superseded_at IS NULL
       AND NOT EXISTS (SELECT 1 FROM svc.ticket_message x
                        WHERE x.source_draft_id = m.message_id AND x.message_status = 'SENT')
     LIMIT 1
  ) d ON true
  LEFT JOIN LATERAL (
    SELECT true AS reminder_sent
      FROM svc.ticket_message m
     WHERE m.sub_ticket_id = s.sub_ticket_id AND m.notice_transition = 'REMINDER' AND m.message_status = 'SENT'
     LIMIT 1
  ) r ON true;
COMMENT ON VIEW svc.v_inquiry_inbox IS '접수함 한 줄 = 문의 하나(FR-029). SLA는 지금 기준';

-- v_ticket_summary 티켓 한 줄 요약 (티켓 상세 머리).
-- 대표 문의 = 끝나지 않은 문의 → 경고 있는 문의 → 남은 시간이 적은 문의 (D16). 티켓 상태 = 대표 문의 상태.
CREATE VIEW svc.v_ticket_summary AS
WITH ranked AS (
  SELECT i.*,
         row_number() OVER (
           PARTITION BY i.ticket_id
           ORDER BY (i.status IN ('RESOLVED','CLOSED')),
                    (cardinality(i.alerts) > 0) DESC,
                    i.remaining_h NULLS LAST,
                    i.seq) AS rk
    FROM svc.v_inquiry_inbox i
)
SELECT t.ticket_id,
       t.received_at_utc,
       t.channel,
       t.language,
       t.customer_id,
       c.company_masked,
       t.customer_tier,
       t.multi_yn,
       t.source,
       t.source_ticket_id,
       agg.inquiry_count,
       agg.open_count,
       rep.sub_ticket_id                           AS rep_sub_ticket_id,
       rep.status                                  AS status,
       rep.res_status                              AS rep_res_status,
       rep.remaining_h                             AS rep_remaining_h,
       agg.needs_info,
       agg.has_unsent_draft,
       EXISTS (SELECT 1 FROM eval.gold_set g
                WHERE g.source_ticket_id = t.source_ticket_id) AS gold_set_yn   -- 채점용 문의
  FROM svc.ticket t
  JOIN ref.customer c ON c.customer_id = t.customer_id
  JOIN ranked rep ON rep.ticket_id = t.ticket_id AND rep.rk = 1
  JOIN (
    SELECT ticket_id,
           count(*)                                                    AS inquiry_count,
           count(*) FILTER (WHERE status NOT IN ('RESOLVED','CLOSED'))  AS open_count,
           bool_or(needs_info AND status NOT IN ('RESOLVED','CLOSED'))  AS needs_info,
           bool_or(has_unsent_draft)                                   AS has_unsent_draft
      FROM svc.v_inquiry_inbox
     GROUP BY ticket_id
  ) agg ON agg.ticket_id = t.ticket_id;
COMMENT ON VIEW svc.v_ticket_summary IS '티켓 한 줄 요약. 상태는 대표 문의에서 계산(D16). gold_set_yn = 팀 정답지 문의';

-- 문의 한 줄 재료: SLA(지금 기준), 풀리지 않은 경고, 승인 대기 초안, 리마인드
-- v_inquiry_inbox 접수함 한 줄 = 문의 하나 (FR-029).
-- 부서 접수함은 assigned_dept 또는 escalated_to가 그 부서인 줄(FR-033),
-- 나의 업무 현황(FR-047)은 assignee_masked = 상담원 ID로 거른다.
CREATE VIEW scoring.v_inquiry_inbox AS
SELECT s.sub_ticket_id,
       s.ticket_id,
       s.seq,
       count(*) OVER (PARTITION BY s.ticket_id)                    AS inquiry_count,   -- 복합 n건 중 k (k = seq)
       t.received_at_utc,
       t.channel,
       t.language,
       t.customer_id,
       c.company_masked,
       t.customer_tier,
       s.product_code,
       s.category_code,
       s.urgency_flag,
       s.priority,
       s.assigned_dept,
       s.escalated_to,
       s.assignee_masked,
       s.status,
       f.fr_status,
       f.res_status,
       f.remaining_h,
       coalesce(a.alerts, '{}')                                    AS alerts,
       cardinality(s.missing_blocking_info) > 0                    AS needs_info,
       coalesce(d.has_unsent_draft, false)                         AS has_unsent_draft, -- 승인 대기
       coalesce(r.reminder_sent, false)                            AS reminder_sent     -- 리마인드 발송됨
  FROM scoring.sub_ticket s
  JOIN scoring.ticket t   ON t.ticket_id = s.ticket_id
  JOIN ref.customer c   ON c.customer_id = t.customer_id
  JOIN scoring.inquiry_sla(now()) f ON f.sub_ticket_id = s.sub_ticket_id
  LEFT JOIN LATERAL (
    SELECT array_agg(al.alert_type ORDER BY al.alert_type) AS alerts
      FROM scoring.sla_alert al
     WHERE al.sub_ticket_id = s.sub_ticket_id AND al.cleared_at_utc IS NULL
  ) a ON true
  LEFT JOIN LATERAL (
    SELECT true AS has_unsent_draft
      FROM scoring.ticket_message m
     WHERE m.sub_ticket_id = s.sub_ticket_id
       AND m.message_status IN ('DRAFT','APPROVED')
       AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE')
       AND m.superseded_at IS NULL
       AND NOT EXISTS (SELECT 1 FROM scoring.ticket_message x
                        WHERE x.source_draft_id = m.message_id AND x.message_status = 'SENT')
     LIMIT 1
  ) d ON true
  LEFT JOIN LATERAL (
    SELECT true AS reminder_sent
      FROM scoring.ticket_message m
     WHERE m.sub_ticket_id = s.sub_ticket_id AND m.notice_transition = 'REMINDER' AND m.message_status = 'SENT'
     LIMIT 1
  ) r ON true;
COMMENT ON VIEW scoring.v_inquiry_inbox IS '접수함 한 줄 = 문의 하나(FR-029). SLA는 지금 기준';

-- v_ticket_summary 티켓 한 줄 요약 (티켓 상세 머리).
-- 대표 문의 = 끝나지 않은 문의 → 경고 있는 문의 → 남은 시간이 적은 문의 (D16). 티켓 상태 = 대표 문의 상태.
CREATE VIEW scoring.v_ticket_summary AS
WITH ranked AS (
  SELECT i.*,
         row_number() OVER (
           PARTITION BY i.ticket_id
           ORDER BY (i.status IN ('RESOLVED','CLOSED')),
                    (cardinality(i.alerts) > 0) DESC,
                    i.remaining_h NULLS LAST,
                    i.seq) AS rk
    FROM scoring.v_inquiry_inbox i
)
SELECT t.ticket_id,
       t.received_at_utc,
       t.channel,
       t.language,
       t.customer_id,
       c.company_masked,
       t.customer_tier,
       t.multi_yn,
       t.source,
       t.source_ticket_id,
       agg.inquiry_count,
       agg.open_count,
       rep.sub_ticket_id                           AS rep_sub_ticket_id,
       rep.status                                  AS status,
       rep.res_status                              AS rep_res_status,
       rep.remaining_h                             AS rep_remaining_h,
       agg.needs_info,
       agg.has_unsent_draft,
       EXISTS (SELECT 1 FROM eval.gold_set g
                WHERE g.source_ticket_id = t.source_ticket_id) AS gold_set_yn   -- 채점용 문의
  FROM scoring.ticket t
  JOIN ref.customer c ON c.customer_id = t.customer_id
  JOIN ranked rep ON rep.ticket_id = t.ticket_id AND rep.rk = 1
  JOIN (
    SELECT ticket_id,
           count(*)                                                    AS inquiry_count,
           count(*) FILTER (WHERE status NOT IN ('RESOLVED','CLOSED'))  AS open_count,
           bool_or(needs_info AND status NOT IN ('RESOLVED','CLOSED'))  AS needs_info,
           bool_or(has_unsent_draft)                                   AS has_unsent_draft
      FROM scoring.v_inquiry_inbox
     GROUP BY ticket_id
  ) agg ON agg.ticket_id = t.ticket_id;
COMMENT ON VIEW scoring.v_ticket_summary IS '티켓 한 줄 요약. 상태는 대표 문의에서 계산(D16). gold_set_yn = 팀 정답지 문의';

-- =====================================================================
-- 7. 권한 — 서비스 계정 (정의서 §3 권한, §5)
-- 앱이 접속하는 로그인 계정에 cs_service 역할을 준다: GRANT cs_service TO <앱 계정>;
-- 표·뷰의 주인은 이 파일을 실행한 계정이다(채점 배치·적재 작업이 쓴다).
-- =====================================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cs_service') THEN
    CREATE ROLE cs_service NOLOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA ref, gold, svc, eval TO cs_service;   -- scoring은 주지 않는다(서비스 화면은 보지 않음)

-- ref: 읽기만
GRANT SELECT ON ALL TABLES IN SCHEMA ref TO cs_service;

-- gold: v_inputs 뷰만. ticket_gold, resolution_case_gold의 정답 열은 읽을 수 없다
GRANT SELECT ON gold.v_inputs TO cs_service;

-- svc: 읽고 쓰기. 지우기는 보존 기간이 지난 실행(agent_run, agent_step)만
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA svc TO cs_service;
GRANT DELETE ON svc.agent_run, svc.agent_step TO cs_service;
GRANT USAGE ON SEQUENCE svc.ticket_new_no TO cs_service;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA svc TO cs_service;

-- eval: 자체 검사 쓰기, 상담원 기록(여유 시) 쓰기·검토, 교정 사례 읽기
GRANT SELECT, INSERT ON eval.self_check TO cs_service;
GRANT SELECT, INSERT, UPDATE ON eval.agent_feedback TO cs_service;
GRANT SELECT ON eval.prompt_example TO cs_service;
-- 팀 정답지는 불러오기(FR-003)에 필요한 입력 열만 읽는다
GRANT SELECT (gold_set_id, set_version, source_ticket_id, channel, customer_id, product_code,
              language, inquiry_body, received_at_utc) ON eval.gold_set TO cs_service;

COMMIT;
