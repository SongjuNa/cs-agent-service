// 고객 포털 미리보기가 쓰는 데이터. 목업(mock.json)에서 포털에 필요한 것만 뽑았다: 제품 23종, 공개 문서(정책·데이터시트·설치 가이드·릴리스 노트·유지보수),
// 유형별 필수 정보와 막는 정보. 실제 시스템에서는 서버의 제품·문서 API가 이 자리를 채운다.
import raw from "./portalData.json";

export interface LibSection { level: number; section: string; title: string; body: string }
export interface LibDoc { doc_id: string; title: string; doc_type: string; product_code: string; family: string; sections: LibSection[] }
export interface Product { product_name: string; family: string; warranty_months?: string; std_lead_time_weeks?: string }

const D = raw as unknown as {
  products: Record<string, Product>; library: LibDoc[]; fields: Record<string, string>;
  errorCodes: string[]; required: Record<string, string[]>; blocking: Record<string, string[]>;
};
export const PRODUCTS = D.products;
export const LIBRARY = D.library;
export const ERROR_CODES = D.errorCodes;
export const REQUIRED_BY_CAT = D.required;
export const BLOCKING_BY_CAT = D.blocking;
export const CAT: Record<string, string> = {
  TECH_SPEC: '기술 사양', DEFECT: '고장', INSTALL: '설치·시운전', MANUAL: '문서 요청', FW_UPDATE: '펌웨어',
  COMPLIANCE: '인증·규격', ORDER_LEAD: '납기', RETURN: '반품', QUOTE: '견적', WARRANTY: '보증',
}

const FIELD_KO: Record<string, string> = {
  product_model: '제품 모델', serial_no: '시리얼 번호', application: '용도(전압·부하)', target_standard: '요구 규격·인증',
  target_country: '대상 국가', site_condition: '현장 조건', wiring_diagram: '배선도', photos: '제품·명판 사진',
  purchase_doc: 'PO·송장 번호', install_date: '설치일', failure_description: '고장 내용', po_number: 'PO 번호',
  quantity: '수량', required_date: '희망 납기', incoterms: '인코텀즈', document_type: '문서 종류', doc_language: '문서 언어',
  error_code: '에러 코드', operating_condition: '운전 조건', logs: '이벤트 로그', current_fw: '현재 펌웨어',
  tool_version: '툴 버전', return_reason: '반품 사유', packaging_condition: '포장 상태', parameter_backup: '파라미터 백업',
  motor_nameplate: '모터 명판', program_backup: '프로젝트 백업', battery_status: '배터리 상태', load_profile: '부하 기록',
  oil_test: '오일 분석', string_config: '스트링 구성', battery_age: '배터리 사용 기간',
}
export const fieldLabelEn = (f: string) => D.fields[f] ?? f;
export const fieldLabel = (f: string) => FIELD_KO[f] ?? D.fields[f] ?? f;
