# negativeyouth.net — Archive Restoration Plan

Rebuild the lost `negativeyouth.net` WordPress blog as a self-contained static site,
sourced entirely from web.archive.org, and re-host it at the recovered domain.

**Target output:** pixel-faithful mirror of the original 2010–2013 "Sandbox" WordPress theme.

**Status:** Phases 1-8 complete. Phase 9 (hosting artifacts and deploy) pending.

| Phase | Report | Data |
|---|---|---|
| 1 manifest | `_reports/manifest.md` | `_work/manifest.csv` |
| 2 completeness | `_reports/completeness.md` | `_work/posts.csv`, `_work/pagination.csv` |
| 3 feeds | `_reports/feeds.md` | `_work/feeds.csv` |
| 4 fetch | `_reports/fetch.md` | `_cache/` |
| 5 verify | `_reports/verify.md` | `_work/verify.csv` |
| 6 rewrite | `_reports/missing-assets.md` | `_work/filename-map.csv` |
| 6b link check | `_reports/linkcheck.md` | — |
| 7 generate | `_reports/build.md` | `site/` |
| 8 provenance | `_reports/build.md` | `site/`, `posts.csv`, `posts.json` |

---

## 1. Source inventory (verified against the CDX index)

The archive was queried with:

```
https://web.archive.org/cdx/search/cdx
  ?url=negativeyouth.net
  &matchType=domain
  &output=text
  &fl=timestamp,original,mimetype,statuscode,digest,length
```

Queried **uncollapsed** so the best capture per resource could be chosen, and
paginated via `resumeKey` since a single page returns only ~2,000 rows.

**9,893 raw rows → 3,810 distinct resources → 3,541 usable captures, 236.5 MB.**

| Bucket | Files | Size | Notes |
|---|---:|---:|---|
| Posts (pretty permalinks) | 949 | — | The actual writing |
| Tag archives (`/tag/*`) | 143 | — | |
| Date archives (`/YYYY/` + `/YYYY/MM/`) | 37 | — | 2010-10 → 2013-06 |
| Category archives (`/category/*`) | 12 | — | 9 categories + pagination pages |
| Author archives (`/author/*`) | 8 | — | cas, daniela-quant, eduardo-caudilio, eduardo-caudillo, el-carlos, ella, jc, victor |
| Pages (Tumblr-era + About) | 11 | — | `/tagged/*`, `/post/*`, `/about`, `/ask`, … |
| Homepage + pagination | 2 | — | `/` and `/page/2/` |
| CSS | 21 | — | |
| Fonts | 16 | — | |
| JS | 4 | — | |
| Other assets | 4 | — | robots.txt, wp-includes, … |
| **HTML total** | **1,116** | | |
| Images | 1,478 | | all on own domain |
| RSS/XML feeds | 851 | | Jetpack per-post comment feeds |
| **Total (200 only)** | **3,541** | **236.5 MB** | |

Excluded: 226 URLs with no 200 capture, plus 6 captured *only* after the domain
lapsed (those belong to whoever held it then). Full detail in
`_reports/manifest.md`; per-resource rows in `_work/manifest.csv`.

Non-200 captures excluded: 880 × 301, 76 × 302, 12 × 404, 2 × 500, 10 × `warc/revisit`.

### 1.0 Definitive post inventory

Phase 2 reconciled three independent sources to establish what actually existed:

| Source | Method | Posts |
|---|---|---:|
| A | CDX index | 794 |
| A+C | + date-archive listings | 166 |
| B | + prev/next chain walk | 6 |

**960 posts total: 957 recovered, 3 permanently lost.** 949 carry a recoverable
date. Twelve authors, nine categories, 143 distinct tags. Per-post detail in
`_work/posts.csv`; full audit in `_reports/completeness.md`.

### 1.1 Content ceiling

- Last date archive: **`/2013/06/`**
- Newest post on the captured homepage: **"LATER FAGS" — 2013-07-03**
- The site stayed online until at least Feb 2015 but **nothing was posted after July 2013.**

The gap between the last post and the last capture is dead time, not lost writing. The
archive very likely contains essentially the entire blog.

> Note: the reference snapshot `20150211213342` is **Feb 11 2015**, not 2025.

### 1.2 Theme and plugin assets captured

