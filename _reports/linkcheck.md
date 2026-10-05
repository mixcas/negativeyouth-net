# Phase 6b - Internal link check

Every same-origin reference in all **1,160** pages of `site/` was
resolved against the output tree: **1,087,212** references checked,
**19,051** unresolved.

Almost none of this is a defect. The archive never crawled the vast
majority of the site's generated views, and it never stored a single byte
of audio or video. The categories below make that concrete.

| Category | Unresolved refs | Distinct targets | Why |
|---|---:|---:|---|
| uncaptured post (sidebar widget) | 6,955 | 38 |  |
| tag page | 5,365 | 1,425 | only 143 of ~1,500 tags were captured by any crawler |
| WordPress PHP endpoint | 2,419 | 2 | cannot execute on static hosting |
| date archive | 2,027 | 43 | month archive beyond 2013-06 was never captured |
| trackback endpoint | 947 | 947 | XML-RPC pingback; was PHP, never captured |
| other | 481 | 163 |  |
| missing asset | 479 | 76 | thumbnail or file the archive never stored |
| Tumblr-era page | 198 | 107 | pre-WordPress URL, only a handful captured |
| audio / flash | 68 | 50 | NO media was ever archived by anyone |
| author page | 59 | 19 | same: most author pages were never crawled |
| category page | 40 | 18 | same: most category pages were never crawled |
| attachment or feed page | 7 | 7 | WordPress auto-generated view |
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

**163** distinct targets do not resolve and do not fit any known
category.

**None of them correspond to a page we hold.** Every one is a path the
archive never captured, so the rewrite is mapping it to a
deterministic local path that simply has no file behind it. That is
the intended behaviour for unrecoverable references, not a defect.

### Full list

| Target | Referenced |
|---|---:|
| `/wp-includes/js/l10n.js-qver-20101110-a46a72` | 104 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 15 |
| `/rss-d219a7/index.html` | 15 |
| `/kinder-dieser-stadt-7ad48e/index.html` | 14 |
| `/wp-content/plugins/jetpack/modules/widgets/widgets.css-qver-20120924-f632` | 9 |
| `/wp-content/plugins/download-monitor/page-addon/styles.css-qver-3.4.2-e881` | 9 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 9 |
| `/wp-content/plugins/jquery-archive-list-widget/jal.js-qver-3.4.2-e88135` | 9 |
| `/popisblack-d4b2b8/index.html` | 6 |
| `/glasspopcorn-interview-33d561/index.html` | 5 |
| `/_host-http-tag-maligna-51be8e/index.html` | 4 |
| `/_host-http-tags-vagina-vangi-4f6a39/index.html` | 4 |
| `/wp-content/plugins/really-simple-facebook-twitter-share-buttons/style.css` | 4 |
| `/wp-content/plugins/jquery-archive-list-widget/jal.js-qver-3.3.1-fdee51` | 4 |
| `/we-cant-stop-54ebb9/index.html` | 4 |
| `/rvver-a887e4/index.html` | 4 |
| `/blissedout-2c6f6c/index.html` | 3 |
| `/search-puro-instinct-be8373/index.html` | 3 |
| `/the-red-wing-4a640f/index.html` | 3 |
| `/serpent-remixes-gatekeeper-750e0b/index.html` | 3 |
| `/just-for-hits-richard-dawkins-feed-5b3a85/index.html` | 2 |
| `/jj-2-feed-dff869/index.html` | 2 |
| `/zola-jesus-en-mexico-2-feed-8f20af/index.html` | 2 |
| `/pictureplane-en-mexico-4-feed-c5b8ca/index.html` | 2 |
| `/planningtorock-the-knife-doorway-2-feed-6e6c5a/index.html` | 2 |
| `/dipset-trance-party-2-feed-c43860/index.html` | 2 |
| `/patrick-wolf-esta-de-vuelta-2-feed-7e7165/index.html` | 2 |
| `/angelina-pivarnick-im-hot-2-feed-5ffc52/index.html` | 2 |
| `/black-yellow-vs-green-yellow-2-feed-e43065/index.html` | 2 |
| `/entrevista-con-jewels-of-the-nile-mp3s-2-feed-730a7f/index.html` | 2 |
| `/jewelsofthenileinterview-0000e5/index.html` | 2 |
| `/pop-is-black-2-feed-af60fc/index.html` | 2 |
| `/holy-other-touch-2-feed-bb84e8/index.html` | 2 |
| `/unison-blood-blood-blood-2-feed-57fb46/index.html` | 2 |
| `/fotos-negative-babes-2-dbccc7/index.html` | 2 |
| `/geneva-jacuzzi-bad-moods-2-feed-e722be/index.html` | 2 |
| `/avalanche-slow-feed-1b0fbb/index.html` | 2 |
| `/la-ultima-fiesta-del-ano-2-feed-613d4f/index.html` | 2 |
| `/the-firm-feed-63dbdf/index.html` | 2 |
| `/myr-l3wyckøff-2-feed-eed2b6/index.html` | 2 |
| `/mas-nike7up-2-feed-54269a/index.html` | 2 |
| `/video-not-in-love-2-feed-68eaf4/index.html` | 2 |
| `/maluca-hector-2-feed-88f876/index.html` | 2 |
| `/mentira-mentira-turnaway-2-feed-d24cbe/index.html` | 2 |
| `/gif-mashup-2-feed-84ba01/index.html` | 2 |
| `/alexico-gordo-grande-y-marica-2-feed-755713/index.html` | 2 |
| `/hard-as-a-motherfucker-2-feed-497cf7/index.html` | 2 |
| `/all-american-orgy-2-feed-fbdcb3/index.html` | 2 |
| `/6-foot-7-foot-2-feed-1ad0ba/index.html` | 2 |
| `/inca-gold-2-feed-2afde2/index.html` | 2 |

_...and 113 more._

## What is not broken

- **No page we hold is referenced incorrectly.** Every post, page and
  archive page in the inventory resolves.
- **Zero references to the live `negativeyouth.net` survive** anywhere in
  the HTML, so a visitor cannot be sent to whoever holds the parked
  domain.
