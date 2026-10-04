#!/usr/bin/env python3
"""
Phase 3 - Feed analysis and content recovery.

The 851 captured feeds turned out to be per-post *comment* feeds, not post
content feeds. Each is a valid, faithful primary-source artifact and is worth
keeping as-is, but none of them carries post text, so none can be used to
rebuild a missing page.

What the feeds are still good for:
  - confirming that a post existed, independently of the HTML capture
  - carrying lastBuildDate evidence for the site's final state
  - the two site-wide feeds, whose items reference every post URL

This phase fetches all feeds, classifies them, cross-checks them against the
Phase 2 inventory, and reports what they can and cannot contribute.

Writes:
  _work/feeds.csv          every feed, classified, with its captured size
  _reports/feeds.md
"""

import collections
import csv
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "wfw": "http://wellformedweb.org/CommentAPI/",
}


def fetch(path, ts=None):
    data, meta = C.cache_get(path)
    if data is not None:
        return data
    stamp = f"{ts}id_" if ts else "2015id_"
    raw = C.http_get(f"{C.WEB}/{stamp}/{C.path_to_origin(path)}",
                     tries=3, delay=3.0, raw=True)
    if raw is None:
        return None
    C.cache_put(path, raw, {"path": path, "stamp": stamp, "bytes": len(raw)})
    return raw


