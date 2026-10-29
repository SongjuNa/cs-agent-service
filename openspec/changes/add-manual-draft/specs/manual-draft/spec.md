## ADDED Requirements

### Requirement: 초안이 없는 종류는 상담원이 직접 쓴다 (FR-030)
초안이 없는 종류에서 상담원은 정보 요청 또는 답변 초안을 직접 만들 수 있어야 한다(MUST). 만든 초안은 sender AGENT인 DRAFT여야 하고, SENT로 바꾸는 것은 승인 API뿐이어야 한다(MUST). 같은 종류의 안 보낸 초안이 있거나, 보냈을 때 전이가 없는 상태면 만들기를 거부해야 한다(MUST).

#### Scenario: 제안 AC-030-6 근거 없는 답변을 직접 써서 보냄
- **GIVEN** CSV1-000004(막는 항목 없음)를 근거 없음으로 만들어 답변 초안이 없는 상태
- **WHEN** 상담원이 숫자 없는 FINAL_REPLY를 직접 써서 임시 저장하고 승인·발송한다
- **THEN** FINAL_REPLY SENT(sender AGENT) 행이 1건 생기고 하위 문의 상태가 RESOLVED가 된다

#### Scenario: 시스템 초안이 있으면 거부
- **GIVEN** 안 보낸 시스템 정보 요청 초안이 있는 CSV1-000017
- **WHEN** 같은 하위 문의에 INFO_REQUEST를 직접 만들려 한다
- **THEN** 409로 거부되고 새 행이 생기지 않는다

#### Scenario: 전이가 없는 상태면 거부
- **GIVEN** WAITING_CUSTOMER인 하위 문의
- **WHEN** INFO_REQUEST를 직접 만들려 한다
- **THEN** 409로 거부된다

#### Scenario: 빈 본문 거부
- **GIVEN** 답변 초안이 없는 하위 문의
- **WHEN** 본문이 공백뿐인 초안을 만들려 한다
- **THEN** 400 "내용을 입력하세요"로 거부된다

### Requirement: 직접 쓴 초안도 승인 전 검사를 거친다 (FR-031)
직접 쓴 초안을 승인할 때도 시스템 초안과 같은 승인 전 검사를 해야 하고, 걸리면 확인을 받은 뒤에만 보내야 한다(MUST). 검증 에이전트는 자동으로 부르지 않아야 한다(MUST).

#### Scenario: 제안 AC-030-7 근거 밖 숫자 확인
- **GIVEN** 제안 AC-030-6의 상태에서 직접 쓴 답변 본문에 조회값(520 USD, 4주)에 없는 "999 USD"가 있음
- **WHEN** 승인을 누른다
- **THEN** 409 확인 필요가 오고, override_check로 다시 보내면 발송되며 발송 행에 override_check가 남는다

#### Scenario: 막는 항목이 남은 답변
- **GIVEN** 막는 항목(serial_no)이 남은 CSV1-000017에서 직접 쓴 FINAL_REPLY
- **WHEN** 승인을 누른다
- **THEN** 409 확인 필요가 온다

#### Scenario: 검증 에이전트 없음
- **GIVEN** 상담원이 방금 직접 만든 초안
- **WHEN** 상세를 연다
- **THEN** 그 초안의 L8 단계가 없고 검토 표시 ⑤는 "검증 전"이다
