// 목업 v1.42의 아이콘(SVG)을 그대로 옮겼다. 손으로 고치지 말고 목업이 바뀌면 다시 뽑는다.
// 값은 이 파일 안의 고정 문자열이라 innerHTML로 넣어도 안전하다.

const PATHS: Record<string, string> = {
  notice: "<path d=\"M3 10v4h3l7 5V5L6 10H3z\"></path><path d=\"M16.5 8.5a5 5 0 0 1 0 7\"></path><path d=\"M19 6a8.5 8.5 0 0 1 0 12\"></path>",
  sysnote: "<rect x=\"3\" y=\"4\" width=\"18\" height=\"12\" rx=\"1\"></rect><path d=\"M8 20h8M12 16v4\"></path><path d=\"M12 7.5v4M12 13.6h.01\"></path>",
  home: "<rect x=\"3\" y=\"3\" width=\"7\" height=\"9\" rx=\"1\"></rect><rect x=\"14\" y=\"3\" width=\"7\" height=\"5\" rx=\"1\"></rect><rect x=\"14\" y=\"12\" width=\"7\" height=\"9\" rx=\"1\"></rect><rect x=\"3\" y=\"16\" width=\"7\" height=\"5\" rx=\"1\"></rect>",
  inbox: "<path d=\"M3 13h5l2 3h4l2-3h5\"></path><path d=\"M5 5h14l2 8v6H3v-6z\"></path>",
  phone: "<path d=\"M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2\"></path>",
  similar: "<rect x=\"8\" y=\"8\" width=\"13\" height=\"13\" rx=\"2\"></rect><path d=\"M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3\"></path>",
  customers: "<circle cx=\"9\" cy=\"8\" r=\"3.5\"></circle><path d=\"M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5\"></path><path d=\"M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.8c1.6.8 2.6 2.6 3 5.2\"></path>",
  chatbot: "<rect x=\"4\" y=\"7\" width=\"16\" height=\"12\" rx=\"3\"></rect><path d=\"M12 7V4M9 12h.01M15 12h.01M9.5 15.5h5\"></path>",
  docs: "<path d=\"M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z\"></path><path d=\"M14 3v5h5M8.5 13h7M8.5 17h7\"></path>",
  rules: "<path d=\"M9 6h11M9 12h11M9 18h11\"></path><path d=\"m3.5 6 1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2\"></path>",
  products: "<path d=\"M21 8 12 3 3 8v8l9 5 9-5z\"></path><path d=\"m3 8 9 5 9-5M12 13v8\"></path>",
  depts: "<path d=\"M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 10h4a1 1 0 0 1 1 1v10M3 21h18M8 8h3M8 12h3M8 16h3\"></path>",
  etc: "<circle cx=\"5\" cy=\"12\" r=\"1.5\"></circle><circle cx=\"12\" cy=\"12\" r=\"1.5\"></circle><circle cx=\"19\" cy=\"12\" r=\"1.5\"></circle>",
  ops: "<path d=\"M4 20V10M10 20V4M16 20v-7M22 20H2\"></path>",
  portal: "<circle cx=\"12\" cy=\"12\" r=\"9\"></circle><path d=\"M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18\"></path>",
  ext: "<path d=\"M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5\"></path>",
  bell: "<path d=\"M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8\"></path><path d=\"M10 20a2 2 0 0 0 4 0\"></path>",
  help: "<circle cx=\"12\" cy=\"12\" r=\"9\"></circle><path d=\"M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6\"></path><path d=\"M12 17.2h.01\"></path>",
  collapse: "<path d=\"m15 6-6 6 6 6\"></path>",
  crumbHome: "<path d=\"M12 3.2 2.5 11.1l1.3 1.5L5 11.6V21h5.2v-6h3.6v6H19v-9.4l1.2 1 1.3-1.5z\"></path>",
  chev: "<path d=\"m9 6 6 6-6 6\"></path>",
  search: "<circle cx=\"11\" cy=\"11\" r=\"7\"></circle><path d=\"m20 20-3.5-3.5\"></path>",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, className }: { name: string; className?: string }) {
  return <svg viewBox="0 0 24 24" className={className} aria-hidden="true" dangerouslySetInnerHTML={{ __html: PATHS[name] ?? "" }} />;
}

/** 목업 머리 막대의 ONCE 글자 로고 */
export function Wordmark() {
  return <svg viewBox="0 -20 362 120" role="img" aria-label="ONCE" className="shell-wordmark" dangerouslySetInnerHTML={{ __html: "<defs><clipPath id=\"hd-in\"><circle cx=\"50\" cy=\"50\" r=\"26\"></circle></clipPath></defs><g transform=\"translate(20,0) skewX(-12)\"><circle cx=\"50\" cy=\"50\" r=\"33\" fill=\"none\" stroke=\"#FFFFFF\" stroke-width=\"14\"></circle><g clip-path=\"url(#hd-in)\" fill=\"none\" stroke=\"#FFFFFF\" stroke-width=\"6\"><ellipse cx=\"50\" cy=\"50\" rx=\"11\" ry=\"30\"></ellipse><line x1=\"10\" y1=\"50\" x2=\"90\" y2=\"50\"></line></g><polygon fill=\"#FFFFFF\" points=\"105,90 105,10 128,10 151,52 151,10 174,10 174,90 151,90 128,48 128,90\"></polygon><path fill=\"none\" stroke=\"#FFFFFF\" stroke-width=\"22\" d=\"M248.4,30.7 A29,29 0 1 0 248.4,69.3\"></path><polygon fill=\"#FFFFFF\" points=\"268,10 328,10 328,29 291,29 291,40.5 322,40.5 322,59.5 291,59.5 291,71 328,71 328,90 268,90\"></polygon><path fill=\"#FA002D\" d=\"M266,3 C290,-2 314,-8 336,-17 L330,4 C310,2 288,2 266,3 Z\"></path></g>" }} />;
}
