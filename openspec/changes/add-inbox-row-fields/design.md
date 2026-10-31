# Design: 접수함 줄·건수 값 추가

## Decisions

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 줄 값 | `country`는 `ref.customer.country`, `inquiry_subject`는 `ticket.inquiry_subject`. 둘 다 없을 수 있다(null) | 상세 응답 `Ticket.country`·`inquiry_subject`와 같은 출처 |
| 신규·이관 건수 | `status = 'NEW'`, `'ESCALATED'`인 줄 수 | 목업 `새 문의`, `이관` 탭 |
| 초과·임박 | 초과 = `alerts`에 `FR_BREACHED`나 `RES_BREACHED`. 임박 = `FR_AT_RISK`나 `RES_AT_RISK`만 있고 초과는 없음 | 목업 `alertOf`(초과가 임박보다 우선) |
| 건수 범위 | 현재 필터가 걸린 줄(기존 `counts`와 같음) | 기존 동작 유지 |
| 뷰와 같은 값 | `v_inquiry_inbox` 비교 시험(`test_same_rows_as_view`)은 기존 열만 비교하므로 영향 없음 | `test_inbox.py` |

## Risks

- 채점용 재생 데이터에는 문의 제목이 비어 있다(서비스 DB는 364건 중 309건에 있음). 시험은 칸이 있는지만 본다.
- 제목이 원문 언어(영어 등)라 목업의 한국어 요약과 다르게 보인다.
