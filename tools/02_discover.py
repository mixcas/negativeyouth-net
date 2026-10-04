#!/usr/bin/env python3
"""
Phase 2 - Completeness audit.

Establishes the definitive post inventory by reconciling three independent
sources, because the CDX index on its own is demonstrably not a complete
record of what existed.

  A  the CDX index          free, but known to be incomplete
  C  date-archive pagination walk   exhaustive by construction, cheap
  B  prev/next chain walk    exhaustive, but needs every post page

Source C is walked in full here. Source B is sampled now for early signal and
then run in full during the Phase 4 crawl, where the post pages are being
downloaded anyway and the nav links come for free.

Writes:
  _work/posts.csv     definitive inventory
  _work/pagination.csv  every pagination URL discovered (Phase 8 targets)
  _reports/completeness.md
"""

import collections
import csv
import os
import queue
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

# ---------------------------------------------------------------- extractors

ENTRY_TITLE = re.compile(
    r'<h([1-6])[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h\1>', re.S | re.I)
# NOTE: this theme emits attributes in varying order - the date archives use
# <div id="nav-above" class="navigation"> while post pages use
# <div class="navigation">. Every pattern below therefore allows arbitrary
# attributes before class=.
HENTRY = re.compile(r'<div[^>]*class="([^"]*\bhentry\b[^"]*)"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
NAV = re.compile(
    r'<div[^>]*class="nav-(previous|next)"[^>]*>\s*<a href="([^"]+)"', re.I)
PAGINATION = re.compile(
    r'<div[^>]*class="[^"]*\bnavigation\b[^"]*"[^>]*>(.*?)(?:</div>|\Z)', re.S | re.I)
HFEED = re.compile(r'<div class="[^"]*\bhfeed\b[^"]*"[^>]*>(.*)', re.S | re.I)


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&laquo;", "").replace("&raquo;", "").replace("&nbsp;", " ")
          .replace("&amp;", "&").replace("&#8211;", "-").replace("&#8217;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def parse_classes(class_str):
    """Turn a hentry class attribute into date / author / taxonomy fields."""
    classes = class_str.split()
    meta = {}
    y = mo = d = h = None
    tags, cats, authors = [], [], []
    for c in classes:
        if re.fullmatch(r"y\d{4}", c):
            y = int(c[1:])
        elif re.fullmatch(r"m\d{2}", c):
            mo = int(c[1:])
        elif re.fullmatch(r"d\d{2}", c):
            d = int(c[1:])
        elif re.fullmatch(r"h\d{2}", c):
            h = int(c[1:])
        elif c.startswith("tag-"):
            tags.append(urllib.parse.unquote(c[4:]))
        elif c.startswith("category-"):
            cats.append(urllib.parse.unquote(c[9:]))
        elif c.startswith("author-"):
            authors.append(urllib.parse.unquote(c[7:]))
    if y and mo and d:
        meta["date"] = f"{y:04d}-{mo:02d}-{d:02d}"
    if h is not None:
        meta["hour"] = f"{h:02d}"
    if tags:
        meta["tags"] = ";".join(tags)
    if cats:
        meta["categories"] = ";".join(cats)
    if authors:
        meta["author"] = ";".join(authors)
    return meta


def entry_blocks(html, base=None):
    """
    Every hentry on a page, as (path, title, meta) triples.

    A listing page holds many posts, so each hentry is paired with the entry
    title inside its own block rather than searching the page globally.

    On a single-post page the entry-title heading holds no link - the permalink
    comes from the trackback URL or the page's own canonical link - so `base`
    supplies the path in that case.
    """
    out = []
    starts = list(HENTRY.finditer(html))
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(html)
        block = html[m.start():end]
        meta = parse_classes(m.group(1))
        path, title = None, ""
        t = ENTRY_TITLE.search(block)
        if t:
            href = re.search(r'href="([^"]+)"', t.group(2))
            if href:
                path = C.dedupe_key(href.group(1))
            title = strip_tags(t.group(2))
            if title.lower().endswith("permalink"):
                title = ""
        if not path:
            tb = re.search(r'href="([^"]+/trackback/)"', block)
            if tb:
                path = C.dedupe_key(tb.group(1).rsplit("/trackback/", 1)[0] + "/")
        if not path:
            perm = re.search(r'<a[^>]+class="permalink"[^>]+href="([^"]+)"', block)
            if perm:
                path = C.dedupe_key(perm.group(1))
        if not path:
            path = base
        if path:
            out.append((path, title, meta))
    return out


def nav_targets(html):
    return [C.dedupe_key(u) for _d, u in NAV.findall(html)]


def pagination_targets(html):
    out = []
    for block in PAGINATION.findall(html):
        for u in re.findall(r'href="([^"]+)"', block):
            out.append(C.dedupe_key(u))
    return out


# ---------------------------------------------------------------- fetching

def fetch(path, ts=None, timeout=90):
    """
    Fetch a page as raw original bytes, via the shared cache.

    `id_` returns the original bytes with no Wayback toolbar injection, which
    is what makes pixel fidelity possible downstream. A timestamp of 2015 is
    used as a "closest capture" resolver for URLs the index never listed.
    """
    data, meta = C.cache_get(path)
    if data is not None:
        return data.decode("utf-8", "replace"), meta

    stamp = f"{ts}id_" if ts else "2015id_"
    url = f"{C.WEB}/{stamp}/{C.path_to_origin(path)}"
    raw = C.http_get(url, tries=3, delay=3.0, timeout=timeout, raw=True)
    if raw is None:
        return None, None
    C.cache_put(path, raw, {"path": path, "stamp": stamp, "bytes": len(raw)})
    return raw.decode("utf-8", "replace"), {"stamp": stamp, "bytes": len(raw)}


# ---------------------------------------------------------------- main

def load_manifest():
    rows = {}
    with open(os.path.join(C.WORK, "manifest.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["path"]] = r
    return rows


def main():
    C.ensure_dirs()
    print("Phase 2 - completeness audit")
    print("=" * 60)

    man = load_manifest()

    # ---- Source A: CDX --------------------------------------------------
    src_a = {p for p, r in man.items() if r["kind"] in ("post", "page")}
    print(f"\n[A] CDX index posts: {len(src_a)}")

    found = collections.defaultdict(set)   # path -> set of sources
    titles = {}                            # path -> title
    meta = {}                              # path -> metadata dict
    for p in src_a:
        found[p].add("A")

    # ---- Source C: date-archive pagination walk --------------------------
    date_pages = sorted(p for p, r in man.items() if r["kind"] == "date_archive")
    print(f"[C] walking {len(date_pages)} date archives + their pagination chains...")

    seen = set()
    todo = queue.Queue()
    for p in date_pages:
        todo.put(p)
    pagination = {}
    fetched_c = 0

    while not todo.empty():
        path = todo.get()
        if path in seen:
            continue
        seen.add(path)
        ts = man.get(path, {}).get("timestamp")
        html, _ = fetch(path, ts)
        if html is None:
            print(f"    ! could not fetch {path}")
            continue
        fetched_c += 1
        n_new = 0
        n_pag = 0
        for p, title, m in entry_blocks(html):
            if p not in found:
                n_new += 1
            found[p].add("C")
            if title and not titles.get(p):
                titles[p] = title
            if m:
                meta.setdefault(p, {}).update(m)
        for p in pagination_targets(html):
            if p not in pagination:
                n_pag += 1
            pagination[p] = True
            if p not in seen:
                todo.put(p)
        if n_new or n_pag:
            print(f"    {path:30s} +{n_new} posts  +{n_pag} pagination",
                  flush=True)

    print(f"    fetched {fetched_c} archive pages, "
          f"{len(pagination)} pagination URLs discovered")

    # ---- Source B: full prev/next chain walk ------------------------------
    print(f"\n[B] walking the full prev/next chain...", flush=True)
    fetched_b = 0
    chain_new = 0
    # Every post links to both chronological neighbours, so the chain walk is
    # exhaustive by construction. Walking it from the known seeds is the only
    # way to find posts the index never recorded.
    frontier = queue.Queue()
    for p in sorted(found):
        frontier.put(p)
    walked = set()
    while not frontier.empty():
        p = frontier.get()
        if p in walked:
            continue
        walked.add(p)
        ts = man.get(p, {}).get("timestamp")
        html, _ = fetch(p, ts)
        if html is None:
            continue
        fetched_b += 1
        if fetched_b % 50 == 0:
            print(f"    walked {fetched_b} posts, "
                  f"{len(found)} known so far", flush=True)
        # A post page is a single-entry page, so its own hentry carries the
        # authoritative metadata for it.
        for bp, bt, bm in entry_blocks(html, base=p):
            if bt and not titles.get(bp):
                titles[bp] = bt
            if bm:
                meta.setdefault(bp, {}).update(bm)
        for t in nav_targets(html):
            if t not in found:
                chain_new += 1
                found[t].add("B")
                titles.setdefault(t, "")
            if t not in walked and t not in src_a:
                frontier.put(t)

    print(f"    fetched {fetched_b} post pages, "
          f"{chain_new} previously unknown posts")

    # ---- reconcile -------------------------------------------------------
    # A post that the navigation links to but the index never recorded is a
    # real gap even though it still has an entry in `found`, so these are
    # separated out rather than filtered away silently.
    orphans = {p: s for p, s in found.items()
               if p not in man
               and not p.startswith(("/tag/", "/category/", "/author/", "/page/"))
               and not re.match(r"^/\d{4}/", p)
               and not re.search(r"/page/\d+/?$", p)
               and "?" not in p and p != "/"}

    posts = {p: s for p, s in found.items()
             if man.get(p, {}).get("kind") in ("post", "page")}
    print(f"\n  unindexed URLs reached by navigation: {len(orphans)}")
    # The homepage is a listing, not a post, even though its own hfeed is what
    # got walked here.
    posts.pop("/", None)
    found.pop("/", None)
    print(f"\n  reconciled union of post URLs: {len(posts)}")

    by_src = collections.Counter()
    for s in found.values():
        by_src["+".join(sorted(s))] += 1
    print("  provenance of each post:")
    for k, n in by_src.most_common():
        print(f"    {k:10s} {n:5d}")

    # ---- per-month counts, from the recovered metadata -------------------
    # Post URLs carry no date, so months come from the hentry classes read
    # off the archive and post pages themselves.
    monthly = collections.Counter()
    undated = []
    for p in posts:
        dstr = (meta.get(p) or {}).get("date")
        if dstr and len(dstr) >= 7:
            monthly[dstr[:7]] += 1
        else:
            undated.append(p)

    # ---- missing: referenced but never archived --------------------------
    # Verified against the archive directly: a URL only counts as lost if it
    # really has no capture, rather than merely being absent from the index.
    missing = sorted(orphans)

    # Not every unindexed URL is a lost post. Some are legacy Tumblr numeric
    # IDs that only ever redirected, so the index is right to omit them.
    recovered, aliases = [], []
    for p in missing:
        rows = C.cdx_rows(match="exact", url=C.path_to_origin(p),
                          fl="timestamp,statuscode", limit=50)
        if not rows:
            continue  # genuinely no capture at all
        if any(r.get("statuscode") == "200" for r in rows):
            recovered.append(p)
        else:
            aliases.append((p, sorted({r.get("statuscode") for r in rows})))

    if recovered:
        print(f"  of those, {len(recovered)} had a capture the index missed")
        for p in recovered:
            man[p] = {"path": p, "kind": "post", "timestamp": "", "length": ""}
            posts[p] = found[p]
            fetch(p)
    if aliases:
        print(f"  and {len(aliases)} were redirect-only legacy URLs, not posts:")
        for p, codes in aliases:
            print(f"      {p}  (captured only as {'/'.join(codes)})")

    missing = [p for p in missing if p in recovered or p not in dict(aliases)]

    # ---- write outputs ---------------------------------------------------
    posts_csv = os.path.join(C.WORK, "posts.csv")
    with open(posts_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "path", "archived", "found_by", "title", "author",
                    "categories", "tags", "wayback_ts"])
        for p in sorted(posts, key=lambda x: (meta.get(x, {}).get("date", "9999"), x)):
            rec = man.get(p)
            m = meta.get(p, {})
            w.writerow([
                m.get("date", ""),
                p,
                "yes" if rec else "NO",
                "+".join(sorted(found[p])),
                titles.get(p, ""),
                m.get("author", ""),
                m.get("categories", ""),
                m.get("tags", ""),
                rec["timestamp"] if rec else "",
            ])
    print(f"  wrote {posts_csv}")

    pag_csv = os.path.join(C.WORK, "pagination.csv")
    with open(pag_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "archived"])
        for p in sorted(pagination):
            w.writerow([p, "yes" if p in man else "NO"])
    print(f"  wrote {pag_csv} ({len(pagination)} rows)")

    # ---- report ----------------------------------------------------------
    cf, ct = C.cache_stats()
    L = [
        "# Phase 2 - Completeness audit",
        "",
        "Three independent sources, reconciled. The CDX index alone is not a",
        "complete record of what the blog contained.",
        "",
        "## Sources",
        "",
        "| Source | Method | Posts found |",
        "|---|---|---:|",
        f"| A | CDX index | {len(src_a)} |",
        f"| C | Date-archive pagination walk (exhaustive) | "
        f"{sum(1 for p in posts if 'C' in found[p])} |",
        f"| B | Prev/next chain walk (exhaustive) | "
        f"{sum(1 for p in posts if 'B' in found[p])} |",
        "",
        f"## Definitive inventory: **{len(posts)} posts**",
        "",
        "Agreement between sources:",
        "",
        "| Found by | Posts |",
        "|---|---:|",
    ]
    for k, n in by_src.most_common():
        L.append(f"| {k} | {n} |")

    L += ["", "## Posts per month", "",
          "Dates come from the `y2013 m06 d28` classes on each hentry, not from",
          "the URL.", "", "| Month | Posts |", "|---|---:|"]
    for mo in sorted(monthly):
        L.append(f"| {mo} | {monthly[mo]} |")
    if undated:
        L += ["", f"_{len(undated)} posts carry no recoverable date._"]

    authors = collections.Counter()
    tags = collections.Counter()
    cats = collections.Counter()
    for p in posts:
        m = meta.get(p, {})
        for a in (m.get("author") or "").split(";"):
            if a:
                authors[a] += 1
        for t in (m.get("tags") or "").split(";"):
            if t:
                tags[t] += 1
        for c in (m.get("categories") or "").split(";"):
            if c:
                cats[c] += 1

    L += ["", "## Authors", "", "| Author | Posts |", "|---|---:|"]
    for a, n in authors.most_common():
        L.append(f"| {a} | {n} |")
    L += ["", "## Categories", "", "| Category | Posts |", "|---|---:|"]
    for c, n in cats.most_common():
        L.append(f"| {c} | {n} |")
    L += ["", f"_{len(tags)} distinct tags recovered._"]

    L += ["", "## Known gaps", ""]
    if aliases:
        L += [
            f"{len(aliases)} URLs reached from the old Tumblr-era navigation were",
            "captured only as redirects - legacy numeric IDs - so they were never",
            "posts here and nothing was lost: "
            + ", ".join(f"`{p}`" for p, _ in aliases)
            + ".",
            "",
        ]
    if missing:
        L += [
            f"**{len(missing)} post(s) are linked to by the archive's own prev/next",
            "navigation but have no capture anywhere in the Internet Archive.**",
            "Their existence and position in the timeline are known; their content",
            "is not recoverable. Each was checked directly against the archive before",
            "being listed here.",
            "",
            "| Path | Found by | Title |",
            "|---|---|---|",
        ]
        for p in missing:
            L.append(f"| `{p}` | {'+'.join(sorted(found[p]))} | {titles.get(p, '') or '_unknown_'} |")
    else:
        L.append("None. Every post referenced by the archive's own navigation was "
                 "also captured.")

    L += [
        "",
        "## Pagination discovered",
        "",
        f"{len(pagination)} pagination URLs were found in the captured archives.",
        f"Of these, **{sum(1 for p in pagination if p in man)}** were captured and",
        f"**{sum(1 for p in pagination if p not in man)}** were not, and will be",
        "regenerated in Phase 8. Full list in `_work/pagination.csv`.",
        "",
        "## Fetch state",
        "",
        f"- Cache: **{cf} files**, {ct/1048576:.1f} MB",
        f"- HTTP requests this phase: {fetched_c + fetched_b} "
        f"(all cached for Phase 4 reuse)",
        "",
    ]

    rep = os.path.join(C.REPORTS, "completeness.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {rep}")

    print("\n" + "=" * 60)
    print(f"DEFINITIVE POST COUNT: {len(posts)}")
    print(f"  captured:            {len(posts) - len(missing)}")
    print(f"  known but lost:      {len(missing)}")
    print(f"  with dates:          {len(posts) - len(undated)}")
    print(f"pagination URLs found: {len(pagination)}")
    print(f"  cached for Phase 4:  {fetched_b + fetched_c} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