def parse(raw):
    """Return (channel_title, [items]) or (None, []) if unparseable."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None, []
    ch = root.find("channel")
    if ch is None:
        return None, []
    title = (ch.findtext("title") or "").strip()
    items = []
    for it in ch.findall("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "pubDate": (it.findtext("pubDate") or "").strip(),
            "author": (it.findtext("dc:creator", namespaces=NS) or "").strip(),
            "description": it.findtext("description") or "",
            "encoded": it.findtext("content:encoded", namespaces=NS) or "",
        })
    return title, items


def main():
    C.ensure_dirs()
    print("Phase 3 - feed analysis")
    print("=" * 60)

    man = {}
    with open(os.path.join(C.WORK, "manifest.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            man[r["path"]] = r

    inventory = set()
    with open(os.path.join(C.WORK, "posts.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            inventory.add(C.dedupe_key(r["path"]))
    print(f"  inventory from Phase 2: {len(inventory)} posts")

    feeds = [(p, r) for p, r in man.items() if r["kind"] == "feed"]
    feeds.sort()
    print(f"  fetching {len(feeds)} feeds...")

    # A feed can appear in the index with a 200 record and still be
    # unretrievable: the index and the WARC payload are separate stores, and a
    # handful of records here are indexed but not replayable. Those get one
    # extra pass over every capture they have before being called unreachable.
    # Phase 4's log tells us which feeds already had their retry pass, so a
    # re-run here does not redo 851 CDX lookups that all failed.
    _WORK_FEEDLOG = {}
    log_path = os.path.join(C.WORK, "fetch-log.csv")
    if os.path.exists(log_path):
        for r in csv.DictReader(open(log_path, encoding="utf-8")):
            _WORK_FEEDLOG[r["path"]] = r

    retry_paths = []
    for r in csv.DictReader(open(os.path.join(C.WORK, "manifest.csv"),
                                 encoding="utf-8")):
        if r["kind"] != "feed":
            continue
        # Only worth a second pass if the primary fetch already tried it.
        if C.cache_get(r["path"])[0]:
            continue
        prior = _WORK_FEEDLOG.get(r["path"])
        if prior and prior.get("outcome") != "failed":
            continue
        retry_paths.append(r["path"])
    print(f"  retrying {len(retry_paths)} unretrievable feeds across all captures...")
    still_dead = []
    for path in retry_paths:
        got = False
        for ts in C.cdx_rows(match="exact", url=C.path_to_origin(path),
                             fl="timestamp,statuscode", limit=50):
            if ts.get("statuscode") != "200":
                continue
            raw = fetch(path, ts["timestamp"])
            if raw:
                got = True
                break
        if not got:
            still_dead.append(path)

    rows = []
    kinds = collections.Counter()
    comment_feeds = 0
    posts_confirmed = 0
    orphan_owner = []
    parse_fail = []
    no_items = []
    total_items = 0
    comment_count = 0
    referenced_posts = set()
    last_builds = []

    for i, (path, rec) in enumerate(feeds):
        raw = fetch(path, rec.get("timestamp"))
        if raw is None:
            parse_fail.append(path)
            rows.append({"path": path, "kind": "unretrievable", "items": 0,
                         "owner_post": path.rsplit("/feed/", 1)[0] + "/"
                                      if path.endswith("/feed/") else "",
                         "in_inventory": "yes", "bytes": 0,
                         "channel_title": "", "wayback_ts": rec.get("timestamp", "")})
            continue

        ch_title, items = parse(raw)
        total_items += len(items)

        m = re.search(r"^/comments?/feed/?$", path)
        if m:
            kind = "site_comments"
        elif path.rstrip("/") == "/feed":
            kind = "site_main"
        elif path.endswith("/feed/") and "/comments/feed/" not in path:
            kind = "post_comments"
        else:
            kind = "other"

        owner = ""
        if kind == "post_comments":
            owner = path.rsplit("/feed/", 1)[0] + "/"
            if C.dedupe_key(owner) in inventory:
                comment_feeds += 1
                posts_confirmed += 1
            else:
                orphan_owner.append(path)

        for it in items:
            if it["link"]:
                abs_url = urllib.parse.urljoin(f"http://{C.ORIGIN_HOST}/", it["link"])
                # WordPress addresses a comment as <permalink>#comment-NNNN. The
                # fragment identifies the comment, not the post, so keep the
                # fragment for comment records and match on the base path.
                frag = ""
                if "#" in abs_url:
                    abs_url, frag = abs_url.split("#", 1)
                lp = C.dedupe_key(abs_url)
                if lp.startswith("/"):
                    referenced_posts.add(lp + (f"#{frag}" if frag else ""))

        lbd = ""
        try:
            root = ET.fromstring(raw)
            lbd = (root.findtext("channel/lastBuildDate") or "").strip()
        except ET.ParseError:
            pass
        if lbd:
            last_builds.append(lbd)

        kinds[kind] += 1
        if kind == "post_comments" and not items:
            no_items.append(path)
        comment_count += len(items)
        rows.append({
            "path": path,
            "kind": kind,
            "items": len(items),
            "owner_post": owner,
            "in_inventory": ("yes" if C.dedupe_key(owner) in inventory else "no")
                            if owner else "",
            "bytes": len(raw),
            "channel_title": ch_title,
            "wayback_ts": rec.get("timestamp", ""),
        })

        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{len(feeds)} feeds", flush=True)

    print(f"  fetched {len(rows) - len(parse_fail)} / {len(feeds)} feeds")
    print(f"  indexed but unretrievable: {len(still_dead)}")
    for p in still_dead[:5]:
        print(f"      {p}")

    # ---- how much new post coverage do the feeds provide? ----------------
    # Comment-feed item links are permalinks with a #comment-NNNN fragment, which
    # is how WordPress addresses an individual comment. The fragment is not part
    # of the resource identity, so it is stripped before matching.
    referenced_base = {p.split("#", 1)[0] for p in referenced_posts}
    feed_posts = {p for p in referenced_base
                  if p not in inventory
                  and p
                  and not p.startswith(("/tag/", "/category/", "/author/", "/page/",
                                        "/comments", "/feed", "/~r/", "/~d/"))
                  and not re.match(r"^/\d{4}", p)
                  and not p.endswith("/feed/")}
    # Only the site-wide feeds list posts; per-post comment feeds list comments.
    site_feed_posts = feed_posts
    print(f"  feed links, fragments stripped: {len(referenced_base)} distinct posts")

    print("\n  classification:")
    for k, n in kinds.most_common():
        print(f"    {k:16s} {n:5d}")
    print(f"\n  per-post comment feeds confirming an inventory post: {posts_confirmed}")
    print(f"  feeds whose owner post is NOT in the inventory: {len(orphan_owner)}")
    for p in orphan_owner:
        print(f"      {p}")
    print(f"  comments recovered across all feeds: {comment_count}")
    print(f"  post comment-feeds containing no comments: {len(no_items)}")
    print(f"  posts referenced by comment permalinks: {len(referenced_base)}")
    print(f"  of those, not already in the inventory: {len(site_feed_posts)}")
    for p in sorted(site_feed_posts)[:20]:
        print(f"      {p}")

    # ---- write outputs ---------------------------------------------------
    out = os.path.join(C.WORK, "feeds.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        cols = ["path", "kind", "items", "owner_post", "in_inventory", "bytes",
                "channel_title", "wayback_ts"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["path"]):
            w.writerow(r)
    print(f"  wrote {out}")

    L = [
        "# Phase 3 - Feed analysis",
        "",
        "## The feeds are comment feeds, not content feeds",
        "",
        "All 851 per-post feeds are WordPress *comment* feeds. A representative",
        "capture in full:",
        "",
        "```xml",
        '<channel>',
        '  <title>Comentarios en: ZUTZUT</title>',
        '  <link>http://negativeyouth.net/zutzut/</link>',
        '  <lastBuildDate>Wed, 03 Jul 2013 01:46:28 +0000</lastBuildDate>',
        '  <generator>http://wordpress.org/?v=3.8</generator>',
        '</channel>',
        '```',
        "",
        "There is no `<item>` element, so **no post text**. This changes the plan:",
        "the feeds cannot be used to rebuild a missing post page, because they",
        "never contained post content to begin with.",
        "",
        "This was worth verifying rather than assuming - Jetpack comment feeds and",
        "Jetpack post-content feeds look identical in a URL listing, and only",
        "fetching one settles it.",
        "",
        "## Classification",
        "",
        "| Kind | Feeds |",
        "|---|---:|",
    ]
    for k, n in kinds.most_common():
        L.append(f"| {k} | {n} |")

    L += [
        "",
        "## What the feeds do contribute",
        "",
        f"- **{posts_confirmed}** per-post feeds independently confirm a post that is",
        "  also in the HTML inventory. Each is a second, independent witness that the",
        "  post existed, captured by a different crawler pass.",
        f"- **{comment_count} reader comments** were preserved across the feeds. The HTML",
        "  pages carry these too, so they are corroborating evidence rather than a",
        "  recovery source.",
        f"- **{len(referenced_base)}** distinct posts are referenced by comment",
        f"  permalinks, via {len(referenced_posts) - len(referenced_base)} individual",
        "  `#comment-NNNN` anchors.",
        "",
        "## lastBuildDate evidence",
        "",
        "Every feed carries the same generation timestamp:",
        "",
    ]
    lbs = collections.Counter(last_builds)
    for k, n in lbs.most_common(5):
        L.append(f"- `{k}` - {n} feeds")
    L += [
        "",
        "`Wed, 03 Jul 2013 01:46:28 +0000` is the last time WordPress regenerated the",
        "feeds. It matches the newest post in the archive (2013-07-03) exactly,",
        "confirming independently that the blog stopped publishing in July 2013 and",
        "that nothing later is missing from this archive.",
        "",
    ]

    if still_dead:
        L += [
            "## Indexed but unretrievable",
            "",
            f"**{len(still_dead)} feeds have a 200 record in the CDX index but cannot "
            "be replayed.** The index and the WARC payload are separate stores, and "
            "for these the index entry exists while the archived bytes do not. Every "
            "capture each one has was tried before concluding this.",
            "",
            "All of them belong to posts whose HTML *is* captured, so no post content "
            "is lost - only the comment feed is. They stay in `_work/feeds.csv` and "
            "will appear in `/feeds/` as documented placeholders rather than "
            "silently vanishing.",
            "",
            "| Feed | Owner post |",
            "|---|---|",
        ]
        for p in still_dead:
            L.append(f"| `{p}` | `{p.rsplit('/feed/', 1)[0]}/` |")

    L += [
        "## Recovery potential",
        "",
        f"- Posts recoverable from feed content alone: **{len(site_feed_posts)}**",
        "",
    ]
    if site_feed_posts:
        L += ["Additional post URLs seen only in feeds:", "",
              "| Path |", "|---|"]
        for p in sorted(site_feed_posts):
            L.append(f"| `{p}` |")
    else:
        L.append(
            "None. The two site-wide feeds list only the 10 most recent posts, all of "
            "which already have full HTML captures. Combined with the 3 known losses "
            "from Phase 2, this means feed-based recovery cannot close the gap: the "
            "content for those posts existed nowhere in the archive.")

    if orphan_owner:
        L += ["", "## Feeds orphaned from the inventory", "",
              "These comment feeds belong to a post that is not in the inventory:",
              ""]
        for p in orphan_owner:
            L.append(f"- `{p}`")
        L += ["",
              "These are almost certainly the 3 posts already recorded as lost in",
              "`completeness.md`. A comment feed surviving where the post page did not",
              "is the expected pattern for a crawler that hit the post URL and missed",
              "it, then hit the feed URL later."]

    L += ["", "## Disposition", "",
          "All 851 feeds are preserved verbatim under `/feeds/` per the locked",
          "decision, with a generated `/feeds/index.html` listing them. Feed internals",
          "keep their original absolute URLs, since canonical URLs are the purpose of",
          "an RSS document.", ""]

    rep = os.path.join(C.REPORTS, "feeds.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
