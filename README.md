# バフェット式スクリーナー

東証プライム・スタンダード・グロースの全銘柄（約3,700社）を、バークシャー・ハサウェイの投資基準を写した条件で採点するスクリーナー。ブラウザだけで動く静的サイト＋PWAで、サーバーもデータベースも不要。

---

## ファイル構成

```
（リポジトリのルート）
├ index.html      アプリ本体。HTML・CSS・JavaScriptが全部この1ファイルに入っている
├ jpdata.js       全銘柄の財務データ（約520KB）。window.JPDATA に配列で入る
├ manifest.json   PWAの定義。アプリ名・アイコン・全画面表示の設定
├ sw.js           サービスワーカー。初回表示時にキャッシュし、2回目以降はオフラインで起動
├ .nojekyll       GitHub PagesのJekyll変換を無効化（これが無いと一部ファイルが配信されない）
├ icon-192.png / icon-512.png / icon-512-maskable.png / icon-180.png
│                 ホーム画面アイコン。180はiOS用
├ scripts/
│  └ fetch_data.py     jpdata.js を作り直すスクリプト
└ .github/workflows/
   └ update-data.yml   毎週日曜6時（JST）にfetch_data.pyを実行して自動コミット
```

データの流れはこれだけです。

```
fetch_data.py  →  jpdata.js  →  index.html が読み込んで採点・表示
（週1回・自動）     （データ）      （ブラウザ内で完結）
```

`index.html` は `jpdata.js` を `<script src="jpdata.js">` で読むだけなので、**データを差し替えたいときは jpdata.js だけ置き換えれば済みます**。

---

## 公開の手順（GitHub Pages）

1. GitHubで新しいリポジトリを作る（例：`buffett-screener`、Publicのまま）
2. このフォルダの中身を全部アップロード
   - Webでやるなら「uploading an existing file」にファイルをドラッグ＆ドロップ
   - `.github/workflows/update-data.yml` はフォルダ構造ごとドラッグすれば保持されます
3. リポジトリの **Settings → Pages** で Source を `Deploy from a branch`、ブランチを `main` / `(root)` にして保存
4. 1〜2分後に `https://<ユーザー名>.github.io/buffett-screener/` が公開される

## iPhoneでアプリにする

1. 上のURLを **Safari** で開く（Chromeではホーム画面追加が正しく動きません）
2. 共有ボタン → **ホーム画面に追加**
3. アイコンから起動するとアドレスバーのない全画面アプリになり、2回目以降は**オフラインでも起動**します

---

## データの自動更新

`.github/workflows/update-data.yml` が**毎週日曜6:00（JST）**に動き、

1. `scripts/fetch_data.py` を実行して `jpdata.js` を作り直す
2. `sw.js` のキャッシュ名を `buffett-screener-<日時>` に書き換える（古いキャッシュを確実に捨てるため）
3. 変更があればコミット＆プッシュ → GitHub Pagesが自動で再デプロイ

Actionsタブの「株価データの更新」→ **Run workflow** で手動実行もできます。所要時間は8〜10分、GitHub Actionsの無料枠（月2,000分）の範囲に十分収まります。

> 初回だけ **Settings → Actions → General → Workflow permissions** を `Read and write permissions` にしてください。これが無いと自動コミットが失敗します。

手元で動かす場合：

```bash
pip install openpyxl
python3 scripts/fetch_data.py          # 全銘柄（8〜10分）
LIMIT=40 python3 scripts/fetch_data.py # 40銘柄だけで動作確認
```

---

## データの出どころ

| 項目 | 取得元 |
|---|---|
| 銘柄一覧（コード・銘柄名・市場区分・33業種） | [日本取引所グループ 上場銘柄一覧](https://www.jpx.co.jp/markets/statistics-equities/misc/01.html)（xlsx） |
| 株価・時価総額・PER・PBR・配当利回り・EPS・BPS | Yahoo Finance quote API |
| ROE・ROA・営業利益率・有利子負債・FCF・配当性向 | Yahoo Finance quoteSummary API |
| 純利益の推移（増益回数の判定） | Yahoo Finance incomeStatementHistory |
| ボラティリティ・1年騰落率 | Yahoo Finance chart API（日次終値1年分から年率換算） |

すべてTTM（直近12か月）ベース。ROICは全銘柄分が揃わないためROAで代用し、自己資本比率は ROA÷ROE から推計しています。自社株買いの有無は全銘柄分を取得できないため採点条件から外しています。

## jpdata.js の中身

```js
window.JPDATA = {
  asof: "2026-09-23",
  sectors: ["ガラス・土石製品", "サービス業", ...],   // 33業種
  rows: [ [ ...25個の値... ], ... ]                  // 1銘柄1行
}
```

`rows` の並び順（`index.html` の `K` オブジェクトと対応）：

| # | 内容 | # | 内容 |
|---|---|---|---|
| 0 | 証券コード | 13 | 有利子負債÷純利益（年） |
| 1 | 銘柄名 | 14 | 増益比率（％） |
| 2 | 市場（0=プライム 1=スタンダード 2=グロース） | 15 | 増益比率の母数（比較回数） |
| 3 | 業種インデックス | 16 | FCF黒字フラグ（1/0） |
| 4 | 株価 | 17 | FCF利回り（％） |
| 5 | 時価総額（億円） | 18 | 配当性向（％） |
| 6 | PER | 19 | ボラティリティ（％・年率） |
| 7 | PBR | 20 | EPS |
| 8 | 配当利回り（％） | 21 | BPS |
| 9 | ROE（％） | 22 | 1年騰落率（％） |
| 10 | ROA（％） | 23 | 予備 |
| 11 | 営業利益率（％） | 24 | 予備 |
| 12 | 自己資本比率（％・推計） | | |

値が取れなかった項目は `null` が入り、採点では自動的に分母から外れます。

---

## 採点条件を変えたいとき

`index.html` 内の `PROFILES` を編集します。閾値と配点はアプリ画面上でも変更できますが、既定値を変えたい場合はここです。

```js
const PROFILES = {
  origin:{ name:"原典型（質重視）", short:"原典型", desc:"...",
    crit:[
      {f:"roe", n:"ROE", sub:"自己資本利益率", dir:"gte", th:15, w:18, u:"%"},
      //  f  = jpdata.js の項目名   dir = gte(以上) / lte(以下) / bool(黒字)
      //  th = 閾値                 w   = 配点      u = 単位
      ...
```

プロファイルを追加したい場合は `PROFILES` にキーを1つ足すだけで、画面のタブも自動で増えます。

---

## ライセンスと免責

個人利用を想定した自作ツールです。財務データは外部APIの値をそのまま使っており、正確性は保証されません。**投資助言ではありません。** 発注の前に必ず決算短信・有価証券報告書などの一次情報で確認してください。
