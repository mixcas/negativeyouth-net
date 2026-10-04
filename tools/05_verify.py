#!/usr/bin/env python3
"""
Phase 5 - Verify the cache against the archive's own checksums.

The `id_` endpoint occasionally returns a truncated body, an error page, or an
HTML challenge page instead of the capture, especially under load. The CDX index
carries a base32 SHA-1 digest and a compressed length for every record, so every
cached file can be checked against the archive's own account of what it stored.

Checks, in order of strictness:
  1. digest      base32(sha1(payload)) must equal the CDX digest
  2. length      payload length must be plausible for the CDX length
  3. content     HTML must not be an archive error/offline page

A file that fails is evicted from the cache so Phase 4 can retry it.

Writes:
  _work/verify.csv
  _reports/verify.md
"""

import base64
import csv
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

# Pages the archive serves in place of a capture when something has gone wrong.
POISON = [
    (re.compile(rb"Temporarily Offline", re.I), "archive-offline page"),
    (re.compile(rb"<title>\s*Internet Archive", re.I), "archive error page"),
    (re.compile(rb"Wayback Machine has not archived", re.I), "not-archived page"),
    (re.compile(rb"<!\[CDATA\[__wm", re.I), "toolbar-injected replay"),
    (re.compile(rb"web-static\.archive\.org", re.I), "replay asset reference"),
]


def digest_b32(data):
    return base64.b32encode(hashlib.sha1(data).digest()).decode("ascii").rstrip("=")


def main():
    C.ensure_dirs()
    print("Phase 5 - verify")
    print("=" * 60)

    with open(os.path.join(C.WORK, "manifest.csv"), encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))

    print(f"  manifest: {len(manifest)} resources")

    rows = []
    stats = {"ok": 0, "no_capture": 0, "digest_mismatch": 0,
             "length_mismatch": 0, "poisoned": 0, "missing": 0}
    evictions = []
    digest_checked = 0

    for rec in manifest:
        path = rec["path"]
        data, meta = C.cache_get(path)
        row = {
            "path": path,
            "kind": rec["kind"],
            "status": "",
            "detail": "",
            "bytes": len(data) if data else 0,
            "expected_length": rec.get("length", ""),
            "stamp": (meta or {}).get("stamp", ""),
        }

        if data is None:
            row["status"] = "missing"
            stats["missing"] += 1
            rows.append(row)
            continue

        # 3. content sanity, before anything else
        poisoned = None
        for pat, why in POISON:
            if pat.search(data[:8000]):
                poisoned = why
                break
        if poisoned:
            row["status"] = "poisoned"
            row["detail"] = poisoned
            stats["poisoned"] += 1
            evictions.append(path)
            rows.append(row)
            continue

        # 1. digest
        want = (rec.get("digest") or "").strip()
        if want:
            got = digest_b32(data)
            if got != want.upper():
                row["status"] = "digest_mismatch"
                row["detail"] = f"want {want} got {got}"
                stats["digest_mismatch"] += 1
                evictions.append(path)
                rows.append(row)
                continue
            digest_checked += 1
            row["detail"] = "digest ok"
        else:
            row["detail"] = "no digest in index"

        # 2. length. CDX length is the compressed record length, so it is only
        #    a sanity bound, not an equality test.
        try:
            want_len = int(rec.get("length") or 0)
        except ValueError:
            want_len = 0
        if want_len and len(data) < want_len // 4:
            row["status"] = "length_mismatch"
            row["detail"] = f"{len(data)} bytes vs indexed {want_len}"
            stats["length_mismatch"] += 1
            evictions.append(path)
            rows.append(row)
            continue

        row["status"] = "ok"
        stats["ok"] += 1
        rows.append(row)

    # Evict failures so a re-run of Phase 4 retries them cleanly.
    if evictions:
        print(f"\n  evicting {len(evictions)} bad files from the cache")
        for p in evictions:
            bp, jp = C.cache_paths(p)
            for f in (bp, jp):
                try:
                    os.remove(f)
                except OSError:
                    pass

    out = os.path.join(C.WORK, "verify.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        cols = ["path", "kind", "status", "detail", "bytes", "expected_length", "stamp"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  wrote {out}")

    bad = [r for r in rows if r["status"] not in ("ok",)]
    L = [
        "# Phase 5 - Verification",
        "",
        "Every cached file is checked against the CDX index's own SHA-1 digest and",
        "length, and screened for archive error pages served in place of a capture.",
        "",
        "## Results",
        "",
        "| Status | Resources |",
        "|---|---:|",
    ]
    for k in ("ok", "missing", "digest_mismatch", "length_mismatch", "poisoned"):
        L.append(f"| {k} | {stats[k]} |")
    L += [
        "",
        f"**{digest_checked}** files verified against a cryptographic digest.",
        f"**{stats['ok'] - digest_checked}** had no digest in the index and were",
        "checked on length and content only.",
        "",
    ]
    if bad:
        L += ["## Files needing attention", "",
              "| Path | Status | Detail |", "|---|---|---|"]
        for r in sorted(bad, key=lambda x: x["path"])[:200]:
            L.append(f"| `{r['path']}` | {r['status']} | {r['detail']} |")
        if len(bad) > 200:
            L.append(f"\n_...and {len(bad) - 200} more, see `_work/verify.csv`._")
        L += [
            "",
            f"{len(evictions)} file(s) were evicted from the cache. Re-run Phase 4 to",
            "retry them; the archive is often merely under load, and the same URL",
            "usually succeeds on a later attempt.",
            "",
        ]
    else:
        L += ["No file failed verification.", ""]

    rep = os.path.join(C.REPORTS, "verify.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {rep}")

    print("\n" + "=" * 60)
    print(f"ok={stats['ok']}  missing={stats['missing']}  "
          f"digest_mismatch={stats['digest_mismatch']}  "
          f"length_mismatch={stats['length_mismatch']}  "
          f"poisoned={stats['poisoned']}")
    return 0 if not evictions else 1


if __name__ == "__main__":
    sys.exit(main())
