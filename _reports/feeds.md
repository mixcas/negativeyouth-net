# Phase 3 - Feed analysis

## The feeds are comment feeds, not content feeds

All 851 per-post feeds are WordPress *comment* feeds. A representative
capture in full:

```xml
<channel>
  <title>Comentarios en: ZUTZUT</title>
  <link>http://negativeyouth.net/zutzut/</link>
  <lastBuildDate>Wed, 03 Jul 2013 01:46:28 +0000</lastBuildDate>
  <generator>http://wordpress.org/?v=3.8</generator>
</channel>
```

There is no `<item>` element, so **no post text**. This changes the plan:
the feeds cannot be used to rebuild a missing post page, because they
never contained post content to begin with.

This was worth verifying rather than assuming - Jetpack comment feeds and
Jetpack post-content feeds look identical in a URL listing, and only
fetching one settles it.

## Classification

| Kind | Feeds |
|---|---:|
| post_comments | 821 |
| site_comments | 1 |
| site_main | 1 |
| other | 1 |

## What the feeds do contribute

- **821** per-post feeds independently confirm a post that is
  also in the HTML inventory. Each is a second, independent witness that the
  post existed, captured by a different crawler pass.
- **219 reader comments** were preserved across the feeds. The HTML
  pages carry these too, so they are corroborating evidence rather than a
  recovery source.
- **150** distinct posts are referenced by comment
  permalinks, via 59 individual
  `#comment-NNNN` anchors.

## lastBuildDate evidence

Every feed carries the same generation timestamp:

- `Wed, 03 Jul 2013 01:46:28 +0000` - 821 feeds
- `Thu, 04 Jul 2013 02:11:45 +0000` - 1 feeds
- `Fri, 13 May 2011 01:45:04 +0000` - 1 feeds

`Wed, 03 Jul 2013 01:46:28 +0000` is the last time WordPress regenerated the
feeds. It matches the newest post in the archive (2013-07-03) exactly,
confirming independently that the blog stopped publishing in July 2013 and
that nothing later is missing from this archive.

## Indexed but unretrievable

**27 feeds have a 200 record in the CDX index but cannot be replayed.** The index and the WARC payload are separate stores, and for these the index entry exists while the archived bytes do not. Every capture each one has was tried before concluding this.

All of them belong to posts whose HTML *is* captured, so no post content is lost - only the comment feed is. They stay in `_work/feeds.csv` and will appear in `/feeds/` as documented placeholders rather than silently vanishing.

| Feed | Owner post |
|---|---|
| `/actually-huizenga-live-softrock-1-3/feed/` | `/actually-huizenga-live-softrock-1-3/` |
| `/all-your-gifs-are-belong-to-us/feed/` | `/all-your-gifs-are-belong-to-us/` |
| `/bb-pinkblue/feed/` | `/bb-pinkblue/` |
| `/dont/feed/` | `/dont/` |
| `/evian-christ-no-experiences/feed/` | `/evian-christ-no-experiences/` |
| `/ez-does-it/feed/` | `/ez-does-it/` |
| `/gauntlet-hair-top-bunk/feed/` | `/gauntlet-hair-top-bunk/` |
| `/holy-other-love-some1-teengirl-fantasy-remix-featuring-kelela/feed/` | `/holy-other-love-some1-teengirl-fantasy-remix-featuring-kelela/` |
| `/icepunk-2-compilation/feed/` | `/icepunk-2-compilation/` |
| `/julia-holter-nite-jewel-what-we-see/feed/` | `/julia-holter-nite-jewel-what-we-see/` |
| `/king-night-rotterdam-terror-corps-remix/feed/` | `/king-night-rotterdam-terror-corps-remix/` |
| `/lost-in-my-bedroom/feed/` | `/lost-in-my-bedroom/` |
| `/mr-kitty-evaporating-sun/feed/` | `/mr-kitty-evaporating-sun/` |
| `/narcissistic-cannibal-ritualz-remix/feed/` | `/narcissistic-cannibal-ritualz-remix/` |
| `/opening-botiquin-by-petit-pistolette/feed/` | `/opening-botiquin-by-petit-pistolette/` |
| `/ritualz-alien/feed/` | `/ritualz-alien/` |
| `/selma-oxor-lo-que-quiero-video/feed/` | `/selma-oxor-lo-que-quiero-video/` |
| `/sky-ferreira-red-lips/feed/` | `/sky-ferreira-red-lips/` |
| `/soft/feed/` | `/soft/` |
| `/sorry-hun/feed/` | `/sorry-hun/` |
| `/spoek-mathambo-control-2/feed/` | `/spoek-mathambo-control-2/` |
| `/strain/feed/` | `/strain/` |
| `/tell-me/feed/` | `/tell-me/` |
| `/unicorn-kid/feed/` | `/unicorn-kid/` |
| `/volume-control/feed/` | `/volume-control/` |
| `/weekend-update/feed/` | `/weekend-update/` |
| `/zonora-point-douster-2/feed/` | `/zonora-point-douster-2/` |
## Recovery potential

- Posts recoverable from feed content alone: **0**

None. The two site-wide feeds list only the 10 most recent posts, all of which already have full HTML captures. Combined with the 3 known losses from Phase 2, this means feed-based recovery cannot close the gap: the content for those posts existed nowhere in the archive.

## Disposition

All 851 feeds are preserved verbatim under `/feeds/` per the locked
decision, with a generated `/feeds/index.html` listing them. Feed internals
keep their original absolute URLs, since canonical URLs are the purpose of
an RSS document.
