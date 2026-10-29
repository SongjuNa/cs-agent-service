"""팀 정답지 채점 배치 (기술 명세서 v1.4 §10, 명세서 v1.5 그룹 7 머리말 "채점 18개는 채점 배치로", D30).

채점 코드다. 정답(eval.gold_set의 정답 열, gold.ticket_gold의 정답 열)을 읽어 처리 결과와 비교한다(CLAUDE.md 규칙 6 예외).
처리 흐름(run_ticket)에는 eval.gold_set의 입력 열 6개만 넘긴다. 처리 흐름은 DB를 읽기만 하므로
서비스 DB(svc)에는 아무것도 쓰지 않고, 결과는 eval.eval_run·eval_case·eval_summary와 csv에만 남긴다(§10-1 2·4).
초안은 DRAFT로만 생기고 저장하지 않는다(규칙 3).

두 번 채점한다.
1. TEAM_GOLD: 팀 정답지 80건을 실제 처리 흐름(Gemini 호출)으로 돌려 AC 13개 항목을 비교한다.
   규칙 항목(우선순위·부서·SLA 목표)의 기대값은 정답지에 열이 없으므로(테이블 정의서 v1.3 6-1),
   정답 유형·긴급도·제공 항목·제품·고객을 같은 규칙 함수에 넣어 만든다.
2. ALL_4000: 규칙 항목을 운영진 데이터 4,000건 전체로 재현한다(§10-1 1 "규칙 항목과 SLA 계산식"). 언어 모델을 부르지 않는다.
   SLA 상태·경과는 jobs/replay_gold.py가 따로 채점한다.

정답지 파일은 저장소에 넣지 않는다(규칙 8 취지). eval.gold_set이 비어 있으면 --gold-csv로 넣는다.

실행: backend 폴더에서 PYTHONPATH=..:. python -m jobs.score_team_gold --gold-csv <gold_set_v1.csv> [--workers 4] [--only GS-001 …]
      규칙 재현만: python -m jobs.score_team_gold --rules-only
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection

from app.config import get_settings
from app.llm.client import default_transport
from app.llm.embed import default_embedder
from app.pipeline.graph import RunOutcome, run_ticket
from app.pipeline.state import SubTicketState
from app.rules.lookup import lookup_customer, lookup_product
from app.rules.priority import decide_priority
from app.rules.required_info import check_required_info
from app.rules.routing import assign_dept, decide_return_kind
from app.rules.sla import find_sla_target

INPUT_COLUMNS = ("channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")
GOLD_SET_COLUMNS = ("gold_set_id", "set_version", "source_ticket_id", *INPUT_COLUMNS, "category_code",
                    "secondary_category", "urgency_flag", "provided_info", "missing_blocking_info", "reference_doc_id",
                    "reference_section", "expected_numbers", "note", "created_by", "created_at_utc")
NO_NUMBER = "("          # expected_numbers가 "(…: 숫자 없음)" 꼴이면 숫자 정답이 없다
NO_EVIDENCE = "(근거 없음"

# 항목 → (AC, 기준). 기준 None = 참고(보고만). 기준은 명세서 v1.5 "제안 기준, 팀 정답지 첫 측정 후 확정"
ITEMS: dict[str, tuple[str, Decimal | None]] = {
    "body_language": ("AC-004-4", Decimal("0.95")),
    "category_code": ("AC-005-4", Decimal("0.95")),
    "category_set": ("AC-006-4", Decimal("0.85")),
    "urgency_flag": ("AC-007-4", Decimal("0.90")),
    "urgency_safety_recall": ("AC-007-4", Decimal("1")),
    "urgency_site_down_recall": ("AC-007-4", Decimal("0.97")),
    "provided_info": ("AC-008-5", Decimal("0.90")),
    "priority_rule_id": ("AC-011-4", Decimal("1")),
    "priority": ("AC-011-4", Decimal("1")),
    "priority_rule_id_all": ("AC-011-4", None),
    "routing_rule_id": ("AC-012-5", Decimal("1")),
    "assigned_dept": ("AC-012-5", Decimal("1")),
    "assigned_dept_all": ("AC-012-5", None),
    "missing_blocking_info": ("AC-013-4", Decimal("1")),
    "missing_blocking_info_all": ("AC-013-4", Decimal("0.90")),
    "sla_first_response_target_h": ("AC-014-3", Decimal("1")),
    "sla_resolution_target_h": ("AC-014-3", Decimal("1")),
    "sla_target_all": ("AC-014-3", None),
    "reference_doc_topk": ("AC-016-4", Decimal("0.85")),
    "reference_section_topk": ("AC-016-4", None),
    "reference_doc_top1": ("AC-016-4", None),
    "no_evidence_no_draft": ("AC-016-4", None),
    "spec_number_lookup": ("AC-017-4", Decimal("1")),
    "spec_number_in_draft": ("AC-017-4", None),
    "draft_number_citation_check": ("대표 지표 ②", Decimal("1")),
    "compound_status_lines": ("AC-022-5", Decimal("0.95")),
    "compound_citation_in_sub": ("AC-022-5", Decimal("1")),
    "all_core_items": ("기획서 10-2 전체 일치", None),
}
# 반품_사유_단어목록_v1_20261022.md 2장: 영어 반품 211건이 담고 있는 여섯 문장(시험 test_w10_1과 같은 목록).
# 운영진 본문에는 사유 문장 밖에도 "damaged" 같은 단어(포장 상태 칸)가 있어, 사유 문장만 단어 규칙에 넣는다.
# 서비스에서는 L2가 정리한 사유(return_reason)를 넣는다(§5-3).
RETURN_SENTENCES = (
    "The goods arrived with damaged packaging and a cracked housing",
    "The unit was dead on arrival and does not power up",
    "The units have a recurring quality problem",
    "We received a different model from what we ordered",
    "We ordered the wrong rating by mistake",
    "The project was cancelled and the units are unused",
)
RULE_ITEMS_4000 = ("priority_rule_id", "priority", "routing_rule_id", "assigned_dept",
                   "sla_first_response_target_h", "sla_resolution_target_h", "missing_blocking_info")


# ---------- 정답지 읽기 ----------

def split_list(value: str | None) -> list[str]:
    return [f.strip() for f in (value or "").split(";") if f.strip()]


def parts(value: str | None) -> list[str] | None:
    """복합 문의 칸 "[1] a | [2] b" → ["a", "b"]. 나뉘지 않은 칸이면 None."""
    text = (value or "").strip()
    if not text.startswith("[1]"):
        return None
    return [re.sub(r"^\[\d+\]\s*", "", p).strip() for p in text.split(" | ")]


def load_gold_set(conn: Connection, path: Path) -> int:
    """gold_set_v1.csv → eval.gold_set (테이블 정의서 v1.3 6-1: 20열 이름·순서 같음, 목록 열은 ;로 나눠 배열)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if tuple(rows[0].keys()) != GOLD_SET_COLUMNS:
        raise SystemExit(f"정답지 열이 eval.gold_set과 다르다: {list(rows[0].keys())}")
    with conn.transaction():
        for r in rows:
            values = [r[c] or None for c in GOLD_SET_COLUMNS]
            for name in ("provided_info", "missing_blocking_info"):  # "[1] … | [2] …"는 글 하나 그대로 둔다
                i = GOLD_SET_COLUMNS.index(name)
                values[i] = [r[name]] if r[name].startswith("[1]") else split_list(r[name])
            conn.execute(
                f"""INSERT INTO eval.gold_set ({", ".join(GOLD_SET_COLUMNS)})
                    VALUES ({", ".join(["%s"] * len(GOLD_SET_COLUMNS))}) ON CONFLICT (gold_set_id) DO NOTHING""",
                values)
    return len(rows)


