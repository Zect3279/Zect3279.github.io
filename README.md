just a web site

## works の更新

イベントは `data/works.yml`、フライヤーは `docs/img/works/` に置く。`docs/works.md` は `hooks/works.py` がビルド時に生成するので直接書かない。

- **追加（ふだん）**：Issues → New issue →「works にイベントを追加」。フライヤー画像はフォームにドラッグ&ドロップ。送信すると Actions が yml 追記・画像保存・デプロイまで行い、Issue にコメントして閉じる。直したい時は Issue を編集すると反映し直される。
- **告知前の予定**：イベント名を空欄で送ると日付だけ表示。告知が出たら同じ日付で新しく Issue を立てると上書きされる。
- **手で直す**：`data/works.yml` を編集して push。フライヤーは `flyer: /img/works/2026-10-04.jpg` のようにパスで書く。
- **URL のままのフライヤーを取り込む**：Actions →「フライヤーを取り込む」を手動実行（`python tools/fetch_flyers.py` と同じ）。
- 予定/過去は日付で自動判定。日付をまたいだ反映のため毎日 0:07 (JST) に自動ビルドする。

### works ページのデザイン

- `overrides/works.html`：テンプレート（WALL の壁はビルド時に HTML で出力。JS 無しでも全件見える）
- `docs/assets/works/works.css` / `works.js`：WALL⇄RING 切替、RING（1周22枚の螺旋リング・横スワイプ/ホイール/年ジャンプ）、詳細ビュー
- `hooks/works.py`：works.yml → テンプレート用データ。ローカルのフライヤーは Pillow で `img/works/thumbs/*.webp`（幅640）を自動生成し、縦横比と代表色（RING の背景色）も取る
- 既定は WALL。`/works/#ring` で RING を直接開ける。最後に選んだ表示はブラウザに記憶される