- Theme: `wp-content/themes/sandbox/` — `style.css`, `3c-b.css`, `j/function.js`,
  `j/jquery.blockUI.js`, `backgrounds/fondo3.jpg`, `backgrounds/rotate.php`,
  BebasNeue webfont, 4 × helvetica_lt webfont variants (eot/ttf/woff/svg)
- Plugins: `download-monitor`, `jetpack`, `jquery-archive-list-widget`,
  `really-simple-facebook-twitter-share-buttons`, `simple-sopa-blackout`,
  `wp-recaptcha`, `xavins-review-ratings`

### 1.3 Markup characteristics (why extraction is reliable)

Server-rendered WordPress with standard semantic markup. Post metadata is
machine-readable directly in the `class` attribute:

```html
<div class="hentry p1 post publish author-jc category-video
            tag-columbia-records tag-david-lynch tag-los-angeles
            tag-nine-inch-nails tag-video y2013 m06 d28 h09">
```

This yields title, date (`y`/`m`/`d`/`h`), author, categories and tags with no
scraping guesswork. Body content lives in `.entry-content`. Chronological
neighbours are in `.nav-previous` / `.nav-next`. Pagination is
`posts_per_page=5`, confirmed by the date archives (each lists exactly 5 posts).

---

## 2. Known gaps and permanent losses

These are **not** recoverable. They are documented so the archive is honest about
what it is.

1. **No audio or video files were archived.** Zero mp3, swf, or any other media
   captures exist. Mixtape and music posts survive as text only.
2. **Mixtape downloads are dead.** The `download-monitor` plugin was in use; its
   target files were never archived by anyone.
3. **Some embedded players are gone.** YouTube / Vimeo / Bandcamp embeds survive as
   iframe URLs, but some video IDs no longer resolve. Live embeds are kept as-is
   (see §3.2), so dead IDs will render as broken players. They will be enumerated
   in a report rather than altered.
4. **Some post images were never captured** and cannot be backfilled.
5. **Theme random backgrounds will break.** `backgrounds/rotate.php` is a PHP
   script and will not execute on static hosting; only `fondo3.jpg` was captured.
6. **2022+ captures are not ours.** The domain lapsed and was parked; automated
   sweeps captured `.well-known/*` probes and parking pages. These are excluded —
   otherwise we would publish a stranger's page as the site.
7. **Pagination pages were never captured.** Their URLs are recoverable from the
   captured archives and the pages can be regenerated in Phase 8.
8. **The CDX index understates the archive by 166 posts.** Taken alone it lists
   794; the date-archive listings contribute 166 more that the index omits
   entirely. Trusting the index would have silently dropped them while producing
   an archive that looks complete.

9. **Three posts are permanently lost.** `/light-asylum-dark-allies-2/`,
   `/rvver/` and `/sulk-pictureplanes-ferraris-on-fire-mix/` are linked from the
   archive's own prev/next navigation but have no capture anywhere. Verified
   directly against the archive, not merely absent from the index.

10. **Non-post assets are now all but recovered.** The first fetch pass left 77
    resources with no bytes: 46 thumbnails and 27 comment feeds. A later,
    longer run of `04_fetch.py` recovered all but three of them — `fetch_one()`
    walks *every* capture the CDX lists for a URL, so a resource marked missing
    on the first pass can still be found on a later attempt. Remaining: four,
    of which two are PHP endpoints that cannot execute on static hosting at all
    (`/xmlrpc.php`, `jquery-archive-list-widget/…/list.js.php`) and two comment
    feeds. Recorded here because the earlier "77 permanently lost" figure in
    §2 predates that recovery.

10. **27 comment feeds are indexed but unplayable.** They have a 200 record in
    the CDX index with no retrievable payload. Every capture was tried. All 27
    belong to posts whose HTML *is* captured, so no post text is lost.

---

## 3. Locked decisions

### 3.1 Homepage — regenerate with pagination
The captured homepage is replaced by a generated index built from the full
recovered post inventory, at `posts_per_page=5`:

```
/index.html  /page/2/  /page/3/  …  /page/N/
```

At ~950 posts this is **~190 generated pagination pages**.

Two obligations follow:

