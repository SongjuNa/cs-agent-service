"""발송 전 확인이 필요한 것 (화면 정의서 v2 P7). 상담원 [승인하고 발송]과 자동 발송(변경 add-auto-send)이 같은 검사를 쓴다.

이 검사를 통과하지 못하는 초안은 자동으로 보내지 않는다. 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from psycopg import Connection

from app.db.detail import verify_state
from app.db.store import check_body, intake_step
from app.llm.verify import KIND_NAMES


def send_issues(conn: Connection, draft: dict, final_body: str) -> tuple[list[dict], list[str]]:
    """확인을 받아야 하는 것(issues)과 줄로만 알리는 것(notes). 화면 정의서 v2 P7."""
    issues: list[dict] = []
    notes: list[str] = []
    check = check_body(conn, draft["message_type"], draft["sub_ticket_id"], final_body)
    bad = check["bad_citations"] + check["bad_numbers"]
    if bad:
        issues.append({"kind": "DRAFT_CHECK", "text": f"근거 밖 인용/숫자 {len(bad)}곳", "items": bad})
    if check.get("missing_labels"):
        issues.append({"kind": "DRAFT_CHECK", "text": f"요청할 항목이 본문에 없음: {', '.join(check['missing_labels'])}",
                       "items": check["missing_labels"]})
    if draft["message_type"] == "FINAL_REPLY":
        (blocking,) = conn.execute("SELECT missing_blocking_info FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                   (draft["sub_ticket_id"],)).fetchone()
        if blocking:
            labels = (intake_step(conn, draft["sub_ticket_id"], "Q5") or {}).get("labels", {})
            names = [labels.get(f, f) for f in blocking]
            issues.append({"kind": "BLOCKING", "text": f"막는 정보({', '.join(names)})가 아직 없습니다", "items": names})
    verify = conn.execute(
        """SELECT passed_yn, detail FROM eval.self_check WHERE message_id = %s AND check_type = 'VERIFY'
            ORDER BY checked_at_utc DESC, check_id DESC LIMIT 1""", (draft["message_id"],)).fetchone()
    state, text, findings = verify_state(None if verify is None else {"passed_yn": verify[0], "detail": verify[1]},
                                         draft["body"])
    if state == "FOUND":
        issues.append({"kind": "VERIFY", "text": f"⑤ 검증 에이전트 지적 {len(findings)}곳",
                       "items": [f"{KIND_NAMES.get(f['kind'], f['kind'])} — {f['quote']}" for f in findings]})
    elif state == "FAILED":
        notes.append("⑤ 검증 못 함 — 검증 없이 보냅니다")
    elif state == "STALE":
        notes.append("⑤ 고친 뒤 검증 안 함")
    return issues, notes
