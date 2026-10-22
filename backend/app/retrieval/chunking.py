"""문서를 절 단위 청크로 나눈다 (기술 명세서 v1.4 §4-2, 작업 W2).

- `##` 또는 `###` 머리글 하나 = 청크 하나. `##` 아래에 `###`가 있으면 `##` 청크에는 바로 아래 글만 넣는다.
- 청크 ID는 `{doc_id}§{절 번호}`. 절 번호는 글자로 보존한다("2.10").
- 문서 정보(--- … ---)와 `#` 제목 줄은 청크에 넣지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{2,3})\s+((?:Q[0-9]+|[0-9]+(?:\.[0-9]+)*))\.?\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    section_no: str
    section_title: str
    text: str

    def embed_text(self, doc_title: str) -> str:
        """임베딩 입력: 문서 제목과 절 제목을 앞에 붙인다(§4-2)."""
        return f"{doc_title} > {self.section_no} {self.section_title}\n{self.text}"


def strip_front_matter(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return markdown


def split_sections(doc_id: str, markdown: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: tuple[str, str] | None = None
    body: list[str] = []

    def close() -> None:
        if current is not None:
            no, title = current
            chunks.append(Chunk(f"{doc_id}§{no}", doc_id, no, title, "\n".join(body).strip()))

    for line in strip_front_matter(markdown).splitlines():
        m = _HEADING.match(line)
        if m:
            close()
            current, body = (m.group(2), m.group(3)), []
        elif line.startswith("#"):
            close()  # `#` 제목 줄 등 번호 없는 머리글: 앞 청크를 닫고 다음 머리글까지 버린다
            current, body = None, []
        elif current is not None:
            body.append(line)
    close()
    return chunks
