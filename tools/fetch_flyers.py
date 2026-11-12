"""works.yml の flyer が URL のものを docs/img/works/ に落とし、flyer をローカルパスに書き換える。

    python tools/fetch_flyers.py

何度実行してもよい（ローカルパスのものは触らない）。失敗したものは URL のまま残して一覧表示する。
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import works_lib as W  # noqa: E402

UA = "Mozilla/5.0 (zscode works flyer fetcher)"


def download(url: str, token: str | None = None) -> tuple[bytes, str]:
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "")
    if not ctype.startswith("image/") and data[:4] not in (b"\x89PNG", b"RIFF") and data[:2] != b"\xff\xd8":
        raise ValueError(f"画像ではないレスポンス ({ctype})")
    return data, W.ext_from(ctype, url)


def save_image(date, data: bytes, ext: str, taken: set[str]) -> str:
    W.IMG_DIR.mkdir(parents=True, exist_ok=True)
    name = W.flyer_name(date, ext, taken)
    (W.IMG_DIR / name).write_bytes(data)
    taken.add(name)
    return f"{W.IMG_URL}/{name}"


def main() -> None:
    events = W.load()
    taken: set[str] = set()
    failed = []
    for e in events:
        src = e.get("flyer") or ""
        if not src.startswith("http"):
            continue
        try:
            data, ext = download(src)
            e["flyer"] = save_image(e["date"], data, ext, taken)
            print(f"ok   {e['date']} {e.get('title')} -> {e['flyer']}")
        except Exception as ex:  # noqa: BLE001
            failed.append((e, ex))
            print(f"FAIL {e['date']} {e.get('title')}: {ex}")
    W.save(events)
    if failed:
        print(f"\n{len(failed)} 件失敗（URLのまま残しています）")


if __name__ == "__main__":
    main()
