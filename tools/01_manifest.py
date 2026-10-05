#!/usr/bin/env python3
"""
Phase 1 - Build the manifest.

Pulls the complete CDX index for negativeyouth.net, canonicalises every URL,
selects the best capture per resource, classifies everything, and excludes the
lapsed/parked era.

Writes:
  _work/manifest.csv        every canonical resource + chosen capture
  _reports/manifest.md      human-readable summary
"""

import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

FIELDS = "timestamp,original,mimetype,statuscode,digest,length"


def main():
    C.ensure_dirs()
    print("Phase 1 - manifest")
    print("=" * 60)

    print("  querying CDX (paginated, uncollapsed)...")
    rows = C.cdx_rows(fl=FIELDS, limit=20000)
    print(f"  raw CDX rows: {len(rows)}")

    if not rows:
        print("  FATAL: CDX returned nothing. Aborting.", file=sys.stderr)
        return 1

    # ---- group by canonical URL ------------------------------------------
    # Keyed on dedupe_key(), not the full URL, so that scheme variants and
    # tracking-parameter duplicates collapse into one resource instead of
    # producing duplicate manifest rows.
    by_url = collections.defaultdict(list)
    for r in rows:
        if not r.get("original"):
            continue
        by_url[C.dedupe_key(r["original"])].append(r)

    print(f"  distinct resources after canonicalisation: {len(by_url)}")

    # ---- pick the best capture per URL -----------------------------------
    # Prefer HTTP 200 in the content era, then the largest payload (most
    # complete rendering), then the earliest such capture for stability.
    chosen = {}
    stats = collections.Counter()
    overridden = []

    for url, caps in by_url.items():
        era = [c for c in caps if C.in_content_era(c.get("timestamp", ""))]
        if era:
            stats["in_era"] += 1
        else:
            stats["era_only_excluded"] += 1

        ok = [c for c in caps if c.get("statuscode") == "200"]
        if not ok:
            stats["no_200"] += 1
            continue

        # A resource captured *only* after the domain lapsed belongs to whoever
        # held it then. Keeping it would republish a stranger's page.
        pool = [c for c in ok if C.in_content_era(c.get("timestamp", ""))]
        if not pool:
            stats["no_era_200"] += 1
            continue

        def length(c):
            try:
                return int(c.get("length") or 0)
            except (TypeError, ValueError):
                return 0

        best = sorted(pool, key=lambda c: (-length(c), c["timestamp"]))[0]
        rec = dict(best)

        # A pinned capture wins over the largest-payload default. See
        # common.CAPTURE_OVERRIDES for why `/about/` is one.
        pinned = C.capture_override(url)
        if pinned:
            hit = next((c for c in pool if c["timestamp"] == pinned), None)
            if hit is None:
                hit = next((c for c in caps if c["timestamp"] == pinned), None)
            if hit is not None:
                if hit is not best:
                    overridden.append(url)
                rec = dict(hit)
            else:
                print(f"  WARNING: override {pinned} for {url} not in the CDX "
                      f"index; keeping the default {best['timestamp']}",
                      file=sys.stderr)

        rec["captures"] = len(caps)
        rec["years"] = sorted({C.year_of(c["timestamp"]) for c in caps if c.get("timestamp")})
        rec["urls"] = sorted({C.canonical(c["original"]) for c in caps if c.get("original")})
        chosen[url] = rec

    print(f"  resources with a usable capture: {len(chosen)}")
    if overridden:
        print(f"  site-owner capture overrides applied: {len(overridden)}")
        for u in sorted(overridden):
            print(f"    {u} -> {C.capture_override(u)}")
    for k in ("in_era", "era_only_excluded", "no_200", "no_era_200"):
        print(f"    {k:20s} {stats[k]}")

    # ---- classify ---------------------------------------------------------
    for url, rec in chosen.items():
        rec["kind"] = C.classify(url, rec.get("mimetype"))
        rec["path"] = C.to_origin_path(url)

    kinds = collections.Counter(r["kind"] for r in chosen.values())
    print("\n  classification:")
    for k, n in kinds.most_common():
        print(f"    {k:16s} {n:5d}")

    # ---- write manifest ---------------------------------------------------
    out = os.path.join(C.WORK, "manifest.csv")
    cols = ["path", "kind", "timestamp", "mimetype", "length", "digest",
            "statuscode", "captures", "years", "url", "alt_urls"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for url in sorted(chosen):
            r = chosen[url]
            w.writerow({
                "path": r["path"],
                "kind": r["kind"],
                "timestamp": r["timestamp"],
                "mimetype": r.get("mimetype", ""),
                "length": r.get("length", ""),
                "digest": r.get("digest", ""),
                "statuscode": r.get("statuscode", ""),
                "captures": r.get("captures", 1),
                "years": ";".join(str(y) for y in r.get("years", [])),
                "url": C.canonical(r.get("urls", [url])[0]),
                "alt_urls": " ".join(r.get("urls", [])[1:]),
            })
    print(f"\n  wrote {out} ({len(chosen)} rows)")

    # ---- excluded set, for the record ------------------------------------
    excl = [u for u in by_url if u not in chosen]
    with open(os.path.join(C.WORK, "excluded.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["resource", "reason", "captures"])
        for u in sorted(excl):
            caps = by_url[u]
            reason = "no_200"
            if not any(C.in_content_era(c.get("timestamp", "")) for c in caps):
                reason = "parked_era_only"
            w.writerow([u, reason, len(caps)])
    print(f"  wrote excluded.csv ({len(excl)} rows)")

    # ---- report -----------------------------------------------------------
    by_kind_bytes = collections.Counter()
    by_kind_files = collections.Counter()
    for r in chosen.values():
        try:
            n = int(r.get("length") or 0)
        except (TypeError, ValueError):
            n = 0
        by_kind_bytes[r["kind"]] += n
        by_kind_files[r["kind"]] += 1

    total_bytes = sum(by_kind_bytes.values())
    total_files = sum(by_kind_files.values())

    lines = [
        "# Phase 1 - Manifest summary",
        "",
        f"Generated from the web.archive.org CDX index for `{C.ORIGIN_HOST}`.",
        "",
        "## Totals",
        "",
        f"- Raw CDX rows (uncollapsed): **{len(rows)}**",
        f"- Distinct canonical URLs: **{len(by_url)}**",
        f"- Usable resources in manifest: **{len(chosen)}**",
        f"- Excluded: **{len(excl)}** (see `_work/excluded.csv`)",
        f"- Projected payload: **{total_bytes/1048576:.1f} MB** across **{total_files}** files",
        "",
        "## By kind",
        "",
        "| Kind | Files | Size |",
        "|---|---:|---:|",
    ]
    for k, n in by_kind_files.most_common():
        lines.append(f"| {k} | {n} | {by_kind_bytes[k]/1048576:.2f} MB |")
    lines.append(f"| **total** | **{total_files}** | **{total_bytes/1048576:.2f} MB** |")

    lines += [
        "",
        "## Capture era distribution",
        "",
        "| First capture year | Resources |",
        "|---|---:|",
    ]
    yr = collections.Counter()
    for r in chosen.values():
        ys = r.get("years") or []
        yr[ys[0] if ys else "?"] += 1
    for y, n in sorted(yr.items(), key=lambda x: str(x[0])):
        lines.append(f"| {y} | {n} |")

    excl_reason = collections.Counter()
    with open(os.path.join(C.WORK, "excluded.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            excl_reason[row["reason"]] += 1
    lines += [
        "",
        "## Exclusions",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ]
    for k, n in excl_reason.most_common():
        lines.append(f"| {k} | {n} |")
    lines += [
        "",
        "Anything excluded as `parked_era_only` was captured after the domain",
        "lapsed and belongs to whoever held it then - not to this blog.",
        "",
    ]

    rep = os.path.join(C.REPORTS, "manifest.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  wrote {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