- The Sandbox post-loop markup must be harvested from the captured date/tag/category
  archives, and **a pristine copy of the captured Feb 2015 homepage must be written
  to `_provenance/` before it is overwritten.** That homepage is also the only
  source for the sidebar widgets (`textwidget`, `ctc`, `advanced-random-posts`,
  search form), which are carried into the generated pages so they still render
  correctly.
- Ordering is reverse-chronological by post date, taken from two independent
  sources: RSS `pubDate` and the `hentry` class date attributes.

### 3.2 Embeds — keep live
YouTube / Vimeo / Bandcamp iframes are left byte-identical so they keep playing.
Dead IDs are reported, not rewritten.

### 3.3 Broken images — leave the original `src`
Unrecoverable assets keep their original reference. No placeholder substitution.
This makes the rewrite pass strictly lossless: pure URL→path substitution, never
content edits.

### 3.4 Rewrite *all* same-origin references, cached or not
A hard requirement, not an optimisation. During the lapse, `negativeyouth.net` was
parked and swept by automated requests, so any surviving absolute link would send
visitors to whatever is there now.

**Consequence: the finished site makes zero outbound requests to the live domain.**
A failed asset backfill 404s against our own host instead of leaking visitors.

### 3.5 Feeds — keep all 851, browsable
Retained under `/feeds/` as genuine archival history, and they are what enables the
Phase 3 content recovery. A generated `/feeds/index.html` groups them by post.

**Sole exception to §3.4:** feed *internals* are left verbatim. RSS canonical URLs
are the entire purpose of a feed; rewriting them would falsify a primary-source
artifact. Post pages are fully rewritten; feeds stay as captured.

---

## 4. Architecture

Python 3, **standard library only** — so the tooling still runs in five years with
no dependency rot. Optional `requests` for speed, never required.

```
negative-youth-net/
├── RESTORE.md              this document
├── tools/
│   ├── 01_manifest.py      CDX pull, normalisation, classification
│   ├── 02_discover.py      prev/next chain walk + pagination walk
│   ├── 03_feeds.py         RSS parse + content recovery
│   ├── 04_fetch.py         polite resumable downloader
│   ├── 05_verify.py        digest/length verification
│   ├── 06_rewrite.py       link rewriting + asset reconciliation
│   ├── 07_generate.py      homepage, pagination, missing archives
│   └── 08_report.py        size, file count, gaps, dead embeds
├── _cache/                 content-addressed raw Wayback bytes (resumable)
├── _provenance/            pristine copies of replaced captured pages
├── _work/                  intermediates, manifests, CSVs
├── _reports/               human-readable audit output
└── site/                   FINAL static output — this is what gets deployed
```

`tools/` is committed to git **before the first fetch**, so the crawl is
reproducible.

---

## 5. Phases

### Phase 0 · Workspace
Create the tree above. `git init`, commit the tooling. Empty commit is fine; the
point is that the crawl is reproducible from a known state.

### Phase 1 · Manifest
Pull the **full** CDX result set (not collapsed) so we can prefer 200-status
captures and choose the best timestamp per URL. Then:

- Normalise scheme and `:80` duplicates to a single canonical entry per resource.
- Classify each URL: `post`, `tag`, `category`, `author`, `date`, `feed`, `image`,
  `css`, `js`, `font`, `redirect`, `error`, `exclude`.
- Drop 301/302 (resolve targets instead), 404, 500, and **everything timestamped
  2022 or later**.
- Triage the 7 residual unclassified HTML paths.
- Emit `_work/manifest.csv`: `url, timestamp, mime, status, digest, length, kind`.

### Phase 2 · Completeness audit — three sources, reconciled
The Wayback index alone is **not** a complete inventory. Three independent methods:

| Source | Method | Yields |
|---|---|---|
| **A** | CDX post list | 933 post URLs |
| **B** | prev/next chain walk from each known post | posts absent from the index |
| **C** | walk `/YYYY/MM/page/N/` links inside the 33 captured date archives | complete per-month listings |

Source B is exhaustive by construction — every post links to both neighbours, so
walking the chain from any seed traverses the whole blog. Source C cross-checks it.

Output `_reports/completeness.md`: the union of all discovered post URLs, which
source(s) found each, and the definitive post count. Anything discovered but not
archived is logged as a **named, dated gap** — we know it existed and we say so.

