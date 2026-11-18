# 해외 고객 C/S 대응 AI Agent

해외 고객의 C/S 문의를 접수부터 회신, 부서 이관까지 돕는 AI Agent 서비스입니다.
**정확해야 빨라진다: 근거로 검증된 답만 내보내는 C/S Agent**를 목표로 만들었습니다.
**LS ELECTRIC 기업 연계 프로젝트**로, LS ITC가 교육용으로 제공한 LS ELECTRIC 합성 데이터(고객 문의 4,000건, 해결 사례 800건, 제품·정책 문서 107개)를 사용했습니다.
성균관대 × LS AI 교육과정(SKKU × LS AI CAMPUS) 팀 프로젝트를 개인 저장소로 옮겨 정리했습니다.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-3.8%20flash-8E75B2?logo=googlegemini&logoColor=white)
![Docker](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)

> 원본 팀 저장소: [skkuls-final-team/CS-agent-service](https://github.com/skkuls-final-team/CS-agent-service) · 팀원 4명 · 2026.10.12 ~ 2026.11.01
> 11월 초 팀의 과제 주제가 바뀌면서 이 서비스는 최종 발표에 포함되지 않았습니다. 이후 개인적으로 이어서 고도화한 내용은 [팀 개발 이후 개인 고도화](#팀-개발-이후-개인-고도화)에 있습니다.

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="docs/assets/readme/cs-1-intake.gif"><img src="docs/assets/readme/cs-1-intake.gif" alt="접수함에서 문의 번호를 검색해 열면 AI 요약과 판단 칩이 보이는 화면" width="100%"></a>
      <p><b>① 접수·분류</b></p>
      <ul>
        <li>AI가 문의 언어, 유형 10종, 긴급도를 판정하고 여러 요청이 섞인 문의는 요청별로 나눠 동시에 처리합니다.</li>
        <li>우선순위·담당 부서·필수 정보·응답 기한(SLA)은 AI가 아닌 <b>규칙 엔진</b>이 정합니다.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <a href="docs/assets/readme/cs-2-draft.gif"><img src="docs/assets/readme/cs-2-draft.gif" alt="회신 초안과 한국어 번역문을 보고, 값 옆의 출처를 눌러 근거 문서 절을 확인하는 화면" width="100%"></a>
      <p><b>② 근거 기반 회신 초안</b></p>
      <ul>
        <li>제품·정책 문서 107개(절 895개)를 검색하고, 가격·납기·사양·펌웨어는 테이블에서 조회합니다.</li>
        <li>근거가 있을 때만 고객 언어로 초안을 쓰고, 답변의 수치·사양마다 근거 문서·절을 바로 확인할 수 있습니다.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="docs/assets/readme/cs-3-ello.gif"><img src="docs/assets/readme/cs-3-ello.gif" alt="ELLO 상담원 도우미에 차단 용량을 묻고 출처가 붙은 답을 받는 화면" width="100%"></a>
      <p><b>③ ELLO 상담원 도우미</b></p>
      <ul>
        <li>상담원 전용 챗봇. 보고 있는 문의의 제품·오류 코드에 맞춰 질문 후보를 띄웁니다.</li>
        <li>문서를 검색해 출처와 함께 답하며, 답변은 상담원 참고용이라 고객 회신에는 사용하지 않습니다.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <a href="docs/assets/readme/cs-4-check.gif"><img src="docs/assets/readme/cs-4-check.gif" alt="승인하고 발송을 누르면 검증 Agent 경고가 뜨고 상담원이 돌아가서 고치는 화면" width="100%"></a>
      <p><b>④ 발송 전 검증 · 사람 승인</b></p>
      <ul>
        <li>초안의 인용·숫자를 코드로 대조하고, 검증 Agent가 근거와 다른 문장·확정적 약속 표현을 찾습니다.</li>
        <li>고객에게 가는 글은 모두 초안이며, <b>상담원이 확인한 뒤에만</b> 발송됩니다.</li>
      </ul>
    </td>
  </tr>
</table>

## 내 역할 — 나송주 · LLM·RAG 기능 담당 (4인 팀) · 개인 고도화 BE·FE

팀은 역할을 **기능 단위**로 나눴습니다. 저는 문의를 이해하고 근거를 찾아 초안을 쓰는 **LLM·RAG 기능**을 맡았고, 팀 개발 이후에는 이관 메일 연동을 서버부터 화면까지 별도로 구현했습니다.

| 구분 | 맡은 기능 | 내용 | 코드 |
| --- | --- | --- | --- |
| 팀 단계 | 모델 선정 | 언어 모델·임베딩 모델과 임베딩 차원 결정, 분류 출력 형식 제안 | `backend/app/config.py` |
| 팀 단계 | 문의 이해 | 언어 식별, 유형 10종 분류, 복합 문의 요청 나누기, 긴급도 판단을 **LLM 호출 한 번**으로 묶음 (FR-004~007) | `backend/app/llm/understand.py`, `prompts/l1_*` |
| 팀 단계 | 제공 정보 추출 | 본문에서 제품·일련번호 등 고객이 제공한 정보를 추출해 필수 정보 점검 규칙에 전달 (FR-008) | `backend/app/llm/extract.py`, `prompts/l2_*` |
| 팀 단계 | 문서 근거 검색 | 제품·정책 문서 107개에서 문의에 맞는 근거 절을 찾음 (FR-016) | `backend/app/retrieval/search.py` |
| 팀 단계 | 정보 요청 문안 · 답변 초안 | 빠진 정보를 고객 언어로 요청하고, 근거가 있을 때만 답변 초안을 쓴 뒤 인용·숫자를 자체 대조 (FR-015, FR-021) | `backend/app/llm/drafts.py`, `backend/app/checks/draft_check.py`, `prompts/l3_*`, `prompts/l4_*` |
| 팀 단계 | 진행 안내 · 초안 번역문 | 상태가 바뀔 때 안내 초안, 상담원용 한국어 번역문 표시 (FR-023, FR-039) | `prompts/l7_gloss_v1.md` |
| 팀 단계 | 프롬프트 개선 | 분류·긴급도·추출, 검색·다국어 초안 프롬프트를 버전별로 개선 | `prompts/*_v2.md`, `prompts/l4_draft_v3.md` |
| 개인 단계 | 이관 메일 발송·수신 (BE) | SMTP 발송, 메일함 확인으로 부서 답장을 문의에 자동 연결, API 3개와 주기적 메일 확인 작업(스케줄러) 추가, 테스트 11개 | `backend/app/mail/`, `backend/app/api/mail.py`, `backend/app/scheduler.py` |
| 개인 단계 | 이관·이력 화면 메일 연동 (FE) | 이관 팝업에 실제 부서 주소·발송 결과 표시, 이력 탭에 메일함 열기·지금 확인·부서 답장 시연 | `frontend/src/features/ticket/ActionPopups.tsx`, `HistoryTab.tsx` |

> 팀은 공용 Claude 계정으로 OpenSpec 기반 개발(스펙 → 구현 → archive)을 진행해, 팀 저장소의 커밋 작성자는 Claude·팀 계정으로 기록되어 있습니다.

## AI 활용과 직접 판단·검증한 영역

이 프로젝트는 팀 단계와 개인 고도화 단계 모두 **AI 코딩 도구(Claude Code)로 구현하고, 사람은 스펙·설계 결정·검증을 맡는 방식**으로 만들었습니다.

| 단계 | AI가 한 일 | 내가 판단·검증한 일 |
| --- | --- | --- |
| 스펙 | OpenSpec 제안서·작업 목록 초안 작성 | 무엇을 만들고 무엇을 범위 밖으로 둘지 결정 (예: 메일 발송·수신은 하고, 실제 회사 메일 연동과 첨부 처리는 범위 밖) |
| 설계 | 기존 코드 탐색, 구현 방법 후보 제시 | 답장을 문의에 연결하는 기준(제목 표시 + 이관받은 부서 주소만 허용), 발송 실패 때도 이관은 확정한다는 정책, DB 테이블을 바꾸지 않는다는 제약 |
| 구현 | 코드와 테스트 코드 작성 | 기존 [회신 등록] 경로를 재사용하게 해 상태 전이·실행 기록·재처리가 화면 회신과 같도록 함 |
| 검증 | 테스트 실행 | 완료 기준(AC)마다 테스트를 두고 전체 회귀 테스트 통과를 확인, 실제 메일 서버(Mailpit)로 끝까지 직접 시연 |
| 문제 해결 | 원인 분석과 수정안 작성 | 시연 중 **[지금 확인]을 눌러도 답장이 연결되지 않는 문제를 직접 발견**해 원인(메일을 열어 보면 "읽음"이 되어 확인 대상에서 빠짐)을 확인하고, 수정과 회귀 테스트 추가까지 검증 |

AI가 생성한 코드는 그대로 반영하지 않고, 테스트와 실제 실행 결과로 확인한 것만 커밋했습니다.

## 팀 개발 이후 개인 고도화

주제 변경으로 팀 개발이 멈춘 뒤(팀 저장소 마지막 커밋 2026-11-01) 이 저장소로 옮겨 이어서 개발한 내용입니다. 팀 개발 때와 같은 방식으로 OpenSpec 제안서를 먼저 쓰고 구현했습니다.

### 1. 이관 메일 실제 발송·수신 — [제안서](openspec/changes/add-escalation-mail-live/proposal.md)

팀 개발 당시에는 "이관 요청을 메일로도 보내기"가 **UI 목업**(실제 동작 없음)이었습니다. 체크해도 메일은 발송되지 않았고, 부서 회신은 [회신 메일 도착 (시연)] 버튼으로 대체되어 있었습니다. 이관받은 부서가 시스템에 들어오지 않고 **메일만으로 일할 수 있도록** 실제로 동작하게 만들었습니다.

<p align="center"><img src="docs/assets/readme/cs-mail.gif" alt="이관 요청 메일이 Mailpit에 도착하고, 부서 답장이 문의에 자동 연결된 뒤 AI가 RMA 번호를 반영해 초안을 다시 쓰는 화면" width="100%"></p>

<p align="center"><img src="docs/assets/readme/cs-mail-seq.png" alt="이관 메일 흐름: 상담원 이관 → 서버가 [ESC:하위 문의 번호] 제목으로 메일 발송 → 부서 답장 → 30초마다 받은 메일함 확인 → 답장을 문의에 연결 → 회신을 근거로 초안 다시 생성 → 상담원 검토·발송" width="85%"></p>

| 고민한 점 | 선택 |
| --- | --- |
| 답장과 문의 연결 방식 | 요청 메일 제목에 `[ESC:하위 문의 번호]`를 넣고, 답장 제목에서 다시 찾음 |
| 외부 발신자의 답장 처리 | **이관받은 부서 메일함에서 온 메일만** 연결하고, 나머지는 제외 사유를 로그로 기록 |
| 메일 발송 실패 시 처리 | 이관은 확정하되 응답과 화면에 실패를 알림. 발송한 메시지는 DB 트리거로 수정이 막혀 있어서, 발송을 이관과 같은 트랜잭션 안에서 먼저 하고 **실제 결과로 기록**함 |
| 답장 본문의 인용문 | `>` 줄, "On … wrote:", "…님이 작성:" 등 영어·한국어 메일 프로그램의 인용 부분을 제거하고 새로 작성된 본문만 저장 |
| 중복 처리 방지 | 처음엔 "안 읽은 메일"만 확인했는데, 직접 시연하다가 **메일함에서 답장을 열어 보기만 해도 읽음 처리되어 확인 대상에서 제외되고 연결되지 않는 버그**를 발견함. 읽음 상태 대신 C/S 주소와 "처리함" 태그로 고르도록 바꾸고 회귀 테스트를 추가함. 이미 회신이 등록된 문의에 늦게 온 답장은 건너뜀 |
| 기존 흐름과의 일관성 | 새 처리 경로를 만들지 않고 기존 [회신 등록] 함수를 그대로 써서 상태 전이·실행 로그·재처리가 화면 회신과 같음 |
| DB 변경 | 테이블·컬럼 추가 없이 설정(부서 도메인)만으로 부서 주소를 만듦 |

- **테스트**: 모의(mock) SMTP 서버·메일함으로 "보내기 → 답장 → 연결 → 다시 처리" 전체와 사칭·중복·늦은 답장·발송 실패·메일 연동 비활성화를 확인하는 테스트 11개를 추가했습니다. 전체 테스트 442개가 통과합니다(팀 저장소에서도 실패하던 대시보드 날짜 테스트 1개 제외).
- **실제 확인**: Mailpit과 서버를 띄워 이관 → 요청 메일 도착 → 한국어 메일 프로그램 형식의 답장 → 주기적 메일 확인으로 회신 등록·재처리 실행까지 확인했습니다.
- **다음 단계**: 받은 메일함·발송 인터페이스(`Inbox`, `Sender`)를 Microsoft Graph나 Gmail API 구현으로 바꾸면 실제 회사 메일에 연결할 수 있습니다.

## 아키텍처

<p align="center"><img src="docs/assets/readme/cs-architecture.png" alt="CS Agent 시스템 구성: React 화면, FastAPI·LangGraph 서버, Docker Compose(api, PostgreSQL+pgvector, Mailpit), Gemini" width="100%"></p>

| 기술적 결정 | 근거 |
| --- | --- |
| 우선순위·부서·기한은 **규칙 엔진**, LLM은 문장 이해·생성만 | 과제 제공 규칙표로 100% 재현되는 값을 모델에 맡기면 오류 가능성만 커짐. 규칙 코드는 언어 모델 호출 코드를 import하지 않음 |
| LangGraph로 **순서를 고정한 그래프** | 자율 Agent 대신 처리 순서를 고정해 재현성을 확보하고, 복합 문의의 요청을 동시에 처리하며 단계마다 실행 기록을 남김 |
| PostgreSQL 하나에 기준정보·서비스·벡터 검색 | 문서 검색(pgvector)과 업무 데이터를 한 DB에서 트랜잭션으로 다룸 |
| 언어 모델 호출은 **한 계층**에서만, 보내기 직전 개인정보 가림 | 고객 이메일·전화번호가 외부 모델로 나가지 않게 한 곳에서 통제 |
| 고객에게 가는 글은 **상담원 승인 뒤에만** 발송 | 근거 밖 문장·확정적 약속이 고객에게 그대로 나가는 사고를 막음 |

## 처리 흐름

문의 1건을 요청별로 나눠 **동시에** 처리하고, 고객에게 가는 글은 모두 상담원 확인을 거칩니다.

<p align="center"><img src="docs/assets/readme/cs-flow.png" alt="처리 흐름: 문의 이해 → (요청마다 동시에) 정보 추출 → 규칙 엔진 → 근거 검색 → 답변 초안 → 발송 전 검증 → 상담원 확인" width="100%"></p>

**LangGraph를 쓴 이유**는 자율형 Agent가 필요해서가 아니라, 반대로 **처리 순서를 고정해 모델의 재량을 줄이면서도** 복합 문의의 요청을 병렬 처리하고 단계마다 실행 기록을 남기기 위해서였습니다. 우선순위·부서·기한처럼 규칙표로 100% 재현되는 것은 모델에 묻지 않습니다.

## 데이터 모델

스키마를 용도별로 나눴습니다. `ref`(기준정보 테이블 24개), `svc`(서비스 데이터), `gold`(과제 제공 정답 데이터, 서비스는 입력 컬럼만 읽음), `eval`·`scoring`(팀 정답지와 채점)입니다. 설계에서 정한 원칙은 세 가지입니다.

- **상태·우선순위·기한은 하위 문의 단위**: 한 메일에 요청이 여러 개면 요청마다 부서와 기한이 다르기 때문입니다. 동시 수정 충돌은 `version` 컬럼(낙관적 잠금)으로 방지합니다.
- **지우지 않는 기록**: 메시지, 상태 이력, 실행 기록은 추가만 하고 수정·삭제하지 않습니다(append-only). 발송된 메시지(SENT)는 DB 트리거가 수정·삭제를 막습니다(이관 메일 설계에 영향을 준 제약).
- **정답 격리**: 서비스 코드는 정답 컬럼을 읽지 않고 `gold.v_inputs`(입력 컬럼)만 읽어, 평가가 오염되지 않게 했습니다.

<p align="center"><img src="docs/assets/readme/cs-erd.png" alt="서비스 핵심 테이블 ERD: CUSTOMER, TICKET, SUB_TICKET, TICKET_MESSAGE, INQUIRY_FIELD, TICKET_STATUS_HISTORY, PRODUCT, AGENT_RUN, AGENT_STEP" width="85%"></p>

자세한 컬럼 정의는 [테이블 정의서](docs/database/table-specification.md)에 있습니다.

## 주요 기능

- **안전 우선 규칙**: 안전·설비 정지 문의는 놓치지 않도록 조금이라도 해당하면 높은 긴급도로 분류하고, 상담원 화면에 "확인 필요"로 표시
- **개인정보 가림**: 이메일·이름·전화번호는 Gemini에 보내기 직전과 실행 로그 저장 직전에 가림
- **부서 이관과 회신**: 이관 후보를 띄우고, 부서 회신이 오면 그 요청을 근거 검색부터 다시 처리. 이관 요청과 부서 회신은 실제 메일로 주고받음(개인 고도화)
- **ELLO 상담원 도우미**: 상담원 전용 챗봇. 보고 있는 문의의 제품·오류 코드에 맞춘 질문 후보를 띄우고, 제품·정책 문서를 검색해 근거와 함께 답함
- **시간 관리**: SLA 경고, 126시간 리마인드, 168시간 자동 종료를 스케줄러가 처리
- **그 밖에**: 고장 진단·유사 해결 사례 검색, 통화 받아쓰기, 한국어 번역문 표시, 상담원 업무 현황·운영 대시보드

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 백엔드 | Python 3.11, FastAPI, psycopg 3, 스케줄러 |
| AI | Google Gen AI SDK(Gemini `gemini-3.8-flash`, 임베딩 `gemini-embedding-2`), LangGraph |
| 데이터·검색 | PostgreSQL 16 + pgvector, 기준정보 테이블 24개, 문의 4,000건·해결 사례 800건 |
| 프론트 | React 18, TypeScript 5, Vite 5, TanStack Query 5, OpenAPI로 API 타입 생성 |
| 인프라 | Docker Compose, Mailpit(로컬 메일 서버, 개인 고도화) |
| 개발 방식 | OpenSpec 기반 스펙 주도 개발(SDD), 명세서 완료 기준(AC) 하나마다 테스트 하나 |

## 실행

```bash
cp .env.example .env                 # GEMINI_API_KEY 입력
docker compose up -d --build         # db(pgvector) + api(:8000) + mailpit(:8025)

python -m jobs.load_reference        # 기준정보 적재
python -m jobs.load_gold             # 문의·해결 사례 적재
python -m jobs.build_doc_index       # 문서 107개 → 절 895개 인덱싱
python -m jobs.replay_demo           # 시연용 미해결 문의

cd frontend && npm install && npm run dev   # http://localhost:5173
```

이관할 때 보낸 메일과 부서 답장은 http://localhost:8025 (Mailpit)에서 볼 수 있습니다. 메일은 외부로 발송되지 않습니다.

원천 데이터(`data/`)와 `.env`는 저장소에 포함하지 않습니다. 테스트는 `pip install -e "backend[test]" && cd backend && pytest`로 실행합니다.

## 주요 API

전체 API 49개 중 문의 처리 흐름과 이관 메일 기능의 핵심만 추렸습니다. 전체 목록은 서버 실행 후 `/docs`(Swagger)나 [`frontend/openapi.json`](frontend/openapi.json)에서 볼 수 있습니다.

★ 표시는 위 "내 역할" 표에 있는 기능입니다(LLM·RAG 기능, 개인 고도화).

| 구분 | 메서드 · 경로 | 하는 일 |
|---|---|---|
| 문의 | `POST /tickets` | 문의 등록 |
| 문의 | `GET /tickets` | 접수함 목록 (상태·담당자·처리 차례로 거르기) |
| 문의 | `POST /tickets/{ticket_id}/reprocess` | 같은 문의를 새 실행으로 처음부터 다시 처리 (발송한 메시지는 유지) |
| 실행 기록 | `GET /runs/{run_id}/steps` | 처리 단계별 실행 기록 조회 |
| 답변 ★ | `POST /messages/{message_id}/verify` | 답변 초안 다시 검증 |
| 답변 ★ | `POST /messages/{message_id}/gloss` | 상담원용 한국어 대역 다시 만들기 |
| 답변 | `POST /messages/{message_id}/send` | 승인·발송 (확인이 필요한 항목이 있으면 409와 목록 반환) |
| 이관 ★ | `POST /sub-tickets/{sub_ticket_id}/escalate` | 타부서 이관 확정 · 메일 연동이 켜져 있으면 부서 메일함으로 요청 메일 발송 (메일 발송은 개인 고도화) |
| 이관 | `POST /sub-tickets/{sub_ticket_id}/dept-reply` | 부서 회신 등록 → 해당 하위 문의 다시 처리 |
| 이관 메일 ★ | `POST /mail/poll` | 받은 메일함을 지금 확인하고, 연결된 회신마다 하위 문의 다시 처리 (개인 고도화) |
| 이관 메일 ★ | `POST /mail/dept-reply-demo` | 시연용 부서 답장 (SMTP로 부서 메일함 주소에 답장 발송, 개인 고도화) |
| 이관 메일 ★ | `GET /mail/config` | 메일 연동 설정 조회 (개인 고도화) |

## API 문서와 데모

- **API 문서**: 서버를 띄운 뒤 http://localhost:8000/docs 에서 Swagger 문서로 모든 API를 직접 호출해 볼 수 있습니다. API 계약은 [`frontend/openapi.json`](frontend/openapi.json)(49개)에 있고, 프론트엔드 타입은 이 계약에서 자동 생성합니다. 계약과 서버가 어긋나면 테스트가 실패합니다.
- **데모**: 부트캠프 기간에는 팀이 클라우드에 배포해 시연했고, 과정 종료 후 서비스를 종료해 현재는 운영하지 않습니다. 위 GIF는 로컬에서 실제 AI를 호출하며 녹화한 화면이고, [실행](#실행) 순서대로 직접 띄워 볼 수 있습니다.

## 문서

- [기능 요구사항 명세서](docs/requirements/functional-requirements.md) · [기술 명세서](docs/technical/technical-specification.md)
- [Agent 설계서](docs/technical/agent-design.md) · [테이블 정의서](docs/database/table-specification.md) · [화면 정의서](docs/technical/screen-specification.md)

---

화면과 평가에는 LS ITC가 교육용으로 제공한 LS ELECTRIC 합성 데이터와 시연용 가상 인물을 사용했습니다. 실제 LS ELECTRIC 제품·고객·업체 정보와는 관계가 없으며, 원본 데이터는 저장소에 포함하지 않습니다.