@dataclass
class GoldSub:
    """정답의 하위 문의 1개. 복합 문의는 [1]=category_code, [2..]=secondary_category 순서."""

    seq: int
    category: str
    provided: list[str]
    blocking: list[str]
    doc_id: str | None
    section: str | None
    numbers: str
    provided_ticket_level: bool = False  # 복합 문의인데 정답 provided_info가 나뉘지 않은 칸(티켓 단위로 비교)


@dataclass
class GoldRow:
    gold_set_id: str
    source_ticket_id: str | None
    inputs: dict[str, Any]
    urgency: str
    note: str
    subs: list[GoldSub]
    language_expected: str
    product_code_expected: str | None
    operator: dict[str, Any] = field(default_factory=dict)  # A 60행의 운영진 정답(반품 구분 등)

    @property
    def compound(self) -> bool:
        return len(self.subs) > 1


def _ref(text: str, section_col: str | None) -> tuple[str | None, str | None]:
    """"TG-ACB-AS-2000 §3.2" → (문서, 절). 절 칸이 따로 있으면 그것을 쓴다."""
    text = text.strip()
    if not text or text.startswith(NO_EVIDENCE):
        return None, None
    doc, _, sec = text.partition(" §")
    return doc.strip(), (sec.strip() or section_col or None)


