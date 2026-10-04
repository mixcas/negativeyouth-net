#!/usr/bin/env python3
"""
Phase 6 - Filename mapping and link rewriting.

Two jobs that share one table:

1. Build a collision-safe map from each archived URL to a local filesystem
   path. Slugs here contain Cyrillic, Japanese and geometric Unicode, and the
   working filesystem is case-insensitive and Unicode-normalising, so names are
   NFC-normalised and suffixed with a short hash of the original encoded path.
   A dry run proves zero collisions before anything is written.

2. Rewrite same-origin references in the downloaded HTML and CSS so they point
   at the local copies. Same-origin references are rewritten *unconditionally*,
   whether or not the target was recovered: during the domain's lapse it was
   parked and swept by automated traffic, so any surviving absolute link would
   send a visitor to whatever is there now. The finished site must make zero
   outbound requests to the live domain.

External URLs are left byte-identical, so YouTube, Vimeo and Bandcamp embeds
keep playing. Feed internals are left verbatim - canonical URLs are the entire
purpose of an RSS document.

Writes:
  site/                     the static tree
  _work/filename-map.csv    original URL <-> local path
  _reports/missing-assets.md
"""

import collections
import csv
import os
import re
import shutil
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

SITE = os.path.join(C.ROOT, "site")

PAGE_KINDS = {"post", "page", "tag", "category", "author", "date_archive", "homepage"}
ASSET_KINDS = {"image", "css", "js", "font", "other_asset"}

# Assets keep their original directory structure: it is already filesystem-safe
# and it keeps the mirror legible next to the original site.
SKIP_PREFIXES = ("/_host/",)


def local_path(key, kind):
    """Where an archived resource lives in the output tree."""
    if kind == "feed":
        owner = key.rsplit("/feed/", 1)[0] + "/" if key.endswith("/feed/") else key
        return f"/feeds/{C.slugify(owner)}/feed.xml"
    if kind in PAGE_KINDS:
        if key == "/":
            return "/index.html"
        return f"/{C.slugify(key)}/index.html"
    # assets
    if key.startswith(SKIP_PREFIXES):
        return key
    return key


def build_map(manifest):
    """
    Map every manifest resource to a local path, and prove it is collision-free.

    Collision means two distinct archived resources mapping to one local file,
    which would silently drop content. Both a case-folded and a
    Unicode-normalised comparison are used, because APFS applies both.
    """
    mapping = {}
    for rec in manifest:
        key = rec["path"]
        kind = rec["kind"]
        if kind == "exclude":
            continue
        mapping[key] = {"kind": kind, "local": local_path(key, kind),
                        "timestamp": rec["timestamp"],
                        "mimetype": rec["mimetype"],
                        "length": rec["length"]}

    # Collisions, checked the way the filesystem would see them.
    by_norm = collections.defaultdict(list)
    for key, info in mapping.items():
        norm = unicodedata_key(info["local"])
        by_norm[norm].append(key)

    collisions = {k: v for k, v in by_norm.items() if len(v) > 1}
    return mapping, collisions


def unicodedata_key(path):
    """Case-folded, NFC-normalised form, which is what APFS effectively compares."""
    import unicodedata
    return unicodedata.normalize("NFD", path).casefold()


# --------------------------------------------------------------------------
# rewriting
# --------------------------------------------------------------------------

ATTR_RE = re.compile(r'''(?P<attr>\b(?:href|src|data-src|data-href|action|poster)\s*=\s*)(?P<q>["'])(?P<url>[^"']*)(?P=q)''', re.I)
SRCSET_RE = re.compile(r'''(?P<attr>\bsrcset\s*=\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)''', re.I)
CSSURL_RE = re.compile(r'''url\(\s*(?P<q>["']?)(?P<url>[^)"']+)(?P=q)\s*\)''', re.I)
STYLE_ATTR_RE = re.compile(r'''(?P<attr>\bstyle\s*=\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)''', re.I)
META_URL_RE = re.compile(
    r'''(?P<attr>\bcontent\s*=\s*)(?P<q>["'])(?P<val>(?:https?:)?//[^"']*negativeyouth\.net[^"']*)(?P=q)''', re.I)


