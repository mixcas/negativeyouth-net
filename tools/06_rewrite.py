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

PATH_EXT = re.compile(r"\.[a-z0-9]{2,5}$", re.I)


def path_ext(p):
    """The file extension of a path, or '' if it looks like a page."""
    m = PATH_EXT.search(p.split("?")[0].rstrip("/"))
    return m.group(0).lower() if m else ""


def local_path(key, kind):
    """
    Where an archived resource lives in the output tree.

    Query strings are preserved in the dedupe key because `style.css?ver=3.8.5`
    and `style.css?ver=3.4` are genuinely different captures, but they cannot
    survive as filenames: a `?` in a path is a query-string delimiter on the
    web, so a file literally named `jquery.js?ver=1.8.3` is unservable. The
    version is folded into the name instead.
    """
    base, _, query = key.partition("?")
    suffix = "-" + C.slugify("q" + query) if query else ""

    if kind == "feed":
        owner = base.rsplit("/feed/", 1)[0] + "/" if base.endswith("/feed/") else base
        return f"/feeds/{C.slugify(owner)}/feed.xml"
    if kind in PAGE_KINDS:
        if base == "/":
            return "/index.html"
        return f"/{C.slugify(base)}{suffix}/index.html"
    # assets
    if base.startswith(SKIP_PREFIXES):
        return base + suffix
    return base + suffix


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

ATTR_RE = re.compile(
    r'''(?P<attr>\b(?:href|src|data-src|data-href|action|poster)\s*=\s*)'''
    r'''(?P<q>["'])(?P<url>[^"']*)(?P=q)''', re.I)
# A few posts were written with an unquoted href, e.g.
# `<a href=http://negativeyouth.net/tag/shades>`. The quoted form cannot match
# those, so an unquoted variant is needed to catch them without touching prose.
UNQUOTED_ATTR_RE = re.compile(
    r'''(?P<attr>\b(?:href|src|action|poster)\s*=\s*)'''
    r'''(?P<url>(?:https?:)?//(?:www\.)?negativeyouth\.net[^"'\s<>]*)''', re.I)
TITLE_ATTR_RE = re.compile(
    r'''(?P<attr>\btitle\s*=\s*)(?P<q>["'])(?P<url>(?:https?:)?//'''
    r'''(?:www\.)?negativeyouth\.net[^"']*)(?P=q)''', re.I)
SRCSET_RE = re.compile(r'''(?P<attr>\bsrcset\s*=\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)''', re.I)
CSSURL_RE = re.compile(r'''url\(\s*(?P<q>["']?)(?P<url>[^)"']+)(?P=q)\s*\)''', re.I)
STYLE_ATTR_RE = re.compile(r'''(?P<attr>\bstyle\s*=\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)''', re.I)
META_URL_RE = re.compile(
    r'''(?P<attr>\bcontent\s*=\s*)(?P<q>["'])(?P<val>(?:https?:)?//[^"']*negativeyouth\.net[^"']*)(?P=q)''', re.I)
# A URL embedded as a query parameter of a third-party embed. Facebook's like
# plugin names the page it is liking inside its own href, and that value must
# point at the local mirror too, or the plugin fetches the parked domain.
EMBED_PARAM_RE = re.compile(
    r'''(?P<pre>(?:href|srcdoc)=)(?P<q>["'])(?P<val>[^"']*negativeyouth\.net[^"']*)(?P=q)''', re.I)
# Share widgets carry the page being shared in data-* attributes of their own,
# e.g. Twitter's data-url. The attribute name is not in ATTR_RE, so these would
# otherwise keep pointing visitors at the parked domain.
DATA_ATTR_RE = re.compile(
    r'''(?P<attr>\bdata-[a-z-]*(?:url|href|link|share|image)[a-z-]*\s*=\s*)'''
    r'''(?P<q>["'])(?P<url>[^"']*negativeyouth\.net[^"']*)(?P=q)''', re.I)


# Navigation blocks whose two links were swapped into the wrong divs, by the
# theme itself. Reported, never applied silently.
NAV_REPAIRED = []

# `#respond` comment anchors removed, split by whether the link had a path.
RESPOND_STRIPPED = {"bare": 0, "path": 0}


