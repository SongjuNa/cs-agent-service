"""서버 계약(OpenAPI)을 frontend/openapi.json으로 뽑는다 (변경 add-api-response-models, design 결정 4).

사용: cd backend && python ../jobs/export_openapi.py
서버나 DB를 켜지 않는다. 앱을 불러와 계약만 만든다. 그 뒤 frontend에서 npm run gen:api로 화면 타입을 만든다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"


def contract() -> dict:
    from app.main import app

    return app.openapi()


def render(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(contract()), encoding="utf-8")
    print(f"계약을 썼다: {OUT}", file=sys.stderr)
