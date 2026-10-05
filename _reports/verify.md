# Phase 5 - Verification

Every cached file is checked against the CDX index's own SHA-1 digest and
length, and screened for archive error pages served in place of a capture.

## Results

| Status | Resources |
|---|---:|
| ok | 3532 |
| digest_unstable | 5 |
| short_but_valid | 4 |
| missing | 4 |
| digest_mismatch | 0 |
| length_mismatch | 0 |
| poisoned | 0 |

**3532** files matched the index's cryptographic digest exactly.

**5** differed from it but are structurally valid. The archive
is not byte-stable for every resource: replaying the same URL at the same
timestamp can return a different payload depending on the edge node.
`/category/entrevistas/` and `/ana-caprix-.../feed/` both mismatched once
and matched exactly on refetch, while `/category/eventos/` consistently
returns a different but valid page. Treating a digest mismatch as failure
on its own destroyed 32 good files, so a mismatch is only a failure when
the payload is *also* structurally broken.

**4** are shorter than the indexed record length but carry a valid
format terminator. CDX length is the compressed record size and only a
loose bound; the theme's separator graphics are genuinely tiny
(`cruz.png` is ~140 bytes when complete).

**0** had no digest in the index and were checked on length and
content only.

## Files needing attention

| Path | Status | Detail |
|---|---|---|
| `/weekend-update/feed/` | missing |  |
| `/wp-content/plugins/jquery-archive-list-widget/jquery-archive-list.js.php` | missing |  |
| `/xmlrpc.php` | missing |  |
| `/zonora-point-douster-2/feed/` | missing |  |

0 file(s) were evicted from the cache. Re-run Phase 4 to
retry them; the archive is often merely under load, and the same URL
usually succeeds on a later attempt.