def read_gold_set(conn: Connection, only: list[str] | None = None) -> list[GoldRow]:
    rows = conn.execute(
        f"SELECT {', '.join(GOLD_SET_COLUMNS[:18])} FROM eval.gold_set ORDER BY gold_set_id").fetchall()
    operator = {r[0]: {"body_language": r[1], "routing_rule_id": r[2]} for r in conn.execute(
        "SELECT ticket_id, body_language, routing_rule_id FROM gold.ticket_gold").fetchall()}
    out = []
    for r in rows:
        d = dict(zip(GOLD_SET_COLUMNS[:18], r))
        note = d["note"] or ""
        if only and d["gold_set_id"] not in only:
            continue
        cats = [d["category_code"], *split_list(d["secondary_category"])]
        n = len(cats)

        def per_sub(value: list[str] | str | None, n=n) -> list[list[str]]:
            raw = value[0] if isinstance(value, list) and len(value) == 1 and value[0].startswith("[1]") else None
            p = parts(raw)
            if p is not None:
                return [split_list(x) for x in p] + [[] for _ in range(n - len(p))]
            items = list(value or [])
            return [items] * n  # 나뉘지 않은 칸: 하위 문의 모두에 같은 목록(티켓 단위 정답)

        provided, blocking = per_sub(d["provided_info"]), per_sub(d["missing_blocking_info"])
        docs = parts(d["reference_doc_id"]) or [d["reference_doc_id"] or ""] * n
        nums = parts(d["expected_numbers"]) or [d["expected_numbers"] or ""] * n
        subs = []
        for i, cat in enumerate(cats):
            doc, sec = _ref(docs[i] if i < len(docs) else "", d["reference_section"])
            subs.append(GoldSub(i + 1, cat, provided[i], blocking[i], doc, sec, nums[i] if i < len(nums) else "",
                                n > 1 and parts((d["provided_info"] or [""])[0]) is None))
        m = re.search(r"정답 제품:\s*([A-Za-z0-9\-]+)", note)
        op = operator.get(d["source_ticket_id"] or "", {})
        out.append(GoldRow(
            d["gold_set_id"], d["source_ticket_id"], {k: d[k] for k in INPUT_COLUMNS}, d["urgency_flag"], note, subs,
            # 본문 언어 정답 열이 정답지에 없다: A행은 운영진 body_language, B행은 팀이 쓴 language
            op.get("body_language") or d["language"], d["product_code"] or (m.group(1) if m else None), op))
    return out


# ---------- 기대값 (정답 라벨 → 같은 규칙 함수) ----------

def expected_return_kind(g: GoldRow) -> str | None:
    """반품 구분 정답. 정답지에 열이 없어 비고(note)와 운영진 배정 규칙에서 읽는다(D13)."""
    if "UNKNOWN" in g.note:
        return "UNKNOWN"
    if "비불량" in g.note:
        return "NON_DEFECT"
    if g.operator.get("routing_rule_id") == "RT-ALL-RETURN-NON_DEFECT":
        return "NON_DEFECT"
    return "DEFECT"


