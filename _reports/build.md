# Phase 8 - Build report

Measured 05 October 2026.

## Size

| Metric | Value |
|---|---:|
| Files | **5,149** |
| Directories | 3,743 |
| Total size | **610.9 MB** |
| HTML pages | 2,843 |
| Largest file | 3.66 MB |

## By type

| Type | Files | Size |
|---|---:|---:|
| .html | 2,843 | 406.17 MB |
| .jpg | 994 | 132.74 MB |
| .xml | 824 | 0.78 MB |
| .png | 322 | 38.79 MB |
| .jpeg | 73 | 13.87 MB |
| .gif | 37 | 16.24 MB |
| .ttf | 6 | 0.25 MB |
| .woff | 5 | 0.10 MB |
| .eot | 5 | 0.09 MB |
| .svg | 5 | 0.27 MB |
| .css | 3 | 0.02 MB |
| .1-90d1c0 | 3 | 0.01 MB |

## Largest files

| Size | Path |
|---:|---|
| 3747 KB | `/wp-content/uploads/2012/11/ALLYRGIFS700.gif` |
| 2964 KB | `/wp-content/uploads/2012/06/flyer_itsdangerous.gif` |
| 1555 KB | `/wp-content/uploads/2012/01/jochoDOOOOOM.gif` |
| 1480 KB | `/wp-content/uploads/2013/03/DIVASlol.gif` |
| 1343 KB | `/wp-content/uploads/2011/09/stage33d_yungjake1.gif` |
| 1231 KB | `/wp-content/uploads/2013/09/wallpaper.jpg` |
| 1129 KB | `/wp-content/uploads/2012/06/adeptus.png` |
| 995 KB | `/wp-content/uploads/2014/08/bg.jpg` |
| 994 KB | `/wp-content/uploads/2011/09/nahson_yungjake.gif` |
| 911 KB | `/wp-content/uploads/2012/11/artworks-000033828513-8brjui-original1.png` |
| 909 KB | `/wp-content/uploads/2011/10/nguzu21.gif` |
| 880 KB | `/wp-content/uploads/2012/06/pablitomix.jpeg` |
| 870 KB | `/wp-content/uploads/2012/09/mexico_bonsaibabies.jpg` |
| 870 KB | `/wp-content/uploads/2012/09/mexico_teehn_bwitches.jpg` |
| 867 KB | `/wp-content/uploads/2012/09/mexico_ritualz.jpg` |

## Hosting

| Host | Limit | This build | Verdict |
|---|---|---|---|
| Cloudflare Pages | 25,000 files | 5,149 files, 611 MB | **fits comfortably** |
| GitHub Pages | 1 GB repo, 100 MB/file | 611 MB, largest 3.7 MB | **fits comfortably** |
| Bluehost shared | inode caps often 2,000-5,000 | 5,149 files (2.6x a 2,000 cap) | **borderline - measure first** |

At 5,149 files the build is over the file count that many shared
hosting plans allow, and Bluehost's cap varies by plan. Disk space is a
non-issue: the quota is measured in tens of gigabytes and this is
611 MB.

If Bluehost refuses the upload, the fallback is Cloudflare Pages, which
is comfortable at this size. Keeping the 851 feeds was the locked
decision, and it is the main reason the file count is where it is.

## Content

- **960 posts** recovered, 3 permanently lost
- **949** posts carry a recovered date
- Spanning **2010-10-18** to **2013-07-03**

## Markup integrity of generated listings

**1,721** generated pages, **4,693** post entries, all structurally sound.

| Check | Result |
|---|---|
| Entries nested inside another entry | **0** |
| Entries left open at end of listing | **0** |
| `<table>` left unclosed at end of listing | **0** |
| Entries carrying the theme's 3-column table + metadata column | 4,693 / 4,693 |
| Entries with an unclosed phrasing tag (`p`, `span`, `small`) | 4,689 |

The phrasing-tag figure is inherited verbatim from the 2013 theme: several posts'
metadata column reads `Autor:<a>jc</a><p>Tags: ...` with no closing tag at all.
The HTML parser closes those at the next block boundary, so they cannot affect
layout, and repairing them would mean inventing markup the capture never had.

Surplus closing block tags were removed from **1** captured body
(`/occultdλnϟσ-ufomania-negative-youth-2013-3`), which the original page's parser
discarded but which would otherwise match a generated entry's own `</div>` and
push the following posts out of `.hfeed`. See `RESTORE.md` Phase 8.

This gate exists because of a real defect: an earlier extraction stripped the
share-button block out to the next `<hr>`, which swallowed `</tr></tbody></table>`
and left every entry holding an open table. Re-running the same check against
that extraction flags **948 of 948** dated posts.

## Deploying to Bluehost

```bash
# from the project root
rsync -av --delete site/ user@your-account.bluehost.com:~/public_html/
```

The tree resolves as directories, so no rewrite rules are needed for
navigation. `.htaccess` carries 3,463 redirects from the original URLs so
that old links and Wayback links still land in the right place.
