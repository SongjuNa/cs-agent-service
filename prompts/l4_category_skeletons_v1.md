QUOTE: 제품·수량·단가·합계·표준 납기·견적 유효기간 + "정확한 견적(수량 할인 등)은 영업 담당이 별도로 안내" | 반드시 쓰는 조회값: list_price_usd, 합계, std_lead_time_weeks | 우선 인용: POL-ORDER §5(유효기간 30일)
ORDER_LEAD: 표준 납기. 확정 출하일 금지 | 반드시 쓰는 조회값: std_lead_time_weeks, moq | 우선 인용: POL-ORDER
TECH_SPEC: 묻는 사양값 + 출처 절 + 데이터시트 첨부 안내 | 반드시 쓰는 조회값: product_spec_facts.csv 행 | 우선 인용: DS
COMPLIANCE: 묻는 사양값 + 출처 절 + 데이터시트 첨부 안내 | 반드시 쓰는 조회값: product_spec_facts.csv 행 | 우선 인용: DS
DEFECT: 원인 후보·점검 순서(TG/IG 절에 있는 것만) | 반드시 쓰는 조회값: 없음 | 우선 인용: TG, IG
INSTALL: 원인 후보·점검 순서(TG/IG 절에 있는 것만) | 반드시 쓰는 조회값: 없음 | 우선 인용: TG, IG
FW_UPDATE: 현재 버전·접수 시점 최신·업데이트 또는 이미 최신 | 반드시 쓰는 조회값: firmware_history.csv 비교 결과 | 우선 인용: RN
RETURN: 정책 조항·필요 서류·판정은 사람이 한다는 안내 | 반드시 쓰는 조회값: 없음 | 우선 인용: POL-RETURN
WARRANTY: 정책 조항·필요 서류·판정은 사람이 한다는 안내 | 반드시 쓰는 조회값: warranty_months | 우선 인용: POL-WARRANTY
MANUAL: 해당 문서 ID와 절 안내 | 반드시 쓰는 조회값: 없음 | 우선 인용: IG, TG, RN, DS, MG