def expected_rules(conn: Connection, g: GoldRow, sub: GoldSub) -> dict[str, Any]:
    family = lookup_product(conn, g.product_code_expected).product_family
    tier = lookup_customer(conn, g.inputs["customer_id"]).customer_tier
    pr = decide_priority(conn, sub.category, g.urgency)
    kind = expected_return_kind(g) if sub.category == "RETURN" else None
    rt = assign_dept(conn, family, sub.category, kind)
    sla = find_sla_target(conn, sub.category, tier, pr.priority)
    return {"priority_rule_id": pr.priority_rule_id, "priority": pr.priority, "return_kind": kind,
            "routing_rule_id": rt.routing_rule_id, "assigned_dept": rt.assigned_dept,
            "sla_first_response_target_h": sla.sla_first_response_target_h,
            "sla_resolution_target_h": sla.sla_resolution_target_h}


# ---------- 비교 ----------

def _norm(text: Any) -> str:
    return re.sub(r"[\s,]", "", str(text)).lower()


def spec_value(numbers: str) -> str | None:
    """"37 kA (Ultimate …, DS-… §2.2)" → "37 kA". 숫자 정답이 없으면 None."""
    text = numbers.strip()
    if not text or text.startswith(NO_NUMBER):
        return None
    return re.sub(r"\s*\(.*$", "", text).strip() or None


def pair_subs(g: GoldRow, actual: list[SubTicketState]) -> list[tuple[GoldSub, SubTicketState | None]]:
    """정답 하위 문의 ↔ 처리 결과 하위 문의. 같은 유형을 먼저 짝짓고, 남은 것은 순번으로."""
    left = sorted(actual, key=lambda s: s.seq)
    pairs = []
    for gs in g.subs:
        hit = next((s for s in left if s.category_code == gs.category), None)
        pairs.append((gs, hit))
        if hit:
            left.remove(hit)
    return [(gs, s if s is not None else (left.pop(0) if left else None)) for gs, s in pairs]