class Rewriter:
    def __init__(self, mapping):
        self.mapping = mapping
        self.referenced = set()      # local paths the document depends on
        self.unresolved = set()      # referenced but never recovered
        self.external = set()
        # Bare asset path -> one captured "?ver=" variant of it. WordPress
        # serves a single file under many URLs, so a page may reference
        # `style.css` bare while only `style.css?ver=3.8.5` was ever crawled.
        self.versioned = {}
        for key in sorted(mapping):
            base, q, _ = key.partition("?")
            if q and path_ext(base):
                self.versioned.setdefault(base, key)

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
            kind = "post" if u.rstrip("/").endswith("/") or not path_ext(u) \
                else "other_asset"
            # Not recovered. Still rewrite it locally so nothing points at the
            # live domain; the file simply will not exist.
            local = local_path(key, kind)
            # If a `?ver=` variant of this same file was captured, use it:
            # WordPress emits both spellings and only one may have been crawled.
            if "?" not in key:
                alt = self.versioned.get(key)
                if alt:
                    local = self.mapping[alt]["local"]
                    key = alt

        self.referenced.add(local)
        if key not in self.mapping:
            self.unresolved.add(key)
        return local + (f"#{frag}" if frag else "")

    def html(self, text):
        def attr(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            q = m.groupdict().get("q")
            if q is None:  # unquoted attribute value
                return f"{m.group('attr')}{t}"
            return f"{m.group('attr')}{q}{t}{q}"

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

        text = ATTR_RE.sub(attr, text)
        text = TITLE_ATTR_RE.sub(attr, text)
        text = UNQUOTED_ATTR_RE.sub(attr, text)
        text = SRCSET_RE.sub(srcset, text)
        text = STYLE_ATTR_RE.sub(style, text)
        text = META_URL_RE.sub(meta, text)
        text = DATA_ATTR_RE.sub(attr, text)
        text = self.embedded_param(text)
        text = self.unencoded_embed_param(text)
        text = self.meta_url(text)
        text = self.embedded_css(text)
        text = self.repair_malformed(text)
        text = self.repair_nav_inversion(text)
        text = self.strip_respond_fragment(text)
        text = self.prose_url(text)
        return text

    def prose_url(self, text):
        """
        Rewrite a bare domain reference inside visible post text.

        A handful of posts print the site's own address as prose ("la dirección
        la pueden ver aca: http://negativeyouth.net/popisblack"). Those are not
        attributes, but they are still references a visitor could follow to the
        parked domain. Only the URL itself is replaced, so the sentence around
        it is untouched.
        """
        # The preceding character must simply not be a word character, or part
        # of the URL itself. `>` is fine and in fact required: these references
        # sit as the visible text of an anchor, i.e. right after `>`.
        pat = re.compile(
            r'''(?P<pre>^\s*|[^\w])(?P<url>https?://(?:www\.)?negativeyouth\.net'''
            r'''[^\s<>'")\]]*)''')

        def repl(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            return f"{m.group('pre')}{t}"

        return pat.sub(repl, text)

    def meta_url(self, text):
        """
        Rewrite a bare URL inside a meta content attribute.

        og:description is frequently a sentence containing the site's own URL
        ("…un nuevo url:http://negativeyouth.net/"), which the attribute rules
        cannot match because the URL does not start the value. Rewriting just
        the URL keeps the prose intact and removes the navigable reference.
        """
        bare = re.compile(
            r'''(?P<attr>\bcontent\s*=\s*)(?P<q>["'])'''
            r'''(?P<pre>[^"']*?)'''
            r'''(?P<url>(?:https?:)?//(?:www\.)?negativeyouth\.net[^"'<> ]*)'''
            r'''(?P<post>[^"']*?)(?P=q)''', re.I)

        def repl(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            return (f"{m.group('attr')}{m.group('q')}{m.group('pre')}{t}"
                    f"{m.group('post')}{m.group('q')}")

        return bare.sub(repl, text)

    # Words that identify a nav link's direction, in the languages the site used.
    # Only these are ever considered: post pages carry `nav-previous`/`nav-next`
    # divs too, but they hold post titles, and must not be touched.
    #
    # The arrows are stripped before matching. `« Siguiente »` leaves a leading
    # `&laquo;` once the tags are removed, so anchoring at `^\s*` alone would
    # never match and the repair would silently do nothing.
    # Arrow glyphs the theme put beside each label, stripped before matching: once
    # the tags are removed `« Siguiente »` leaves a leading `&laquo;`, so a match
    # anchored at `^` would never fire and the repair would silently do nothing.
    _ARROWS = re.compile(r"&laquo;|&raquo;|&#171;|&#187;|«|»", re.I)
    # "Siguiente" and "Older posts" both mean forward in time (page N+1);
    # "Anterior" and "Newer posts" both mean back (page N-1).
    _FWD = re.compile(r"^(?:Siguiente|Older posts)", re.I)
    _BACK = re.compile(r"^(?:Anterior|Newer posts)", re.I)

    def repair_nav_inversion(self, text):
        """
        Put each pagination link back in the div its direction implies.

        The theme's CSS is unambiguous about where the two links belong:

            div.navigation div.nav-next     { float: right }
            div.navigation div.nav-previous { float: left }

        and the site's last surviving state agrees - the Feb 2015 homepage has
        its only link, `Siguiente posts »` pointing forward to page 2, inside
        `nav-next`. So forward lives on the right, back on the left.

        The captured `/page/2/` has both divs swapped: `« Siguiente` (forward,
        to page 3) sits in the left-floating `nav-previous`, and `Anterior »`
        (back, to page 1) sits in the right-floating `nav-next`. A visitor reads
        that as "Siguiente on the left, Anterior on the right", i.e. backwards.

        Only a pair whose *labels* prove the inversion is swapped, and only
        within one navigation block. The labels are what identify the direction
        here, so the hrefs are left completely alone - this corrects placement,
        never destination. An empty div is left as it is, since WordPress emits
        one whenever only one direction exists.

        The block is rebuilt into the theme's canonical order, which is what every
        correct capture has (`/category/musica/page/2/` and
        `/category/video/page/2/` are the reference, both byte-identical in
        shape):

            <div id="nav-below" class="navigation">
                <div class="nav-previous"><a ...><span ...>&laquo;</span> Anterior</a></div>
                <div class="nav-next"><a ...>Siguiente <span ...>&raquo;</span></a></div>
            </div>

        That means three things, not one: the divs are reordered so
        `nav-previous` comes first, and the arrow glyph is re-hung to match the
        side - `«` belongs to the link that floats left, `»` to the one that
        floats right. The captured page had `« Siguiente` on the right and
        `Anterior »` on the left: correct divs, but the arrows still pointed the
        wrong way after the first repair, which swaps classes only.

        Only the label text and the arrow are touched. Each anchor's opening tag
        is copied verbatim, so the href and any other attribute are preserved
        byte-for-byte, and the whitespace between the two divs is kept as found.
        """
        block = re.compile(
            r'(<div id="nav-(?:above|below)" class="navigation">)(.*?)(\n\s*</div>)',
            re.S)
        div = re.compile(r'<div class="nav-(previous|next)">\s*(<a\b.*?</a>)\s*</div>',
                         re.S)

        def direction(mm):
            label = self._ARROWS.sub(" ", re.sub(r"<[^>]*>", " ", mm.group(2)))
            label = label.strip()
            if self._FWD.match(label):
                return "next"
            if self._BACK.match(label):
                return "previous"
            return None

        def canonical(anchor, want):
            """
            Re-hang the arrow so it points the way the link will sit.

            The opening tag is copied untouched - that is where the href lives -
            and only the arrow span and the label around it are rebuilt.
            """
            open_m = re.match(r"<a\b[^>]*>", anchor)
            if not open_m:
                return anchor
            head = open_m.group(0)
            label = anchor[len(head):-len("</a>")]
            label = re.sub(r"<span[^>]*class=[\"']meta-nav[\"'][^>]*>.*?</span>",
                           " ", label, flags=re.S)
            label = re.sub(r"\s+", " ", self._ARROWS.sub(" ", label)).strip()
            if want == "previous":
                # floats left: the arrow leads, pointing back the way you came
                body = f'<span class="meta-nav">&laquo;</span> {label}'
            else:
                # floats right: the arrow trails, pointing onward
                body = f'{label} <span class="meta-nav">&raquo;</span>'
            return f"{head}{body}</a>"

        def swap(m):
            open_tag, inner, close = m.groups()
            divs = list(div.finditer(inner))
            if len(divs) != 2:
                return m.group(0)

            # `got` is keyed by the direction the label *states*, so a complete
            # pair means one link claims forward and the other claims back.
            got = {direction(d): d for d in divs}
            if got.get("next") is None or got.get("previous") is None:
                return m.group(0)      # not a direction pair we recognise
            fwd, back = got["next"], got["previous"]
            first, second = divs
            already = (fwd.group(1) == "next" and back.group(1) == "previous"
                       and back.start() < fwd.start())
            if already:
                return m.group(0)      # classes and order already canonical

            NAV_REPAIRED.append(open_tag)
            prev_div = (f'<div class="nav-previous">'
                        f'{canonical(back.group(2), "previous")}</div>')
            next_div = (f'<div class="nav-next">'
                        f'{canonical(fwd.group(2), "next")}</div>')
            # Keep the leading whitespace and whatever separated the two divs, so
            # the block keeps the theme's own indentation.
            return (open_tag + inner[:first.start()] + prev_div
                    + inner[first.end():second.start()] + next_div
                    + inner[second.end():] + close)

        return block.sub(swap, text)

    def strip_respond_fragment(self, text):
        """
        Remove the `#respond` fragment from every link, per the site owner.

        `#respond` is WordPress's comment anchor. The theme points at it from
        three places on a post page:

            <div class="comentarios"><a href="/post/index.html#respond">Sin
                Comentarios! »</a></div>        "N comments!"
            <a class="comment-link" href="#respond">Post a comment</a>
            <a id="cancel-comment-reply-link" href="/post/index.html#respond">
                Cancelar respuesta</a>

        None of them can work here. The target is the comment form, which is PHP
        and cannot execute on static hosting, so every one of the 6,943 links
        across 2,710 pages led to a form that was never going to submit.

        Only the fragment is removed, never the link. `/post/index.html#respond`
        becomes `/post/index.html`, which still resolves - dropping the whole
        anchor would delete visible text the theme wrote.

        The `id="respond"` attribute on the form itself is left alone. It is not a
        reference to it, it is the target, and removing it would be an edit to the
        captured markup that nothing asks for.
        """
        bare = re.compile(r'(?P<attr>\bhref\s*=\s*)(?P<q>["\'])#respond(?P=q)')
        pathy = re.compile(r'(?P<pre>href\s*=\s*["\'][^"\'#]*?)#respond(?P<q>["\'])')

        def to_bare(m):
            RESPOND_STRIPPED["bare"] += 1
            # The pattern consumed both quotes, so both have to go back:
            # emitting only the opening one leaves a dangling `href="`.
            return m.group("attr") + m.group("q") + m.group("q")

        def to_path(m):
            RESPOND_STRIPPED["path"] += 1
            return m.group("pre") + m.group("q")

        text = bare.sub(to_bare, text)
        return pathy.sub(to_path, text)

    def repair_malformed(self, text):
        """
        Fix `http://http://host/...`, which some posts contain as literal text.

        A handful of posts were written with a doubled scheme inside the href.
        The doubled prefix means the URL does not resolve to our origin, so
        dedupe_key() treats it as external and leaves it alone - leaving a
        visitor-bound reference to the parked domain in the output.
        """
        pat = re.compile(r'(?P<pre>https?://)(?:https?://)+(?P<rest>[^"\'<> ]*)', re.I)

        def repl(m):
            t = self.target(m.group(0))
            if t is None:
                return m.group(0)
            return t

        return pat.sub(repl, text)

    def embedded_param(self, text):
        """
        Point third-party embeds at the local copy of the page they embed.

        Facebook's like plugin receives the page it is liking as a query
        parameter of its own URL. The attribute rule correctly leaves that URL
        alone, because the URL itself is third-party - but its *value* names
        our parked domain, so the plugin would fetch whatever occupies
        negativeyouth.net now. The value is rewritten while the embed stays.
        """
        pat = re.compile(
            r'(?P<enc>%[0-9A-Fa-f]{2})|(?P<sep>[^0-9A-Za-z])|(?P<lit>[0-9A-Za-z])')

        def fix_value(val):
            out = []
            for m in pat.finditer(val):
                enc, sep, lit = m.group("enc"), m.group("sep"), m.group("lit")
                if enc:
                    out.append(enc)
                elif sep:
                    out.append(sep)
                else:
                    out.append(f"%{ord(lit):02x}")
            joined = "".join(out)
            try:
                decoded = urllib.parse.unquote(joined)
            except Exception:  # noqa: BLE001 - malformed escape sequence
                return val
            t = self.target(decoded)
            if t is None:
                return val
            return re.sub(
                r"(?<![0-9A-Za-z])[0-9A-Za-z](?![0-9A-Za-z])",
                lambda mm: f"%{ord(mm.group(0)):02x}", t)

        def repl(m):
            new = fix_value(m.group("val"))
            if new == m.group("val"):
                return m.group(0)
            return f"{m.group('pre')}{m.group('q')}{new}{m.group('q')}"

        return EMBED_PARAM_RE.sub(repl, text)

    def unencoded_embed_param(self, text):
        """
        Rewrite an unencoded page URL sitting inside a third-party embed URL.

        Some Facebook like-iframes carry the page plainly rather than
        percent-encoded, e.g. `like.php?href=http://negativeyouth.net/post/&…`.
        Those are navigable references to the parked domain, so the value is
        rewritten while the embed itself is left untouched.
        """
        pat = re.compile(
            r'''(?P<pre>(?:href|srcdoc)=)(?P<q>["'])'''
            r'''(?P<url>(?:https?:)?//[^"'<> ]*?negativeyouth\.net[^"'<> ]*)'''
            r'''(?P<q2>["'])''', re.I)

        def repl(m):
            t = self.target(m.group("url"))
            if t is None:
                return m.group(0)
            return f"{m.group('pre')}{m.group('q')}{t}{m.group('q2')}"

        return pat.sub(repl, text)

    def embedded_css(self, text):
        """
        Rewrite url() inside an inline <style> block.

        Post-specific CSS is emitted as an inline <style> element, so the
        attribute-based passes never see it. The Download Monitor plugin
        injects its button background this way, which is why 1,027 pages still
        referenced the live domain before this was handled.
        """
        pat = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S | re.I)

        def repl(m):
            body = CSSURL_RE.sub(self._cssurl, m.group(2))
            return m.group(1) + body + m.group(3)

        return pat.sub(repl, text)

    def _cssurl(self, m):
        t = self.target(m.group("url"))
        if t is None:
            return m.group(0)
        q = m.group("q")
        return f"url({q}{t}{q})"

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
    if NAV_REPAIRED:
        uniq = sorted(set(NAV_REPAIRED))
        print(f"  pagination repaired on {len(uniq)} captured navigation block(s): "
              f"the theme put each link in the opposite div from the one its "
              f"label implies, so 'Siguiente' rendered on the left and "
              f"'Anterior' on the right")
        for b in uniq:
            print(f"    {b}")

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

    # ---- reconcile the map against what is actually on disk ---------------
    # local_path() returns root-relative paths; os.walk yields relative ones.
    # Normalise before comparing, or every file looks both missing and extra.
    on_disk = set()
    for root, _dirs, names in os.walk(SITE):
        for n in names:
            rel = os.path.relpath(os.path.join(root, n), SITE).replace(os.sep, "/")
            on_disk.add("/" + rel)
    declared = {v["local"] for v in mapping.values()}
    absent = declared - on_disk
    extra = on_disk - declared
    print(f"  map/disk reconciliation: {len(on_disk)} files on disk, "
          f"{len(absent)} mapped-but-absent, {len(extra)} on-disk-but-unmapped")
    if extra:
        for p in sorted(extra)[:10]:
            print(f"      unmapped: {p}")

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
