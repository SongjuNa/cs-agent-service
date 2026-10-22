// 초안 본문 그리기 (화면 정의서 v2 CP-4 출처 링크, CP-5 강조).
// 인용 (DOC §n.m)과 조회값 숫자는 링크(P2), 자체 대조 불일치는 Red 밑줄, ⑤ 지적 문장은 Red 점선 밑줄.
import type { ReactNode } from "react";
import type { Finding, Lookup } from "./api";

const CITATION = /\(\s*([A-Z]{2,4}-[A-Za-z0-9_.-]+?)\s*§\s*(Q?[0-9]+(?:\.[0-9]+)*)\s*\)/g;

export type BodyLink = { kind: "cite"; doc_id: string; section: string; text: string } | { kind: "lookup"; lookup: Lookup };

interface CharMark {
  link?: number;
  bad?: boolean;
  finding?: number;
}

function markAll(body: string, needle: string, apply: (m: CharMark) => void, marks: CharMark[], wholeNumber = false): void {
  if (!needle) return;
  let at = body.indexOf(needle);
  while (at >= 0) {
    const end = at + needle.length;
    // 숫자는 앞뒤가 숫자가 아닐 때만 같은 값으로 본다("1"이 "15" 안에서 잡히지 않게)
    const whole = !wholeNumber || (!/[\d.,]/.test(body[at - 1] ?? "") && !/\d/.test(body[end] ?? "") && !/[.,]\d/.test(body.slice(end, end + 2)));
    if (whole) for (let i = at; i < end; i++) apply(marks[i]);
    at = body.indexOf(needle, end);
  }
}

export function renderBody(
  body: string,
  opts: {
    lookups: Lookup[];
    bad: string[];
    findings: Finding[];
    onLink: (link: BodyLink) => void;
    findingRef?: (el: HTMLElement | null) => void;
  },
): ReactNode[] {
  const marks: CharMark[] = Array.from({ length: body.length }, () => ({}));
  const links: BodyLink[] = [];
  for (const m of body.matchAll(CITATION)) {
    const idx = links.push({ kind: "cite", doc_id: m[1], section: m[2], text: m[0] }) - 1;
    for (let i = m.index!; i < m.index! + m[0].length; i++) marks[i].link = idx;
  }
  for (const lv of opts.lookups) {
    const value = String(lv.value);
    if (!/\d/.test(value)) continue;
    const idx = links.push({ kind: "lookup", lookup: lv }) - 1;
    markAll(body, value, (m) => (m.link = m.link ?? idx), marks, true);
  }
  for (const token of opts.bad) markAll(body, token, (m) => (m.bad = true), marks, true);
  opts.findings.forEach((f, i) => markAll(body, f.quote, (m) => (m.finding = m.finding ?? i), marks));

  const out: ReactNode[] = [];
  let start = 0;
  let firstFinding = true;
  const same = (a: CharMark, b: CharMark) => a.link === b.link && a.bad === b.bad && a.finding === b.finding;
  for (let i = 1; i <= body.length; i++) {
    if (i < body.length && same(marks[i], marks[start])) continue;
    const text = body.slice(start, i);
    const m = marks[start];
    let node: ReactNode = text;
    const classes = [m.bad ? "hl-bad" : "", m.finding !== undefined ? "hl-finding" : ""].filter(Boolean).join(" ");
    const title = m.finding !== undefined ? opts.findings[m.finding].reason : m.bad ? "근거 밖 인용/숫자" : undefined;
    if (m.link !== undefined) {
      const link = links[m.link];
      node = (
        <button type="button" className={`link ${classes}`} title={title} onClick={() => opts.onLink(link)}>
          {text}
        </button>
      );
    } else if (classes) {
      node = <span className={classes} title={title}>{text}</span>;
    }
    if (m.finding !== undefined && firstFinding && opts.findingRef) {
      firstFinding = false;
      node = <span ref={opts.findingRef}>{node}</span>;
    }
    out.push(<span key={start}>{node}</span>);
    start = i;
  }
  return out;
}
