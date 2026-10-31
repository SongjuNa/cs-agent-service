# Proposal: 운영 대시보드 — 최신 목업 구성 (add-ops-overview)

## Why
최신 목업의 운영 대시보드("운영 현황")는 숫자 카드 5개, 일별 접수 추이 선 그래프, 먼저 볼 나라, 부서별 병목, 상담원별 업무량, 처리 단계별 현황을 한 화면에 보인다. 저장소에는 화면도 API도 없고(2026-10-29 조장 결정으로 목업 전용, 보류 제안 `add-ops-dashboard`·`add-dashboard-tabs`는 구현 전), 목업과 구성이 다르다. 팀 합의(2026-10-31)로 목업이 최신 기준이고, 보류 제안은 **이 변경으로 대체**한다. 그래프를 실제 값으로 그리기 위해 해결·종료 이력을 변경 `add-dashboard-history`로 먼저 적재했다.

## What Changes
- **새 API 1개** `GET /dashboard/summary?days=&as_of=`(읽기만, 새 열·표 없음). 미해결·기한 초과·임박·기준일 신규, 기간 안 접수분의 기한 충족(1차 응답 MET·BREACHED, 해결 위반 아님), 일별 접수(빈 날 0), 부서·상담원·나라별 쌓임(미해결·위반·임박·안전·이관 지연), 처리 단계별 현황, 고쳐 보낸 비율의 재료.
  - 문의별 값을 SQL 한 번(`inquiry_sla(as_of)`)으로 읽고 파이썬에서 센다. 초과·임박 정의는 접수함과 같다. 이관 지연 = 이관 후 168시간.
- 화면 SCR-06 `/dashboard`: 목업의 구성. 막대·선 그래프는 라이브러리 없이 SVG/CSS. 막대를 누르면 문의 배정 관리로 간다.
- 보류 제안 `add-ops-dashboard`, `add-dashboard-tabs`에 "대체됨" 표시.

## 목업과 다른 곳 (SCR-06 명세에 적음)
- 3D 지구본과 AI 문장은 넣지 않고 "먼저 볼 나라" 순위로 대신. 문장은 숫자로 화면이 만든다(모델 호출 없음).
- "AI와 사람이 나눠 처리한 비중"·"AI 자동 처리율"은 자동 발송 구현 전이라 값이 없어 "고쳐 보낸 비율"로 대신(재생 이력에는 edited_yn이 없어 시스템에서 보낸 답변이 생기기 전까지는 "—").

## 범위 밖
- 내 실적(나의 업무 현황, 다음 변경), 자동 발송 관련 카드, 지구본, 제품·고객·AI 탭.

## Impact
`backend/app/db/dashboard.py`·`api/dashboard.py`·`schemas.py`·`main.py`, `openapi.json`·`api.gen.ts`, 화면 `features/ops/`·`App.tsx`·`api.ts`, 명세 SCR-06·README, 시험 `test_dashboard.py`(4개)·계약 시험(40 → 41)·`scr-06.spec.ts`(5개).
DB 구조는 고치지 않는다. 응답 시간은 직접 쟀을 때 0.15~0.23초.
