"""works.yml から、検索エンジン・AI・他のツール向けの公開物を作る（hooks/works.py から使う）。

- イベントごとのページ（docs/works/<slug>.md 相当を生成）… イベント名で検索したときに出るように
- シリーズのページ（docs/works/series/<slug>.md 相当）… 同じシリーズの回をまとめる
- データの書き出し：works.json / works.ics / works/feed.xml / llms.txt 追記 / llms-full.txt
"""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from xml.sax.saxutils import escape as xesc

import works_lib as W

DOW_JA = "月火水木金土日"
KIND_JA = {"club": "クラブイベント", "live": "ライブ"}
PERSON = "Zect"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/deed.ja"
LICENSE_NOTE = (f"出演データ（テキスト）は CC BY 4.0 で公開しています。出典「{PERSON}（zscode.net）」を表示すれば、"
                "転載・加工・商用利用も自由です。フライヤー画像の著作権は各イベントの主催者・制作者にあり、このライセンスの対象外です。")


# ---------- 下ごしらえ ----------

def series_name(title: str) -> str:
    """「HELLO, VOCALOID vol.4」→「HELLO, VOCALOID」。回数・周年などの表記を落とす。"""
    t = re.sub(r"\s*[-–—]?\s*(vol|Vol|VOL)\.?\s*[\d.]+.*$", "", title)
    t = re.sub(r"\s+\d+(st|nd|rd|th)\s+Anniversary.*$", "", t, flags=re.I)
    t = re.sub(r"\s+(第\s*\d+\s*回|#\d+|\d{4})$", "", t)
    return t.strip()


def slugify(s: str) -> str:
    s = re.sub(r"[\s\u3000/\\?#%&:;,.'\"!！？（）()\[\]【】「」『』<>|*+=~^`]+", "-", s.lower())
    return re.sub(r"-{2,}", "-", s).strip("-") or "series"


