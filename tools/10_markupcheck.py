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

def main():
    files = sorted(glob.glob('site/**/index.html', recursive=True))
    checked = tot_o = tot_c = nested = unclosed_at_end = open_tables = 0
    problems = []
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
    print(f"generated listing pages checked : {checked}")
    print(f"post entries opened              : {tot_o}")
    print(f"entries closed at `<!-- .post -->`: {tot_c}")
    print(f"entries nested inside another    : {nested}")
    print(f"pages ending with an entry open  : {unclosed_at_end}")
    print(f"pages ending with <table> open   : {open_tables}")
    if problems:
        print(f"\npages with problems ({len(problems)}):")
        for pr in problems[:20]: print("  ", pr)
        return 1
    print("\nOK: every post entry is a sibling, none nested, none left open, "
          "no table left unclosed.")
    return 0

sys.exit(main())
