"""旧 docs/works.md（手書きMarkdown）を data/works.yml に変換する一回限りのスクリプト。

    python tools/migrate_works_md.py [path/to/works.md]

フライヤーは元のURLのまま flyer に入る。ローカルに落とすのは tools/fetch_flyers.py。
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import works_lib as W  # noqa: E402

LINK = re.compile(r'^\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)$')
DATE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
IMG = re.compile(r'<img\s+src="([^"]+)"(?:\s+alt="([^"]*)")?')
SECTION_KIND = {"過去ライブ": "live", "過去VJ (クラブ)": "club"}


def text_and_url(v: str) -> tuple[str | None, str | None]:
    v = v.strip()
    if v in ("", "N/A"):
        return None, None
    m = LINK.match(v)
    return (m.group(1), m.group(2)) if m else (v, None)


def ticket_item(v: str) -> dict | None:
    v = v.strip()
    if v in ("", "N/A"):
        return None
    label = None
    if "｜" in v:
        label, v = (s.strip() for s in v.split("｜", 1))
    txt, url = text_and_url(v)
    url = url or (txt if txt and txt.startswith("http") else None)
    if not url:
        return {"label": label or txt}
    return {"label": label, "url": url} if label else {"url": url}


def parse(md: str) -> list[dict]:
    events, cur, kind, in_tickets = [], None, None, False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("<!--"):
            break
        if line.startswith("## "):
            kind = SECTION_KIND.get(line[3:].strip())
            continue
        if line.startswith("### "):
            title = line[4:].strip()
            cur = {"title": None if title == "N/A" else title, "kind": kind, "tickets": []}
            events.append(cur)
            in_tickets = False
            continue
        if cur is None:
            continue
        m = IMG.search(line)
        if m:
            cur["flyer"], cur["flyer_alt"] = m.group(1), m.group(2)
            continue
        if in_tickets and re.match(r"^\s{2,}- ", line):
            t = ticket_item(line.strip()[2:])
            if t:
                cur["tickets"].append(t)
            continue
        in_tickets = False
        m = re.match(r"^- (\w+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key == "date":
            ds = [dt.date(int(y), int(mo), int(d)) for y, mo, d in DATE.findall(val)]
            cur["date"] = ds[0]
            cur["end"] = ds[1] if len(ds) > 1 else None
        elif key == "at":
            cur["venue"], cur["venue_url"] = text_and_url(val)
        elif key == "by":
            cur["organizer"], cur["organizer_url"] = text_and_url(val)
        elif key == "ticket":
            if val.strip() == "":
                in_tickets = True
            else:
                t = ticket_item(val)
                if t:
                    cur["tickets"].append(t)
        elif key == "job":
            cur["role"] = val.strip()
    return events


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else W.ROOT / "docs" / "works.md"
    events = parse(src.read_text(encoding="utf-8"))
    W.save(events)
    print(f"{len(events)} events -> {W.DATA.relative_to(W.ROOT)}")


if __name__ == "__main__":
    main()
