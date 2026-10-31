// 글을 고치는 칸 위에 확인할 구간을 형광펜으로 겹쳐 보인다(최신 목업 MarkedTextarea).
// 입력 칸 뒤에 같은 글자를 투명으로 깔고 구간만 노랗게 칠한다. 클릭·입력은 그대로 아래 입력 칸으로 간다.
import { useLayoutEffect, useRef, type ReactNode, type TextareaHTMLAttributes } from "react";

export function MarkedTextarea({ ranges, ...rest }: { ranges: [number, number][] } & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ta = useRef<HTMLTextAreaElement>(null);
  const ov = useRef<HTMLDivElement>(null);
  const sync = () => {
    if (ov.current && ta.current) { ov.current.scrollTop = ta.current.scrollTop; ov.current.scrollLeft = ta.current.scrollLeft; }
  };
  const text = String(rest.value ?? "");
  const parts: ReactNode[] = [];
  let at = 0;
  ranges.forEach(([a, b], i) => { parts.push(text.slice(at, a), <mark key={i}>{text.slice(a, b)}</mark>); at = b; });
  parts.push(text.slice(at));
  useLayoutEffect(sync);
  return (
    <div className="ui-mk">
      <textarea ref={ta} {...rest} onScroll={(e) => { sync(); rest.onScroll?.(e); }} />
      <div ref={ov} className={`ui-mk__ov ${rest.className ?? ""}`} dir={rest.dir} aria-hidden="true">{parts}{"\n"}</div>
    </div>
  );
}
