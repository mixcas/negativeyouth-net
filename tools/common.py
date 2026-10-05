"""
Shared plumbing for the negativeyouth.net restoration.

Standard library only, so this tooling still runs years from now with no
dependency rot.

Provides:
  - polite, resumable Wayback fetching (shared on-disk cache)
  - CDX index queries with resumeKey pagination
  - URL canonicalisation
  - classification of archived resources
"""

import base64
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "_cache")
WORK = os.path.join(ROOT, "_work")
REPORTS = os.path.join(ROOT, "_reports")
PROVENANCE = os.path.join(ROOT, "_provenance")

CDX = "https://web.archive.org/cdx/search/cdx"
WEB = "https://web.archive.org/web"

ORIGIN_HOST = "negativeyouth.net"

# The site also served content from two subdomains: cas. and maligna.
# Both are this blog's own content and must be mirrored with it, otherwise
# assets referenced only from those hosts 404.
SUBDOMAINS = (ORIGIN_HOST, f"cas.{ORIGIN_HOST}", f"maligna.{ORIGIN_HOST}")


def is_own_host(host):
    """True for any host this site served content from."""
    h = (host or "").lower().replace(":80", "")
    return h in SUBDOMAINS

UA = (
    "Mozilla/5.0 (compatible; negativeyouth.net archival restoration; "
    "+local research mirror)"
)

# Resources timestamped at or after this year belong to the lapsed/parked era,
# not to the original blog. Publishing them would republish a stranger's page.
EXCLUDE_YEAR = 2022


def ensure_dirs():
    for d in (CACHE, WORK, REPORTS, PROVENANCE):
        os.makedirs(d, exist_ok=True)


# --------------------------------------------------------------------------
# URL canonicalisation
# --------------------------------------------------------------------------

def canonical(url):
    """
    Reduce a URL to a stable identity for this site.

    Normalises scheme and default port, lowercases the host, and leaves the
    percent-encoded path exactly as captured. The path is NOT decoded here:
    percent-encoding is part of the original URL, and we need it verbatim later
    when generating redirect rules for old inbound links.
    """
    url = url.strip()
    # Some posts contain a doubled scheme, e.g. `http://http://host/path`.
    # The extra scheme parses as a hostname, which makes the URL look
    # third-party and silently exempts it from rewriting, so it is repaired
    # before anything else inspects it.
    url = re.sub(r"^(https?):\s*//\s*(?:https?://)+", r"\1://", url, flags=re.I)
    m = re.match(r"^(https?)://([^/]*)(/.*)?$", url, re.I)
    if not m:
        return url
    scheme, host, path = m.group(1).lower(), m.group(2), (m.group(3) or "/")
    host = host.lower()
    if host.endswith(":80"):
        host = host[:-3]
    path = re.sub(r"^:80(?=/)", "", path)
    if not path:
        path = "/"
    return f"{scheme}://{host}{path}"


def same_origin(url):
    """True if this URL points at the original site or one of its subdomains."""
    u = re.sub(r"^(https?):\s*//\s*(?:https?://)+", r"\1://", url.strip(), flags=re.I)
    m = re.match(r"^(?:https?:)?//([^/]+)", u, re.I)
    if not m:
        # bare relative path
        return u.startswith("/") and not u.startswith("//")
    return is_own_host(m.group(1))


def host_of(url):
    m = re.match(r"^(?:https?:)?//([^/]+)", url.strip(), re.I)
    return m.group(1).lower() if m else ""


# Query strings that identify a genuinely distinct resource rather than a
# duplicate request for the same one.
_ASSET_EXT = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|eot|ttf|woff2?)$", re.I)


def dedupe_key(url):
    """
    The identity used to collapse captures of the same thing.

    Scheme is dropped: every link gets rewritten to a root-relative path
    anyway, so http vs https is not a real difference. Subdomain is NOT
    dropped - `cas.negativeyouth.net/tb/style.css` and
    `negativeyouth.net/wp-content/...` are different files on different hosts,
    and collapsing them would lose one.

    Percent-escapes are upper-cased. The same resource reaches us spelled with
    different escape case - `%D0%BC` and `%d0%bc` are the same bytes - and
    without this 37 posts appear to exist twice.

    For assets the query string is preserved, since `style.css?ver=3.8.5` and
    `style.css?ver=3.4` are genuinely distinct captures worth keeping.
    """
    p = to_origin_path(canonical(url))
    host = host_of(url).lower().replace(":80", "")
    prefix = f"/_host/{host}" if host and host != ORIGIN_HOST else ""
    if _ASSET_EXT.search(p.split("?")[0]):
        return prefix + _upper_escapes(p)
    return (prefix + _upper_escapes(p.split("?")[0])) or (prefix or "/")


def _upper_escapes(path):
    """Normalise %xx escapes to upper case, leaving other bytes untouched."""
    return re.sub(r"%([0-9a-f]{2})", lambda m: "%" + m.group(1).upper(), path)


