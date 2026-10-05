#!/usr/bin/env python3
"""
Phase 8 - Provenance, metadata, and the build report.

Three deliverables:

1. A provenance footer on every page, naming the capture it came from and
   linking to that snapshot. An archive that does not say where it got its
   bytes is indistinguishable from a fabrication.
2. `posts.csv` / `posts.json`, the machine-readable record of the whole blog.
   This is the artefact that survives if the HTML is ever lost again.
3. A size report, which settles the hosting question.

The footer is the only thing in the build that deliberately references
web.archive.org. Every other same-origin reference is local.
"""

import collections
import csv
import datetime as dt
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "r6", os.path.join(os.path.dirname(os.path.abspath(__file__)), "06_rewrite.py"))
_r6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r6)

SITE = os.path.join(C.ROOT, "site")

FOOTER_ID = "ny-archive-provenance"

FOOTER_CSS = """
<style type="text/css">
#ny-archive-provenance{clear:both;margin:2em 0 0;padding:14px 18px;
 border-top:1px solid #333;background:#111;color:#888;font:12px/1.5
 "Helvetica Neue",Helvetica,Arial,sans-serif;text-align:center}
#ny-archive-provenance a{color:#ff0179;text-decoration:none}
#ny-archive-provenance a:hover{text-decoration:underline}
#ny-archive-provenance .snap{font-family:Menlo,Consolas,monospace}
</style>
"""


def wayback_url(original_key, timestamp):
    if not timestamp:
        return ""
    key = original_key.split("?")[0]
    host = C.ORIGIN_HOST
    if key.startswith("/_host/"):
        host, _, rest = key[len("/_host/"):].partition("/")
        key = "/" + rest
    return f"https://web.archive.org/web/{timestamp}id_/http://{host}{key}"


def footer_for(original_key, timestamp, kind):
    """The provenance note for one page."""
    when = "unknown date"
    if timestamp and len(timestamp) == 14:
        try:
            d = dt.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
            when = d.strftime("%d %B %Y")
        except ValueError:
            pass

    if kind == "feed":
        what = "This feed is preserved byte-for-byte as the archive stored it."
    elif kind in ("post", "page", "tag", "category", "author", "date_archive",
                  "homepage"):
        what = "Page served from a capture of negativeyouth.net."
    else:
        what = "Resource served from a capture of negativeyouth.net."

    snap = wayback_url(original_key, timestamp)
    link = (f'<a href="{html.escape(snap, quote=True)}" rel="nofollow">'
            f'web.archive.org, {when}</a>') if snap else "the Internet Archive"

    return (
        f'<div id="{FOOTER_ID}">'
        f'{what} Archived by the Internet Archive on '
        f'<span class="snap">{html.escape(when)}</span> &mdash; '
        f'<a href="{html.escape(snap, quote=True)}" rel="nofollow">original '
        f'snapshot</a>.<br />'
        f'Restored as a static mirror. The original site no longer exists; '
        f'anything it linked to may be gone too.'
        f'</div>'
    )