def prepare(events: list[dict], today: dt.date) -> list[dict]:
    """告知済みのイベントに slug・series・status を付けて、日付順に返す。"""
    evs = sorted((e for e in events if W.announced(e)), key=lambda e: (e["date"], e["title"]))
    seen: dict[str, int] = defaultdict(int)
    for e in evs:
        base = e["date"].isoformat()
        seen[base] += 1
        e["_slug"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
        e["_status"] = "past" if (e.get("end") or e["date"]) < today else "upcoming"
    # シリーズ：yml の series を優先、なければタイトルから推定し、2 回以上あるものだけ
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in evs:
        name = e.get("series") or series_name(e["title"])
        groups[name.lower()].append(e)
    for members in groups.values():
        if len(members) < 2:
            continue
        name = members[0].get("series") or series_name(members[0]["title"])
        for e in members:
            e["_series"] = name
            e["_series_slug"] = slugify(name)
    return evs


def series_groups(evs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for e in evs:
        if e.get("_series_slug"):
            out[e["_series_slug"]].append(e)
    return out


# ---------- 文字列 ----------

def jdate(d: dt.date) -> str:
    return f"{d.year}年{d.month}月{d.day}日（{DOW_JA[d.weekday()]}）"


def jrange(e: dict) -> str:
    d, end = e["date"], e.get("end")
    if not end or end == d:
        return jdate(d)
    tail = f"{end.month}月{end.day}日（{DOW_JA[end.weekday()]}）" if end.year == d.year else jdate(end)
    return f"{jdate(d)}〜{tail}"


def md(s: str) -> str:
    """Markdown の記号をエスケープ。"""
    return re.sub(r"([\\`*_\[\]<>#|~])", r"\\\1", str(s))


def mdlink(text: str, url: str | None) -> str:
    return f"[{md(text)}]({url})" if url else md(text)


def role(e: dict) -> str:
    return e.get("role") or "VJ"


def summary(e: dict) -> str:
    """イベントの説明文（ページ本文・description・JSON-LD で共通）。"""
    kind = KIND_JA.get(e.get("kind") or "", "イベント")
    venue = e.get("venue")
    if e["_status"] == "past":
        where = f"{venue} で開催された" if venue else "開催された"
        s = f"{jrange(e)}、{where}{kind}「{e['title']}」に、{PERSON} が {role(e)} として出演しました。"
    else:
        where = f"{venue} で開催される" if venue else "開催される"
        s = f"{jrange(e)}に{where}{kind}「{e['title']}」に、{PERSON} が {role(e)} として出演します。"
    if e.get("organizer"):
        s += f"主催は {e['organizer']}。"
    return s


# ---------- ページ（Markdown を生成） ----------

def front(meta: dict) -> str:
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items()) + "---\n\n"


def event_page(e: dict, prev: dict | None, nxt: dict | None, series: list[dict], img_size: tuple[int, int] | None) -> str:
    meta = {
        "title": e["title"],
        "description": summary(e) + " 日付・会場・チケット・フライヤーなどのイベント情報。",
        "event_slug": e["_slug"],
        "hide": ["navigation", "toc"],
    }
    flyer = e.get("flyer") or ""
    if flyer and not flyer.startswith("http"):
        meta["ogp_image"] = flyer.lstrip("/")
        if img_size:
            meta["ogp_image_w"], meta["ogp_image_h"] = img_size

    rows = [("日付", jrange(e))]
    if e.get("venue"):
        rows.append(("会場", mdlink(e["venue"], e.get("venue_url"))))
    if e.get("organizer"):
        rows.append(("主催", mdlink(e["organizer"], e.get("organizer_url"))))
    rows.append(("種別", KIND_JA.get(e.get("kind") or "", "イベント")))
    rows.append(("出演", f"{PERSON}（{md(role(e))}）"))
    tickets = [mdlink(t.get("label") or "チケット・詳細", t.get("url")) for t in e.get("tickets") or []]
    if tickets:
        rows.append(("チケット・告知", " / ".join(tickets)))
    if e.get("_series"):
        rows.append(("シリーズ", f"[{md(e['_series'])}](series/{e['_series_slug']}.md)"))

    out = [front(meta), f"# {md(e['title'])}\n\n"]
    badge = "開催予定" if e["_status"] == "upcoming" else "開催済み"
    out.append(f"**{jrange(e)}**{' · ' + md(e['venue']) if e.get('venue') else ''} · {badge}\n\n")
    out.append(md(summary(e)) + "\n\n")
    out.append("| 項目 | 内容 |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in rows) + "\n")
    if flyer:
        src = flyer if flyer.startswith("http") else "../" + flyer.lstrip("/")
        alt = e.get("flyer_alt") or f"{e['title']} フライヤー"
        out.append(f"![{md(alt)}]({src})\n\n")
    others = [s for s in series if s is not e]
    if others:
        out.append(f"## 「{md(e['_series'])}」の他の回\n\n")
        out += [f"- [{md(s['title'])}]({s['_slug']}.md) — {jrange(s)}\n" for s in reversed(others)]
        out.append("\n")
    nav = []
    if prev:
        nav.append(f"← [{md(prev['title'])}]({prev['_slug']}.md)")
    nav.append("[VJ Works 一覧](../works.md)")
    if nxt:
        nav.append(f"[{md(nxt['title'])}]({nxt['_slug']}.md) →")
    out.append("---\n\n" + " · ".join(nav) + "\n")
    return "".join(out)


def series_page(slug: str, members: list[dict]) -> str:
    name = members[0]["_series"]
    y0, y1 = members[0]["date"].year, members[-1]["date"].year
    years = f"{y0}年" if y0 == y1 else f"{y0}年〜{y1}年"
    meta = {
        "title": f"{name}（シリーズ）",
        "description": f"「{name}」で {PERSON} が VJ として出演した回の一覧（{len(members)}回・{years}）。各回の日付・会場・フライヤー。",
        "series_slug": slug,
        "hide": ["navigation", "toc"],
    }
    out = [front(meta), f"# {md(name)}\n\n",
           f"{PERSON} が VJ として出演した「{md(name)}」の回の一覧です（全{len(members)}回、{years}）。\n\n",
           "| 日付 | イベント | 会場 |\n|---|---|---|\n"]
    out += [f"| {jrange(e)} | [{md(e['title'])}](../{e['_slug']}.md) | {mdlink(e['venue'], e.get('venue_url')) if e.get('venue') else ''} |\n"
            for e in reversed(members)]
    out.append("\n---\n\n[VJ Works 一覧](../../works.md)\n")
    return "".join(out)


# ---------- 構造化データ（JSON-LD） ----------

def absu(site: str, u: str) -> str:
    return u if not u or u.startswith("http") else f"{site}/{u.lstrip('/')}"


def page_url(site: str, e: dict) -> str:
    return f"{site}/works/{e['_slug']}/"


def event_ld(e: dict, site: str) -> dict:
    url = page_url(site, e)
    ev = {
        "@type": "MusicEvent",
        "@id": url + "#event",
        "name": e["title"],
        "url": url,
        "startDate": e["date"].isoformat(),
        "endDate": (e.get("end") or e["date"]).isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "inLanguage": "ja",
        "description": summary(e),
        "performer": {"@id": f"{site}/#person"},
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
        ev["image"] = absu(site, e["flyer"])
    offers = [{"@type": "Offer", "url": t["url"]} for t in e.get("tickets") or [] if t.get("url")]
    if offers:
        ev["offers"] = offers
    if e.get("_series"):
        ev["superEvent"] = {"@type": "EventSeries", "@id": f"{site}/works/series/{e['_series_slug']}/#series", "name": e["_series"]}
    return ev


def crumbs(site: str, items: list[tuple[str, str]]) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def dumps(data) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def event_page_ld(e: dict, site: str) -> str:
    return dumps({"@context": "https://schema.org", "@graph": [
        event_ld(e, site),
        crumbs(site, [("Zscode", f"{site}/"), ("VJ Works", f"{site}/works/"), (e["title"], page_url(site, e))]),
    ]})


def series_page_ld(slug: str, members: list[dict], site: str) -> str:
    name = members[0]["_series"]
    url = f"{site}/works/series/{slug}/"
    return dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "EventSeries", "@id": url + "#series", "name": name, "url": url,
         "subEvent": [{"@id": page_url(site, e) + "#event", "name": e["title"], "url": page_url(site, e),
                       "startDate": e["date"].isoformat()} for e in members]},
        crumbs(site, [("Zscode", f"{site}/"), ("VJ Works", f"{site}/works/"), (name, url)]),
    ]})


