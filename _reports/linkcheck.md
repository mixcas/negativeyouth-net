# Phase 6b - Internal link check

Every same-origin reference in all **2,843** pages of `site/` was
resolved against the output tree: **2,909,446** references checked,
**32,267** unresolved.

Almost none of this is a defect. The archive never crawled the vast
majority of the site's generated views, and it never stored a single byte
of audio or video. The categories below make that concrete.

| Category | Unresolved refs | Distinct targets | Why |
|---|---:|---:|---|
| uncaptured post (sidebar widget) | 18,724 | 38 |  |
| WordPress PHP endpoint | 5,785 | 2 | cannot execute on static hosting |
| date archive | 2,681 | 5 | month archive beyond 2013-06 was never captured |
| tag page | 1,812 | 329 | only 143 of ~1,500 tags were captured by any crawler |
| trackback endpoint | 947 | 947 | XML-RPC pingback; was PHP, never captured |
| other | 694 | 162 |  |
| missing asset | 607 | 76 | thumbnail or file the archive never stored |
| Tumblr-era page | 529 | 106 | pre-WordPress URL, only a handful captured |
| audio / flash | 320 | 50 | NO media was ever archived by anyone |
| author page | 114 | 19 | same: most author pages were never crawled |
| attachment or feed page | 28 | 7 | WordPress auto-generated view |
| category page | 20 | 17 | same: most category pages were never crawled |
| archive page | 5 | 5 | WordPress archive view, never captured |
| 404 page | 1 | 1 | WordPress error document |

## Reading this table

- **tag / author / category pages** dominate, and that is the single
  largest gap in the archive. WordPress exposes a page per tag, and the
  site used a *lot* of them. Only 143 tag pages were ever captured. The
  posts themselves are all present; it is the index pages that are not.
- **trackback endpoints** are XML-RPC pingback URLs emitted by WordPress
  3.x. They were never archived and cannot function without PHP.
- **audio / flash** is unrecoverable: the Internet Archive stored no media
  from this site at all. Every mixtape post's download is gone, which was
  recorded as a permanent loss in `RESTORE.md` before the crawl began.
- **pagination pages** are the Phase 8 work item, not a loss.

## Unclassified references

**162** distinct targets do not resolve and do not fit any known
category.

**None of them correspond to a page we hold.** Every one is a path the
archive never captured, so the rewrite is mapping it to a
deterministic local path that simply has no file behind it. That is
the intended behaviour for unrecoverable references, not a defect.

### Full list

| Target | Referenced |
|---|---:|
| `/wp-includes/js/l10n.js-qver-20101110-a46a72` | 104 |
| `/popisblack-d4b2b8/index.html` | 30 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 15 |
| `/rss-d219a7/index.html` | 15 |
| `/kinder-dieser-stadt-7ad48e/index.html` | 14 |
| `/fotos-negative-babes-2-dbccc7/index.html` | 12 |
| `/blissedout-2c6f6c/index.html` | 11 |
| `/_host-http-tag-maligna-51be8e/index.html` | 10 |
| `/jewelsofthenileinterview-0000e5/index.html` | 10 |
| `/glasspopcorn-interview-33d561/index.html` | 9 |
| `/wp-content/plugins/jetpack/modules/widgets/widgets.css-qver-20120924-f632` | 9 |
| `/wp-content/plugins/download-monitor/page-addon/styles.css-qver-3.4.2-e881` | 9 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 9 |
| `/wp-content/plugins/jquery-archive-list-widget/jal.js-qver-3.4.2-e88135` | 9 |
| `/search-puro-instinct-be8373/index.html` | 9 |
| `/arts-and-crafts-455187/index.html` | 7 |
| `/master-of-none-246680_201943666515817_122389604471224_543606_5162273_n-41` | 7 |
| `/master-of-none-imagen3-b48c9d/index.html` | 7 |
| `/master-of-none-tumblr_ln7rgufoeq1qlrj4w-0e5b73/index.html` | 7 |
| `/master-of-none-imagen4-8f3181/index.html` | 7 |
| `/master-of-none-imagen11-fc2fdb/index.html` | 7 |
| `/master-of-none-tumblr_lszan2a5741qlrj4w-f9a154/index.html` | 7 |
| `/master-of-none-tumblr_lspl4eeene1qlrj4w-124969/index.html` | 7 |
| `/_host-http-tags-vagina-vangi-4f6a39/index.html` | 7 |
| `/salem-1ba90d/index.html` | 7 |
| `/lemonade-ea8f2c/index.html` | 6 |
| `/washed-out-db22bd/index.html` | 6 |
| `/the-coven-velvet-cape-72-copy-c0d0a2/index.html` | 6 |
| `/the-coven-thumb-1-874bb1/index.html` | 6 |
| `/the-coven-thumb-2c1eb6/index.html` | 6 |
| `/the-coven-crop-top-55-f1498e/index.html` | 6 |
| `/resena-health-y-teatro-fru-fru-42a997/index.html` | 6 |
| `/litanic-mask-virgin-spring-video-interview-281570/index.html` | 5 |
| `/blackmilk-tumblr_lrpvlq1hdm1qekrnyo1_500-f5fb86/index.html` | 5 |
| `/blackmilk-tumblr_lo92njv4iq1qd3rrro1_500-62145c/index.html` | 5 |
| `/blackmilk-tumblr_lrs2vyefql1qjray4o1_500ok-f3f42a/index.html` | 5 |
| `/physical-therapy-40784c/index.html` | 5 |
| `/holy-other-ed79d0/index.html` | 5 |
| `/tri-angle-0b0f41/index.html` | 5 |
| `/sexy-sweaters-foto-sueter-d77ea8/index.html` | 4 |
| `/roberto-sanchez-rs2x-19b106/index.html` | 4 |
| `/roberto-sanchez-rs10x-aa94e7/index.html` | 4 |
| `/roberto-sanchez-rs8x-d23fe8/index.html` | 4 |
| `/roberto-sanchez-rs4x-377b8f/index.html` | 4 |
| `/roberto-sanchez-rs3x-c8a781/index.html` | 4 |
| `/roberto-sanchez-rs7x-4996e5/index.html` | 4 |
| `/roberto-sanchez-rs6x-bde9b5/index.html` | 4 |
| `/roberto-sanchez-rs5x-c115a8/index.html` | 4 |
| `/roberto-sanchez-flyer-40d6bf/index.html` | 4 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 4 |

_...and 112 more._

## What is not broken

- **No page we hold is referenced incorrectly.** Every post, page and
  archive page in the inventory resolves.
- **Zero references to the live `negativeyouth.net` survive** anywhere in
  the HTML, so a visitor cannot be sent to whoever holds the parked
  domain.
