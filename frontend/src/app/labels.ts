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

export const label = (map: Record<string, string>, code: string | null | undefined): string =>
  code ? map[code] ?? code : "—";
