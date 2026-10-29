// 통화 녹음 칸 (명세서 FR-050 처리 6·7, 기술 명세서 v1.4.1 §12-5). 접수 시뮬레이터에서 채널 PHONE일 때 보인다.
// SCR-05 전화 상담 슬라이스에서 그 화면으로 옮긴다(화면 명세 SCR-05).
import { useState } from "react";
import { api, ApiError, type CallNote, type CallResult } from "../../api";

const mmss = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

/** 지금에서 녹음 길이를 뺀 UTC 시각(통화 시작 추정, 구현 선택 C-181) → 입력 칸 값 */
function callStart(durationSec: number): string {
  return new Date(Date.now() - durationSec * 1000).toISOString().slice(0, 19);
}

/** 통화 녹음 칸 (명세서 FR-050 처리 6·7, 기술 명세서 v1.4.1 §12-5). 채널 PHONE일 때만 보인다 */
export function CallPanel({ customerId, language, productCode, onNote }: {
  customerId: string; language: string; productCode: string; onNote: (note: string, startedAt: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<CallResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "transcribe" | "note">("");

  function show(note: CallNote, startedAt: string) {
    if (note.note_en) onNote(note.note_en, startedAt); // 메모 초안은 본문 칸에 바로 채운다. 상담원이 고친 뒤 [접수]
  }

  async function transcribe() {
    if (!file) return;
    setBusy("transcribe");
    setError(null);
    try {
      const res = await api.transcribe(file, customerId, language, productCode);
      setResult(res);
      show(res, callStart(res.duration_sec));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "서버에 닿지 못함");
    } finally {
      setBusy("");
    }
  }

  async function redraft() {
    if (!result) return;
    setBusy("note");
    setError(null);
    try {
      const note = await api.noteDraft(result.utterances, language, productCode || null);
      setResult({ ...result, ...note });
      show(note, callStart(result.duration_sec));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "서버에 닿지 못함");
    } finally {
      setBusy("");
    }
  }

  const gapAt = (sec: number) => result?.gaps.find((g) => g.reason === "NO_SPEECH" && Math.abs(g.end_sec - sec) < 0.05);

  return (
    <fieldset className="wide call-panel">
      <legend>통화 녹음 <small className="muted">AI가 녹음 전체를 받아쓰고 메모 초안을 만듭니다. 저장하지 않습니다</small></legend>
      <div className="call-upload">
        <input type="file" accept=".wav,.mp3,.flac,.ogg" aria-label="통화 녹음 파일"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(null); }} />
        <button type="button" onClick={transcribe} disabled={!file || busy !== ""}>
          {busy === "transcribe" ? "받아쓰기 중…" : error && !result ? "다시 받아쓰기" : "받아쓰기"}
        </button>
        <span className="small muted">wav·mp3·flac·ogg, 20MB·15분 이하</span>
      </div>
      {error && <p className="bad">! {error}</p>}
      {result && (
        <div className="call-result">
          <div className="call-transcript">
            <h4>받아쓴 글 <small className="muted">{mmss(result.duration_sec)}</small></h4>
            {result.gaps.length > 0 && <p className="bad small">받아쓰지 못한 구간 {result.gaps.length}곳: 녹음과 대조하세요</p>}
            <ol>
              {result.utterances.map((u) => {
                const gap = gapAt(u.start_sec);
                const inaudible = u.text.toLowerCase().includes("[inaudible]");
                return (
                  <li key={u.no}>
                    {gap && <div className="call-gap">받아쓰지 못한 구간 {mmss(gap.start_sec)}~{mmss(gap.end_sec)}</div>}
                    <span className="muted">[{u.no}] {u.speaker === "AGENT" ? "상담원" : "고객"} {mmss(u.start_sec)}</span>{" "}
                    {inaudible ? <span className="call-gap">알아들을 수 없음 {mmss(u.start_sec)}~{mmss(u.end_sec)}</span> : u.text}
                  </li>
                );
              })}
            </ol>
            {result.gaps.filter((g) => g.reason === "NO_SPEECH" && !result.utterances.some((u) => Math.abs(u.start_sec - g.end_sec) < 0.05))
              .map((g) => <div key={g.start_sec} className="call-gap">받아쓰지 못한 구간 {mmss(g.start_sec)}~{mmss(g.end_sec)}</div>)}
          </div>
          <div className="call-note">
            <h4>메모 초안 <small className="muted">본문 칸에 채움 · 가린 곳 {result.mask_count}</small></h4>
            {result.note_error ? <p className="bad">! {result.note_error}</p> : <p>{result.note_en}</p>}
            {result.provided.length > 0 && (
              <ul className="call-provided">
                {result.provided.map((p) => (
                  <li key={`${p.field_code}-${p.value}`} className={p.found ? "" : "bad"}>
                    {p.label}={p.value} {p.found ? <span className="muted small">[{p.utterance_no}]</span> : <strong>({p.message})</strong>}
                  </li>
                ))}
              </ul>
            )}
            <button type="button" onClick={redraft} disabled={busy !== "" || result.utterances.length === 0}>
              {busy === "note" ? "만드는 중…" : "메모 다시 만들기"}
            </button>
          </div>
        </div>
      )}
    </fieldset>
  );
}