### Phase 3 · Feed analysis — **assumption corrected**
> **Outcome: the feeds are comment feeds, not content feeds.** All 851 per-post
> feeds are WordPress *comment* feeds with **no `<item>` elements and no post
> text**. The planned content-recovery path does not exist. They are still worth
> keeping, and they did independently confirm the site's final state: 821 feeds
> carry `lastBuildDate` of `Wed, 03 Jul 2013 01:46:28 +0000`, matching the newest
> post exactly and confirming the blog stopped publishing in July 2013.

What they actually contribute: independent confirmation that 821 posts existed,
219 reader comments, and 150 posts referenced via `#comment-NNNN` permalinks —
**zero** posts outside the Phase 2 inventory, so they cannot close the 3-post gap.
Jetpack comment and content feeds are indistinguishable in a URL listing; only
fetching one settles it. See `_reports/feeds.md`.

### Phase 4 · Polite, resumable fetch
For each manifest entry, fetch:

```
https://web.archive.org/web/{timestamp}id_/{original_url}
```

The `id_` modifier returns the **raw original bytes with no Wayback toolbar or
banner injection**. This is the single decision that makes pixel fidelity possible —
the default replay view injects an iframe toolbar and rewrites every asset URL.

Crawler requirements:

- ~1 request/second, 2–3 workers, exponential backoff, long timeouts.
- Honour 429/503 with extended sleeps.
- **Resumable**: content-addressed `_cache/` keyed by URL + digest. Re-runs skip
  what is already fetched. Mandatory, not optional.
- Run in background. **Expect 3–5 hours** for ~3,500 files.

> Observed during recon: the Internet Archive returned *Connection refused* after
> ~20 rapid requests, and *Temporarily Offline* during one probe. Aggressive
> crawling risks an IP ban and permanent loss of access. Politeness is not
> optional.

### Phase 5 · Verification
Check every cached file against its CDX `digest` and `length`. Report mismatches.
The `id_` endpoint occasionally returns a truncated or error body under load; this
gate catches it before it reaches the output tree.

### Phase 6 · Filename mapping
**The landmine.** Slugs contain Cyrillic, Japanese, and geometric Unicode —
`◒` `◇` `◈` `■` `†` `•` `–` — e.g.
`/%E2%96%BC%E2%96%B2%E2%96%BC-vagina-vangi-orthodox-2/`.

macOS APFS is **case-insensitive and Unicode-normalising**, so writing these
verbatim will silently collide and corrupt.

Mitigation:

1. Unicode-normalise (NFC) the decoded slug.
2. Append `-` + 6-char blake2b of the **original percent-encoded path**.
3. **Dry-run the collision check across all ~3,500 URLs before writing a single
   byte.**

Layout: `<dir>/index.html` for pages; original extensions for assets.

Emit `_work/filename-map.csv` (original URL ↔ local path) — needed by Phase 7 and
by anyone auditing the build later.

### Phase 7 · Link rewriting + asset reconciliation
Rewrite **only same-origin** references — `http://negativeyouth.net/…`,
`https://negativeyouth.net/…`, protocol-relative `//negativeyouth.net/…` —
from absolute to root-relative local paths, using the filename map.

Covers: `href`, `src`, `srcset`, `<link>`, `<script>`, inline
`style="background:url(...)"`, and `url()` inside the downloaded stylesheets.

**Leave external URLs completely untouched** (§3.2, §3.5).

Rewrite unconditionally, whether or not the target file is in cache (§3.4).

Then reconcile: diff every local asset referenced by downloaded HTML/CSS against
what was actually fetched; backfill misses from Wayback via closest-capture lookup.
Emit `_reports/missing-assets.md`. A failed backfill is a **no-op on the markup** —
reported only (§3.3).

**Hard assertion gate:** zero occurrences of `web.archive.org` or
`web-static.archive.org` anywhere in `site/`, excluding the deliberate provenance
footer links.

### Phase 8 · Regenerate what was never captured
Using the captured date/tag/category pages as pixel-faithful templates, plus the
preserved homepage (§3.1):

- `/index.html` and `/page/2/` … `/page/N/` — `posts_per_page=5`
- Every missing `/YYYY/MM/page/N/`
- Any tag / category / author page that exists in post metadata but was not captured
  (128 tags captured; the posts reference more)