def score_row(conn: Connection, g: GoldRow, out: RunOutcome) -> list[dict]:
    cases: list[dict] = []

    def add(item, exp, act, match, sub_id=None, reason=None):
        cases.append({"gold_set_id": g.gold_set_id, "sub_ticket_id": sub_id, "item": item,
                      "expected_value": None if exp is None else str(exp),
                      "actual_value": None if act is None else str(act),
                      "match_yn": match, "excluded_reason": reason})

    state = out.state
    if state is None or out.run_status != "SUCCESS":
        for item in ("body_language", "category_code", "urgency_flag", "provided_info", "priority_rule_id"):
            add(item, None, None, False, reason=None)
        cases[-1]["actual_value"] = f"처리 실패 {out.error_type}: {out.message}"
        return cases

    actual = sorted(state.sub_tickets, key=lambda s: s.seq)
    add("body_language", g.language_expected, state.body_language, state.body_language == g.language_expected)
    exp_cats = sorted(s.category for s in g.subs)
    act_cats = sorted(s.category_code or "" for s in actual)
    if g.compound:
        add("category_set", exp_cats, act_cats, exp_cats == act_cats)
    else:
        add("category_code", g.subs[0].category, act_cats, act_cats == exp_cats)

    # 긴급도: 정답은 티켓 하나에 한 값. 정답 첫 유형과 짝지은 하위 문의의 값과 비교, 놓침은 티켓의 어느 하위 문의든
    pairs = pair_subs(g, actual)
    first = pairs[0][1]
    act_urg = first.urgency_flag if first else None
    if pairs[0][1] is not None and pairs[0][1].category_code == g.subs[0].category:
        add("urgency_flag", g.urgency, act_urg, act_urg == g.urgency, first.sub_ticket_id)
    else:
        add("urgency_flag", g.urgency, act_urg, None, reason="유형이 틀려 긴급도 비교 제외(§10-2 정답 유형과 같은 하위 문의)")
    any_urg = {s.urgency_flag for s in actual}
    if g.urgency == "SAFETY":
        add("urgency_safety_recall", "SAFETY", sorted(any_urg), "SAFETY" in any_urg)
    if g.urgency == "SITE_DOWN":
        add("urgency_site_down_recall", "SITE_DOWN", sorted(any_urg), "SITE_DOWN" in any_urg)

    drafts = {d.sub_ticket_id: d for d in out.drafts if d.message_type == "FINAL_REPLY"}
    all_ok = True
    for gs, s in pairs:
        sid = s.sub_ticket_id if s else None
        if s is None:
            add("provided_info", gs.provided, None, False, reason=None)
            all_ok = False
            continue
        cat_ok = s.category_code == gs.category
        if gs.provided_ticket_level:  # 정답이 티켓 단위: 하위 문의들이 뽑은 항목의 합집합과 한 번만 비교
            prov = sorted({pf.field for a in actual for pf in a.provided_fields})
            prov_ok = prov == sorted(set(gs.provided))
            if gs.seq == 1:
                add("provided_info", sorted(set(gs.provided)), prov, prov_ok, None)
        else:
            prov = sorted({pf.field for pf in s.provided_fields})
            prov_ok = prov == sorted(set(gs.provided))
            add("provided_info", sorted(set(gs.provided)), prov, prov_ok, sid)

        exp = expected_rules(conn, g, gs)
        urg_ok = s.urgency_flag == g.urgency
        rule_ok = cat_ok and urg_ok
        why = None if rule_ok else "유형 또는 긴급도가 틀림(규칙 입력이 다름)"
        add("priority_rule_id", exp["priority_rule_id"], s.priority_rule_id,
            s.priority_rule_id == exp["priority_rule_id"] if rule_ok else None, sid, why)
        add("priority", exp["priority"], s.priority_final, s.priority_final == exp["priority"] if rule_ok else None, sid, why)
        add("priority_rule_id_all", exp["priority_rule_id"], s.priority_rule_id, s.priority_rule_id == exp["priority_rule_id"], sid)

        kind_ok = gs.category != "RETURN" or s.return_kind == exp["return_kind"]
        prod_ok = s.product_family == lookup_product(conn, g.product_code_expected).product_family
        route_ok = cat_ok and kind_ok and prod_ok
        why = None if route_ok else ("유형이 틀림" if not cat_ok else "반품 구분이 틀림(D13 따로 집계)" if not kind_ok else "제품군이 틀림")
        add("routing_rule_id", exp["routing_rule_id"], s.routing_rule_id,
            s.routing_rule_id == exp["routing_rule_id"] if route_ok else None, sid, why)
        add("assigned_dept", exp["assigned_dept"], s.assigned_dept,
            s.assigned_dept == exp["assigned_dept"] if route_ok else None, sid, why)
        add("assigned_dept_all", exp["assigned_dept"], s.assigned_dept, s.assigned_dept == exp["assigned_dept"], sid)

        blk = sorted(s.missing_blocking_info)
        blk_exp = sorted(set(gs.blocking))
        add("missing_blocking_info", blk_exp, blk, blk == blk_exp if prov_ok and cat_ok else None, sid,
            None if prov_ok and cat_ok else "제공 항목 또는 유형이 틀림")
        add("missing_blocking_info_all", blk_exp, blk, blk == blk_exp, sid)

        sla_ok = rule_ok and s.priority_final == exp["priority"]
        why = None if sla_ok else "유형·긴급도·우선순위가 틀림(조회 키가 다름)"
        for item, a in (("sla_first_response_target_h", s.fr_target_h), ("sla_resolution_target_h", s.res_target_h)):
            add(item, exp[item], a, a == exp[item] if sla_ok else None, sid, why)
        add("sla_target_all", (exp["sla_first_response_target_h"], exp["sla_resolution_target_h"]),
            (s.fr_target_h, s.res_target_h),
            (s.fr_target_h, s.res_target_h) == (exp["sla_first_response_target_h"], exp["sla_resolution_target_h"]), sid)

        # 근거 문서(AC-016-4): 막는 정보가 있어 검색하지 않은 하위 문의는 제외
        cands = [(c.doc_id, c.section_no) for c in s.doc_candidates]
        searched = not s.missing_blocking_info or s.dept_reply
        if gs.doc_id:
            reason = None if searched else "정보 요청으로 가서 근거 검색 안 함"
            add("reference_doc_topk", gs.doc_id, [c[0] for c in cands],
                gs.doc_id in {c[0] for c in cands} if searched else None, sid, reason)
            add("reference_doc_top1", gs.doc_id, cands[0][0] if cands else None,
                bool(cands) and cands[0][0] == gs.doc_id if searched else None, sid, reason)
            if gs.section:
                add("reference_section_topk", f"{gs.doc_id} §{gs.section}", cands,
                    (gs.doc_id, gs.section) in set(cands) if searched else None, sid, reason)
        elif NO_EVIDENCE in (gs.numbers or ""):
            add("no_evidence_no_draft", "초안 없음", "초안 있음" if sid in drafts else "초안 없음", sid not in drafts, sid)

        # 숫자 조회(AC-017-4): TECH_SPEC 하위 문의의 사양 숫자가 조회값 안에 있는가
        value = spec_value(gs.numbers)
        if gs.category == "TECH_SPEC" and value:
            looked = [lv.value for lv in s.lookups]
            hit = any(_norm(value) == _norm(v) or _norm(value) in _norm(v) for v in looked)
            add("spec_number_lookup", value, looked, hit if searched else None, sid,
                None if searched else "정보 요청으로 가서 조회 안 함")
            draft = drafts.get(sid)
            nums = re.findall(r"\d+(?:[.,]\d+)?", value)
            add("spec_number_in_draft", value, None if draft is None else "초안 있음",
                draft is not None and all(n.replace(",", "") in draft.body.replace(",", "") for n in nums), sid)

        all_ok = all_ok and cat_ok and urg_ok and s.priority_final == exp["priority"] \
            and s.assigned_dept == exp["assigned_dept"] and blk == blk_exp

    for d in out.drafts:  # 대표 지표 ②: 초안 숫자·인용 대조(D14, FR-021 자체 대조)
        if d.check is not None:
            add("draft_number_citation_check", True, d.check.get("passed"), bool(d.check.get("passed")), d.sub_ticket_id)

    if g.compound:  # AC-022-5
        cand = {s.sub_ticket_id: {c.doc_id for c in s.doc_candidates} for s in actual}
        for sid, d in drafts.items():
            lines = (d.compose or {}).get("status_lines", [])
            add("compound_status_lines", len(actual), len(lines), len(lines) >= len(actual), sid)
            cited = {c.get("doc_id") for c in d.citations if c.get("doc_id")}
            add("compound_citation_in_sub", sorted(cand.get(sid, set())), sorted(cited), cited <= cand.get(sid, set()), sid)

    add("all_core_items", True, all_ok, all_ok and len(actual) == len(g.subs))
    return cases


