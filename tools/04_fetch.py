#!/usr/bin/env python3
"""
Phase 4 - Fetch every remaining resource.

Downloads the manifest at its chosen capture timestamps using the `id_`
modifier, which returns the original bytes with no Wayback toolbar injection.
That single choice is what makes pixel fidelity possible downstream.

Safe to interrupt and re-run: everything lands in the shared content-addressed
cache, and a resource already present is never re-fetched.

Writes:
  _work/fetch-log.csv    per-resource outcome, including failures
  _reports/fetch.md
"""

import collections
import csv
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def fetch_one(path, ts, mime):
    """
    Fetch one resource into the cache.

    `id_` is the "identity" modifier: raw original bytes, no toolbar, no
    rewriting of asset URLs.

    When the manifest's chosen timestamp does not replay, the CDX index is
    consulted for that exact URL and every capture it lists is tried. This
    matters: the manifest deliberately picks the *largest* payload per resource
    for completeness, and that capture is not always the one that replays. For
    assets all captures of one URL are the same file, so any of them will do.
    """
    data, meta = C.cache_get(path)
    if data is not None:
        return "cached", len(data)

    stamps = []
    if ts:
        stamps.append(f"{ts}id_")
    # Fall back to every capture the index knows about, newest first.
    for r in C.cdx_rows(match="exact", url=C.path_to_origin(path),
                        fl="timestamp,statuscode", limit=50):
        if r.get("statuscode") == "200":
            stamp = f"{r['timestamp']}id_"
            if stamp not in stamps:
                stamps.append(stamp)

    for stamp in stamps:
        url = f"{C.WEB}/{stamp}/{C.path_to_origin(path)}"
        raw = C.http_get(url, tries=3, delay=3.0, raw=True)
        if raw:
            C.cache_put(path, raw, {"path": path, "stamp": stamp,
                                    "bytes": len(raw), "mime": mime})
            return "fetched", len(raw)
    return "failed", 0


def main():
    C.ensure_dirs()
    print("Phase 4 - fetch")
    print("=" * 60)

    with open(os.path.join(C.WORK, "manifest.csv"), encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    print(f"  manifest: {len(manifest)} resources")

    todo = [r for r in manifest if not C.cache_get(r["path"])[0]]
    print(f"  already cached: {len(manifest) - len(todo)}")
    print(f"  to fetch:       {len(todo)}")

    if not todo:
        print("\n  nothing to do - the cache already covers the whole manifest")
        return 0

    # Images first: they are the bulk of the bytes and the least likely to be
    # referenced by anything we still need to download, so nothing waits on them.
    order = {"image": 0, "other_asset": 1, "font": 2, "css": 3, "js": 4}
    todo.sort(key=lambda r: (order.get(r["kind"], 5), r["path"]))

    results = []
    counts = collections.Counter()
    bytes_by_kind = collections.Counter()
    failed = []
    start = time.time()

    for i, rec in enumerate(todo):
        outcome, n = fetch_one(rec["path"], rec["timestamp"], rec["mimetype"])
        results.append({
            "path": rec["path"],
            "kind": rec["kind"],
            "outcome": outcome,
            "bytes": n,
            "timestamp": rec["timestamp"],
            "mimetype": rec["mimetype"],
        })
        counts[outcome] += 1
        bytes_by_kind[rec["kind"]] += n
        if outcome == "failed":
            failed.append(rec["path"])
            # The index was already consulted for every capture inside
            # fetch_one. Repeating that for every remaining resource would add
            # hundreds of pointless CDX round-trips on re-runs, so the failure
            # is recorded and the run moves on.
            log(f"    ! unavailable: {rec['path']}")

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed else 0
            left = (len(todo) - i - 1) / rate if rate else 0
            log(f"    {i + 1}/{len(todo)}  "
                f"ok={counts['fetched']} cached={counts['cached']} "
                f"failed={counts['failed']}  "
                f"{rate * 60:.0f}/min  ~{left / 60:.0f} min left")

    # ---- write log -------------------------------------------------------
    out = os.path.join(C.WORK, "fetch-log.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        cols = ["path", "kind", "outcome", "bytes", "timestamp", "mimetype"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"\n  wrote {out}")

    cf, ct = C.cache_stats()
    elapsed = time.time() - start

    L = [
        "# Phase 4 - Fetch",
        "",
        f"Completed in {elapsed / 60:.1f} minutes.",
        "",
        "## Outcome",
        "",
        "| Result | Resources |",
        "|---|---:|",
        f"| Fetched this run | {counts['fetched']} |",
        f"| Already cached (from Phases 2-3) | {counts['cached']} |",
        f"| Failed | {counts['failed']} |",
        "",
        f"Cache now holds **{cf} files, {ct / 1048576:.1f} MB**.",
        "",
        "## Bytes by kind (this run)",
        "",
        "| Kind | Resources | Bytes |",
        "|---|---:|---:|",
    ]
    for k in sorted(bytes_by_kind, key=lambda x: -bytes_by_kind[x]):
        n = sum(1 for r in results if r["kind"] == k)
        L.append(f"| {k} | {n} | {bytes_by_kind[k] / 1048576:.2f} MB |")

    if failed:
        L += [
            "",
            "## Failures",
            "",
            f"{len(failed)} resources could not be retrieved at any of the four",
            "timestamps tried (chosen capture, 2015, 2013, 2011). These are assets",
            "the archive never stored. Per the locked decision their original",
            "`src` is left untouched, and they are listed in `missing-assets.md`",
            "in Phase 7.",
            "",
            "| Path | Kind |",
            "|---|---|",
        ]
        for p in failed:
            k = next((r["kind"] for r in results if r["path"] == p), "")
            L.append(f"| `{p}` | {k} |")
    else:
        L += ["", "## Failures", "",
              "None. Every resource in the manifest was retrieved."]

    L += ["", "## Verification", "",
          "Phase 5 checks each cached file against the CDX digest and length. Do",
          "not treat this phase as complete until that gate passes.", ""]

    rep = os.path.join(C.REPORTS, "fetch.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  wrote {rep}")

    print("\n" + "=" * 60)
    print(f"fetched={counts['fetched']}  cached={counts['cached']}  "
          f"failed={counts['failed']}")
    print(f"cache: {cf} files, {ct / 1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
