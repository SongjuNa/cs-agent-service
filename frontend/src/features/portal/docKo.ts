/**
 * 문서 라이브러리의 한국어 표기. 목업에는 번역 AI가 없어서 문서 종류·절 제목·표의 용어와
 * 정책 4종의 요약만 미리 옮겨 둔 것이다. 실제 시스템에서는 번역 AI가 본문 전체를 번역한다.
 */
export const DOC_TYPE_KO: [string, string][] = [
  ['Installation and Commissioning Guide', '설치·시운전 가이드'],
  ['Troubleshooting and Error Code Guide', '고장 해결 및 오류 코드 가이드'],
  ['Firmware Release Notes', '펌웨어 릴리스 노트'],
  ['Maintenance Guide', '유지보수 가이드'],
  ['Datasheet', '데이터시트'],
  ['Warranty and RMA Policy', '보증 및 RMA 정책'],
  ['Return and Exchange Policy', '반품 및 교환 정책'],
  ['Ordering, Lead Time and Shipping Policy', '주문·납기·배송 정책'],
  ['Customer Service Levels and Escalation', '고객 응대 수준 및 이관'],
  ['FAQ', '자주 묻는 질문'],
]
export const koTitle = (t: string) => DOC_TYPE_KO.reduce((s, [en, ko]) => s.replace(en, ko), t)

export const SECTION_KO: Record<string, string> = {
  'Overview': '개요', 'Technical specifications': '기술 사양', 'Ratings': '정격', 'Installation data': '설치 정보', 'Terminals': '단자',
  'Standards and certifications': '규격 및 인증', 'Ordering information': '주문 정보', 'Related documents': '관련 문서', 'Safety': '안전',
  'Receiving and storage': '수령 및 보관', 'Mounting and clearances': '설치 위치와 이격 거리', 'Wiring and tightening torques': '배선과 조임 토크',
  'Commissioning procedure': '시운전 절차', 'Pre-energisation checklist': '통전 전 점검표', 'Common commissioning issues': '자주 생기는 시운전 문제',
  'How to use this guide': '이 가이드 사용법', 'Error code and symptom list': '오류 코드와 증상 목록', 'Troubleshooting procedures': '고장 해결 절차',
  'Information required when contacting support': '지원 요청 시 필요한 정보', 'Returning a unit': '제품 반품',
  'Performance and characteristics': '성능과 특성', 'Endurance and communication': '내구성과 통신', 'Protection and options': '보호 기능과 옵션',
  'Summary': '요약', 'Version history': '버전 이력', 'Update procedure': '업데이트 절차', 'Compatibility': '호환성',
  'Maintenance intervals': '정비 주기', 'Spare parts': '예비 부품', 'End of life': '수명 종료',
  'Which products does this FAQ cover?': '이 FAQ가 다루는 제품', 'What is the warranty period?': '보증 기간', 'What is the standard lead time?': '표준 납기',
  'Which certifications are available?': '제공 가능한 인증', 'Where can I get manuals and datasheets?': '매뉴얼과 데이터시트를 구하는 곳',
  'What information should I send when reporting a fault?': '고장 신고 시 보낼 정보', 'How do I return a product?': '제품 반품 방법',
  'What is the latest firmware?': '최신 펌웨어', 'Terminal overheating / discoloration': '단자 과열/변색', 'Breaker cannot be reset after trip': '트립 후 차단기 복귀 불가',
  'Warranty period': '보증 기간', 'Coverage': '보증 범위', 'Exclusions': '보증 제외', 'Claim procedure': '클레임 절차', 'Return types': '반품 유형', 'Procedure': '절차',
  'Standard lead times': '표준 납기', 'Order confirmation': '주문 확인', 'Expediting and partial shipment': '납기 단축과 분할 출하', 'Incoterms': '인코텀즈', 'Quotations': '견적',
  'Priority definitions': '우선순위 정의', 'First response targets (hours)': '1차 응답 목표(시간)', 'Resolution targets (hours, before category factor)': '해결 목표(시간, 유형 계수 적용 전)', 'Escalation': '이관',
}
export const koSection = (t: string) => SECTION_KO[t] ?? t

/** 표 머리글과 자주 나오는 말 */
const TERM_KO: [RegExp, string][] = [
  [/\bFrame size\b/g, '프레임 크기'], [/\bRated current\b/g, '정격 전류'], [/\bRated voltage\b/g, '정격 전압'], [/\bRated (?:operational )?voltage\b/g, '정격 전압'],
  [/\bBreaking capacity\b/g, '차단 용량'], [/\bNumber of poles\b/g, '극수'], [/\bWeight\b/g, '무게'], [/\bDimensions\b/g, '치수'],
  [/\bRated output\b/g, '정격 출력'], [/\bnormal duty\b/g, '일반 부하'], [/\bheavy duty\b/g, '중부하'], [/\bOverload capacity\b/g, '과부하 용량'], [/\bfor (\d+) minutes?\b/g, '$1분간'],
  [/\bInput voltage\b/g, '입력 전압'], [/\bOutput frequency\b/g, '출력 주파수'], [/\bAmbient temperature\b/g, '주위 온도'], [/\bEfficiency\b/g, '효율'], [/\bProtection degree\b/g, '보호 등급'],
  [/\bItem\b/g, '항목'], [/\bValue\b/g, '값'], [/\bProduct\b/g, '제품'], [/\bTask\b/g, '작업'], [/\bInterval\b/g, '주기'], [/\bSymptom\b/g, '증상'],
  [/\bLikely cause\b/g, '추정 원인'], [/\bCode\b/g, '코드'], [/\bSeverity\b/g, '심각도'], [/\bCondition\b/g, '조건'], [/\bResult\b/g, '결과'], [/\bCase\b/g, '경우'],
  [/\bmonths\b/g, '개월'], [/\bweeks\b/g, '주'], [/\bhours\b/g, '시간'], [/\bwarranty\b/gi, '보증'], [/\bLifecycle status\b/g, '수명주기 상태'],
]
export const koTerms = (t: string) => TERM_KO.reduce((s, [re, ko]) => s.replace(re, ko), t)

