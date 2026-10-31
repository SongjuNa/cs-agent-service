# Tasks: add-body-translation
- [x] 1. DB: `svc.ticket.body_ko` (schema.sql, table-specification.md, 기존 DB에 ALTER)
- [x] 2. 프롬프트 `prompts/l12_translate_v1.md`, `app/llm/translate.py`
- [x] 3. API `POST /tickets/{id}/translate`, 상세 응답 `ticket.body_ko`
- [x] 4. 시험 `test_body_translation.py` (저장·재사용·동시·가리기·실패·404)
- [x] 5. 계약 갱신(openapi.json, api.gen.ts), 화면 [번역 보기]
- [x] 6. SCR-03 명세·AC, e2e