A listing entry's body is the post's own `.entry-content`, copied verbatim from
the post's captured page, running from the `entry-content` div to the theme's
`<!-- .post -->` marker. **Do not "tidy" that region.** Two earlier attempts
both damaged it, and the damage is invisible in a diff but obvious in a browser:

- A div-depth scan for the end of the body ran past the post into the sidebar,
  because these posts carry markup inside HTML comments and attribute values
  where the tags do not balance in the raw text.
- A regex removing the share buttons ran from the share div to the next `<hr>`.
  The share block sits *inside* the post's three-column table, so that range
  swallowed `</h3></td>`, the metadata column and `</tr></tbody></table>`.
  Each entry was left holding an open `<table>`, so the browser pulled every
  following post into the previous post's table.

The share buttons are not tidied away: the captured 2013-06 archive contains
them inside its own entries, so the theme rendered them on archive pages too.

Every generated entry is checked for block balance before the tree is reported
as good (§6). An unclosed `div`/`table`/`tr`/`td` swallows its siblings, so this
is a build gate, not a lint. Unclosed *phrasing* tags (`p`, `span`, `small`) are
counted but not fatal: the HTML parser closes them at the next block boundary,
and the 2013 theme genuinely emitted them unbalanced — several posts' metadata
column reads `Autor:<a>jc</a><p>Tags: ...` with no closing tag at all.

The one sanctioned edit to a captured body: surplus closing block tags are
dropped. `/occultdλnϟσ-ufomania-negative-youth-2013-3` ends its content with a
`</div>` after a `clear:both` spacer, giving 8 opens and 9 closes. The parser
discarded that token on the original page, but inside a generated listing it
would match the entry's own close and push the following posts out of `.hfeed`.
Deleting it removes a token the browser was ignoring anyway and adds no markup.

Two defects in this phase were invisible in the markup diff and only showed up
in a browser, so both are now build gates.

**The splice must resume at the `</div>` before the `#content` comment, not at
the comment.** The theme ends a listing with

```
…nav-below…
</div><!-- #content .hfeed -->     <- closes #content
</div><!-- #container -->          <- closes #container
<div id="primary" class="sidebar">
```

Splicing from the comment dropped that first `</div>`, so the line labelled
`#container` closed `#content` instead and left `#primary`, `#secondary` and
`#footer` **inside** `#container` — which the theme sets to `float:left;
width:0px`. The sidebars then could not sit beside the 704px content column: they
fell below it, the left one to x=-151, off the left edge of the page. Three
columns present, none of them in the right place.

The Feb 2015 homepage capture in `_provenance/` has the same missing `</div>`, so
the site's own final state really was laid out this way and matching it
byte-for-byte reproduced the breakage. The working captures — the 2013-06
template and the Nov 2013 `/page/2/` — both have the tag. Fidelity to the last
capture and fidelity to how the theme actually rendered are not the same thing,
and here they disagree. Gate: the region from `<div id="content">` to the
`<!-- #content` comment must be net-zero divs, and the closing markup must match
the template's byte-for-byte.

**Pagination direction follows the theme's CSS, not the labels in isolation.**
`.nav-next{float:right}` and `.nav-previous{float:left}`, and the site's last
surviving state agrees: the Feb 2015 homepage keeps `Siguiente posts »` (forward)
in `nav-next`. So forward is on the right, back on the left. Two places got this
wrong:

- The generated back-link was labelled `Older posts` while pointing at page N-1,
  which holds *newer* posts, and sat in the div meaning the opposite direction.
  Now `« Anterior`.
- The captured `/page/2/` has both divs swapped — `« Siguiente` (forward, page 3)
  in the left-floating `nav-previous`, `Anterior »` (back, page 1) in the
  right-floating `nav-next` — so a visitor read "Siguiente" on the left and
  "Anterior" on the right. `repair_nav_inversion()` in `06_rewrite.py` moves each
  link into the div its own label implies, keyed on the label and never on the
  href, so it cannot change a destination. It fires only on a pair whose labels
  prove the inversion, so the 1,053 post pages whose `nav-previous`/`nav-next`
  divs hold post titles are untouched. Two blocks repaired, both on `/page/2/`.

