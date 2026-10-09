# Kenchoji

鎌倉クオンツラボの記事と、検証に使った分析スクリプト・図表・集計結果を公開するリポジトリです。

公式サイト: https://kamakuraquantlab.jp/

## 公開までの流れ

最終確認を終えた記事本文と、公開可能な分析スクリプト・図表・集計結果をこのリポジトリに置き、Zenn に公開します。

記事ごとに `article/NN_slug/` を用意し、確定した本文を `article.md` に置きます。
分析を伴う記事には、スクリプト、必要なライブラリ、実行方法、測定対象の期間を記載します。
本文には、スクリプトの置き場所として**このリポジトリの該当ディレクトリの URL** を書きます。
下書きのままのリポジトリ内パス（`article/NN_slug/`）では、Zenn の読者は辿り着けません。
認証情報、非公開のインフラ情報、再配布が認められていない市場データは公開しません。

公開後は、公開日と Zenn の記事 URL を記録します。
その後の訂正は、このリポジトリと Zenn の両方に反映します。
読者向けの正式な公開先は Zenn です。Zenn と GitHub の自動同期は設定していません。

## 公開済みの記事

| 記事 | 公開日 | Zenn | 本文・関連ファイル |
|---|---|---|---|
| 鎌倉散歩 — これから書くことについて | 2026-09-17 | [読む](https://zenn.dev/kamakuraquant/articles/2679ccc6c71416) | [本文](article/00_kamakura-sampo/article.md) |
| スプレッドは手数料である — 国内 12 市場を手数料体系で分けて測る | 2026-09-27 | [読む](https://zenn.dev/kamakuraquant/articles/59a62dcdce7ef2) | [本文](article/01_spread-vs-fees/article.md)・[スクリプトと集計結果](article/01_spread-vs-fees/) |
| ボラティリティは「いくつ」ではない — 測る間隔で 3 倍変わり、長く取れば Binance に収束する | 2026-10-03 | [読む](https://zenn.dev/kamakuraquant/articles/c054d44d00f04e) | [本文](article/02_volatility-estimation/article.md)・[スクリプトと集計結果](article/02_volatility-estimation/) |

プロローグは今後の執筆方針を紹介する記事のため、分析スクリプトや数値の検証結果はありません。

## 訂正

| 記事 | 訂正日 | 内容 |
|---|---|---|
| スプレッドは手数料である | 2026-10-09 | 板データ（bitbank）の修復を受けて全スクリプトを再実行し、数値と図を差し替え。結論は変わらず。Binance の約定数も取り直し。詳細は本文冒頭の訂正注記 |
