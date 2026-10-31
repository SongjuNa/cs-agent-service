import { BLOCKING_BY_CAT, PRODUCTS, REQUIRED_BY_CAT } from './portalData'
export { REQUIRED_BY_CAT }

/**
 * 웹 문의 폼의 필수 정보. 문의 유형을 고르면 그 유형에 필요한 정보를 처음부터 모두 받도록 강제해서,
 * 접수한 뒤에 “정보를 더 보내 주세요”라고 다시 요청하는 일을 없앤다.
 * 유형별 필수 항목은 시스템의 필수 정보 규칙(티켓의 required_info)에서 가장 흔한 구성을 그대로 쓴다.
 */
export type FieldType = 'text' | 'textarea' | 'select' | 'date' | 'number' | 'file'
export interface FieldDef { type: FieldType; options?: [string, string, string][]; help?: [string, string]; ph?: [string, string] }
type Opt = [string, string, string]
const opts = (...x: Opt[]) => x

export const FIELD_DEFS: Record<string, FieldDef> = {
  product_model: { type: 'select', options: Object.entries(PRODUCTS).map(([c, p]) => [c, p.product_name, p.product_name] as Opt), help: ['제품 이름을 고르세요. 명판의 모델명으로 찾을 수 있어요.', 'Pick your product. The model is on the nameplate.'] },
  serial_no: { type: 'text', ph: ['예: 2306-A12345', 'e.g. 2306-A12345'], help: ['제품 명판에 적힌 제조(시리얼) 번호예요.', 'The serial number printed on the nameplate.'] },
  application: { type: 'textarea', ph: ['예: 3상 380V 모터 부하, 연속 운전', 'e.g. 3-phase 380 V motor load, continuous duty'], help: ['사용 전압, 부하 종류, 운전 방식을 적어 주세요.', 'Supply voltage, load type and duty.'] },
  target_standard: { type: 'text', ph: ['예: IEC 61439, KC', 'e.g. IEC 61439, UL'], help: ['필요한 규격이나 인증서 이름이에요.', 'The standard or certificate you need.'] },
  target_country: { type: 'text', ph: ['예: 독일', 'e.g. Germany'], help: ['제품을 사용할 국가(시장)예요.', 'The country or market of use.'] },
  site_condition: { type: 'textarea', ph: ['예: 주위 온도 45°C, 해발 800m, 습도 높음', 'e.g. 45 °C ambient, 800 m altitude, high humidity'], help: ['설치 장소의 온도, 고도, 습도를 적어 주세요.', 'Ambient temperature, altitude and humidity at the site.'] },
  wiring_diagram: { type: 'file', help: ['배선도 또는 단선도 파일을 올려 주세요.', 'Upload a wiring or single-line diagram.'] },
  photos: { type: 'file', help: ['제품과 명판이 보이는 사진을 올려 주세요.', 'Upload photos showing the product and nameplate.'] },
  purchase_doc: { type: 'text', ph: ['예: PO-2026-0412', 'e.g. PO-2026-0412'], help: ['구매 주문서(PO) 또는 송장 번호예요.', 'Your PO or invoice number.'] },
  install_date: { type: 'date', help: ['설치 또는 시운전한 날짜예요.', 'Installation or commissioning date.'] },
  failure_description: { type: 'textarea', ph: ['어떤 현상이 언제 발생했는지', 'What happened and when'], help: ['고장 증상과 발생 시각을 자세히 적어 주세요.', 'Describe the failure and when it occurred.'] },
  po_number: { type: 'text', ph: ['예: PO-2026-0412', 'e.g. PO-2026-0412'], help: ['주문서(PO) 번호예요.', 'Your PO number.'] },
  quantity: { type: 'number', help: ['필요한 수량이에요.', 'Quantity required.'] },
  required_date: { type: 'date', help: ['받고 싶은 납품 날짜예요.', 'Requested delivery date.'] },
  incoterms: { type: 'select', options: opts(['FOB', 'FOB 부산', 'FOB Busan'], ['EXW', 'EXW 공장', 'EXW Factory'], ['CIF', 'CIF 도착 항구', 'CIF destination port'], ['CFR', 'CFR 도착 항구', 'CFR destination port'], ['DAP', 'DAP 도착지', 'DAP destination']), help: ['배송 조건과 도착지예요.', 'Delivery terms and destination.'] },
  document_type: { type: 'select', options: opts(['DS', '데이터시트', 'Datasheet'], ['IG', '설치·시운전 가이드', 'Installation guide'], ['TG', '고장 해결 가이드', 'Troubleshooting guide'], ['RN', '펌웨어 릴리스 노트', 'Firmware release notes'], ['CERT', '인증서', 'Certificate']), help: ['어떤 문서가 필요한지 골라 주세요.', 'Which document do you need?'] },
  doc_language: { type: 'select', options: opts(['en', '영어', 'English'], ['ko', '한국어', 'Korean']), help: ['문서를 받고 싶은 언어예요.', 'Preferred document language.'] },
  error_code: { type: 'text', ph: ['예: E.OC', 'e.g. E.OC'], help: ['화면에 표시되는 오류 코드나 증상이에요.', 'The error code or symptom on the display.'] },
  operating_condition: { type: 'textarea', ph: ['예: 70% 부하, 50Hz, 실내 40°C', 'e.g. 70% load, 50 Hz, 40 °C indoors'], help: ['고장 났을 때의 부하, 속도, 온도예요.', 'Load, speed and temperature at the time of failure.'] },
  logs: { type: 'file', help: ['이벤트 또는 트립 로그 파일이에요.', 'The event or trip log export.'] },
  current_fw: { type: 'text', ph: ['예: 3.00', 'e.g. 3.00'], help: ['지금 쓰는 펌웨어 버전이에요.', 'The firmware version in use.'] },
  tool_version: { type: 'text', ph: ['예: Loader 2.4', 'e.g. Loader 2.4'], help: ['사용하는 엔지니어링 툴이나 로더 버전이에요.', 'Engineering tool or loader version.'] },
  return_reason: { type: 'select', options: opts(['DOA', '도착 시 불량', 'Dead on arrival'], ['WRONG', '오배송', 'Wrong item shipped'], ['DAMAGE', '운송 중 파손', 'Shipping damage'], ['ORDER', '주문 실수·과잉 재고', 'Ordering error / excess stock'], ['OTHER', '기타', 'Other']), help: ['반품 사유를 골라 주세요.', 'Reason for return.'] },
  packaging_condition: { type: 'select', options: opts(['ORIGINAL', '원포장 그대로', 'Original, intact'], ['DAMAGED', '포장 손상', 'Packaging damaged'], ['OPENED', '개봉함', 'Opened'], ['NONE', '포장 없음', 'No packaging']), help: ['도착했을 때 포장 상태예요.', 'Condition of the packaging on arrival.'] },
  parameter_backup: { type: 'file', help: ['파라미터 백업 파일이에요.', 'Parameter backup file.'] },
  motor_nameplate: { type: 'text', ph: ['예: 22kW, 380V, 45A, 1760rpm', 'e.g. 22 kW, 380 V, 45 A, 1760 rpm'], help: ['모터 명판의 출력, 전압, 전류, 회전수예요.', 'Power, voltage, current and speed from the motor nameplate.'] },
  program_backup: { type: 'file', help: ['PLC/HMI 프로젝트 백업 파일이에요.', 'PLC/HMI project backup.'] },
  battery_status: { type: 'text', help: ['사고 시점의 배터리 SOC와 셀 온도예요.', 'Battery SOC and cell temperature at the event.'] },
  load_profile: { type: 'file', help: ['부하 전류·온도 기록 파일이에요.', 'Load current / temperature records.'] },
  oil_test: { type: 'file', help: ['오일 가스 분석(DGA) 보고서예요.', 'Oil test (DGA) report.'] },
  string_config: { type: 'text', ph: ['예: 스트링당 모듈 22장', 'e.g. 22 modules per string'], help: ['PV 스트링 하나에 연결된 모듈 수예요.', 'Modules per PV string.'] },
  battery_age: { type: 'date', help: ['배터리를 설치한 날짜예요.', 'Battery installation date.'] },
}

