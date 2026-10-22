# gold-dataset Specification

## Purpose
운영진 정답지 원본(tickets.csv, resolution_cases.csv)을 gold 스키마에 바꾸지 않고 넣는다. 채점과 불러오기(FR-003)가 이것을 쓰며, 서비스는 입력 열 뷰 v_inputs만 읽는다(기술 명세서 v1.4 §6-1, W3).

## Requirements

### Requirement: 정답지는 원본 그대로 들어간다 (W3)
정답지 적재 작업은 tickets.csv를 gold.ticket_gold에, resolution_cases.csv를 gold.resolution_case_gold에 원본 열 이름 그대로, 모든 값을 문자열로 넣어야 한다(MUST)(테이블 정의서 v1.3 §3). 다시 실행하면 표를 비우고 다시 넣어야 한다(MUST).

#### Scenario: W3-1 행 수와 뷰 행 수가 정의서와 같다
- **GIVEN** 빈 gold 스키마
- **WHEN** 정답지 적재 작업을 실행한다
- **THEN** gold.ticket_gold는 4,000행, gold.resolution_case_gold는 800행이다
- **AND** gold.v_inputs는 4,000행이다

#### Scenario: W3-2 값이 원본 CSV와 글자까지 같다
- **GIVEN** 정답지 적재를 마친 DB
- **WHEN** gold.ticket_gold의 모든 행·열을 tickets.csv와 비교한다
- **THEN** 4,000행 58열이 모두 같다(빈 칸은 빈 문자열이 아니라 비어 있음(NULL)으로 저장된 것만 예외)