def inject_footers():
    """Add the provenance footer to every HTML page in site/."""
    with open(os.path.join(C.WORK, "filename-map.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_local = {}
    for r in rows:
        if r["present"] == "yes":
            by_local[r["local_path"]] = r

    pages = [os.path.join(r, n)
             for r, _d, names in os.walk(SITE)
             for n in names if n.endswith(".html")]

    # Pages Phase 7 generated have no capture of their own; they are built
    # from the recovered inventory, so they say so rather than claiming a
    # capture that never existed.
    captured_locals = {r["local_path"] for r in rows if r["present"] == "yes"}
    generated_locals = {"/" + os.path.relpath(p, SITE).replace(os.sep, "/")
                        for p in pages} - captured_locals

    stats = collections.Counter()
    for p in pages:
        rel = "/" + os.path.relpath(p, SITE).replace(os.sep, "/")
        with open(p, encoding="utf-8", errors="replace") as f:
            doc = f.read()
        if FOOTER_ID in doc:
            stats["already"] += 1
            continue

        rec = by_local.get(rel)
        if rec:
            note = footer_for(rec["original_key"], rec["wayback_ts"], rec["kind"])
        else:
            note = (
                f'<div id="{FOOTER_ID}">'
                f'This page was never captured by the Internet Archive. It was '
                f'rebuilt from the archive of the original site so that its '
                f'links still resolve.<br />'
                f'Restored as a static mirror.'
                f'</div>'
            )
        stats["captured" if rec else "reconstructed"] += 1

        if FOOTER_CSS.strip() not in doc:
            doc = doc.replace("</head>", FOOTER_CSS + "</head>", 1)

        if "</body>" in doc:
            doc = doc.replace("</body>", note + "\n</body>", 1)
        else:
            doc = doc + "\n" + note

        with open(p, "w", encoding="utf-8") as f:
            f.write(doc)

    print(f"  footers: {stats['captured']} captured, "
          f"{stats['reconstructed']} reconstructed, {stats['already']} already done")
    return stats


def write_metadata():
    """posts.csv and posts.json - the durable record of the archive."""
    with open(os.path.join(C.WORK, "posts.csv"), encoding="utf-8") as f:
        posts = list(csv.DictReader(f))
    fmap = {}
    with open(os.path.join(C.WORK, "filename-map.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fmap[r["original_key"]] = r
    missing = {}
    if os.path.exists(os.path.join(C.WORK, "completeness.csv")):
        pass
    if os.path.exists(os.path.join(C.WORK, "lost-posts.csv")):
        with open(os.path.join(C.WORK, "lost-posts.csv"), encoding="utf-8") as f:
            missing = {r["path"]: r for r in csv.DictReader(f)}

    out = []
    for p in posts:
        key = C.dedupe_key(p["path"])
        rec = fmap.get(key, {})
        out.append({
            "title": p.get("title", ""),
            "date": p.get("date", ""),
            "author": p.get("author", ""),
            "categories": [c for c in (p.get("categories") or "").split(";") if c],
            "tags": [t for t in (p.get("tags") or "").split(";") if t],
            "original_path": p["path"],
            "local_path": rec.get("local_path", ""),
            "wayback_timestamp": rec.get("wayback_ts", ""),
            "wayback_url": wayback_url(key, rec.get("wayback_ts", "")),
            "recovered": p.get("archived", "") == "yes",
            "found_by": p.get("found_by", ""),
        })

    cols = ["date", "title", "author", "original_path", "local_path",
            "wayback_timestamp", "wayback_url", "categories", "tags",
            "recovered", "found_by"]
    csv_path = os.path.join(SITE, "posts.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            row = dict(r)
            row["categories"] = ";".join(r["categories"])
            row["tags"] = ";".join(r["tags"])
            w.writerow({k: row.get(k, "") for k in cols})
    print(f"  wrote posts.csv ({len(out)} posts)")

    json_path = os.path.join(SITE, "posts.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "site": C.ORIGIN_HOST,
            "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "source": "web.archive.org",
            "post_count": len(out),
            "posts": out,
        }, f, indent=1, ensure_ascii=False)
    print(f"  wrote posts.json")
    return out


def size_report(posts):
    """Measure the tree and settle the hosting question."""
    files = []
    for root, _d, names in os.walk(SITE):
        for n in names:
            p = os.path.join(root, n)
            files.append((p, os.path.getsize(p)))

    total_bytes = sum(s for _p, s in files)
    n_files = len(files)
    biggest = sorted(files, key=lambda x: -x[1])[:15]

    by_ext = collections.Counter()
    bytes_ext = collections.Counter()
    for p, s in files:
        e = os.path.splitext(p)[1].lower() or "(none)"
        by_ext[e] += 1
        bytes_ext[e] += s

    pages = sum(1 for p, _s in files if p.endswith(".html"))
    dirs = sum(1 for _r, d, _n in os.walk(SITE) for _x in d)

    mb = 1024 * 1024
    L = [
        "# Phase 8 - Build report",
        "",
        f"Measured {dt.datetime.now().strftime('%d %B %Y')}.",
        "",
        "## Size",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Files | **{n_files:,}** |",
        f"| Directories | {dirs:,} |",
        f"| Total size | **{total_bytes / mb:.1f} MB** |",
        f"| HTML pages | {pages:,} |",
        f"| Largest file | {biggest[0][1] / mb:.2f} MB |",
        "",
        "## By type",
        "",
        "| Type | Files | Size |",
        "|---|---:|---:|",
    ]
    for e, n in by_ext.most_common(12):
        L.append(f"| {e} | {n:,} | {bytes_ext[e] / mb:.2f} MB |")

    L += [
        "",
        "## Largest files",
        "",
        "| Size | Path |",
        "|---:|---|",
    ]
    for p, s in biggest:
        rel = "/" + os.path.relpath(p, SITE).replace(os.sep, "/")
        L.append(f"| {s / 1024:.0f} KB | `{html.escape(rel[:70])}` |")

    # ---- hosting --------------------------------------------------------
    cf_ok = n_files < 25000
    gh_ok = total_bytes < 1024 * mb
    bh_margin = n_files / 2000

    L += [
        "",
        "## Hosting",
        "",
        "| Host | Limit | This build | Verdict |",
        "|---|---|---|---|",
        f"| Cloudflare Pages | 25,000 files | {n_files:,} files, "
        f"{total_bytes / mb:.0f} MB | {'**fits comfortably**' if cf_ok else 'too many files'} |",
        f"| GitHub Pages | 1 GB repo, 100 MB/file | {total_bytes / mb:.0f} MB, "
        f"largest {biggest[0][1] / mb:.1f} MB | "
        f"{'**fits comfortably**' if gh_ok else 'too large'} |",
        f"| Bluehost shared | inode caps often 2,000-5,000 | {n_files:,} files "
        f"({bh_margin:.1f}x a 2,000 cap) | **borderline - measure first** |",
        "",
    ]

    if n_files > 2000:
        L += [
            f"At {n_files:,} files the build is over the file count that many shared",
            "hosting plans allow, and Bluehost's cap varies by plan. Disk space is a",
            "non-issue: the quota is measured in tens of gigabytes and this is",
            f"{total_bytes / mb:.0f} MB.",
            "",
            "If Bluehost refuses the upload, the fallback is Cloudflare Pages, which",
            "is comfortable at this size. Keeping the 851 feeds was the locked",
            "decision, and it is the main reason the file count is where it is.",
        ]
    else:
        L.append("The file count is within Bluehost's typical limit.")

    L += [
        "",
        "## Content",
        "",
        f"- **960 posts** recovered, 3 permanently lost",
        f"- **{sum(1 for p in posts if p['date'])}** posts carry a recovered date",
        f"- Spanning **{min((p['date'] for p in posts if p['date']), default='?')}** "
        f"to **{max((p['date'] for p in posts if p['date']), default='?')}**",
        "",
        "## Deploying to Bluehost",
        "",
        "```bash",
        "# from the project root",
        "rsync -av --delete site/ user@your-account.bluehost.com:~/public_html/",
        "```",
        "",
        "The tree resolves as directories, so no rewrite rules are needed for",
        "navigation. `.htaccess` carries 3,463 redirects from the original URLs so",
        "that old links and Wayback links still land in the right place.",
        "",
    ]

    rep = os.path.join(C.REPORTS, "build.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote _reports/build.md")
    print(f"\n  {n_files:,} files, {total_bytes / mb:.1f} MB, {dirs:,} directories")
    return n_files, total_bytes


def main():
    C.ensure_dirs()
    print("Phase 8 - provenance, metadata, build report")
    print("=" * 60)
    if not os.path.isdir(SITE):
        print("  site/ missing - run 06_rewrite.py first", file=sys.stderr)
        return 1

    inject_footers()
    posts = write_metadata()
    size_report(posts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