def works_list_ld(evs: list[dict], site: str) -> str:
    items = list(reversed(evs))
    return dumps({
        "@context": "https://schema.org", "@type": "ItemList", "name": f"{PERSON} の VJ 出演一覧",
        "numberOfItems": len(items),
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": event_ld(e, site)} for i, e in enumerate(items)],
    })


# ---------- データの書き出し ----------

def record(e: dict, site: str) -> dict:
    r = {
        "date": e["date"].isoformat(),
        "end": e["end"].isoformat() if e.get("end") else None,
        "title": e["title"],
        "status": e["_status"],
        "kind": e.get("kind"),
        "role": role(e),
        "venue": e.get("venue"), "venue_url": e.get("venue_url"),
        "organizer": e.get("organizer"), "organizer_url": e.get("organizer_url"),
        "series": e.get("_series"),
        "tickets": [t for t in e.get("tickets") or [] if t.get("url")],
        "flyer": absu(site, e["flyer"]) if e.get("flyer") else None,
        "page": page_url(site, e),
    }
    return {k: v for k, v in r.items() if v not in (None, [])}


def works_json(evs: list[dict], site: str, now: dt.datetime) -> str:
    return json.dumps({
        "title": f"{PERSON} VJ 出演データ",
        "description": f"VJ・{PERSON} の出演履歴と出演予定（クラブイベント・ライブ）。イベント資料・カレンダー・調べものにどうぞ。",
        "source": f"{site}/works/",
        "performer": {"name": PERSON, "url": f"{site}/"},
        "license": "CC-BY-4.0",
        "license_url": LICENSE_URL,
        "license_note": LICENSE_NOTE,
        "attribution": f"出典: {PERSON}（{site}/works/）",
        "updated": now.isoformat(timespec="seconds"),
        "count": len(evs),
        "events": [record(e, site) for e in reversed(evs)],
    }, ensure_ascii=False, indent=2) + "\n"


