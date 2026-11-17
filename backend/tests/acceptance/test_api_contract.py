"""API 계약 시험 (변경 add-api-response-models, spec api-contract). DB 없이 돈다."""

import json
import sys
from pathlib import Path

from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "jobs"))
import export_openapi  # noqa: E402


def _success(op: dict) -> dict:
    code = next(c for c in op["responses"] if c.startswith("2"))
    return op["responses"][code].get("content", {}).get("application/json", {}).get("schema", {})


def test_ac_contract_1_every_api_has_named_response():
    """AC-contract-1: 모든 경로·메서드의 성공 응답이 이름 있는 스키마를 가리킨다."""
    spec = app.openapi()
    missing = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            schema = _success(op)
            ref = schema.get("$ref") or schema.get("items", {}).get("$ref")
            if not ref or ref.rsplit("/", 1)[-1] not in spec["components"]["schemas"]:
                missing.append(f"{method.upper()} {path}")
    assert missing == []
    # 27(add-api-response-models) + 고객 관리 3(add-customer-views: /customers, /customers/countries, /customers/{id})
    # + 기준정보 보기 4(add-reference-views: /ref/documents, /ref/documents/{doc_id}, /ref/products/{product_code}, /ref/rules/{kind})
    # + 해결사례 검색 2(add-case-search: /cases, /cases/{case_id})
    # + 상담원 도우미 1(add-agent-assistant: /assist/ask)
    # + 내부 메모 2(add-internal-notes: GET·POST /tickets/{id}/notes)
    # + 담당 변경 1(add-reassign: POST /sub-tickets/assign)
    # + 운영 대시보드 1(add-ops-overview: GET /dashboard/summary)
    # + 내 실적 1(add-my-performance: GET /me/performance)
    # + 자동 발송 3(add-auto-send: GET·PUT /auto-rules, POST /sub-tickets/{id}/auto-review)
    # + 이관 메일 연동 3(add-escalation-mail-live: GET /mail/config, POST /mail/poll, POST /mail/dept-reply-demo)
    assert sum(len(ops) for ops in spec["paths"].values()) == 49


def test_ac_contract_2_frontend_copy_is_current():
    """AC-contract-2: frontend/openapi.json이 서버가 지금 내는 계약과 같다. 다르면 jobs/export_openapi.py를 다시 돌린다."""
    saved = json.loads(export_openapi.OUT.read_text(encoding="utf-8"))
    assert saved == json.loads(export_openapi.render(export_openapi.contract()))


def test_extra_values_are_kept():
    """design 결정 2: 모델에 적지 않은 값도 응답에서 빠지지 않고, 적은 칸 중 없던 칸이 새로 생기지 않는다."""
    from fastapi.encoders import jsonable_encoder

    from app.api import schemas

    row = {"ticket_id": "CSV1-000001", "processing": True, "not_in_model": 1}
    model = schemas.Accepted.model_validate(row)
    assert jsonable_encoder(model, exclude_unset=True) == row