def slugify(path):
    """
    A filesystem-safe, readable, collision-free directory name for a URL path.

    Slugs here contain Cyrillic, Japanese and geometric Unicode. APFS is
    case-insensitive and normalising, so writing them verbatim would silently
    collide. NFC normalisation plus a short hash of the original encoded path
    keeps names readable while guaranteeing uniqueness.
    """
    import hashlib as _h
    import unicodedata

    decoded = urllib.parse.unquote(path).strip("/")
    decoded = unicodedata.normalize("NFC", decoded)
    keep = []
    for ch in decoded:
        if ch.isalnum() or ch in "-_.~":
            keep.append(ch)
        elif ch in " \t":
            keep.append("-")
        else:
            keep.append("-")
    name = re.sub(r"-{2,}", "-", "".join(keep)).strip("-")[:80].strip("-")
    if not name:
        name = "index"
    digest = _h.blake2b(path.encode("utf-8"), digest_size=3).hexdigest()
    return f"{name}-{digest}"


def to_origin_path(url):
    """
    Map any own-origin URL (absolute or protocol-relative) to a bare path.

    Used for link rewriting and for set membership tests.
    """
    u = url.strip()
    u = re.sub(r"^(?:https?:)?//[^/]*", "", u)
    if not u:
        return "/"
    u = re.sub(r"^:80(?=/)", "", u)
    return u


def path_to_origin(key):
    """Inverse of dedupe_key: recover the fetchable absolute URL for a key."""
    if key.startswith("/_host/"):
        host, _, rest = key[len("/_host/"):].partition("/")
        return f"http://{host}/{rest}"
    return f"http://{ORIGIN_HOST}{key}"


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

# Top-level WP paths that are infrastructure rather than published content.
WP_INFRA = re.compile(
    r"^/(wp-content|wp-includes|wp-admin|wp-json|xmlrpc\.php|wp-login\.php|"
    r"wp-cron\.php|robots\.txt|favicon\.ico|feed/?$)",
    re.I,
)


def classify(url, mime):
    """
    Return a kind label for a captured URL.

    kind is one of: homepage post date_archive category tag author feed
                    image css js font other_asset exclude
    """
    p = to_origin_path(canonical(url))

    if p.startswith("/.well-known/") or p in ("/security.txt", "/.htaccess"):
        return "exclude"

    # robots.txt is per-host boilerplate served by the hosting account, not
    # blog content. Excluding it also stops a subdomain's robots.txt from being
    # mistaken for a page of this site.
    if p.rstrip("/").split("?")[0].endswith("/robots.txt"):
        return "exclude"

    if mime and mime.startswith("image/"):
        return "image"
    if mime in ("text/css",):
        return "css"
    if mime in ("application/javascript", "text/javascript"):
        return "js"
    if mime and ("font" in mime or p.endswith((".woff", ".woff2", ".ttf", ".eot", ".otf"))):
        return "font"
    if p.rstrip("/").split("?")[0].endswith(".php"):
        # WordPress endpoints. xmlrpc.php happens to be served as text/xml,
        # which would otherwise classify it as a feed.
        return "exclude"
    if mime == "text/xml" or p.rstrip("/").endswith("/feed"):
        return "feed"

    if WP_INFRA.match(p):
        return "other_asset" if mime and mime != "text/html" else "other_asset"

    if p == "/":
        return "homepage"

    # Tumblr-era URLs from before the WordPress migration. These are the same
    # blog at its previous address, and the nav links still point at them.
    if re.match(r"^/post/\d+/", p) or p.startswith("/tagged/") or \
            p.rstrip("/") in ("/about", "/ask", "/mobile", "/nosotros", "/archive"):
        return "page"
    if re.match(r"^/\d{4}/\d{2}/\d{2}/?$", p):
        return "date_archive"
    if re.match(r"^/\d{4}/\d{2}/?$", p):
        return "date_archive"
    if re.match(r"^/\d{4}/?$", p):
        return "date_archive"
    if re.match(r"^/\d{4}/\d{2}/page/\d+/?$", p):
        return "date_archive"
    if p.startswith("/category/"):
        return "category"
    if p.startswith("/tag/"):
        return "tag"
    if p.startswith("/author/"):
        return "author"
    if re.match(r"^/page/\d+/?$", p):
        return "homepage"

    if "?" in p:
        return "exclude"

    # A dated archive path that slipped through the checks above, e.g.
    # /2012/05/page/2/ reaching here with an unexpected shape.
    if re.match(r"^/\d{4}(/\d{2})*(/page/\d+)?/?$", p):
        return "date_archive"

    return "post"


def year_of(ts):
    try:
        return int(str(ts)[:4])
    except (TypeError, ValueError):
        return 0


def in_content_era(ts):
    return 0 < year_of(ts) < EXCLUDE_YEAR


# --------------------------------------------------------------------------
# CDX
# --------------------------------------------------------------------------

