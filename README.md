# Kenchoji

鎌倉クオンツラボの記事と、検証に使った分析スクリプト・図表・集計結果を公開するリポジトリです。

公式サイト: https://kamakuraquantlab.jp/

## 公開までの流れ

最終確認を終えた記事本文と、公開可能な分析スクリプト・図表・集計結果をこのリポジトリに置き、Zenn に公開します。

記事ごとに `assets/NN_slug/` を用意し、確定した本文を `article.md` に置きます。
分析を伴う記事には、スクリプト、必要なライブラリ、実行方法、測定対象の期間を記載します。
本文には、スクリプトの置き場所として**このリポジトリの該当ディレクトリの URL** を書きます。
下書きのままのリポジトリ内パス（`assets/NN_slug/`）では、Zenn の読者は辿り着けません。
認証情報、非公開のインフラ情報、再配布が認められていない市場データは公開しません。

公開後は、公開日と Zenn の記事 URL を記録します。
その後の訂正は、このリポジトリと Zenn の両方に反映します。
読者向けの正式な公開先は Zenn です。Zenn への反映は GitHub 連携の自動デプロイで行います（末尾の「Zenn 自動デプロイ」を参照）。

## 公開済みの記事

| 記事 | 公開日 | Zenn | 本文・関連ファイル |
|---|---|---|---|
| 鎌倉散歩 — これから書くことについて | 2026-09-17 | [読む](https://zenn.dev/kamakuraquant/articles/2679ccc6c71416) | [本文](assets/00_kamakura-sampo/article.md) |
| スプレッドは手数料である — 国内 12 市場を手数料体系で分けて測る | 2026-09-27 | [読む](https://zenn.dev/kamakuraquant/articles/59a62dcdce7ef2) | [本文](assets/01_spread-vs-fees/article.md)・[スクリプトと集計結果](assets/01_spread-vs-fees/) |
| ボラティリティは「いくつ」ではない — 測る間隔しだいで違う値が出て、長く取れば Binance に収束する | 2026-10-03 | [読む](https://zenn.dev/kamakuraquant/articles/c054d44d00f04e) | [本文](assets/02_volatility-estimation/article.md)・[スクリプトと集計結果](assets/02_volatility-estimation/) |

プロローグは今後の執筆方針を紹介する記事のため、分析スクリプトや数値の検証結果はありません。

## Zenn 自動デプロイ

Zenn の GitHub 連携による自動デプロイを有効にしています。
`main` ブランチの `articles/` 以下の Markdown が、そのまま Zenn に反映されます。
ファイル名（拡張子を除く）が Zenn の記事スラッグです。

`articles/*.md` の本文は `assets/NN_slug/article.md` と同じ内容で、先頭の frontmatter だけ Zenn 用（`title`・`emoji`・`type`・`topics`・`published`）です。
本文を直すときは両方を揃えてください。
図表やスクリプトは `assets/NN_slug/` に置き、本文からは GitHub の URL（`https://raw.githubusercontent.com/kamakuraquantlab/Kenchoji/main/assets/...`）で参照します。

| 記事ファイル | 本文・関連ファイル | Zenn URL |
|---|---|---|
| [articles/2679ccc6c71416.md](articles/2679ccc6c71416.md) | [assets/00_kamakura-sampo/](assets/00_kamakura-sampo/) | https://zenn.dev/kamakuraquant/articles/2679ccc6c71416 |
| [articles/59a62dcdce7ef2.md](articles/59a62dcdce7ef2.md) | [assets/01_spread-vs-fees/](assets/01_spread-vs-fees/) | https://zenn.dev/kamakuraquant/articles/59a62dcdce7ef2 |
| [articles/c054d44d00f04e.md](articles/c054d44d00f04e.md) | [assets/02_volatility-estimation/](assets/02_volatility-estimation/) | https://zenn.dev/kamakuraquant/articles/c054d44d00f04e |
