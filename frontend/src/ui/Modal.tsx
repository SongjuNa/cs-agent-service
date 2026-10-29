// 모달(대화 창) (principles §4). 목업 .overlay / .dialog (header, .db, footer).
// 브라우저 기본 alert·confirm은 쓰지 않는다. Esc와 바깥 누르기로 닫고, 열리면 창 안 첫 칸에 초점을 둔다.
import { useEffect, useId, useRef, type ReactNode } from "react";

export interface ModalProps {
  title: string;
  children: ReactNode;
  /** 아래 버튼 줄. 보통 [취소] [확인] 순서로 둔다 */
  footer?: ReactNode;
  onClose: () => void;
  wide?: boolean;
  /** 보내는 중에는 Esc·바깥 누르기로 닫히지 않게 한다 */
  locked?: boolean;
}

export function Modal({ title, children, footer, onClose, wide = false, locked = false }: ModalProps) {
  const titleId = useId();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !locked) onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, locked]);

  useEffect(() => {
    const first = box.current?.querySelector<HTMLElement>("input, select, textarea, button");
    first?.focus();
  }, []);

  return (
    <div className="ui-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget && !locked) onClose(); }}>
      <div ref={box} className={wide ? "ui-dialog ui-dialog--wide" : "ui-dialog"} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId} className="ui-dialog__head">{title}</h2>
        <div className="ui-dialog__body">{children}</div>
        {footer && <div className="ui-dialog__foot">{footer}</div>}
      </div>
    </div>
  );
}
