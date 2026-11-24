just a web site

## works の更新

イベントは `data/works.yml`、フライヤーは `docs/img/works/` に置く。イベント・シリーズごとのページ、`works.json` / `works.ics` / `works/feed.xml` / `llms*.txt` はビルド時に自動生成（`hooks/works.py` → `tools/works_publish.py`）。

### 手書きする場所

- `docs/works.md` の `lead`：WALL の一番上に出るリード文（1〜2文）
- `docs/works.md` の `profile`：About 欄の表（VJ 歴・拠点・スタイル・ソフト・連絡先・リンク）
- `docs/works.md` の本文（front matter の下）：About 本文。Markdown
- `data/works.yml` の各イベントの `note`（Issue フォームの「ひとこと」）：イベントページの「ひとこと」

どれも空ならページに出ない。書いた内容は検索エンジン向けの構造化データと `llms.txt` にも入る。Zect の名前・情報は works 配下（`/works/`）にだけ出し、トップやサイト共通の部分には出さない。

- **追加（ふだん）**：Issues → New issue →「works にイベントを追加」。フライヤー画像はフォームにドラッグ&ドロップ。送信すると Actions が yml 追記・画像保存・デプロイまで行い、Issue にコメントして閉じる。直したい時は Issue を編集すると反映し直される。
- **告知前の予定**：イベント名を空欄で送ると日付だけ表示。告知が出たら同じ日付で新しく Issue を立てると上書きされる。
- **手で直す**：`data/works.yml` を編集して push。フライヤーは `flyer: /img/works/2026-10-04.jpg` のようにパスで書く。
- **料金・主催（Google のイベント表示用）**：チケットに `price: 2500`（円の整数、無料は `0`）、分かれば発売日 `on_sale: 2026-10-01` を書くと構造化データの offers に入る。料金の無いチケットは offers に出さない。`organizer` も分かれば入れる（無いと Search Console で推奨項目の警告が出る）。
- **URL のままのフライヤーを取り込む**：Actions →「フライヤーを取り込む」を手動実行（`python tools/fetch_flyers.py` と同じ）。
- 予定/過去は日付で自動判定。日付をまたいだ反映のため毎日 0:07 (JST) に自動ビルドする。

### works ページのデザイン

- `overrides/works.html`：テンプレート（WALL の壁はビルド時に HTML で出力。JS 無しでも全件見える）
- `docs/assets/works/works.css` / `works.js`：WALL⇄RING 切替、RING（1周22枚の螺旋リング・横スワイプ/ホイール/年ジャンプ）、詳細ビュー
- `hooks/works.py`：works.yml → テンプレート用データ。ローカルのフライヤーは Pillow で `img/works/thumbs/*.webp`（幅640）を自動生成し、縦横比と代表色（RING の背景色）も取る
- 既定は WALL。`/works/#ring` で RING を直接開ける。最後に選んだ表示はブラウザに記憶される
