# Design: add-body-translation

## 결정
1. **저장 위치:** `svc.ticket.body_ko text`. 번역은 문의(티켓)의 원문 하나에 대한 것이라 티켓 열이 맞다. 다시 처리(RETRY)해도 원문이 같으므로 지우지 않는다.
2. **언제:** 상담원이 [번역 보기]를 누를 때만. 이미 있으면 모델 호출 없이 저장값을 돌려준다.
3. **호출:** `app/llm/translate.py`의 `translate_body(transport, source_language_name, body)` — `generate_json(call "L12", prompt l12_translate_v1.md)`, 스키마 `{translation: string}`. 두 번 실패하면 `LlmError`를 그대로 올린다.
4. **동시 요청:** 같은 문의를 두 번 누르면 모델을 두 번 부를 수 있다. 저장은 `UPDATE ... SET body_ko = %s WHERE ticket_id = %s AND body_ko IS NULL`로 먼저 저장된 값을 이기지 않게 하고, 응답은 저장된 값을 다시 읽어 돌려준다.
5. **프롬프트:** 의미만 옮기고 더하거나 빼거나 풀어 쓰지 않는다. 제품 코드·오류 코드·숫자·URL·첨부 표시(`[attachment: ...]`)는 그대로 둔다. 가려진 표시(`**MASKED**` 등)도 그대로 둔다.
6. **응답:** `{ticket_id, body_ko, cached}` (`cached`=저장돼 있던 값을 돌려줌).

## 위험
- 번역 오류: "검토용" 표시, 원문 병기.
- 개인정보: generate_json이 보내기 직전 가린다. 번역문은 가려진 입력에서 나온 것이라 가린 표시가 번역문에 남는다.
- 비용: 누른 문의에만 든다.
