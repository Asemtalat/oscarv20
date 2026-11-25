from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_LEFT = 52
MARGIN_RIGHT = 52
MARGIN_TOP = 58
MARGIN_BOTTOM = 52
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT


@dataclass
class Block:
    kind: str
    text: str = ""


@dataclass
class Line:
    text: str
    font: str
    size: int
    indent: int = 0


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_text(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=width,
        replace_whitespace=False,
        drop_whitespace=True,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]


def parse_markdown(text: str) -> list[Block]:
    blocks: list[Block] = []
    in_code = False
    code_lines: list[str] = []

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                blocks.append(Block("code", "\n".join(code_lines)))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            blocks.append(Block("space"))
            continue

        if line.startswith("# "):
            blocks.append(Block("title", line[2:].strip()))
            continue
        if line.startswith("## "):
            blocks.append(Block("h1", line[3:].strip()))
            continue
        if line.startswith("### "):
            blocks.append(Block("h2", line[4:].strip()))
            continue
        if line.startswith("- "):
            blocks.append(Block("bullet", line[2:].strip()))
            continue

        blocks.append(Block("p", line.strip()))

    if code_lines:
        blocks.append(Block("code", "\n".join(code_lines)))
    return blocks


def blocks_to_lines(blocks: list[Block]) -> list[Line]:
    lines: list[Line] = []
    for block in blocks:
        if block.kind == "space":
            lines.append(Line("", "body", 10))
            continue

        if block.kind == "title":
            for item in wrap_text(block.text, 34):
                lines.append(Line(item, "bold", 22))
            lines.append(Line("", "body", 10))
            continue

        if block.kind == "h1":
            for item in wrap_text(block.text.upper(), 55):
                lines.append(Line(item, "bold", 15))
            lines.append(Line("", "body", 10))
            continue

        if block.kind == "h2":
            for item in wrap_text(block.text, 68):
                lines.append(Line(item, "bold", 12))
            continue

        if block.kind == "bullet":
            wrapped = wrap_text(block.text, 76)
            first = True
            for item in wrapped:
                prefix = "• " if first else "  "
                lines.append(Line(prefix + item, "body", 10, indent=12))
                first = False
            continue

        if block.kind == "code":
            code_lines = block.text.splitlines() or [""]
            lines.append(Line("", "body", 10))
            for item in code_lines:
                wrapped = wrap_text(item if item else " ", 72)
                for part in wrapped:
                    lines.append(Line(part, "mono", 9, indent=18))
            lines.append(Line("", "body", 10))
            continue

        wrapped = wrap_text(block.text, 88)
        for item in wrapped:
            lines.append(Line(item, "body", 10))
    return lines


def line_height(line: Line) -> int:
    if line.size >= 20:
        return 28
    if line.size >= 15:
        return 22
    if line.size >= 12:
        return 18
    return 14


def paginate(lines: list[Line]) -> list[list[Line]]:
    pages: list[list[Line]] = []
    current: list[Line] = []
    available = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM - 20
    used = 0

    for line in lines:
        needed = line_height(line)
        if used + needed > available and current:
            pages.append(current)
            current = []
            used = 0
        current.append(line)
        used += needed

    if current:
        pages.append(current)
    return pages or [[Line("Empty document", "body", 10)]]


def page_stream(lines: list[Line], page_no: int, page_count: int) -> bytes:
    commands = []
    y = PAGE_HEIGHT - MARGIN_TOP

    commands.extend(
        [
            "0.18 0.45 0.69 RG",
            f"{MARGIN_LEFT} {PAGE_HEIGHT - 40} m {PAGE_WIDTH - MARGIN_RIGHT} {PAGE_HEIGHT - 40} l S",
            "0.85 0.88 0.92 RG",
            f"{MARGIN_LEFT} {MARGIN_BOTTOM - 8} m {PAGE_WIDTH - MARGIN_RIGHT} {MARGIN_BOTTOM - 8} l S",
        ]
    )

    for line in lines:
        font_name = {"body": "F1", "bold": "F2", "mono": "F3"}[line.font]
        commands.extend(
            [
                "BT",
                f"/{font_name} {line.size} Tf",
                "0 0 0 rg",
                f"{MARGIN_LEFT + line.indent} {y} Td",
                f"({pdf_escape(line.text)}) Tj",
                "ET",
            ]
        )
        y -= line_height(line)

    footer = f"Page {page_no} of {page_count}"
    commands.extend(
        [
            "BT",
            "/F1 9 Tf",
            "0.35 0.35 0.35 rg",
            f"{PAGE_WIDTH - MARGIN_RIGHT - 60} {MARGIN_BOTTOM - 24} Td",
            f"({pdf_escape(footer)}) Tj",
            "ET",
        ]
    )
    return "\n".join(commands).encode("latin-1", errors="replace")


def write_pdf(pages: list[list[Line]], output_path: Path) -> None:
    objects: list[bytes] = []

    def add_object(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    helvetica = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    helvetica_bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    courier = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids: list[int] = []
    content_ids: list[int] = []

    for idx, page_lines in enumerate(pages, start=1):
        stream = page_stream(page_lines, idx, len(pages))
        content_id = add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        content_ids.append(content_id)
        page_ids.append(add_object(b""))

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(
        f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("latin-1")
    )

    for index, page_id in enumerate(page_ids):
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {helvetica} 0 R /F2 {helvetica_bold} 0 R /F3 {courier} 0 R >> >> "
            f"/Contents {content_ids[index]} 0 R >>"
        ).encode("latin-1")

    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode("latin-1"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )

    output_path.write_bytes(output)


def main() -> None:
    module_dir = Path(__file__).resolve().parents[1]
    source = module_dir / "POSTMAN_API_GUIDE.md"
    target = module_dir / "POSTMAN_API_GUIDE.pdf"
    blocks = parse_markdown(source.read_text(encoding="utf-8"))
    lines = blocks_to_lines(blocks)
    pages = paginate(lines)
    write_pdf(pages, target)
    print(target)


if __name__ == "__main__":
    main()
