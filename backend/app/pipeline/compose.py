"""T5 답변 메일 구성 (명세서 v1.5 FR-022, 기술 명세서 v1.4 §2-2 T5, 에이전트 설계서 v1.1 4-7절·부록 A-2).

복합 문의에서 답변 단락(L4 단락 모드)이 생긴 하위 문의마다 메일 한 통:
인사말(L5) → 단락 → 문의 상태 목록(S-1~S-6, 한 줄 = 하위 문의 하나) → 맺음말(L5).
상태 문구는 고정 문안만 쓴다. 예상 완료 시각·SLA 목표 시간은 넣지 않는다(FR-022 처리 3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.checks.draft_check import check_draft
from app.llm.client import Transport
from app.llm.drafts import CATEGORY_NAMES, CHECK_PROVIDED_FIELDS, FLAG_CHECK_FAILED, Draft, Source
from app.llm.wrap import write_wrap
from app.pipeline.state import SubTicketState

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "status_list"
FLAG_STATUS_LIST_MISSING = "상태 목록 누락"  # FR-022 예외 1행
# 상태 → 부록 A-2 문장 번호 (S-1 이 메일, S-6 처리 실패·초안 없음은 아래에서 따로)
STATUS_LINE = {"RESOLVED": "S-2", "CLOSED": "S-2", "WAITING_CUSTOMER": "S-4", "ESCALATED": "S-5",
               "NEW": "S-3", "IN_PROGRESS": "S-3"}


def template(language: str = "en") -> dict[str, str]:
    """영어 원문만 있다(부록 A-2, T40 전, C-92)."""
    return json.loads((TEMPLATE_DIR / "en.json").read_text(encoding="utf-8"))


def topic(category_code: str | None) -> str:
    """부록 A-2 {topic}: 유형의 고객용 이름(예 Quotation, Firmware update)."""
    name = CATEGORY_NAMES.get(category_code or "", "support")
    return name[:1].upper() + name[1:]


def status_lines(subs: list[SubTicketState], answered: str, statuses: dict[str, str],
                 checking: set[str]) -> list[str]:
    """하위 문의마다 한 줄(seq 순). checking = 처리 실패·초안 없음으로 "담당자 확인 중"(S-6)인 하위 문의."""
    t = template()
    lines = []
    for sub in sorted(subs, key=lambda s: s.seq):
        if sub.sub_ticket_id == answered:
            key = "S-1"
        elif sub.sub_ticket_id in checking:
            key = "S-6"
        else:
            key = STATUS_LINE.get(statuses.get(sub.sub_ticket_id, "NEW"), "S-3")
        lines.append(t[key].format(n=sub.seq, topic=topic(sub.category_code)))
    return lines


def mail_check(body: str, sources: list[Source], lookups: list[tuple], provided: list[tuple[str, str]],
               seqs: list[int]) -> dict[str, Any]:
    """메일 전체의 자체 대조(FR-022 처리 5). 허용 숫자에 상태 목록의 문의 번호를 더한다(에이전트 설계서 6-1 2번)."""
    allowed = ([s.text for s in sources] + [str(v) for _, v, _, _ in lookups]
               + [v for name, v in provided if name in CHECK_PROVIDED_FIELDS and v] + [str(n) for n in seqs])
    return check_draft(body, {(s.doc_id, s.section_no) for s in sources}, allowed).as_dict()


def compose_mail(transport: Transport, draft: Draft, sub: SubTicketState, subs: list[SubTicketState],
                 statuses: dict[str, str], checking: set[str], sources: list[Source]) -> Draft:
    """단락 초안(draft)을 메일로 감싼다. draft.body·check·compose·flags를 바꿔 돌려준다."""
    paragraph = draft.body
    greeting, closing, wrap = write_wrap(transport, draft.language, [topic(sub.category_code)])
    lines = status_lines(subs, sub.sub_ticket_id, statuses, checking)
    if len(lines) < len(subs):  # 누락 검사(FR-022 예외 1행): 한 번 다시 만든다
        lines = status_lines(subs, sub.sub_ticket_id, statuses, checking)
    ok = len(lines) >= len(subs)
    draft.body = "\n\n".join([greeting, paragraph, "\n".join([template()["head"], *lines]), closing])
    lookups = [(lv.item, lv.value, lv.unit, f"{lv.source_table}:{lv.source_key}") for lv in sub.lookups]
    provided = [(pf.field, pf.value_norm or pf.value_raw) for pf in sub.provided_fields]
    draft.check = mail_check(draft.body, sources, lookups, provided, [s.seq for s in subs])
    draft.flags = [f for f in draft.flags if f != FLAG_CHECK_FAILED]
    if not draft.check["passed"]:
        draft.flags.append(FLAG_CHECK_FAILED)
    if not ok:
        draft.flags.append(FLAG_STATUS_LIST_MISSING)
    draft.compose = {"seq": sub.seq, "status_lines": lines, "wrap": wrap, "status_list_ok": ok,
                     "paragraph_check": sub.draft_check}
    return draft
