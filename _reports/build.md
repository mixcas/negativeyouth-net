# Phase 8 - Build report

Measured 05 October 2026.

## Size

| Metric | Value |
|---|---:|
| Files | **5,149** |
| Directories | 3,743 |
| Total size | **610.2 MB** |
| HTML pages | 2,843 |
| Largest file | 3.66 MB |

## By type

| Type | Files | Size |
|---|---:|---:|
| .html | 2,843 | 405.52 MB |
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
| Cloudflare Pages | 25,000 files | 5,149 files, 610 MB | **fits comfortably** |
| GitHub Pages | 1 GB repo, 100 MB/file | 610 MB, largest 3.7 MB | **fits comfortably** |
| Bluehost shared | inode caps often 2,000-5,000 | 5,149 files (2.6x a 2,000 cap) | **borderline - measure first** |

At 5,149 files the build is over the file count that many shared
hosting plans allow, and Bluehost's cap varies by plan. Disk space is a
non-issue: the quota is measured in tens of gigabytes and this is
610 MB.

If Bluehost refuses the upload, the fallback is Cloudflare Pages, which
is comfortable at this size. Keeping the 851 feeds was the locked
decision, and it is the main reason the file count is where it is.

## Content

- **960 posts** recovered, 3 permanently lost
- **949** posts carry a recovered date
- Spanning **2010-10-18** to **2013-07-03**

## Layout integrity of generated listings

**1,683** generated pages, **4,503** post entries, all structurally sound.

| Check | Result |
|---|---|
| Entries nested inside another entry | **0** |
| Entries left open at end of listing | **0** |
| `<table>` left unclosed at end of listing | **0** |
| `#content` region out of balance | **0** |
| Closing markup differing from the template | **0** |
| Entries carrying the theme's 3-column table + metadata column | 4,503 / 4,503 |

Measured in Chrome at 1280px, the three columns land where the theme's CSS puts
them: left sidebar `x=58`, content `x=271` (`margin-left:213px`), right sidebar
`x=999`, body `1150px` wide.

Two defects in this phase were invisible in a diff and only showed up in a
browser. Both are recorded in `RESTORE.md` §5 Phase 8:

1. **The splice dropped the `</div>` closing `#content`**, so the line labelled
   `#container` closed `#content` and left the sidebars inside `#container` —
   which the theme sets to `float:left; width:0px`. They fell below the content
   instead of beside it, the left one to x=-151. The Feb 2015 homepage capture in
   `_provenance/` has the same missing tag, so the site's own final state was
   laid out this way; matching it byte-for-byte reproduced the breakage.
2. **Pagination ran backwards.** The theme floats `.nav-next` right and
   `.nav-previous` left, and the Feb 2015 homepage keeps `Siguiente posts »`
   (forward) in `nav-next`. The generated back-link was labelled `Older posts`
   while pointing at *newer* posts, and the captured `/page/2/` had both divs
   swapped, so `Siguiente` rendered on the left and `Anterior` on the right. Two
   captured navigation blocks repaired; 1,053 post pages with `nav-next` holding
   post titles are untouched.

An unclosed phrasing tag (`p`, `span`, `small`) appears in 4,499 entries,
inherited verbatim from the 2013 theme: several posts' metadata column reads
`Autor:<a>jc</a><p>Tags: ...` with no closing tag at all. The HTML parser closes
those at the next block boundary, so they cannot affect layout, and repairing
them would mean inventing markup the capture never had.

Surplus closing block tags were removed from **1** captured body
(`/occultdλnϟσ-ufomania-negative-youth-2013-3`), which the original page's parser
discarded but which would otherwise match a generated entry's own `</div>`.

## Deploying to Bluehost

```bash
# from the project root
rsync -av --delete site/ user@your-account.bluehost.com:~/public_html/
```

The tree resolves as directories, so no rewrite rules are needed for
navigation. `.htaccess` carries 3,463 redirects from the original URLs so
that old links and Wayback links still land in the right place.