/** 정책 4종의 한국어 요약 (절 제목 → 요약) */
export const POLICY_KO: Record<string, Record<string, string>> = {
  'POL-WARRANTY': {
    'Warranty period': '제품별 보증 기간은 차단기·접촉기·계전기 18개월, 대부분의 인버터·PLC·HMI·변압기·계측기 24개월, 에너지 저장(PCS·BMS) 36개월입니다. 제품별 상세는 제품 정보에서 확인합니다.',
    'Coverage': '재료와 제작 결함을 보증하며, 결함 부품이나 제품을 수리하거나 교체합니다. 인증 파트너가 설치한 제품은 현장 인건비도 보증에 포함됩니다.',
    'Exclusions': '규격을 벗어난 사용(잘못된 공급 전압, 과부하, 주위 조건), 물 유입·기계적 손상·무단 개조, 그리고 12개월이 지난 소모품(팬·배터리·필터)은 보증에서 제외됩니다.',
    'Claim procedure': '① 시리얼 번호, PO/인보이스, 설치일, 증상 설명과 사진으로 고장을 신고합니다. ② 보증·RMA 데스크가 접수를 평가하고, 필요하면 품질보증팀이 원인을 분석합니다. ③ 승인되면 RMA 번호가 발급되고 대체품이 출하됩니다(표준 납기 적용). ④ 결정은 POL-SERVICE의 응대 수준 안에 통보합니다.',
  },
  'POL-RETURN': {
    'Return types': '도착 시 불량(DOA)은 인도 후 14일 이내 신고하면 무상 교체합니다. 오배송은 우리 쪽 실수이고 14일 이내 신고하면 무상 교환하며 회수를 맡습니다. 운송 중 파손은 포장 사진과 함께 7일 이내 신고하면 교체하고 운송사에 청구합니다. 주문 실수나 과잉 재고는 미사용·원포장·30일 이내면 재입고 수수료 15%를 뺀 크레딧 노트로 처리합니다. 사용하거나 설치한 제품은 반품 대신 보증 클레임으로 처리하고, 30일이 지나면 받지 않습니다.',
    'Procedure': '① PO/인보이스 번호, 시리얼 번호, 사유, 사진과 함께 RMA를 요청합니다. ② 품질 관련 반품(DOA, 반복 결함)은 품질보증팀이 검토합니다. ③ 결함이 아닌 반품은 주문·물류팀이 처리합니다. ④ RMA 양식의 주소로 보내며, RMA 없는 제품은 반송됩니다.',
  },
  'POL-ORDER': {
    'Standard lead times': '제품별 표준 납기(공장 출하 기준)와 최소 주문 수량(MOQ)이 정해져 있습니다. 예: MCCB 100AF 4주(MOQ 10), ACB 2000A 8주, VCB 12주, 건식 변압기 10주, 유입 변압기 12주.',
    'Order confirmation': 'PO를 받은 뒤 영업일 2일 이내에 공장 출하일이 적힌 주문 확인서를 보냅니다.',
    'Expediting and partial shipment': '납기 단축 요청은 생산 계획과 검토하며 납기 단축 비용이 들 수 있습니다. 재고에서의 분할 출하는 요청 시 가능합니다.',
    'Incoterms': '기본 조건은 FOB 부산 또는 EXW 공장입니다. 목적지 항구까지의 CIF/CFR/DAP는 요청 시 견적합니다.',
    'Quotations': '견적 유효 기간은 30일이고, 수량이 많으면 물량 할인이 적용됩니다. 공인 대리점이 있는 지역은 최종 고객 요청을 대리점으로 넘깁니다.',
  },
  'POL-SERVICE': {
    'Priority definitions': 'P1 긴급: 안전 위험(연기·화재·감전·아크) 또는 현장/라인 전체 정지. P2 높음: 생산·운영 영향, 시운전 차질, 반복 트립. P3 보통: 장비는 쓸 수 있는 기술 문제, 일반 보증·반품·주문 건. P4 낮음: 급한 기한 없는 정보 요청(문서, 사양, 견적, 인증서).',
    'First response targets (hours)': '1차 응답 목표(시간): P1은 PLATINUM 1 · GOLD 2 · STANDARD 4, P2는 4 · 8 · 12, P3는 8 · 16 · 24, P4는 24 · 48 · 72입니다.',
    'Resolution targets (hours, before category factor)': '해결 목표(시간, 유형 계수 적용 전): P1은 PLATINUM 24 · GOLD 48 · STANDARD 72, P2는 72 · 120 · 168, P3는 120 · 168 · 240, P4는 168 · 240 · 336입니다. 유형 계수는 반품 ×2.0, 보증 ×1.5, 납기·문서 요청 ×0.5이고 나머지는 ×1.0입니다. 고객 정보를 기다리는 시간은 기한 계산에서 뺍니다.',
    'Escalation': '전문 팀(현장 서비스, 품질보증, 펌웨어 R&D, 인증, 영업 운영)으로의 이관은 내부 배정 규칙에 따릅니다. 안전 관련 건(P1)은 전화로 24시간 365일 처리합니다.',
  },
}
