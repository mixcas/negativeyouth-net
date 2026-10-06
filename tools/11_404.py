"""
Phase 9 - 404 page for static hosting.

GitHub Pages (and any static host) serves `404.html` for unknown paths. The
originals for those paths were never captured, so there is nothing faithful to
reproduce; this page only carries the theme's chrome and a way back home.

It is built from the same captured template as every other generated listing,
so the header, sidebars and footer match the rest of the mirror.

The provenance footer is baked in with the same `id` 09_provenance.py looks
for, so a later re-run of Phase 8 will skip this file instead of stamping it
with a "rebuilt from the archive" note that would be wrong here - this page was
never captured and never rebuilt from anything.
"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

_spec = importlib.util.spec_from_file_location(
    "g8", os.path.join(os.path.dirname(os.path.abspath(__file__)), "08_generate.py"))
g8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g8)

FOOTER_ID = "ny-archive-provenance"

FOOTER_CSS = """
<style type="text/css">
#ny-archive-provenance{clear:both;margin:2em 0 0;padding:14px 18px;
 border-top:1px solid #333;background:#111;color:#888;font:12px/1.5
 "Helvetica Neue",Helvetica,Arial,sans-serif;text-align:center}
#ny-archive-provenance a{color:#ff0179;text-decoration:none}
#ny-archive-provenance a:hover{text-decoration:underline}
</style>
"""

BODY = """<h2 class="page-title">Not found</h2>

\t\t<div class="hfeed">
\t\t\t<p>This page does not exist in the archive. The link you followed
\t\t\tpoints somewhere the crawlers never stored, most likely one of the
\t\t\toriginal addresses that only the redirect file knows about.</p>
\t\t\t<p><a href="/index.html">Back to the homepage</a></p>
\t\t</div>"""

FOOTER = (
    f'<div id="{FOOTER_ID}">'
    f'This page was never part of the original site. '
    f'<a href="/index.html">Back to the homepage</a>.'
    f'</div>'
)


def main():
    tmpl = os.path.join(C.ROOT, "site", "2013-06-9c61bd", "index.html")
    if not os.path.exists(tmpl):
        print("  site/ missing - run 06_rewrite.py first", file=sys.stderr)
        return 1
    with open(tmpl, encoding="utf-8", errors="replace") as f:
        g8.TEMPLATE = f.read()
    text = g8.render(BODY, FOOTER_CSS)
    text = text.replace("</body>", FOOTER + "\n</body>", 1)
    dest = os.path.join(C.ROOT, "site", "404.html")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  wrote site/404.html ({os.path.getsize(dest)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
