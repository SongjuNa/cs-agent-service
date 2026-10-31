# Design: 자동 발송

## 결정 1. 데이터
| 표·열 | 내용 |
|---|---|
| `svc.auto_setting` (새 표) | `key text PK`, `value jsonb`, `updated_by`, `updated_at_utc`. 키 하나 `rules` = `{enabled, cats{MANUAL:true,…}, channels{EMAIL:true,…}}`. 행이 없으면 기본값(목업 `DEFAULT_RULES`: 켜짐, MANUAL·TECH_SPEC·FW_UPDATE 켜짐, COMPLIANCE 꺼짐, PHONE 꺼짐) |
| `svc.auto_review` (새 표) | `message_id bigint PK FK ticket_message`, `reviewed_by`, `reviewed_at_utc`. 행이 있으면 사후 검수 완료. 넣기만 한다 |
| `ticket_message` CHECK | `sender='SYSTEM' AND message_status='SENT' AND message_type='FINAL_REPLY' AND sent_by_name='AI_AUTO'`를 허용하는 절 추가 |
| 자동 발송 표시 | 별도 열 없이 `sender='SYSTEM' AND sent_by_name='AI_AUTO' AND message_type='FINAL_REPLY' AND message_status='SENT'`인 메시지가 있으면 자동 발송 |

## 결정 2. 판정(`rules/autosend.py`, 순수 함수 `verdict(row, rules) -> (auto, passed[], blocked[])`)
입력은 접수함 줄에 이미 있는 값 + 초안 검토 표시. 목업 `autoVerdict`와 같은 순서로 막는 사유를 모은다. 사유 문구는 화면이 그대로 보이도록 서버가 준다(자동 처리 규칙 화면과 상세의 "왜 자동/사람인가").

## 결정 3. 실행
- 접수 처리(`process_ticket`)가 성공으로 끝난 뒤, 하위 문의마다 `maybe_auto_send`를 부른다. 판정이 통과하고 **상담원 발송 API가 쓰는 `issues` 검사가 비어 있을 때만** 보낸다.
- 보내기는 `status/send` 쪽 기존 함수를 `auto=True`(보내는 쪽 SYSTEM, 이름 AI_AUTO, 전이 행위자 AI_AUTO)로 부른다. 새 우회로를 만들지 않는다.
- 실패해도 처리 전체는 실패하지 않는다(자동 발송만 건너뛰고 초안은 남는다 = 상담원이 확인).
- 이미 상담원이 만진(고친) 초안은 자동 발송하지 않는다.

## 결정 4. 사후 검수
`POST /sub-tickets/{id}/auto-review`(머리 `X-Agent-Id`): 자동 발송된 문의에만. 이미 검수했거나 자동 발송이 아니면 409. 접수함 `turn`은 자동 발송 + 검수 전이면 **ME**, next_action `REVIEW_AUTO`(목업 "자동 발송 사후 검수").

## 결정 5. API
- `GET /auto-rules`, `PUT /auto-rules`(설정). 항상 사람 확인 유형은 true로 못 바꾼다(400).
- 접수함 `GET /tickets`: 필터 `auto`(true면 종료 여부와 상관없이 자동 발송 건), 줄 `auto_state`(NONE·PENDING·REVIEWED), `counts.auto`·`counts.auto_pending`.
- 운영 대시보드 `GET /dashboard/summary`: `auto: {sent, reviewed, total}`.

## 결정 6. 시험
판정 단위 시험(조건별), 실행 시험(통과하면 SYSTEM SENT·RESOLVED·이력, 하나라도 걸리면 초안만 남음, 꺼짐이면 아무것도 안 보냄), 사후 검수 시험, 설정 시험(항상 사람 유형 거부), 접수함 필터·계약 시험, 화면 e2e.

## 위험
- 규칙 3 변경 자체가 가장 큰 위험이다. 판정을 보수적으로 두고(고위험 고정) 스위치로 끈다.
- 모델 검증(⑤)이 틀릴 수 있다 → 사후 검수와 이력으로 보완. 검수 대기 건수를 업무 현황·대시보드에 보인다.
