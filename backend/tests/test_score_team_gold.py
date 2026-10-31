"""채점 배치(jobs/score_team_gold.py)가 팀 정답지 v1 칸 모양을 바르게 읽는지 (DB·언어 모델 없이)."""

from jobs.score_team_gold import _ref, parts, spec_value, split_list


def test_compound_cell_split():
    assert parts("[1]  | [2] po_number") == ["", "po_number"]
    assert parts("product_model;serial_no") is None
    assert split_list("product_model;serial_no") == ["product_model", "serial_no"]


def test_reference_doc_and_section():
    assert _ref("TG-ACB-AS-2000 §3.2", None) == ("TG-ACB-AS-2000", "3.2")
    assert _ref("DS-ELCB-EBN-203c", "2.2") == ("DS-ELCB-EBN-203c", "2.2")
    assert _ref("(근거 없음)", None) == (None, None)


def test_spec_value():
    assert spec_value("37 kA (Ultimate breaking capacity Icu at AC 415 V, DS-ELCB-EBN-203c §2.2)") == "37 kA"
    assert spec_value("(정보 요청 대상: 숫자 없음)") is None
