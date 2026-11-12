"""works.yml の読み書きと共通処理。"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "works.yml"
IMG_DIR = ROOT / "docs" / "img" / "works"
IMG_URL = "/img/works"

# yml に書き出すキーの順序
KEYS = ["date", "end", "title", "kind", "venue", "venue_url", "organizer",
        "organizer_url", "tickets", "role", "flyer", "flyer_alt", "issue"]
KINDS = ("club", "live")


def to_date(v) -> dt.date | None:
    if v in (None, ""):
        return None
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v).strip())


def load() -> list[dict]:
    if not DATA.exists():
        return []
    events = yaml.safe_load(DATA.read_text(encoding="utf-8")) or []
    for e in events:
        e["date"] = to_date(e.get("date"))
        e["end"] = to_date(e.get("end"))
    return events


def clean(e: dict) -> dict:
    out = {}
    for k in KEYS:
        v = e.get(k)
        if v in (None, "", []):
            continue
        out[k] = v
    for k, v in e.items():  # 未知のキーも消さずに残す
        if k not in out and k not in KEYS and v not in (None, "", []):
            out[k] = v
    return out


def save(events: list[dict]) -> None:
    events = sorted(events, key=lambda e: (e["date"], e.get("title") or ""))
    DATA.parent.mkdir(parents=True, exist_ok=True)
    head = ("# works のイベント一覧（古い順）。\n"
            "# title が空のイベントは「告知前」として日付だけ表示されます。\n"
            "# 予定/過去の区別はビルド時に日付で自動判定されます。\n")
    body = yaml.safe_dump([clean(e) for e in events], allow_unicode=True,
                          sort_keys=False, default_flow_style=False, width=1000)
    DATA.write_text(head + body, encoding="utf-8")


def announced(e: dict) -> bool:
    return bool(e.get("title"))


def flyer_name(date: dt.date, ext: str, taken: set[str]) -> str:
    """docs/img/works/ 内で重複しないファイル名（例: 2026-10-04.jpg, 2026-10-04-2.jpg）。"""
    ext = ext.lower().lstrip(".")
    ext = "jpg" if ext == "jpeg" else ext
    base = date.isoformat()
    name, n = f"{base}.{ext}", 2
    existing = {p.name for p in IMG_DIR.glob(f"{base}*")} | taken
    while name in existing:
        name, n = f"{base}-{n}.{ext}", n + 1
    return name


def ext_from(content_type: str, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    table = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
    if ct in table:
        return table[ct]
    m = re.search(r"format=(\w+)", url) or re.search(r"\.(jpe?g|png|webp|gif)(?:$|\?)", url, re.I)
    return (m.group(1) if m else "jpg").lower()
