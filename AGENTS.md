# Kenchoji — notes for AI agents

This repo holds the published articles of 鎌倉クオンツラボ and the scripts, figures and
results behind them. It is linked to Zenn through GitHub: **every push to `main`
deploys `articles/` to zenn.dev**. Read the Zenn CLI guide before touching
`articles/`: https://zenn.dev/zenn/articles/zenn-cli-guide

## Layout

```
assets/NN_slug/draft.md   # the article you edit (source of truth)
assets/NN_slug/*.py       # analysis scripts
assets/NN_slug/output/    # JSON results, logs, figures (*.png)
articles/<zenn-slug>.md   # what Zenn deploys; generated from draft.md
```

| Draft | Zenn file | Zenn URL |
|---|---|---|
| `assets/00_kamakura-sampo/draft.md` | `articles/2679ccc6c71416.md` | https://zenn.dev/kamakuraquant/articles/2679ccc6c71416 |
| `assets/01_spread-vs-fees/draft.md` | `articles/59a62dcdce7ef2.md` | https://zenn.dev/kamakuraquant/articles/59a62dcdce7ef2 |
| `assets/02_volatility-estimation/draft.md` | `articles/c054d44d00f04e.md` | https://zenn.dev/kamakuraquant/articles/c054d44d00f04e |

The draft's `canonical_url` frontmatter field also names its Zenn slug.

## Editing and publishing

1. Edit `assets/NN_slug/draft.md`. Never edit the body of `articles/*.md` by hand.
2. Regenerate `articles/<slug>.md` from the draft:
   - keep the existing Zenn frontmatter of `articles/<slug>.md` as is;
   - replace everything below it with the draft body, minus the draft's own
     frontmatter (`slate`, `publish`, `status`, …) and minus the leading `# title`
     line (Zenn shows `title` from frontmatter; the body has no H1);
   - if the draft's H1 title changed, update `title:` to match.
3. Check the two files agree: the body of `articles/<slug>.md` must equal the draft
   body without its frontmatter and H1.
4. Commit and push to `main`. The push is the deploy. Put `[skip ci]` in the commit
   message to push without deploying (e.g. script-only changes).
5. Deploy results and errors show on the Zenn dashboard; the user checks it.

Number fixes in published articles are made in place, with no 訂正 notice.

## Zenn rules that bite

- Zenn frontmatter: `title`, `emoji` (one emoji), `type` (`tech` or `idea`),
  `topics` (array, e.g. `["python", "データ分析"]`), `published` (`true`/`false`).
- **Never rename or delete a file in `articles/`.** The filename is the slug;
  renaming creates a second article, and deleting a file does not delete the
  article on Zenn (that is done from the dashboard).
- **Do not add `published_at` to an already-published article.** It can be set
  only once and never changed.
- New article slugs: 12–50 chars of `a-z0-9`, `-`, `_`. `npx zenn new:article`
  generates a random 14-hex slug, matching the existing ones. Start with
  `published: false` until the user says to publish.
- Preview locally with `npx zenn preview` (http://localhost:8000).

## Images and code links

Figures stay in `assets/NN_slug/output/`. Reference them, and the script
directories, by absolute GitHub URL so they work on Zenn:

- image: `https://raw.githubusercontent.com/kamakuraquantlab/Kenchoji/main/assets/NN_slug/output/<file>.png`
- code: `https://github.com/kamakuraquantlab/Kenchoji/tree/main/assets/NN_slug`

Relative repo paths (`assets/NN_slug/...`) do not resolve on Zenn. If you move a
file under `assets/`, every published article pointing at it breaks until the
URLs are updated and pushed.

## New article checklist

1. Create `assets/NN_slug/draft.md` (and scripts/output if any).
2. Pick the Zenn slug; create `articles/<slug>.md` with Zenn frontmatter and the
   body generated as above.
3. After publishing: set `canonical_url` and `published_at` in the draft's
   frontmatter, and add a row to both tables in `README.md` (公開済みの記事 and
   Zenn 自動デプロイ) and to the table above.

## Git

Work directly on `main` in this checkout; no branches or worktrees.
