/**
 * 개인정보 마스킹 (FR-038). 새로 받는 글(접수 본문, 고객 회신, 고친 초안)에서만 저장 전에 가린다.
 * 날짜, 제조번호, 주문 번호, 에러 코드, 수량·금액은 가리지 않는다.
 */
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g
const INTL_PHONE = /\+\d[\d\s().-]{6,}\d/g
const GROUPED_PHONE = /\b\d{2,4}[\s.-]\d{3,4}[\s.-]\d{4}\b/g

export function maskPII(text: string) {
  let n = 0
  const mask = (to: string) => () => (n++, to)
  const out = text
    .replace(EMAIL, mask('user***@***.masked'))
    .replace(INTL_PHONE, mask('*******'))
    .replace(GROUPED_PHONE, mask('*******'))
  return { text: out, count: n }
}