### Phase 9 · Provenance
Because this is an archival site, it must be honest about what it is:

- Footer on every page: capture timestamp + link to the original Wayback snapshot.
- `posts.csv` and `posts.json` — title, date, author, categories, tags, slug, local
  path, Wayback URL, digest. **This is the real archival artifact**: it makes the
  archive searchable and future-proof even if the HTML is lost again.
- `.htaccess`:
  - `DirectoryIndex index.html`
  - redirect map from the **original percent-encoded** paths to the new
    directories, so existing bookmarks and Wayback links still resolve
  - UTF-8 charset and cache headers

### Phase 10 · Build, measure, then choose a host
Emit `_reports/size.md`: total files, total bytes, largest files, breakdown.

Projected output:

```
1,116  HTML pages
  851  feeds
1,478  images
   45  css/js/fonts/other
  ~240  generated (pagination, missing archives)
──────
~3,730 files, ~237 MB
```

| Host | Limit | Verdict |
|---|---|---|
| **Cloudflare Pages** | 25,000 files, no practical size cap | Comfortable |
| **GitHub Pages** | 1 GB repo, 100 MB/file | Comfortable |
| **Bluehost shared** | inode caps commonly 2,000–5,000, varies by plan | **Borderline at ~3,730** |

227 MB of data is trivial for Bluehost's disk quota; the risk is purely **file
count**. Keeping the feeds (§3.5) consumed the obvious safety valve, so if Bluehost
balked the fallback is Cloudflare Pages, not trimming the archive.

Everything except the final deploy is host-agnostic — build once, measure, then
deploy.

---

### Deviations from the capture, and why

Three places where the output deliberately differs from the bytes the archive
returned. All three are recorded because each one looks like a fidelity bug to
anyone reading the diff later.

1. **Captured pages are never overwritten** (`08_generate.py`, `paginate()`).
   38 pages that the archive holds — `/page/2/`, `/category/musica/page/2/` and
   35 more — are left exactly as captured. The site changed its own markup over
   time: the captured `/page/2/` (Nov 2013) uses `<div id="wrapper"
   class="hfeed">`, `<h6 class="entry-title">` and a 705px baseline table with no
   `.entry-meta`, while the Feb 2015 homepage uses a bare `class="hfeed"`,
   `<h3>` and a 680px table. Both are authentic. The captured one is evidence.

2. **The generated homepage does not match the Feb 2015 homepage byte-for-byte**,
   even though it once did. That capture is missing the `</div>` that closes
   `#content`, which is why the original site's last state rendered with its
   sidebars collapsed below the content. Matching it exactly reproduced the
   breakage; matching the 2013 captures restores the working layout. The broken
   original is preserved in `_provenance/index.html`.

3. **`#respond` fragments are stripped** (`06_rewrite.py`,
   `strip_respond_fragment()`), at the site owner's request. `#respond` is
   WordPress's comment anchor and the theme points at it from three places on a
   post page; the target is a PHP form that cannot execute here, so all 6,851
   such links led nowhere. Only the fragment is removed, never the link, so
   `/post/index.html#respond` becomes `/post/index.html` and still resolves.
   Deliberately **kept**: the `id="respond"` attribute on the form itself, and
   the 92 `</div><!-- #respond -->` comments, which are the theme's closing
   markers in the same family as `<!-- #content -->` and `<!-- #container -->`
   and are invisible when rendered.

### Capture overrides

The manifest picks, per URL, the largest HTTP-200 payload from the content era.
That is right for "the most complete rendering of this post" and wrong for a
handful of pages where a later capture is the better representative.
`common.CAPTURE_OVERRIDES` pins those, keyed by `dedupe_key()`:

- `/about/` -> `20140317064132`. The default pick (2013-06-21) is 145 KB of which
  128 KB is sidebar widget markup; the pinned capture is 30 KB with a 14 KB
  sidebar. The page's own content is the same either way — 88% similar, the
  differences being the share-button widget the theme re-rendered between the
  two dates. The leaner capture is what the site was serving at the end.

An override changes *which* capture is used, never whether it is verified: the
pinned row goes through the same CDX digest check as everything else.

## 6. Verification gates

The build fails loudly rather than shipping a broken archive:

