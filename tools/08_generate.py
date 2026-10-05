#!/usr/bin/env python3
"""
Phase 7 - Generate the pages that were never archived.

The Internet Archive crawled the site but never generated the paginated views:
`/page/2/`, `/2012/05/page/2/`, and roughly 1,400 tag pages exist in the site's
own navigation but were never fetched. Rather than leave those links dead, they
are rebuilt here from the recovered inventory.

Fidelity comes from reusing the theme's own output as a template rather than
writing new markup. The captured date archives contain the exact `index.php`
loop the theme rendered, so an entry is assembled from a post's real captured
page: its title, its `.entry-content`, its `.entry-meta`. Nothing is invented.

The captured Feb 2015 homepage is copied to `_provenance/` before being
replaced, since it is the only source for the sidebar widgets.

Writes into site/:
  index.html, page/N/            homepage pagination
  YYYY/MM/page/N/                month archives, all pages
  YYYY/page/N/                   year archives
  category/X/ , tag/X/           taxonomy pages, all pages
  feeds/index.html               index of the 851 preserved feeds
  .htaccess                      pretty URLs + old-path redirects
"""

import collections
import csv
import datetime as dt
import hashlib
import html
import os
import re
import shutil
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "r6", os.path.join(os.path.dirname(os.path.abspath(__file__)), "06_rewrite.py"))
_r6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r6)

SITE = os.path.join(C.ROOT, "site")

# The original used WordPress's default of 5 posts per archive page; matching it
# keeps the pagination depth and the "Older posts" links faithful.
PER_PAGE = 5

CONTENT_OPEN = '<div id="content">'
# The theme closed this region two different ways across its lifetime: early
# pages say `<!-- #content -->` and later ones `<!-- #content .hfeed -->`. A
# template only matches one, so both are accepted. Splicing resumes at the
# comment, leaving the surrounding `</div>` that closes #content in place.
CONTENT_CLOSE = re.compile(r'<!--\s*#content[^>]*-->')

SPANISH_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                  "julio", "agosto", "septiembre", "octubre", "noviembre",
                  "diciembre"]


# --------------------------------------------------------------------------
# inventory
# --------------------------------------------------------------------------

class Post:
    __slots__ = ("key", "local", "title", "date", "hour", "author",
                 "categories", "tags", "month", "is_page")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def sort_key(self):
        # An undated item must sort last, not first. Sorting an empty date as a
        # high sentinel put the eleven static pages at the top of the homepage.
        return (self.date or "", self.key or "")


