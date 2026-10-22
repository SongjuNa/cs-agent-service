# Tasks: 규칙 엔진

## 1. 준비

- [ ] 1.1 `backend/pyproject.toml`에 `pyyaml`을 더하고 `config/return_reason_words.yaml`을 만든다(design 결정 4). 확인: 파일의 단어가 비불량 25개, 불량 12개다

## 2. 규칙 함수

- [ ] 2.1 `app/rules/lookup.py` (FR-010). 확인: CUST-0350, ACB-AS-2000 조회 값이 AC-010-1과 같다
- [ ] 2.2 `app/rules/priority.py` (FR-011). 확인: CSV1-000017이 P1, PR-02다
- [ ] 2.3 `app/rules/routing.py` (FR-012, 반품 구분). 확인: 영어 사유 "We received a different model from what we ordered"가 NON_DEFECT이고, CSV1-000039(MV_EQUIP, RETURN)에 NON_DEFECT를 주면 SCM이 나온다
- [ ] 2.4 `app/rules/required_info.py` (FR-013). 확인: CSV1-000017의 빠진 항목이 AC-013-1과 같다
- [ ] 2.5 `app/rules/sla.py` (FR-014). 확인: CSV1-000017이 SLA-DEFECT-PLATINUM-P1이다

## 3. 시험

- [ ] 3.1 `backend/tests/acceptance/test_rule_engine.py`에 AC-010-1, AC-010-2, AC-011-1~3, AC-012-1~4, AC-013-1~3, AC-014-1, AC-014-2 시험과 rules/의 `app.llm` import 검사를 만든다
- [ ] 3.2 `backend/tests/rules/test_reproduce_gold.py`에 W1-5, W1-6, W1-7, W10-1 시험을 만든다

## 4. 시험 실행

- [ ] 4.1 `pytest`를 실행해 앞 변경 시험(W7-1~2, W1-1~4, W3-1~2)과 이번 시험이 모두 통과하는지 확인한다

## Workflow follow-up

- 시험이 통과하면 브랜치 `feat/add-rule-engine`을 올리고 PR을 만든다(조장 결정 2026-10-22: 승인은 propose에서 받고, push·PR은 시험 통과 시 자동). `main` 병합은 조장이 한다(CLAUDE.md).
- PR 병합 뒤 `/opsx:archive`.