1. **Collision gate** — zero filename collisions in the Phase 6 dry run.
2. **Integrity gate** — every cached file matches its CDX digest/length (Phase 5).
3. **Purity gate** — zero `web.archive.org` / `web-static.archive.org` references
   in output, except deliberate provenance footer links.
4. **Link gate** — every internal link resolves to a file that exists; unresolved
   targets listed in the report rather than silently broken.
5. **Manifest gate** — output file count and byte totals within ±2% of the CDX
   length predictions.
6. **No-live-domain gate** — zero references to the live `negativeyouth.net`
   anywhere in `site/`.
7. **Sidebar-scope gate** — the region from `<div id="content">` to the
   `<!-- #content` comment is net-zero divs, and the closing markup is
   byte-identical to the template's. Otherwise `#primary`/`#secondary` end up
   inside the zero-width `#container` float and the three columns collapse.
8. **Block-balance gate** — every generated listing entry has balanced
   `div`/`table`/`tr`/`td`/`ul`/`ol`/`blockquote` tags, and a parser walk of
   every generated listing finds no post entry nested inside another and none
   left open. An unclosed block tag silently swallows the posts after it, which
   is invisible in a diff and obvious on screen, so this is checked at build time
   rather than by eye.

---

## 7. Running order

```bash
git init && git add tools/ && git commit -m "archival tooling"

python3 tools/01_manifest.py        # CDX → manifest.csv, classification
python3 tools/02_discover.py        # chain walk → completeness.md  ← REVIEW HERE
python3 tools/03_feeds.py           # RSS analysis (comment feeds, not content)

python3 tools/04_fetch.py           # background, 3–5 hrs, resumable
python3 tools/05_verify.py          # integrity gate
python3 tools/06_rewrite.py         # links + asset reconciliation
python3 tools/07_linkcheck.py       # internal link gate
python3 tools/08_generate.py        # homepage, pagination, missing archives, balance gate
python3 tools/09_provenance.py      # footers, posts.csv/json, build report  ← REVIEW HERE
```

`06_rewrite.py` clears and rebuilds `site/`, so it must finish **before**
`08_generate.py` runs. `09_provenance.py` is idempotent and runs last.

**Two human review points:** after Phase 2, when the true post count and the list of
known gaps are known; and after Phase 10, when the real file count decides the host.

Both fetch and rewrite phases are idempotent and resumable — re-running after an
interruption is always safe.

---

## 8. Design notes

- **Why `id_` and not the replay view.** The default Wayback view injects a toolbar
  iframe and rewrites every asset URL to `web.archive.org`. `id_` returns the
  original bytes untouched. Everything downstream depends on this.
- **Why a custom downloader instead of `wget --mirror`.** `wget` and `httrack` are
  not installed, and their defaults are far too aggressive for the Internet Archive.
  A polite, resumable, verifiable Python crawler is both safer and more
  auditable — and it leaves a provenance record, which `wget` does not.
- **Why the chain walk matters.** The CDX index is demonstrably incomplete. Trusting
  it alone would silently drop posts while producing an archive that looks complete.
  Three independent sources, reconciled, is the minimum for a defensible result.
- **Why feeds are kept.** They are a second content source (Phase 3) and a primary
  artifact in their own right. They are also the cheapest insurance against a
  future loss — a CSV of every post survives even if the HTML does not.
- **Why generated markup is copied, never tidied.** Every listing entry is built
  from the theme's own captured output, so the listing can only be as faithful
  as the extraction. Extraction is where the fidelity was lost: two plausible
  "cleanup" passes each removed real structure (see Phase 8 above), and both
  produced output that looked correct as a diff. The lesson generalises — on a
  mirror, a tag that renders is data, and a regex that "tidies" markup cannot
  tell the two apart. The balance gate exists because of it.
- **Why the four captures containing link-farm markup are kept as-is.** Four
  pages (`/nommo-ogo/`, `/later-fags/`, `/nin-x-david-lynch/`, `/tagged/gatekeeper/`)
  were captured in a May–June 2014 window where the site carried injected
  pharmaceutical link lists hidden by a `display:none` script. This is not a
  defect in the mirror: it is what those captures contain, and the archive's job
  is to reproduce the archive. The site owner's call was to keep it unchanged.
  Recorded here so the decision is not mistaken for an oversight later.