def load_inventory():
    with open(os.path.join(C.WORK, "posts.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fmap = {}
    with open(os.path.join(C.WORK, "filename-map.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fmap[r["original_key"]] = r

    posts = []
    for r in rows:
        key = C.dedupe_key(r["path"])
        rec = fmap.get(key)
        if not rec or rec["present"] != "yes":
            continue
        d = (r.get("date") or "").strip()
        posts.append(Post(
            key=key,
            local=rec["local_path"],
            title=(r.get("title") or "").strip(),
            date=d,
            hour=None,
            author=(r.get("author") or "").split(";")[0],
            categories=[c for c in (r.get("categories") or "").split(";") if c],
            tags=[t for t in (r.get("tags") or "").split(";") if t],
            month=d[:7] if len(d) >= 7 else "",
            # The Tumblr-era URLs (/about, /ask, /tagged/*) are static pages
            # with no publish date, not entries in the chronological loop.
            is_page=rec["kind"] == "page",
        ))
    posts.sort(key=lambda p: p.sort_key)
    return posts


TAG_RE = re.compile(r"<[^>]*>", re.S)

# Block tags whose imbalance changes layout, and the counts of surplus closing
# tags dropped from captured post bodies. Reported, never silently applied.
REPAIRED = []


def entry_body(post):
    """
    The post's own `.entry-content`, copied verbatim from its captured page.

    Reusing the real content is what makes a generated listing faithful: the
    embeds, the tables and the formatting are exactly what the theme served in
    2013, not something reconstructed.

    The body runs from the `entry-content` div to the theme's own
    `<!-- .post -->` marker. That region is self-balancing - verified as divs
    8/8 and tables 1/1 on every post checked - so it is copied untouched.

    Two earlier attempts to "tidy" this region both damaged it:

    - A div-depth scan for the end of the body ran on past the post into the
      sidebar, because these posts put markup inside HTML comments and
      attribute values, where the tags do not balance in the raw text.
    - A regex that removed the share buttons ran from the share div to the next
      `<hr>`. The share block sits *inside* the post's three-column table, so
      that range swallowed `</h3></td>`, the whole metadata column, and
      `</tr></tbody></table>`. Every generated entry was left holding an open
      `<table><tbody><tr><td><h3>`, so the browser pulled each following post
      into the previous post's table and the three-column layout collapsed.

    The share buttons are not tidied away: the captured 2013-06 archive listing
    contains them inside its own entries, so the theme was rendering them on
    archive pages too. Copying the region verbatim is both the simplest and the
    most faithful behaviour.
    """
    path = os.path.join(SITE, post.local.lstrip("/"))
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        doc = f.read()

    m = re.search(r'<div class="entry-content">', doc)
    if not m:
        return ""
    start = m.end()

    end = doc.find("<!-- .post -->", start)
    if end < 0:
        end = doc.find('<div class="entry-meta">', start)
    if end < 0:
        return ""

    body = doc[start:end]
    # Only a trailing run of </div>s belonging to the entry-content wrapper is
    # dropped. With the marker present the region ends at `<hr />` and this is a
    # no-op; without one, the wrapper's own closing tag would otherwise be
    # copied into the body.
    body = re.sub(r"(?:\s*</div>\s*)+\Z", "", body)
    return repair_stray_closes(body.strip(), post)


BLOCK_TAGS = ("div", "table", "tr", "td", "ul", "ol", "blockquote")


def repair_stray_closes(body, post=None):
    """
    Drop closing block tags the capture emitted more of than it opened.

    The 2013 theme's own markup is not always balanced. `/occultdλnϟσ...` ends
    its content with `</div>` after a `clear:both` spacer, giving the region 8
    `div` opens and 9 closes. On the original post page that surplus close had
    nothing left to match and the parser discarded it, so it changed nothing.
    Inside a generated listing it is not harmless: it matches the entry's own
    `</div>`, the hentry closes early, and every post after it falls out of
    `.hfeed` and loses the theme's CSS scoping.

    Deleting the surplus close is the smallest edit that fixes this - it removes
    a token the browser was ignoring anyway, and adds no markup of any kind. A
    region with *unclosed* blocks is left strictly alone and reported as fatal,
    since repairing that would mean inventing tags the capture never had.
    """
    for tag in BLOCK_TAGS:
        opens = len(re.findall(rf"<{tag}\b", body, re.I))
        surplus = len(re.findall(rf"</{tag}\s*>", body, re.I)) - opens
        if surplus <= 0:
            continue
        # Remove the surplus closes from the end backwards: the trailing ones are
        # the ones the parser would have ignored anyway.
        for _ in range(surplus):
            hits = list(re.finditer(rf"</{tag}\s*>", body, re.I))
            if not hits:
                break
            last = hits[-1]
            body = body[:last.start()] + body[last.end():]
        key = post.key if post is not None else "?"
        REPAIRED.append((key, tag, surplus))
    return body


def date_html(post):
    """`28/06/2013`, matching the theme's visible format."""
    if not post.date or len(post.date) < 10:
        return ""
    y, m, d = post.date[:4], post.date[5:7], post.date[8:10]
    return (f'<div class="entry-date"><abbr class="published" '
            f'title="{y}-{m}-{d}T00:00:00-0600">{d}/{m}/{y}</abbr></div>')


def meta_html(post):
    """
    The theme's `.entry-meta` line: author, categories, tags, comment count.

    Each part is joined by the theme's `meta-sep` pipe, and links are only
    emitted when the corresponding page exists locally, so a generated entry
    never points at a page that was never crawled.
    """
    parts = []
    sep = '<span class="meta-sep">|</span>'
    if post.author:
        al = LOCALMAP.get(_r6.local_path(f"/author/{C.dedupe_key(post.author)}/",
                                         "author"))
        if al:
            parts.append(
                f'<span class="author vcard">By <a class="url fn n" href="{al}" '
                f'title="View all posts by {html.escape(post.author)}">'
                f'{html.escape(post.author)}</a></span>')
    if post.categories:
        links = []
        for c in post.categories:
            cm = LOCALMAP.get(_r6.local_path(f"/category/{C.dedupe_key(c)}/",
                                             "category"))
            if cm:
                links.append(f'<a href="{cm}" '
                             f'title="Ver todas las entradas en '
                             f'{html.escape(c)}" rel="category tag">'
                             f'{html.escape(c)}</a>')
        if links:
            parts.append('<span class="cat-links">Posted in '
                         + ", ".join(links) + "</span>")
    if post.tags:
        links = []
        for t in post.tags:
            tm = LOCALMAP.get(_r6.local_path(f"/tag/{C.dedupe_key(t)}/", "tag"))
            if tm:
                links.append(f'<a href="{tm}" rel="tag">{html.escape(t)}</a>')
        if links:
            parts.append('<span class="tag-links">Tagged '
                         + ", ".join(links) + "</span>")
    return (sep + "\n\t\t\t\t\t").join(parts)


def entry_html(post):
    """One `<hentry>` in the theme's listing format."""
    esc = html.escape(post.title or "untitled")
    # The theme's own hentry class list carries the date, author, categories and
    # tags, and the stylesheet keys off them. Reproducing it keeps the listing
    # styled identically to a captured one.
    # The theme emitted `author-jc`, `category-video`, `tag-mp3` - lowercase,
    # percent-escaped, and *without* the hash suffix used for directory names.
    # The stylesheet selects on these, so slugify()'s output would silently
    # break the entry styling.
    def theme_token(value):
        return re.sub(r"[^a-z0-9\-_]+", "-", value.lower()).strip("-")

    classes = ["hentry", "p1", "post", "publish"]
    if post.author:
        classes.append("author-" + theme_token(post.author))
    for c in post.categories:
        classes.append("category-" + theme_token(c))
    for t in post.tags:
        classes.append("tag-" + theme_token(t))
    if post.date:
        y, mo, d = post.date[:4], post.date[5:7], post.date[8:10]
        classes += [f"y{y}", f"m{mo}", f"d{d}"]
    pid = "post-" + hashlib.blake2b(post.key.encode(), digest_size=3).hexdigest()

    body = entry_body(post) or "<p></p>"

    parts = [
        f'<div id="{pid}" class="{" ".join(classes)}">',
        f'\t\t\t\t<h3 class="entry-title"><a href="{post.local}" '
        f'title="Permalink to {esc}" rel="bookmark">{esc}</a></h3>',
        date_html(post),
        f'\t\t\t\t<div class="entry-content">',
        body,
        f'\t\t\t\t</div>',
        f'\t\t\t\t<div class="entry-meta">',
        meta_html(post),
        f'\t\t\t\t</div>',
        '\t\t\t</div><!-- .post -->',
    ]
    return "\n".join(parts)


def assert_balanced(entries):
    """
    Refuse to write a listing whose block structure does not balance.

    An unclosed block tag in one entry silently swallows every entry after it:
    a browser holds the tag open and nests the following posts inside it. That
    is exactly how a broken table in the post body went unnoticed until it was
    spotted in a browser, so the count is checked here rather than by eye.

    Only block containers are checked, and only an *unclosed* block is fatal. A
    surplus `</div>` is repaired upstream in `repair_stray_closes` rather than
    rejected, since the parser ignored it on the original page anyway.

    Unclosed phrasing tags - `p`, `span`, `a`, `small` - are closed implicitly by
    the HTML parser at the next block boundary and cannot swallow a sibling, and
    the 2013 theme genuinely emitted them unbalanced: several posts' metadata
    column reads `Autor:<a>jc</a><p>Tags: ...` with no closing tag at all.
    Failing on those would mean failing on a faithful copy, so they are counted
    and reported separately rather than treated as fatal.

    Returns (fatal, cosmetic) lists of (path, reason).
    """
    fatal = []
    cosmetic = 0
    for post, entry in entries:
        broke = None
        for tag in BLOCK_TAGS:
            opens = len(re.findall(rf"<{tag}\b", entry, re.I))
            closes = len(re.findall(rf"</{tag}>", entry, re.I))
            if opens != closes:
                broke = (post.key, f"{tag} {opens} open / {closes} close")
                break
        if broke:
            fatal.append(broke)
            continue
        for tag in ("p", "span", "small", "abbr"):
            opens = len(re.findall(rf"<{tag}\b", entry, re.I))
            closes = len(re.findall(rf"</{tag}>", entry, re.I))
            if opens != closes:
                cosmetic += 1
                break
    return fatal, cosmetic


def nav_html(base_path, page, total_pages):
    """`« Older posts` / `Siguiente posts »`, matching the theme's markup."""
    out = []
    if page > 1:
        prev = base_path if page == 2 else f"{base_path}page/{page - 1}/"
        prev = _r6.local_path(prev, "homepage")
        prev = LOCALMAP.get(prev, prev)
        out.append(f'<div class="nav-previous"><a href="{prev}" >'
                   f'<span class="meta-nav">&laquo;</span> Older posts</a></div>')
    if page < total_pages:
        nxt = f"{base_path}page/{page + 1}/"
        nxt = _r6.local_path(nxt, "homepage")
        nxt = LOCALMAP.get(nxt, nxt)
        out.append(f'<div class="nav-next"><a href="{nxt}" >Siguiente posts '
                   f'<span class="meta-nav">&raquo;</span></a></div>')
    if not out:
        return ""
    return ('<div id="nav-above" class="navigation">\n\t\t\t'
            + "\n\t\t\t".join(out) + "\n\t\t</div>")


IMBALANCE = []
COSMETIC = []


def paginate(items, base_path, title, page_title_html, extra_head=""):
    """Render every page of a listing."""
    total = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
    written = []
    for page in range(1, total + 1):
        chunk = items[(page - 1) * PER_PAGE: page * PER_PAGE]
        if page == 1:
            local = _r6.local_path(base_path, "homepage")
        else:
            local = _r6.local_path(f"{base_path}page/{page}/", "homepage")
        local = LOCALMAP.get(local, local)
        body = [page_title_html]
        nav = nav_html(base_path, page, total)
        if nav:
            body.append(nav)
        body.append('\t\t<div class="hfeed">')
        entries = [(p, entry_html(p)) for p in chunk]
        fatal, cosmetic = assert_balanced(entries)
        IMBALANCE.extend((base_path, page) + prob for prob in fatal)
        COSMETIC.append(cosmetic)
        body.extend(e for _p, e in entries)
        body.append("\t\t</div>")
        nav2 = nav_html(base_path, page, total)
        if nav2:
            body.append(nav2.replace("nav-above", "nav-below"))
        content = "\n".join(
            '\n\t\t' + b if b else '' for b in body) + "\n\t\t"
        written.append((local, render(content, extra_head)))
    return written


def render(content, extra_head=""):
    """Splice generated content into the captured page template."""
    doc = TEMPLATE
    i = doc.find(CONTENT_OPEN)
    m = CONTENT_CLOSE.search(doc, i + 1) if i >= 0 else None
    if i < 0 or not m:
        raise SystemExit("template does not contain a content block")
    head = doc[: i + len(CONTENT_OPEN)]
    tail = doc[m.start():]
    if extra_head:
        head = head.replace("</head>", extra_head + "\n</head>", 1)
    return head + "\n" + content + "\n\t\t" + tail


def write(local, text):
    dest = os.path.join(SITE, local.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)


LOCALMAP = {}
TEMPLATE = ""


def main():
    global TEMPLATE, LOCALMAP
    C.ensure_dirs()
    print("Phase 7 - generate uncaptured pages")
    print("=" * 60)

    if not os.path.isdir(SITE):
        print("  site/ missing - run 06_rewrite.py first", file=sys.stderr)
        return 1

    # Local paths for every taxonomy page that WAS captured, so generated links
    # point at real files.
    with open(os.path.join(C.WORK, "filename-map.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["present"] == "yes":
                LOCALMAP[_r6.local_path(r["original_key"].split("?")[0],
                                        r["kind"])] = r["local_path"]

    # Template: a captured date archive, which carries the theme's own listing
    # markup, header, sidebar and footer.
    tmpl = os.path.join(SITE, "2013-06-9c61bd", "index.html")
    if not os.path.exists(tmpl):
        cand = [os.path.join(SITE, d, "index.html") for d in os.listdir(SITE)
                if d.startswith("2013-06")]
        tmpl = cand[0] if cand else None
    if not tmpl or not os.path.exists(tmpl):
        print("  no captured archive page to use as a template", file=sys.stderr)
        return 1
    with open(tmpl, encoding="utf-8", errors="replace") as f:
        TEMPLATE = f.read()
    print(f"  template: {os.path.relpath(tmpl, SITE)}")

    # Preserve the captured homepage before replacing it.
    home = os.path.join(SITE, "index.html")
    if os.path.exists(home):
        os.makedirs(C.PROVENANCE, exist_ok=True)
        shutil.copy2(home, os.path.join(C.PROVENANCE, "index.html"))
        print("  preserved captured homepage to _provenance/index.html")

    posts = load_inventory()
    print(f"  inventory: {len(posts)} posts with local pages")

    written = []

    # Chronological listings hold dated posts only. The eleven undated
    # Tumblr-era pages are reachable from the nav but are not entries in the
    # loop, exactly as on the original site.
    dated = [p for p in posts if p.date and not p.is_page]
    print(f"  dated posts for listings: {len(dated)} "
          f"(excluded {len(posts) - len(dated)} static pages)")

    # ---- homepage --------------------------------------------------------
    newest_first = sorted(dated, key=lambda p: p.sort_key, reverse=True)
    written += paginate(
        newest_first, "/",
        "home",
        '<h2 class="page-title">Negative Youth</h2>')

    # ---- month and year archives ----------------------------------------
    by_month = collections.defaultdict(list)
    by_year = collections.defaultdict(list)
    for p in dated:
        if p.month:
            by_month[p.month].append(p)
            by_year[p.month[:4]].append(p)

    for month in sorted(by_month, reverse=True):
        y, m = month.split("-")
        title = (f'<h2 class="page-title">Monthly Archives: '
                 f'<span>{SPANISH_MONTHS[int(m) - 1]} {y}</span></h2>')
        written += paginate(by_month[month], f"/{y}/{m}/", month, title)

    for year in sorted(by_year, reverse=True):
        title = f'<h2 class="page-title">Yearly Archives: <span>{year}</span></h2>'
        written += paginate(by_year[year], f"/{year}/", year, title)

    # ---- taxonomy pages --------------------------------------------------
    def slug_url(prefix, term):
        return f"{prefix}{C.dedupe_key(term)}/"

    tag_index = collections.defaultdict(list)
    cat_index = collections.defaultdict(list)
    for p in dated:
        for t in p.tags:
            tag_index[t].append(p)
        for c in p.categories:
            cat_index[c].append(p)

    def taxonomy(base_dir, label, index, spanish):
        made = 0
        for term in sorted(index):
            base = f"{base_dir}{C.dedupe_key(term)}/"
            captured = LOCALMAP.get(_r6.local_path(base, "tag" if spanish else "category"))
            if captured:
                continue  # the real captured page is already in site/
            label_html = (f'<h2 class="page-title">{label}: '
                          f'<span>{html.escape(term)}</span></h2>')
            written_ = paginate(index[term], base, term, label_html)
            written.extend(written_)
            made += len(written_)
        return made

    made_tags = taxonomy("/tag/", "Tag Archives", tag_index, True)
    made_cats = taxonomy("/category/", "Category Archives", cat_index, False)
    print(f"  generated {made_tags} tag page(s) and {made_cats} category page(s)")

    for local, text in written:
        write(local, text)
    print(f"  wrote {len(written)} generated pages")

    # A listing with an unbalanced block tag nests every following post inside
    # the previous one. Refuse to report success if any entry fails the check.
    if IMBALANCE:
        print(f"\n  FATAL: {len(IMBALANCE)} generated entries have unbalanced "
              f"block markup; the tree was written but is not trustworthy.",
              file=sys.stderr)
        for base, page, key, reason in IMBALANCE[:10]:
            print(f"    {base} page {page}: {key} - {reason}", file=sys.stderr)
        return 1
    print("  block balance check: div/table/tr/td balance in every generated entry")
    if sum(COSMETIC):
        print(f"  {sum(COSMETIC)} entries carry an unclosed phrasing tag (p/span/small), "
              f"inherited verbatim from the 2013 theme; browsers close these "
              f"implicitly and they do not affect layout")
    if REPAIRED:
        uniq = sorted(set(REPAIRED))
        print(f"  {len(uniq)} post(s) had surplus closing block tags removed from "
              f"the copied body (the parser discarded them on the original page):")
        for key, tag, n in uniq:
            print(f"    {key}: -{n} </{tag}>")

    # ---- feeds index -----------------------------------------------------
    feeds_written = feeds_index()

    # ---- .htaccess -------------------------------------------------------
    htaccess_written()

    total = len(written) + feeds_written
    print(f"\n  Phase 7 wrote {total} file(s)")
    return 0


def feeds_index():
    """An index of the preserved feeds, grouped by post."""
    with open(os.path.join(C.WORK, "feeds.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    grouped = collections.defaultdict(list)
    for r in rows:
        owner = r["owner_post"] or r["path"]
        grouped[owner].append(r)

    posts = load_inventory()
    by_local = {p.local: p for p in posts}

    items = []
    for owner in sorted(grouped):
        recs = grouped[owner]
        title = ""
        link = ""
        for r in recs:
            if r["path"].endswith("/feed/") and r["kind"] == "post_comments":
                owner_local = LOCALMAP.get(
                    _r6.local_path(owner, "post"))
                p = by_local.get(owner_local)
                if p:
                    title = p.title
                    link = owner_local
                break
        for r in recs:
            local = LOCALMAP.get(_r6.local_path(r["path"], "feed"))
            if not local:
                continue
            items.append(
                f'<li><a href="{local}">{html.escape(title or owner)}</a> '
                f'<span class="muted">({r["kind"].replace("_", " ")}, '
                f'{r["items"]} item{"s" if r["items"] != "1" else ""})</span></li>')

    body = ['<h2 class="page-title">Feeds</h2>',
            '<p class="feednote">Every RSS feed the Internet Archive captured, '
            'preserved byte-for-byte. Feeds are WordPress <em>comment</em> feeds, '
            'so each contains the comments on one post rather than the post '
            'itself. Their internal URLs are left exactly as the archive found '
            'them, because canonical URLs are an RSS document&rsquo;s entire '
            f'purpose.</p>', '<ul class="feedlist">']
    body.extend(items)
    body.append("</ul>")

    write("/feeds/index.html", render("\n".join(
        "\n\t\t" + b if b else "" for b in body) + "\n\t\t"))
    return 1


def htaccess_written():
    """
    Pretty URLs, plus redirects from the original paths.

    Old links and Wayback links point at the original percent-encoded URLs.
    The site now lives at hashed directory names, so those would all 404 without
    this map.
    """
    lines = [
        "# negativeyouth.net archive - generated by tools/08_generate.py",
        "Options -Indexes",
        "DirectoryIndex index.html",
        "AddDefaultCharset UTF-8",
        "",
        "# The tree already resolves as directories, so no rewrite is needed for",
        "# navigation. This map exists for the original URLs.",
        "RedirectMatch 302 ^/$ /index.html",
        "",
        "<IfModule mod_rewrite.c>",
        "  RewriteEngine On",
        "  # Preserve the archive's own provenance links.",
        "  RewriteRule ^\\.well-known/ - [L]",
    ]

    with open(os.path.join(C.WORK, "filename-map.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["present"] != "yes":
                continue
            src = r["original_key"].split("?")[0]
            if src == "/" or not src:
                continue
            # The key is already percent-encoded and must stay that way.
            # Quoting it again turned %D0%BC into %25D0%25BC, which is a
            # literal "%D0%BC" filename rather than the Cyrillic character, and
            # Apache decodes the request path before matching - so the
            # percent-encoded form is correct here and the doubled form is not.
            pat = src if src.startswith("/") else "/" + src
            if any(ch in pat for ch in " \t\"'{}|\\^`<>[]"):
                # RedirectMatch offers no escape syntax for these characters.
                # The page is still reachable at its canonical path.
                continue
            lines.append(f"  RedirectMatch 301 {pat}$ {r['local_path']}")

    lines += [
        "  ErrorDocument 404 /404.html",
        "</IfModule>",
        "",
        "<IfModule mod_expires.c>",
        "  ExpiresActive On",
        "  ExpiresByType image/jpeg 'access plus 1 year'",
        "  ExpiresByType image/png  'access plus 1 year'",
        "  ExpiresByType text/css   'access plus 1 year'",
        "  ExpiresByType application/javascript 'access plus 1 year'",
        "  ExpiresByType text/html  'access plus 10 minutes'",
        "</IfModule>",
        "",
    ]
    write("/.htaccess", "\n".join(lines))
    return 1


if __name__ == "__main__":
    sys.exit(main())