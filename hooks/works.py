"""MkDocs hook: data/works.yml から works ページ（overrides/works.html）用のデータを作る。

- 予定/過去はビルド時点の日付（JST）で振り分ける。過ぎた告知前の予定は出さない。
- ローカルのフライヤーは Pillow があればサムネイル（webp）と縦横比・代表色を作る。
- データに不備があればビルドを止める。
- イベント・シリーズごとのページと、works.json / works.ics / feed.xml / llms*.txt を作る（tools/works_publish.py）。
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
import works_publish as P  # noqa: E402
from mkdocs.structure.files import File  # noqa: E402

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
_pub: dict = {}  # on_files で作った公開用データ（evs: イベント, series: シリーズ, by_slug）


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
    slug = _pub.get("slug_of", {}).get((e["date"], e.get("title") or ""))
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
        "page": get_relative_url(f"works/{slug}/", page_url) if slug else "",
    }


def index_groups(evs: list[dict], page_url: str) -> dict:
    """works ページ下部のテキスト索引（年ごと・新しい順）。クローラーと AI が全イベントへたどれるように。"""
    years: dict[int, list[dict]] = {}
    for e in reversed(evs):
        years.setdefault(e["date"].year, []).append({
            "title": e["title"], "md": mmdd(e["date"]), "venue": e.get("venue") or "",
            "url": get_relative_url(f"works/{e['_slug']}/", page_url), "upcoming": e["_status"] == "upcoming"})
    series = sorted(((m[0]["_series"], get_relative_url(f"works/series/{s}/", page_url), len(m))
                     for s, m in _pub["series"].items()), key=lambda x: -x[2])
    return {"years": [{"year": y, "items": it} for y, it in years.items()], "series": series}


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def on_files(files, config):
    """イベント・シリーズのページを生成してサイトに足す。"""
    events = W.load()
    if errs := validate(events):
        raise PluginError("works.yml にエラーがあります:\n  " + "\n  ".join(errs))
    evs = P.prepare(events, now_jst().date())
    groups = P.series_groups(evs)
    _pub.update(evs=evs, series=groups, by_slug={e["_slug"]: e for e in evs},
                slug_of={(e["date"], e["title"]): e["_slug"] for e in evs})
    for i, e in enumerate(evs):
        size = None
        if (f := e.get("flyer")) and not f.startswith("http") and Image is not None:
            try:
                with Image.open(DOCS / f.lstrip("/")) as im:
                    size = im.size
            except Exception:  # noqa: BLE001
                pass
        content = P.event_page(e, evs[i - 1] if i else None, evs[i + 1] if i + 1 < len(evs) else None,
                               groups.get(e.get("_series_slug"), []), size)
        files.append(File.generated(config, f"works/{e['_slug']}.md", content=content))
    for slug, members in groups.items():
        files.append(File.generated(config, f"works/series/{slug}.md", content=P.series_page(slug, members)))
    return files


def on_page_context(context, page, config, nav):  # noqa: ARG001
    site = config["site_url"].rstrip("/")
    if slug := page.meta.get("event_slug"):
        context["page_jsonld"] = P.event_page_ld(_pub["by_slug"][slug], site)
        return context
    if slug := page.meta.get("series_slug"):
        context["page_jsonld"] = P.series_page_ld(slug, _pub["series"][slug], site)
        return context
    if page.file.src_uri != "works.md":
        return context
    events = W.load()
    today = now_jst().date()
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
        "jsonld": P.works_list_ld(_pub["evs"], site),
        "index": index_groups(_pub["evs"], page.url),
    }
    return context


def on_post_build(config):
    site = Path(config["site_dir"])
    url = config["site_url"].rstrip("/")
    evs, now = _pub["evs"], now_jst()
    (site / "works.json").write_text(P.works_json(evs, url, now), encoding="utf-8")
    (site / "works.ics").write_text(P.works_ics(evs, url, now), encoding="utf-8", newline="")
    (site / "works" / "feed.xml").write_text(P.works_feed(evs, url, now), encoding="utf-8")
    llms = site / "llms.txt"
    if llms.exists():
        head = llms.read_text(encoding="utf-8")
        llms.write_text(head.rstrip() + "\n" + P.llms_events(evs, url), encoding="utf-8")
        (site / "llms-full.txt").write_text(P.llms_full(head, evs, url), encoding="utf-8")
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