# ---------- 실행 ----------

def run_team_gold(rows: list[GoldRow], workers: int) -> list[dict]:
    settings = get_settings()

    def one(g: GoldRow) -> list[dict]:
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            ticket_input = {"ticket_id": g.gold_set_id, **g.inputs}  # 입력 열 6개만(§10-1 1)
            try:
                with conn.transaction():
                    out = run_ticket(conn, default_transport(), default_embedder(), ticket_input)
            except Exception as exc:  # noqa: BLE001 — 한 건의 실패는 그 건의 결과로 남긴다
                out = RunOutcome(None, "FAILED", error_type=type(exc).__name__, message=str(exc)[:300])
            cases = score_row(conn, g, out)
        print(f"{g.gold_set_id}: {out.run_status} 하위 {len(out.state.sub_tickets) if out.state else 0}개", flush=True)
        return cases

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [c for cs in pool.map(one, rows) for c in cs]


def run_rules_4000(conn: Connection) -> list[dict]:
    """규칙 항목 4,000건 재현(§10-1 1). 정답 유형·긴급도·제공 항목 → 규칙 함수 → 운영진 정답과 비교."""
    rows = conn.execute(
        """SELECT ticket_id, customer_id, product_family, category_code, urgency_flag, provided_info, priority,
                  priority_rule_id, priority_adjusted_by_agent, routing_rule_id, assigned_dept,
                  sla_first_response_target_h, sla_resolution_target_h, missing_blocking_info, inquiry_body, body_language
             FROM gold.ticket_gold ORDER BY ticket_id""").fetchall()
    tiers = dict(conn.execute("SELECT customer_id, tier FROM ref.customer").fetchall())
    cases = []
    for (tid, cust, family, cat, urg, provided, priority, rule_id, adjusted, rt_id, dept, fr_h, res_h,
         blocking, body, body_lang) in rows:
        pr = decide_priority(conn, cat, urg)
        kind, kind_note = None, None
        if cat == "RETURN":  # 반품 구분: 영어는 단어 규칙(W10), 그 밖은 정답 배정 규칙에서(언어 모델 단계라 여기선 재현 불가)
            found = [x for x in RETURN_SENTENCES if x in body]
            if body_lang == "en" and len(found) == 1:
                kind = decide_return_kind(found[0]).return_kind
            else:
                kind, kind_note = ("NON_DEFECT" if rt_id == "RT-ALL-RETURN-NON_DEFECT" else "DEFECT"), "반품 구분은 정답 사용(비영어)"
        rt = assign_dept(conn, family, cat, kind)
        sla = find_sla_target(conn, cat, tiers[cust], priority)  # 조정 건은 정답(조정값) 우선순위로(AC-028-3)
        info = check_required_info(conn, family, cat, split_list(provided))
        actual = {"priority_rule_id": pr.priority_rule_id, "priority": pr.priority, "routing_rule_id": rt.routing_rule_id,
                  "assigned_dept": rt.assigned_dept, "sla_first_response_target_h": sla.sla_first_response_target_h,
                  "sla_resolution_target_h": sla.sla_resolution_target_h,
                  "missing_blocking_info": info.missing_blocking_info}
        expected = {"priority_rule_id": rule_id, "priority": priority, "routing_rule_id": rt_id, "assigned_dept": dept,
                    "sla_first_response_target_h": int(fr_h), "sla_resolution_target_h": int(res_h),
                    "missing_blocking_info": split_list(blocking)}
        for item in RULE_ITEMS_4000:
            reason = kind_note if item in ("routing_rule_id", "assigned_dept") else None
            if item == "priority" and adjusted == "Y":
                cases.append({"source_ticket_id": tid, "item": item, "expected_value": expected[item],
                              "actual_value": actual[item], "match_yn": None,
                              "excluded_reason": "상담원 조정 건(priority_adjusted_by_agent = Y)"})
                continue
            cases.append({"source_ticket_id": tid, "item": item, "expected_value": str(expected[item]),
                          "actual_value": str(actual[item]), "match_yn": expected[item] == actual[item],
                          "excluded_reason": reason})
    return cases


