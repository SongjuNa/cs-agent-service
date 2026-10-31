// 화면에 보이는 이름. 목업 v1.42의 CAT·CHANNEL 이름을 실제 코드(gold.ticket_gold, svc.ticket)에 맞췄다.
// 목업에 없는 코드(COMPLIANCE·PARTNER_PORTAL·WEB_FORM)는 목업의 가까운 이름을 쓰거나(구현 선택) 코드를 그대로 보인다.

export const CATEGORY: Record<string, string> = {
  DEFECT: "고장·불량",
  FW_UPDATE: "펌웨어",
  MANUAL: "매뉴얼",
  QUOTE: "견적",
  TECH_SPEC: "기술 사양",
  COMPLIANCE: "인증·규격", // 목업 CERT
  RETURN: "반품",
  WARRANTY: "보증",
  INSTALL: "설치",
  ORDER_LEAD: "납기",
};

export const CHANNEL: Record<string, string> = {
  EMAIL: "이메일",
  CHAT: "채팅",
  PHONE: "전화",
  PARTNER_PORTAL: "포털", // 목업 PORTAL
  WEB_FORM: "웹 양식", // 목업에 없음(구현 선택)
};

export const STATUS: Record<string, string> = {
  NEW: "신규",
  IN_PROGRESS: "처리 중",
  WAITING_CUSTOMER: "고객 회신 대기",
  ESCALATED: "이관됨",
  RESOLVED: "해결",
  CLOSED: "종료",
};

export const ALERT: Record<string, string> = {
  FR_AT_RISK: "1차 응답 임박",
  FR_BREACHED: "1차 응답 지남",
  RES_AT_RISK: "해결 기한 임박",
  RES_BREACHED: "해결 기한 지남",
};

/** 긴급도 (테이블 정의서 v1.3 urgency_flag) */
export const URGENCY: Record<string, string> = {
  NONE: "특이사항 없음", SAFETY: "안전", SITE_DOWN: "현장 정지", PROD_IMPACT: "생산 영향", DEADLINE: "기한", COMMISSION: "시운전",
};

export const label = (map: Record<string, string>, code: string | null | undefined): string =>
  code ? map[code] ?? code : "—";

/** 접수함 줄의 "다음 행동"(서버 next_action 코드, 변경 add-inbox-turn-depth). 목업 actionOf 문구 */
export const NEXT_ACTION: Record<string, string> = {
  DONE: "처리 완료", WAIT_DEPT: "부서 회신 대기", WAIT_CUSTOMER: "고객 회신 대기", SEND_INFO_REQUEST: "정보 요청 보내기",
  CHECK_DEPT_REPLY: "부서 회신 확인 후 발송", APPROVE_DRAFT: "초안 승인 후 발송", WRITE_ANSWER: "답변 작성",
};
/** 묶음 머리(서버 turn 코드 → 목업 GROUP) */
export const TURN_GROUP: Record<string, string> = { ME: "내가 처리할 문의", DEPT: "기다리는 문의 · 부서·고객 회신", CUSTOMER: "기다리는 문의 · 부서·고객 회신", DONE: "처리 완료" };
export const DEPTH: Record<string, string> = { DEEP: "상세 검토", NORMAL: "일반 확인", QUICK: "빠른 확인" };
