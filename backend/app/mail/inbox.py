"""받은 메일함 읽기. 로컬에서는 Mailpit HTTP API를 쓴다(IMAP 대신, 서버 하나로 보내기·받기 확인).

- 아직 보지 않은 C/S 메일: GET /api/v1/search?query=to:<C/S 주소> -tag:cs-linked
- 한 통 읽기: GET /api/v1/message/{ID} (본문 Text)
- 본 메일 표시: PUT /api/v1/tags {"Tags": ["cs-linked"], "IDs": [...]}

"읽음" 상태는 쓰지 않는다. 사람이 메일함 화면에서 메일을 열기만 해도 읽음이 되어, 그 답장을 영영 놓치기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass
class InboundMail:
    id: str
    sender: str      # 보낸 사람 주소(소문자)
    to: list[str]    # 받는 사람 주소들(소문자)
    subject: str
    text: str


DONE_TAG = "cs-linked"


class Inbox(Protocol):
    def pending(self) -> list[InboundMail]: ...

    def mark_done(self, ids: list[str]) -> None: ...


def _addresses(items: list[dict] | None) -> list[str]:
    return [(i.get("Address") or "").lower() for i in (items or []) if i.get("Address")]


class MailpitInbox:
    def __init__(self, base_url: str, cs_address: str, timeout: float = 10.0, limit: int = 50,
                 transport: httpx.BaseTransport | None = None):
        self.base_url, self.cs_address, self.timeout, self.limit = base_url.rstrip("/"), cs_address, timeout, limit
        self.transport = transport  # 시험용(httpx.MockTransport)

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self.transport)

    def pending(self) -> list[InboundMail]:
        with self._client() as client:
            query = f"to:{self.cs_address} -tag:{DONE_TAG}"
            res = client.get("/api/v1/search", params={"query": query, "limit": self.limit})
            res.raise_for_status()
            out = []
            for summary in res.json().get("messages", []):
                full = client.get(f"/api/v1/message/{summary['ID']}")
                full.raise_for_status()
                data = full.json()
                out.append(InboundMail(id=summary["ID"], sender=(data.get("From") or {}).get("Address", "").lower(),
                                       to=_addresses(data.get("To")), subject=data.get("Subject") or "",
                                       text=data.get("Text") or ""))
            return out

    def mark_done(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._client() as client:
            client.put("/api/v1/tags", json={"Tags": [DONE_TAG], "IDs": ids}).raise_for_status()
