"""Issueフォームの本文を works.yml に反映する（GitHub Actions から実行）。

環境変数: ISSUE_BODY, ISSUE_NUMBER, GITHUB_TOKEN(任意)
結果のメッセージは works_issue_result.md に書き出す（Issueへのコメントに使う）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import works_lib as W  # noqa: E402
from fetch_flyers import download, save_image  # noqa: E402

LABELS = {
    "日付": "date", "最終日": "end", "イベント名": "title", "種別": "kind",
    "会場": "venue", "会場URL": "venue_url", "主催": "organizer", "主催URL": "organizer_url",
    "チケット": "tickets", "役割": "role", "フライヤー": "flyer",
}
RESULT = W.ROOT / "works_issue_result.md"


def parse_form(body: str) -> dict:
    out, key, buf = {}, None, []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = LABELS.get(m.group(1)), []
            continue
        if key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in out.items()}


def parse_tickets(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        if "|" in line:
            label, url = (s.strip() for s in line.split("|", 1))
            items.append({"label": label, "url": url} if label else {"url": url})
        else:
            items.append({"url": line})
    return items


def flyer_url(text: str) -> str | None:
    m = (re.search(r'src="(https?://[^"]+)"', text) or re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)
         or re.search(r"(https?://\S+)", text))
    return m.group(1) if m else None


def fail(msg: str) -> None:
    RESULT.write_text(f"⚠️ 反映できませんでした: {msg}\n", encoding="utf-8")
    print(msg)
    sys.exit(1)


def main() -> None:
    form = parse_form(os.environ.get("ISSUE_BODY", ""))
    issue = int(os.environ["ISSUE_NUMBER"])
    try:
        date = W.to_date(form.get("date"))
        end = W.to_date(form.get("end"))
    except ValueError:
        fail("日付は YYYY-MM-DD で入力してください")
    if not date:
        fail("日付がありません")
    if end and end < date:
        fail("最終日が日付より前になっています")

    events = W.load()
    title = form.get("title") or None
    target = next((e for e in events if e.get("issue") == issue), None)
    mode = "更新"
    if target is None and title:
        target = next((e for e in events if e["date"] == date and not W.announced(e)), None)
        mode = "告知前の予定を上書き" if target else mode
    if target is None:
        target, mode = {}, "追加"
        events.append(target)

    old_flyer = target.get("flyer")
    target.update({
        "date": date, "end": end, "title": title, "kind": form.get("kind") or None,
        "venue": form.get("venue") or None, "venue_url": form.get("venue_url") or None,
        "organizer": form.get("organizer") or None, "organizer_url": form.get("organizer_url") or None,
        "tickets": parse_tickets(form.get("tickets", "")), "role": form.get("role") or None,
        "issue": issue,
    })

    src = flyer_url(form.get("flyer", ""))
    if src:
        token = os.environ.get("GITHUB_TOKEN")
        try:
            try:
                data, ext = download(src)
            except Exception:  # noqa: BLE001  非公開リポジトリの添付は認証が要る
                data, ext = download(src, token)
        except Exception as ex:  # noqa: BLE001
            fail(f"フライヤー画像を取得できませんでした（{ex}）")
        if old_flyer and old_flyer.startswith(W.IMG_URL + "/"):
            (W.ROOT / "docs" / old_flyer.lstrip("/")).unlink(missing_ok=True)
        target["flyer"] = save_image(date, data, ext, set())
        target["flyer_alt"] = f"{title or date.isoformat()} フライヤー"
    elif not form.get("flyer"):
        target["flyer"] = old_flyer  # 空欄なら既存のまま

    W.save(events)
    label = title or "（告知前）"
    lines = [f"✅ {mode}しました: **{date.isoformat()}** {label}"]
    if target.get("flyer"):
        lines.append(f"フライヤー: `{target['flyer']}`")
    lines.append("数分でサイトに反映されます。直したい時はこのIssueを編集してください。")
    RESULT.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