def _ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def works_ics(evs: list[dict], site: str, now: dt.datetime) -> str:
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = site.split("://", 1)[-1]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{host}//works//JA", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{PERSON} VJ 出演", "X-WR-TIMEZONE:Asia/Tokyo",
             f"X-WR-CALDESC:VJ・{PERSON} の出演予定と出演履歴（{site}/works/）。{_ics_text(LICENSE_NOTE)}"]
    for e in evs:
        end = (e.get("end") or e["date"]) + dt.timedelta(days=1)
        lines += ["BEGIN:VEVENT", f"UID:{e['_slug']}@{host}", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{e['date']:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                  f"SUMMARY:{_ics_text(e['title'])}（{PERSON} {_ics_text(role(e))}）",
                  f"DESCRIPTION:{_ics_text(summary(e))}\\n{page_url(site, e)}",
                  f"URL:{page_url(site, e)}"]
        if e.get("venue"):
            lines.append(f"LOCATION:{_ics_text(e['venue'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def works_feed(evs: list[dict], site: str, now: dt.datetime) -> str:
    def ts(d: dt.date) -> str:
        return f"{d.isoformat()}T00:00:00+09:00"
    entries = []
    for e in reversed(evs):
        u = page_url(site, e)
        entries.append(
            f"  <entry>\n    <title>{xesc(e['title'])}（{jrange(e)}）</title>\n"
            f"    <link href=\"{xesc(u)}\"/>\n    <id>{xesc(u)}</id>\n"
            f"    <published>{ts(e['date'])}</published>\n    <updated>{ts(e['date'])}</updated>\n"
            f"    <summary>{xesc(summary(e))}</summary>\n  </entry>\n")
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<feed xmlns=\"http://www.w3.org/2005/Atom\" xml:lang=\"ja\">\n"
            f"  <title>{PERSON} VJ Works</title>\n  <subtitle>VJ・{PERSON} の出演予定と出演履歴</subtitle>\n"
            f"  <link href=\"{site}/works/\"/>\n  <link rel=\"self\" href=\"{site}/works/feed.xml\"/>\n"
            f"  <id>{site}/works/</id>\n  <updated>{now.isoformat(timespec='seconds')}</updated>\n"
            f"  <author><name>{PERSON}</name><uri>{site}/</uri></author>\n"
            f"  <rights>{xesc(LICENSE_NOTE)}</rights>\n" + "".join(entries) + "</feed>\n")


def llms_events(evs: list[dict], site: str) -> str:
    lines = ["", "## VJ 出演（新しい順）", "",
             f"各イベントの詳細ページがあります。機械可読データ: [works.json]({site}/works.json) / "
             f"[カレンダー（ICS）]({site}/works.ics) / [Atom フィード]({site}/works/feed.xml) / "
             f"[全文版 llms-full.txt]({site}/llms-full.txt)", "",
             f"ライセンス: {LICENSE_NOTE}（{LICENSE_URL}）", ""]
    for e in reversed(evs):
        venue = f" @ {e['venue']}" if e.get("venue") else ""
        tag = "（予定）" if e["_status"] == "upcoming" else ""
        lines.append(f"- [{e['title']}]({page_url(site, e)}): {jrange(e)}{venue} — {role(e)}{tag}")
    return "\n".join(lines) + "\n"


def llms_full(head: str, evs: list[dict], site: str) -> str:
    out = [head.rstrip(), "", "## VJ 出演の詳細（新しい順）", ""]
    for e in reversed(evs):
        out.append(f"### {e['title']}")
        out.append("")
        out.append(summary(e))
        out.append("")
        for k, v in [("日付", jrange(e)), ("会場", e.get("venue")), ("会場URL", e.get("venue_url")),
                     ("主催", e.get("organizer")), ("種別", KIND_JA.get(e.get("kind") or "")),
                     ("担当", role(e)), ("シリーズ", e.get("_series")),
                     ("チケット・告知", " ".join(t["url"] for t in e.get("tickets") or [] if t.get("url"))),
                     ("ページ", page_url(site, e))]:
            if v:
                out.append(f"- {k}: {v}")
        out.append("")
    return "\n".join(out) + "\n"