export const CAT_EN: Record<string, string> = {
  TECH_SPEC: 'Technical specification', DEFECT: 'Fault / malfunction', INSTALL: 'Installation & commissioning', MANUAL: 'Manuals & documents', FW_UPDATE: 'Firmware update',
  COMPLIANCE: 'Certification & standards', ORDER_LEAD: 'Order & lead time', RETURN: 'Return & exchange', QUOTE: 'Quotation', WARRANTY: 'Warranty claim',
}

/**
 * 막는 정보(blocking): 없으면 처리를 시작할 수 없는 필수 정보. 유형마다 다르다.
 * 시스템 데이터(티켓의 missing_blocking_info)에서 유형별로 막는 항목을 뽑았다. 같은 항목은 데이터에서 늘 막는 정보로 나온다.
 * 막는 정보는 꼭 입력해야 하고, 막지 않는 필수 정보는 모르면 “모르겠어요”를 선택할 수 있다.
 */
export const isBlocking = (cat: string, k: string) => !!BLOCKING_BY_CAT[cat]?.includes(k)
export const UNKNOWN = '__unknown'
/** 입력칸 순서: 막는 정보를 먼저 */
export const fieldsOf = (cat: string): string[] => {
  const all = REQUIRED_BY_CAT[cat] ?? []
  return [...all.filter((k) => isBlocking(cat, k)), ...all.filter((k) => !isBlocking(cat, k))]
}

export type Values = Record<string, string | string[]>
/** 비어 있는 필수 항목. 파일 항목은 파일 이름 목록, 나머지는 글자 */
export function missingFields(cat: string, v: Values): string[] {
  return (REQUIRED_BY_CAT[cat] ?? []).filter((k) => {
    const val = v[k]
    const type = FIELD_DEFS[k]?.type
    if (val === UNKNOWN && !isBlocking(cat, k)) return false
    if (type === 'file') return !(Array.isArray(val) && val.length)
    if (type === 'number') return !(Number(val) > 0)
    return !(typeof val === 'string' && val.trim())
  })
}
