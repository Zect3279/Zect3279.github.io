"""MkDocs hook: data/works.yml から works ページ（overrides/works.html）用のデータを作る。

- 予定/過去はビルド時点の日付（JST）で振り分ける。過ぎた告知前の予定は出さない。
- ローカルのフライヤーは Pillow があればサムネイル（webp）と縦横比・代表色を作る。
- データに不備があればビルドを止める。
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from mkdocs.exceptions import PluginError
from mkdocs.utils import get_relative_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import works_lib as W  # noqa: E402

try:
    from PIL import Image
except ImportError:  # Pillow が無くても動く（原寸画像をそのまま使う）
    Image = None

JST = dt.timezone(dt.timedelta(hours=9))
DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DOCS = W.ROOT / "docs"
THUMB_DIR = "img/works/thumbs"
THUMB_W = 640
TEXT_KEYS = ["title", "venue", "venue_url", "organizer", "organizer_url", "role"]
_thumb_jobs: list[tuple[Path, str]] = []


def validate(events: list[dict]) -> list[str]:
    errs = []
    for i, e in enumerate(events):
        where = f"works.yml #{i + 1} ({e.get('date')} {e.get('title') or '告知前'})"
        if not isinstance(e.get("date"), dt.date):
            errs.append(f"{where}: date がありません")
            continue
        if e.get("end") and e["end"] < e["date"]:
            errs.append(f"{where}: end が date より前です")
        if e.get("kind") not in (None, *W.KINDS):
            errs.append(f"{where}: kind は {'/'.join(W.KINDS)} のどれかにしてください")
        f = e.get("flyer")
        if f and not f.startswith("http") and not (DOCS / f.lstrip("/")).exists():
            errs.append(f"{where}: flyer のファイルが見つかりません: {f}")
        if any(not isinstance(t, dict) or not (t.get("url") or t.get("label")) for t in e.get("tickets") or []):
            errs.append(f"{where}: tickets の書式が不正です")
    return errs


def image_info(path: Path) -> tuple[str, str]:
    """縦横比 'w / h' と代表色 '#rrggbb'。"""
    if Image is None:
        return "", ""
    try:
        with Image.open(path) as im:
            w, h = im.size
            c = im.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
        return f"{w} / {h}", "#%02x%02x%02x" % c
    except Exception:  # noqa: BLE001
        return "", ""


def flyer(src: str, page_url: str) -> dict:
    """原寸 img・一覧用 thumb・縦横比 ar・代表色 color。"""
    if not src or src.startswith("http"):
        return {"img": src, "thumb": src, "ar": "", "color": ""}
    rel = src.lstrip("/")
    img = get_relative_url(rel, page_url)
    ar, color = image_info(DOCS / rel)
    thumb = img
    if Image is not None:
        out = f"{THUMB_DIR}/{Path(rel).stem}.webp"
        _thumb_jobs.append((DOCS / rel, out))
        thumb = get_relative_url(out, page_url)
    return {"img": img, "thumb": thumb, "ar": ar, "color": color}


def mmdd(d: dt.date) -> str:
    return f"{d.month:02d}.{d.day:02d}"


def item(e: dict, i: int, today: dt.date, page_url: str) -> dict:
    d, end = e["date"], e.get("end")
    rng = mmdd(d) + (f" – {mmdd(end)}" if end else "")
    status = "past" if (end or d) < today else ("upcoming" if W.announced(e) else "tba")
    return {
        "i": i, "y": str(d.year), "md": mmdd(d), "range": rng, "full": f"{d.year}.{rng}",
        "dow": DOW[d.weekday()], "status": status,
        **{k: e.get(k) or "" for k in TEXT_KEYS},
        "tickets": e.get("tickets") or [],
        "alt": e.get("flyer_alt") or f"{e.get('title') or ''} フライヤー",
        **flyer(e.get("flyer") or "", page_url),
    }


def event_jsonld(events: list[dict], site: str, page_url: str) -> str:
    """告知済みイベントを schema.org の MusicEvent として並べる（検索エンジン・LLM 向け）。"""
    def absu(u: str) -> str:
        return u if not u or u.startswith("http") else f"{site}/{u.lstrip('/')}"

    performer = {"@id": f"{site}/#person"}
    out = []
    for e in events:
        if not W.announced(e):
            continue
        ev = {
            "@type": "MusicEvent",
            "name": e["title"],
            "startDate": e["date"].isoformat(),
            "endDate": (e.get("end") or e["date"]).isoformat(),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "inLanguage": "ja",
            "url": f"{site}/{page_url}",
            "performer": performer,
            "description": f"{e['title']}（{e.get('venue') or '会場未定'}）に Zect が {e.get('role') or 'VJ'} として出演。",
        }
        if e.get("venue"):
            place = {"@type": "Place", "name": e["venue"], "address": {"@type": "PostalAddress", "addressCountry": "JP"}}
            if e.get("venue_url"):
                place["url"] = e["venue_url"]
            ev["location"] = place
        if e.get("organizer"):
            org = {"@type": "Organization", "name": e["organizer"]}
            if e.get("organizer_url"):
                org["url"] = e["organizer_url"]
            ev["organizer"] = org
        if e.get("flyer"):
            ev["image"] = absu(e["flyer"])
        offers = [{"@type": "Offer", "url": t["url"]} for t in e.get("tickets") or [] if t.get("url")]
        if offers:
            ev["offers"] = offers
        out.append(ev)
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Zect の VJ 出演一覧",
        "numberOfItems": len(out),
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": ev} for i, ev in enumerate(out)],
    }
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def on_page_context(context, page, config, nav):  # noqa: ARG001
    if page.file.src_uri != "works.md":
        return context
    events = W.load()
    if errs := validate(events):
        raise PluginError("works.yml にエラーがあります:\n  " + "\n  ".join(errs))
    today = dt.datetime.now(JST).date()
    _thumb_jobs.clear()
    shown = [e for e in sorted(events, key=lambda e: e["date"])
             if W.announced(e) or (e.get("end") or e["date"]) >= today]
    items = [item(e, i, today, page.url) for i, e in enumerate(shown)]

    # WALL：予定は近い順、過去は新しい順（年では区切らない）
    upcoming = [it for it in items if it["status"] != "past"]
    past = [it for it in reversed(items) if it["status"] == "past"]
    context["works"] = {
        "wall": [g for g in ({"upcoming": True, "tiles": upcoming},
                             {"upcoming": False, "tiles": past}) if g["tiles"]],
        "count": len(past),
        "json": json.dumps(items, ensure_ascii=False).replace("</", "<\\/"),
        "jsonld": event_jsonld(sorted(events, key=lambda e: e["date"], reverse=True),
                               config["site_url"].rstrip("/"), page.url),
    }
    return context


def write_llms_txt(site: Path) -> None:
    """docs/llms.txt の末尾に出演履歴を足す（LLM が出演情報を拾えるように）。"""
    path = site / "llms.txt"
    if not path.exists():
        return
    events = sorted((e for e in W.load() if W.announced(e)), key=lambda e: e["date"], reverse=True)
    today = dt.datetime.now(JST).date()
    lines = ["", "## VJ 出演履歴（新しい順）", ""]
    for e in events:
        d = e["date"].isoformat() + (f"〜{e['end'].isoformat()}" if e.get("end") else "")
        tag = "（予定）" if (e.get("end") or e["date"]) >= today else ""
        venue = f" @ {e['venue']}" if e.get("venue") else ""
        role = f" — {e['role']}" if e.get("role") else ""
        lines.append(f"- {d} {e['title']}{venue}{role}{tag}")
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def on_post_build(config):
    site = Path(config["site_dir"])
    write_llms_txt(site)
    if Image is None:
        return
    for src, rel in _thumb_jobs:
        out = site / rel
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.width > THUMB_W:
                    im = im.resize((THUMB_W, round(im.height * THUMB_W / im.width)), Image.LANCZOS)
                im.save(out, "WEBP", quality=80)
        except Exception as ex:  # noqa: BLE001
            print(f"works: サムネイル作成に失敗 {src}: {ex}")