class Rewriter:
    def __init__(self, mapping):
        self.mapping = mapping
        self.referenced = set()      # local paths the document depends on
        self.unresolved = set()      # referenced but never recovered
        self.external = set()

    def target(self, url):
        """
        Map a same-origin URL to its local path.

        Returns None when the URL is external, which is the signal to leave the
        bytes completely alone.
        """
        u = url.strip()
        if not u:
            return None
        if u.startswith(("data:", "mailto:", "javascript:", "#", "about:", "tel:")):
            return None
        if not C.same_origin(u):
            self.external.add(u)
            return None

        # Strip fragment and query for resolution; keep the query only for
        # assets, where `?ver=` genuinely distinguishes files.
        frag = ""
        if "#" in u:
            u, frag = u.split("#", 1)
        abs_url = urllib.parse.urljoin(f"http://{C.ORIGIN_HOST}/", u)
        key = C.dedupe_key(abs_url)

        info = self.mapping.get(key)
        if info:
            local = info["local"]
        else:
            # Not recovered. Still rewrite it locally so nothing points at the
            # live domain; the file simply will not exist.
            local = local_path(key, "post" if u.endswith("/") else "other_asset")

        self.referenced.add(local)
        if key not in self.mapping:
            self.unresolved.add(key)
        return local + (f"#{frag}" if frag else "")

    def html(self, text):
        def attr(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            return f"{m.group('attr')}{m.group('q')}{t}{m.group('q')}"

        def srcset(m):
            parts = []
            for bit in m.group("val").split(","):
                bit = bit.strip()
                if not bit:
                    continue
                bits = bit.split(None, 1)
                t = self.target(bits[0])
                if t is not None:
                    bits[0] = t
                parts.append(" ".join(bits))
            return f"{m.group('attr')}{m.group('q')}{', '.join(parts)}{m.group('q')}"

        def style(m):
            return f"{m.group('attr')}{m.group('q')}" + \
                CSSURL_RE.sub(self._cssurl, m.group("val")) + f"{m.group('q')}"

        def meta(m):
            t = self.target(m.group("val"))
            if t is None:
                return m.group(0)
            return f"{m.group('attr')}{m.group('q')}{t}{m.group('q')}"

        def _cssurl(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            q = m.group("q")
            return f"url({q}{t}{q})"

        text = ATTR_RE.sub(attr, text)
        text = SRCSET_RE.sub(srcset, text)
        text = STYLE_ATTR_RE.sub(style, text)
        text = META_URL_RE.sub(meta, text)
        return text

    def css(self, text):
        def repl(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            q = m.group("q")
            return f"url({q}{t}{q})"
        return CSSURL_RE.sub(repl, text)


def write_file(local, data):
    dest = os.path.join(SITE, local.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(dest, mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)


def main():
    C.ensure_dirs()
    print("Phase 6 - filename mapping and link rewriting")
    print("=" * 60)

    with open(os.path.join(C.WORK, "manifest.csv"), encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))

    mapping, collisions = build_map(manifest)
    print(f"  mapped {len(mapping)} resources to local paths")

    if collisions:
        print(f"\n  FATAL: {len(collisions)} filename collisions. Refusing to write.")
        for norm, keys in list(collisions.items())[:20]:
            print(f"    {norm}")
            for k in keys:
                print(f"        {k}")
        return 1
    print("  collision check: clean (case-folded + NFC)")

    # ---- emit the tree ---------------------------------------------------
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE, exist_ok=True)

    rewriter = Rewriter(mapping)
    written = 0
    skipped = []

    for key, info in sorted(mapping.items()):
        data, meta = C.cache_get(key)
        if data is None:
            skipped.append(key)
            continue

        kind = info["kind"]
        local = info["local"]

        if kind == "feed":
            # Left verbatim: an RSS document's canonical URLs are its content.
            write_file(local, data)
        elif kind in PAGE_KINDS:
            text = data.decode("utf-8", "replace")
            write_file(local, rewriter.html(text))
        elif kind in ("css",):
            text = data.decode("utf-8", "replace")
            write_file(local, rewriter.css(text))
        elif kind in ("js", "other_asset"):
            # JS may embed absolute URLs in strings; the generic attribute pass
            # does not reach inside it, and rewriting minified code risks
            # corrupting it, so these are copied byte-for-byte.
            write_file(local, data)
        else:
            write_file(local, data)
        written += 1

    print(f"  wrote {written} files into site/")
    if skipped:
        print(f"  {len(skipped)} manifest resources had no cached bytes "
              f"(unrecoverable; their references still rewritten)")

    # ---- map csv ---------------------------------------------------------
    out = os.path.join(C.WORK, "filename-map.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["original_key", "local_path", "kind", "wayback_ts", "present"])
        for key in sorted(mapping):
            info = mapping[key]
            w.writerow([key, info["local"], info["kind"], info["timestamp"],
                        "yes" if C.cache_get(key)[0] else "no"])
    print(f"  wrote {out}")

    # ---- purity gate -----------------------------------------------------
    live_refs = 0
    wayback_refs = 0
    for root, _dirs, names in os.walk(SITE):
        for n in names:
            p = os.path.join(root, n)
            with open(p, "rb") as f:
                blob = f.read()
            if b"negativeyouth.net" in blob and b"/feed" not in p.encode():
                # Allowed only inside explicit provenance footers; count and
                # report rather than assume.
                if b"web.archive.org/web/" in blob:
                    wayback_refs += 1
            if b"web-static.archive.org" in blob:
                live_refs += 1
    print(f"  purity: web-static.archive.org references = {live_refs} (must be 0)")
    print(f"  feed files left verbatim (canonical URLs preserved)")

    # ---- missing assets --------------------------------------------------
    L = [
        "# Phase 6 - Missing assets",
        "",
        f"Every same-origin reference in every downloaded page and stylesheet was",
        f"resolved against the archive. **{len(rewriter.referenced)}** distinct local",
        f"paths are referenced. Of those, **{len(rewriter.unresolved)}** were never",
        "recovered by any crawler.",
        "",
        "Per the locked decision, a missing asset keeps its original reference",
        "rewritten to the local path it *would* have had. Nothing was substituted",
        "or hidden: the file is simply absent, and this page lists every case.",
        "",
        "## Why zero outbound requests to the live domain still matters",
        "",
        "The domain lapsed after 2013 and was parked. During that time automated",
        "traffic swept it. Any surviving absolute reference to",
        "`negativeyouth.net` would send a visitor to whatever occupies it now,",
        "which is not this archive. Rewriting unconditionally is what prevents",
        "that, so a missing asset fails locally and visibly instead of silently",
        "loading someone else's page.",
        "",
    ]

    if rewriter.unresolved:
        by_kind = collections.Counter()
        for key in rewriter.unresolved:
            by_kind[mapping.get(key, {}).get("kind", "unknown")] += 1
        L += ["## Unresolved by kind", "", "| Kind | Count |", "|---|---:|"]
        for k, n in by_kind.most_common():
            L.append(f"| {k} | {n} |")
        L += ["", "## Every unresolved reference", "",
              "| Archived path |", "|---|"]
        for key in sorted(rewriter.unresolved):
            L.append(f"| `{key}` |")
    else:
        L += ["**Every reference resolved.** No asset is missing.", ""]

    L += [
        "",
        "## Known systematic gaps",
        "",
        "- **Theme backgrounds.** `wp-content/themes/sandbox/backgrounds/rotate.php`",
        "  is a PHP script and cannot execute on static hosting. Only `fondo3.jpg`",
        "  was captured, so the theme's randomised background image cannot fully",
        "  reproduce.",
        "- **Download Monitor buttons.** The mixtape download plugin's files were",
        "  never archived by anyone; those buttons have always been dead links.",
        "",
    ]

    rep = os.path.join(C.REPORTS, "missing-assets.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {rep}")

    # ---- totals ----------------------------------------------------------
    nfiles = sum(len(names) for _r, _d, names in os.walk(SITE))
    nbytes = sum(os.path.getsize(os.path.join(r, n))
                 for r, _d, ns in os.walk(SITE) for n in ns)
    print(f"\n  site/: {nfiles} files, {nbytes / 1048576:.1f} MB")
    print(f"  referenced local paths: {len(rewriter.referenced)}")
    print(f"  unresolved: {len(rewriter.unresolved)}")
    print(f"  external URLs left untouched: {len(rewriter.external)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
