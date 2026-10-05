# Phase 5 - Verification

Every cached file is checked against the CDX index's own SHA-1 digest and
length, and screened for archive error pages served in place of a capture.

## Results

| Status | Resources |
|---|---:|
| ok | 3459 |
| digest_unstable | 5 |
| short_but_valid | 4 |
| missing | 77 |
| digest_mismatch | 0 |
| length_mismatch | 0 |
| poisoned | 0 |

**3459** files matched the index's cryptographic digest exactly.

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
| `/actually-huizenga-live-softrock-1-3/feed/` | missing |  |
| `/all-your-gifs-are-belong-to-us/feed/` | missing |  |
| `/bb-pinkblue/feed/` | missing |  |
| `/dont/feed/` | missing |  |
| `/evian-christ-no-experiences/feed/` | missing |  |
| `/ez-does-it/feed/` | missing |  |
| `/gauntlet-hair-top-bunk/feed/` | missing |  |
| `/holy-other-love-some1-teengirl-fantasy-remix-featuring-kelela/feed/` | missing |  |
| `/icepunk-2-compilation/feed/` | missing |  |
| `/julia-holter-nite-jewel-what-we-see/feed/` | missing |  |
| `/king-night-rotterdam-terror-corps-remix/feed/` | missing |  |
| `/lost-in-my-bedroom/feed/` | missing |  |
| `/mr-kitty-evaporating-sun/feed/` | missing |  |
| `/narcissistic-cannibal-ritualz-remix/feed/` | missing |  |
| `/opening-botiquin-by-petit-pistolette/feed/` | missing |  |
| `/ritualz-alien/feed/` | missing |  |
| `/selma-oxor-lo-que-quiero-video/feed/` | missing |  |
| `/sky-ferreira-red-lips/feed/` | missing |  |
| `/soft/feed/` | missing |  |
| `/sorry-hun/feed/` | missing |  |
| `/spoek-mathambo-control-2/feed/` | missing |  |
| `/strain/feed/` | missing |  |
| `/tag/crackboy/` | missing |  |
| `/tag/true-parameters/` | missing |  |
| `/tell-me/feed/` | missing |  |
| `/unicorn-kid/feed/` | missing |  |
| `/volume-control/feed/` | missing |  |
| `/weekend-update/feed/` | missing |  |
| `/wp-content/plugins/jquery-archive-list-widget/jquery-archive-list.js.php` | missing |  |
| `/wp-content/uploads/2010/12/cce-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/01/negative-youth-4-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/02/dumdum-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/04/5386216546_84442e1782_b1-150x150.jpg` | missing |  |
| `/wp-content/uploads/2011/04/ppmixpmx-150x150.jpg` | missing |  |
| `/wp-content/uploads/2011/06/Blonde+Salem.jpg` | missing |  |
| `/wp-content/uploads/2011/06/event-150x150.jpg` | missing |  |
| `/wp-content/uploads/2011/06/kidcity-150x150.jpg` | missing |  |
| `/wp-content/uploads/2011/07/artworks-000007634829-5nl2sq-original1-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/08/270954_175258772533731_144703902255885_432519_5363668_n-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/09/autom.jpg` | missing |  |
| `/wp-content/uploads/2011/10/htrk-200x200.png` | missing |  |
| `/wp-content/uploads/2011/11/RS5x.jpg` | missing |  |
| `/wp-content/uploads/2011/11/YOUNGMAGIC-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/11/skrinshot-200x200.png` | missing |  |
| `/wp-content/uploads/2011/12/Untitled-1-200x200.jpg` | missing |  |
| `/wp-content/uploads/2011/12/arnold-200x200.png` | missing |  |
| `/wp-content/uploads/2012/01/ny2012-700px-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/02/alexico_elnombredelperro-200x200.png` | missing |  |
| `/wp-content/uploads/2012/02/nrmal-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/03/men-in-burka-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/04/powwoww-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/04/rlgrime.jpg` | missing |  |
| `/wp-content/uploads/2012/05/LD_V_2-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/05/Spaceghostpurrp-608x3651-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/05/ritualz_alien-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/06/earthqake-200x200.png` | missing |  |
| `/wp-content/uploads/2012/06/haleek-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/06/swt5-200x200.png` | missing |  |
| `/wp-content/uploads/2012/07/artworks-000026381381-17nsbd-original.png` | missing |  |
| `/wp-content/uploads/2012/08/borntosuffer-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/08/goin-hamburger-200x200.png` | missing |  |
| `/wp-content/uploads/2012/09/famlay_lilinternet.jpg` | missing |  |
| `/wp-content/uploads/2012/09/mexico_occultdanse.jpg` | missing |  |
| `/wp-content/uploads/2012/09/user69.jpg` | missing |  |
| `/wp-content/uploads/2012/10/BON.jpg` | missing |  |
| `/wp-content/uploads/2012/10/Screen-Shot-2012-10-18-at-12.48.37-PM.png` | missing |  |
| `/wp-content/uploads/2012/11/INDIAN-JEWELRY-PEEL-IT-cover-200x200.jpeg` | missing |  |
| `/wp-content/uploads/2012/11/artworks-000034282831-6kbql0-original-700x960.jpg` | missing |  |
| `/wp-content/uploads/2012/11/bestial-mouths-200x200.png` | missing |  |
| `/wp-content/uploads/2012/12/mr-kitty-200x200.jpg` | missing |  |
| `/wp-content/uploads/2012/12/rihanna.jpg` | missing |  |
| `/wp-content/uploads/2013/01/ryder2-copy.jpg` | missing |  |
| `/wp-content/uploads/2013/02/2533619025-11-200x200.jpg` | missing |  |
| `/wp-content/uploads/2013/02/Screen-Shot-2013-02-20-at-4.39.32-PM-200x200.png` | missing |  |
| `/wp-content/uploads/2013/06/Captura-de-pantalla-2013-06-18-a-las-11.09.25-200x200.png` | missing |  |
| `/xmlrpc.php` | missing |  |
| `/zonora-point-douster-2/feed/` | missing |  |

0 file(s) were evicted from the cache. Re-run Phase 4 to
retry them; the archive is often merely under load, and the same URL
usually succeeds on a later attempt.