def summarize(cases: list[dict], items: list[str]) -> dict[str, dict]:
    out = {}
    for item in items:
        cs = [c for c in cases if c["item"] == item]
        if not cs:
            continue
        scored = [c for c in cs if c["match_yn"] is not None]
        matched = sum(bool(c["match_yn"]) for c in scored)
        out[item] = {"n": len(cs), "excluded_n": len(cs) - len(scored), "matched": matched,
                     "accuracy": (Decimal(matched) / len(scored)).quantize(Decimal("0.0001")) if scored else None}
    return out


def record(conn: Connection, source: str, cases: list[dict], ticket_count: int, note: str,
           thresholds: dict[str, Decimal | None], out_dir: Path, set_version: str | None) -> tuple[int, Path]:
    settings = get_settings()
    summary = summarize(cases, list(thresholds))
    with conn.transaction():
        (run_id,) = conn.execute(
            """INSERT INTO eval.eval_run (input_source, set_version, ticket_count, llm_model, note)
               VALUES (%s, %s, %s, %s, %s) RETURNING eval_run_id""",
            (source, set_version, ticket_count, settings.llm_model_small if source == "TEAM_GOLD" else None, note),
        ).fetchone()
        with conn.cursor().copy(
            """COPY eval.eval_case (eval_run_id, gold_set_id, source_ticket_id, sub_ticket_id, item, expected_value,
                   actual_value, match_yn, excluded_reason) FROM STDIN""") as copy:
            for c in cases:
                copy.write_row((run_id, c.get("gold_set_id"), c.get("source_ticket_id"), c.get("sub_ticket_id"),
                                c["item"], c["expected_value"], c["actual_value"], c["match_yn"], c["excluded_reason"]))
        for item, s in summary.items():
            t = thresholds[item]
            conn.execute(
                """INSERT INTO eval.eval_summary (eval_run_id, item, n, excluded_n, matched, accuracy, threshold, passed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (run_id, item, s["n"], s["excluded_n"], s["matched"], s["accuracy"], t,
                 None if t is None or s["accuracy"] is None else s["accuracy"] >= t))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"scoring_{set_version or source}_{date.today():%Y%m%d}.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        names = ["gold_set_id", "source_ticket_id", "sub_ticket_id", "item", "expected_value", "actual_value",
                 "match_yn", "excluded_reason"]
        writer = csv.DictWriter(f, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cases)
    return run_id, path


def print_summary(title: str, cases: list[dict], thresholds: dict[str, Any], labels: dict[str, str]) -> None:
    print(f"\n== {title} ==")
    for item, s in summarize(cases, list(thresholds)).items():
        acc = "-" if s["accuracy"] is None else f"{s['accuracy'] * 100:.1f}%"
        t = thresholds[item]
        print(f"{labels.get(item, ''):<12} {item:<30} {s['matched']}/{s['n'] - s['excluded_n']} = {acc}"
              f"  (제외 {s['excluded_n']}, 기준 {'참고' if t is None else f'{t * 100:.0f}%'})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="팀 정답지 채점 배치(기술 명세서 §10)")
    parser.add_argument("--gold-csv", type=Path, help="eval.gold_set이 비어 있으면 넣을 gold_set_v1.csv")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", nargs="*", help="이 gold_set_id만(시험 실행용)")
    parser.add_argument("--rules-only", action="store_true", help="4,000건 규칙 재현만")
    parser.add_argument("--out", type=Path, default=Path("scoring"))
    args = parser.parse_args(argv)

    settings = get_settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        cases4000 = run_rules_4000(conn)
        th4000 = {i: Decimal(1) for i in RULE_ITEMS_4000}
        run4000, path4000 = record(conn, "ALL_4000", cases4000, 4000, "규칙 항목 4,000건 재현(§10-1 1), 언어 모델 없음",
                                   th4000, args.out, None)
        print_summary(f"ALL_4000 규칙 재현 (eval_run {run4000}, {path4000})", cases4000, th4000, {})
        if args.rules_only:
            return 0

        (count,) = conn.execute("SELECT count(*) FROM eval.gold_set").fetchone()
        if count == 0:
            if not args.gold_csv:
                print("eval.gold_set이 비어 있다. --gold-csv로 정답지 파일을 넣는다", file=sys.stderr)
                return 1
            print(f"eval.gold_set에 {load_gold_set(conn, args.gold_csv)}행을 넣었다")
        rows = read_gold_set(conn, args.only)
        (version,) = conn.execute("SELECT max(set_version) FROM eval.gold_set").fetchone()

    cases = run_team_gold(rows, args.workers)
    thresholds = {k: v[1] for k, v in ITEMS.items()}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        run_id, path = record(conn, "TEAM_GOLD", cases, len(rows),
                              "팀 정답지 채점(§10-1 1 LLM 항목 + 규칙 항목은 정답 라벨로 만든 기대값)",
                              thresholds, args.out, version)
    print_summary(f"TEAM_GOLD {version} {len(rows)}건 (eval_run {run_id}, {path})", cases, thresholds,
                  {k: v[0] for k, v in ITEMS.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
