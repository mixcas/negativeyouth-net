"""
Phase 9 - markup integrity gate for the generated listings.

`08_generate.py` counts tags per entry, which catches an unclosed tag. Counting
cannot, however, answer the question that actually matters: does a post end up
nested inside another post? Only a parser can. This walks every generated listing
with a real tag stack and asserts that each post entry is a sibling of the others,
that none is left open, and that no `<table>` is left unclosed.

Writes nothing. A failure here means `site/` is not trustworthy, whatever the
per-entry counts said.
"""
import os, re, sys, glob
from html.parser import HTMLParser

VOID = {'br','img','hr','meta','link','input','area','base','col','embed',
        'source','param','track','wbr','!doctype'}

class Entries(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # [(tag, is_post_div)]
        self.open_posts = []     # ids of post divs currently open
        self.depths = []         # (id, stack depth at open)
        self.nested = []         # (id, enclosing_id)
        self.unclosed = []
        self.tables = 0          # <table> elements currently open
    def handle_starttag(self, tag, attrs):
        if tag in VOID: return
        a = dict(attrs)
        pid = a.get('id', '')
        is_post = tag == 'div' and pid.startswith('post-')
        if is_post:
            if self.open_posts:
                self.nested.append((pid, self.open_posts[-1]))
            self.open_posts.append(pid)
            self.depths.append(len(self.stack))
        if tag == 'table':
            self.tables += 1
        self.stack.append((tag, is_post))
    def handle_startendtag(self, tag, attrs):
        pass
    def handle_endtag(self, tag):
        if tag in VOID: return
        # pop to the nearest matching open tag
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                idx = i; break
        if idx is None:
            return          # stray close with nothing open: parser ignores it
        popped = self.stack[idx:]
        for t, is_post in popped:
            if is_post:
                self.open_posts.pop()
            elif t == 'table':
                self.tables -= 1
        del self.stack[idx:]

def entries_in(path):
    src = open(path, encoding='utf-8', errors='replace').read()
    i = src.find('<div class="hfeed">')
    if i < 0: return None, None
    j = src.find('<!-- #content', i)
    seg = src[i:j if j > 0 else len(src)]
    p = Entries(); p.feed(seg)
    # count entries via the theme's own marker, which is unambiguous
    opens = len(re.findall(r'<div id="post-', seg))
    closes = len(re.findall(r'</div>\s*<!-- \.post -->', seg))
    return (opens, closes), p

TEMPLATE_CLOSE = None      # the structural closing sequence, from the template


def load_template_close():
    """
    Read the closing *structure* of the template the generator splices into.

    Every generated listing must end its content region like this:

        </div><!-- #content .hfeed -->     <- closes #content
        </div><!-- #container -->          <- closes #container
        <div id="primary" class="sidebar">

    which is what keeps the sidebars siblings of `#container` rather than
    children of it.

    Only this short structural prefix is compared. An earlier version of this
    check compared the whole tail to end-of-file, which can never pass: every
    page's tail legitimately ends with its own provenance footer carrying that
    page's own Wayback URL, so the bytes after `#primary` differ by design.
    Comparing them would have reported all 1,683 pages as broken.
    """
    global TEMPLATE_CLOSE
    tmpl = os.path.join('site', '2013-06-9c61bd', 'index.html')
    if not os.path.exists(tmpl):
        for d in sorted(os.listdir('site')):
            if d.startswith('2013-06'):
                tmpl = os.path.join('site', d, 'index.html')
                break
    if not os.path.exists(tmpl):
        return False
    src = open(tmpl, encoding='utf-8', errors='replace').read()
    TEMPLATE_CLOSE = closing_sequence(src)
    return TEMPLATE_CLOSE is not None


def closing_sequence(src):
    """The `</div> ... #primary ...` run that closes #content and #container."""
    k = src.find('<!-- #content')
    if k < 0:
        return None
    start = src.rfind('</div>', 0, k)
    if start < 0:
        return None
    prim = src.find('<div id="primary"', k)
    if prim < 0:
        return None
    return re.sub(r"\s+", " ", src[start:prim]).strip()


def content_balance(path):
    """
    Net div balance of the `#content` region.

    Tag counting alone missed the worst layout bug in this project. Every post
    entry balanced perfectly while the listing was still rendering wrong, because
    the fault was one level up: the `</div>` that closes `#content` had been
    dropped, so the line labelled `</div><!-- #container -->` was closing
    `#content` and `#primary`/`#secondary`/`#footer` ended up inside
    `#container` - which the theme sets to `float:left; width:0px`. The
    sidebars then could not sit beside the 704px content column and fell below
    it, the left one to x=-151, off the left edge of the page.

    Both working captures are net-zero in this region (2013-06 template 57/57,
    Nov 2013 /page/2/ 47/47); the broken output was 63/62.

    The check is deliberately byte-level rather than parser-based. These posts
    carry genuinely malformed markup from 2013 - unclosed `<p>`, divs inside
    comments - so any parser walk drifts, and a drifted stack reports confident
    nonsense about where the sidebars sit. The working pages are the reference,
    not an idealised parse.

    Returns (net, closing-sequence) for the page, or (None, None) if it has no
    content region.
    """
    src = open(path, encoding='utf-8', errors='replace').read()
    i = src.find('<div id="content">')
    if i < 0:
        return None, None
    j = src.find('<!-- #content', i)
    if j < 0:
        j = src.find('<!-- #container', i)
    if j < 0:
        return None, None
    seg = src[i:j]
    return (len(re.findall(r'<div\b', seg)) - len(re.findall(r'</div>', seg)),
            closing_sequence(src))

def main():
    files = sorted(glob.glob('site/**/index.html', recursive=True))
    checked = tot_o = tot_c = nested = unclosed_at_end = open_tables = 0
    problems = []
    balance_problems = []
    if not load_template_close():
        print("could not read the template's closing structure", file=sys.stderr)
        return 1
    for f in files:
        counts, p = entries_in(f)
        if counts is None: continue
        checked += 1
        o, c = counts
        tot_o += o; tot_c += c
        nested += len(p.nested)
        # if a post div is still open at the end of the segment, it swallowed the rest
        if p.open_posts:
            unclosed_at_end += len(p.open_posts)
        if p.tables:
            open_tables += p.tables
        if p.nested or o != c or p.open_posts or p.tables:
            problems.append((f, o, c, p.nested[:3], list(p.open_posts)[:3], p.tables))

        net, close = content_balance(f)
        if net is None:
            continue
        if net != 0:
            balance_problems.append(
                (f, f"#content region net {net:+d} divs, so the line labelled "
                    f"#container closes #content and the sidebars fall inside it"))
        elif close is None:
            balance_problems.append((f, "no #primary sidebar found after the "
                                         "content region"))
        elif TEMPLATE_CLOSE is not None and close != TEMPLATE_CLOSE:
            balance_problems.append(
                (f, f"closing structure differs from the template:\n"
                    f"        want: {TEMPLATE_CLOSE}\n"
                    f"        got : {close}"))
    print(f"generated listing pages checked : {checked}")
    print(f"post entries opened              : {tot_o}")
    print(f"entries closed at `<!-- .post -->`: {tot_c}")
    print(f"entries nested inside another    : {nested}")
    print(f"pages ending with an entry open  : {unclosed_at_end}")
    print(f"pages ending with <table> open   : {open_tables}")
    if problems:
        print(f"\nentry-level problems ({len(problems)}):")
        for pr in problems[:20]: print("  ", pr)
    if balance_problems:
        print(f"\n#content balance / sidebar placement problems "
              f"({len(balance_problems)}):")
        for pr in balance_problems[:20]: print("  ", pr)
    if problems or balance_problems:
        return 1
    print("\nOK: every post entry is a sibling, none nested, none left open, "
          "no table left unclosed,")
    print("    and #content balances with the sidebars outside #container.")
    return 0

sys.exit(main())
