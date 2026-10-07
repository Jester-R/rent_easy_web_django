"""Inject data-label attributes on <td> cells so tables stack into cards on phones.

Header labels are derived from the matching <th> cell; when a header renders a
single ``{% t 'key' %}`` expression the key is reused so the label stays
translated. Run from the project root:  python tools/label_table_cells.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

TABLE_RE = re.compile(r"<table class=\"data-table\".*?</table>", re.S)
TH_RE = re.compile(r"<th\b[^>]*>(.*?)</th>", re.S)
TD_RE = re.compile(r"<td\b", re.S)
ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
T_KEY_RE = re.compile(r"\{%\s*t\s+'([a-z0-9_]+)'\s*%\}")
TAG_RE = re.compile(r"<[^>]+>")


def label_for(header_html: str) -> str:
    """Return a data-label expression for one header cell."""
    keys = T_KEY_RE.findall(header_html)
    if len(keys) == 1:
        return "{% t '" + keys[0] + "' %}"
    text = TAG_RE.sub(" ", header_html)
    text = re.sub(r"\{%.*?%\}", " ", text)
    text = re.sub(r"\{\{.*?\}\}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def process(path: Path) -> int:
    source = path.read_text()
    changes = 0

    def fix_table(match: re.Match) -> str:
        nonlocal changes
        table = match.group(0)
        head = re.search(r"<thead\b.*?</thead>", table, re.S)
        if not head:
            return table
        labels = [label_for(cell) for cell in TH_RE.findall(head.group(0))]
        if not labels:
            return table

        def fix_row(row_match: re.Match) -> str:
            nonlocal changes
            row_html = row_match.group(1)
            cells = list(TD_RE.finditer(row_html))
            if not cells:
                return row_match.group(0)
            if any(
                row_html[cell.start() : cell.start() + 24].find("data-label") > -1
                for cell in cells
            ):
                return row_match.group(
                    0
                )  # already labelled — keep the script idempotent
            if len(cells) != len(labels):
                print(
                    f"  ! {path.name}: row has {len(cells)} cells, header has {len(labels)} — skipped"
                )
                return row_match.group(0)

            pieces, cursor = [], 0
            for index, cell in enumerate(cells):
                pieces.append(row_html[cursor : cell.end()])
                # first column is the bulk checkbox, last column holds the row actions
                label = "" if index in (0, len(labels) - 1) else labels[index]
                pieces.append(f' data-label="{label}"')
                cursor = cell.end()
                changes += 1
            pieces.append(row_html[cursor:])

            opening_end = row_match.group(0).index(">") + 1
            return row_match.group(0)[:opening_end] + "".join(pieces) + "</tr>"

        return ROW_RE.sub(fix_row, table)

    new_source = TABLE_RE.sub(fix_table, source)
    if new_source != source:
        path.write_text(new_source)
    return changes


def main() -> int:
    total = 0
    for path in sorted(TEMPLATES.rglob("*.html")):
        count = process(path)
        if count:
            print(f"{path.relative_to(ROOT)}: {count} cells labelled")
            total += count
    print(f"total {total} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