def cdx_rows(match="domain", url=None, fl=None, limit=20000, extra=None):
    """
    Query the CDX index, following resumeKey pagination until exhausted.

    Returns a list of dicts keyed by the requested field names.
    """
    fl = fl or "timestamp,original,mimetype,statuscode"
    params = {
        "url": url if url is not None else ORIGIN_HOST,
        "matchType": match,
        "output": "text",
        "fl": fl,
        "limit": str(limit),
        "showResumeKey": "true",
    }
    if extra:
        params.update(extra)

    rows = []
    resume = None
    while True:
        q = dict(params)
        if resume:
            q["resumeKey"] = resume
        url_q = CDX + "?" + urllib.parse.urlencode(q)
        body = http_get(url_q, tries=5, delay=2.0)
        if body is None:
            print(f"  ! CDX page failed after retries: {q}", file=sys.stderr)
            break

        keys = fl.split(",")
        resume = None
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                # showResumeKey payload
                try:
                    resume = json.loads(line).get("resumeKey")
                except Exception:
                    pass
                continue
            parts = line.split(" ")
            if len(parts) != len(keys):
                continue
            rows.append(dict(zip(keys, parts)))

        if not resume:
            break
        time.sleep(1.0)

    return rows


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class _Throttle:
    """Global minimum-interval gate shared across worker threads."""

    def __init__(self, delay):
        self.delay = delay
        self.lock = threading.Lock()
        self.next_ok = 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            if now < self.next_ok:
                time.sleep(self.next_ok - now)
                now = time.time()
            self.next_ok = now + self.delay


_THROTTLE = _Throttle(1.5)

# The archive intermittently returns 503 and refuses connections outright under
# load. That is a throttle, not a ban, and the cure is to back off for minutes
# rather than seconds. Repeated refusals mean we stop hammering entirely.
_CIRCUIT = {"strikes": 0, "open_until": 0.0}
CIRCUIT_BACKOFF = (0, 30, 60, 120, 300, 300)


def set_delay(seconds):
    global _THROTTLE
    _THROTTLE = _Throttle(seconds)


def _circuit_wait():
    """Sleep out an open circuit breaker, if one is open."""
    wait = _CIRCUIT["open_until"] - time.time()
    if wait > 0:
        print(f"    [circuit open] pausing {wait:.0f}s", file=sys.stderr)
        time.sleep(wait)


def _circuit_strike():
    """Record a throttle response and open the breaker if it's repeating."""
    _CIRCUIT["strikes"] += 1
    idx = min(_CIRCUIT["strikes"], len(CIRCUIT_BACKOFF) - 1)
    secs = CIRCUIT_BACKOFF[idx]
    if secs:
        _CIRCUIT["open_until"] = max(_CIRCUIT["open_until"], time.time() + secs)


def _circuit_close():
    _CIRCUIT["strikes"] = 0
    _CIRCUIT["open_until"] = 0.0


def http_get(url, tries=5, delay=2.0, timeout=90, raw=False):
    """
    Polite GET with exponential backoff and a circuit breaker.

    The Internet Archive throttles aggressively: sustained crawling earns 503s
    and then outright connection refusals. Everything here exists to make a
    long crawl survivable rather than to go faster.
    """
    for attempt in range(tries):
        _circuit_wait()
        _THROTTLE.wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                _circuit_close()
                return data if raw else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                _circuit_strike()
                print(f"    HTTP {e.code}; backing off", file=sys.stderr)
                continue
            print(f"    HTTP {e.code} (not retryable) for {url}", file=sys.stderr)
            return None
        except Exception as e:  # noqa: BLE001 - URLError, timeout, reset
            _circuit_strike()
            print(f"    {type(e).__name__}: {e}; retrying", file=sys.stderr)
            continue
    return None


# --------------------------------------------------------------------------
# Content-addressed cache
# --------------------------------------------------------------------------

def cache_paths(key):
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    d = os.path.join(CACHE, h[:2])
    return os.path.join(d, h + ".bin"), os.path.join(d, h + ".json")


def cache_get(key):
    """Return (bytes, meta) if cached, else (None, None)."""
    bp, jp = cache_paths(key)
    if os.path.exists(bp) and os.path.exists(jp):
        try:
            with open(jp, encoding="utf-8") as f:
                meta = json.load(f)
            with open(bp, "rb") as f:
                return f.read(), meta
        except Exception:
            return None, None
    return None, None


def cache_put(key, data, meta):
    bp, jp = cache_paths(key)
    os.makedirs(os.path.dirname(bp), exist_ok=True)
    with open(bp, "wb") as f:
        f.write(data)
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)


def cache_stats():
    files = 0
    total = 0
    for root, _dirs, names in os.walk(CACHE):
        for n in names:
            if n.endswith(".bin"):
                files += 1
                total += os.path.getsize(os.path.join(root, n))
    return files, total


def sha1_b32(data):
    """CDX digest format: base32 of SHA-1, no padding."""
    return base64.b32encode(hashlib.sha1(data).digest()).decode("ascii").rstrip("=")
