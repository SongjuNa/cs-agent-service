# Proposal: 한국어 한 줄 요약 (add-summary-ko)

## Why
최신 목업의 접수함과 상세는 문의마다 한국어 한 줄 요약을 보인다(목업은 AI가 접수 때 만들어 저장한다고 가정). 저장소에는 요약이 없어 접수함이 영어 등 원문 제목을 보이고 있었다(GAP.md A-1 #1, B-1 #1). 팀 합의(2026-10-31)로 목업이 최신 기준이고 **새 열과 모델 호출 변경을 해도 된다는 허락을 받았다**(규칙 4).

## What Changes
- **새 열 `svc.sub_ticket.summary_ko`**(그리고 채점용 scoring 정의에도 같은 열).
- **모델 호출은 늘리지 않는다.** 접수 때 이미 도는 L1(문의 이해) 호출의 출력에 `summary_ko`를 하위 문의마다 더한다. 프롬프트는 `l1_understand_v2.md`(v1 복사 + 요약 지시). 모델 호출은 계속 `generate_json` 한 곳을 거친다.
- 요약 지시: 한국어 한 문장·60자 이내, **원문에 있는 사실만**, 제품명·모델 코드·오류 코드·펌웨어 버전은 번역하지 않고 그대로, 약속·조언 금지.
- 코드 정리: 공백을 한 줄로, 120자를 넘으면 자르고 `…`, 문자열이 아니거나 비면 None. **요약이 빠져도 처리는 실패하지 않는다.**
- **저장한 값을 보인다.** 모델은 같은 입력에도 매번 조금씩 다른 글을 줄 수 있으므로, 접수 때 한 번 저장하고 화면은 그 값을 보인다(열 때마다 모델을 부르지 않음). 다시 처리할 때 새 값이 있을 때만 바꾼다(`coalesce`).
- 응답: `InboxRow.summary_ko`, `SubTicketRow.summary_ko`. 화면: 접수함 문의 칸·나의 업무 현황 "지금 처리할 건"은 요약(없으면 문의 제목), 상세 머리에 "AI 요약" 줄.

## 범위 밖
- 이미 접수된 문의의 요약 채우기(재처리 때 생김, 예전 접수본은 제목으로 대신).
- 요약 수정, 번역(원문 한국어 번역은 별개 기능).

## 이미 만들어진 DB에 반영하는 방법
```sql
ALTER TABLE svc.sub_ticket ADD COLUMN IF NOT EXISTS summary_ko text;
ALTER TABLE scoring.sub_ticket ADD COLUMN IF NOT EXISTS summary_ko text;
```
데이터는 지우지 않는다.

## Impact
`prompts/l1_understand_v2.md`(v1 유지), `llm/understand.py`, `pipeline/state.py`·`understand.py`, `db/store.py`(UPDATE), `db/inbox.py`·`detail.py`, `schemas.py`, `schema.sql`·`table-specification.md`, `openapi.json`, `api.gen.ts`, 화면(접수함·나의 업무 현황·상세 머리), 시험 `test_summary_ko.py`(3개)·SCR-03-AC-27, 프롬프트 이름을 보는 시험 2곳(v1 → v2).
