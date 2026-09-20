# USS Philadelphia (1776) Gunboat — Hull Model → build123d Integration

## Project goal

Build a simplified, 3D-printable toy hull model of the Continental Navy gunboat
*Philadelphia* (Battle of Valcour Island, 1776; wreck raised 1935; on display at
the Smithsonian NMAH), derived from a real photogrammetry scan of the actual
surviving hull. Geometry has been reduced from the raw scan down to a small set
of 2D "lines plan" curves in a DXF file, hand-faired in LibreCAD, which now need
to become a 3D solid in build123d.

This is not a museum-accuracy replica — it's a kid's toy, simplified from the
real form. Fidelity to the *general* hull shape (flat bottom, flared sides,
raised bow/stern sheer) matters more than dimensional precision.

## Source data & provenance

- Original object: Smithsonian 3D scan of the real hull, downloaded as a
  Draco-compressed GLB (`p1-Hull-83k-4096.glb`, ~247k vertices, ~82.6k faces,
  not watertight — raw scan mesh).
- The scan is at **true 1:1 real-world scale**, units millimeters. Verified by
  comparing extracted bounding-box dimensions against documented historical
  specs:

  | Dimension | Scanned (mm) | Scanned (ft) | Documented |
  |---|---|---|---|
  | Length | 16,365.6 | 53.69 ft | 53–54 ft (sources vary; Smithsonian NMAH says 54 ft) |
  | Beam | 4,620.1 | 15.16 ft | 15 ft 2 in (near-exact match, <0.1% diff) |
  | Height, keel to rail | 1,803.1 | 5.91 ft | not directly comparable — documented "depth of hold" (4 ft) uses a different measurement convention than outside-keel-to-rail |

  **Bottom line: every millimeter in the source data is a real-world
  millimeter on the actual boat.** Any scale-down for the toy is a deliberate
  choice to make later, not something baked into the source.

- Hull form: flat-bottomed, hard-chine gundalow/scow type. This matters for
  the modeling approach — it means the hull can be represented as a flat
  bottom panel + flared/angled sides, not a compound-curved round-bilge hull.

## Methodology used to derive the lines

The raw mesh was sliced into 60 stations along its length axis. At each
station, two bands were sampled:

- **Top band** (~40mm window below the local max height) → gives the
  half-width of the **sheer line** (rail/gunwale edge) at that station, and
  the height of that edge above the keel baseline.
- **Bottom band** (~50mm window above the local min height) → gives the
  half-width of the **chine line** (edge where the flat bottom meets the
  angled side) at that station, and its height above baseline (the "rocker").

This produced four curves, each as (length-position, value) point pairs:
`SHEER_TOP` and `CHINE_BOTTOM` (half-width vs. length — a **half-breadth
plan**), and `SHEER_PROFILE` and `BASE_PROFILE` (height vs. length — a
**profile/side view**). Only half the beam is represented in the plan view
(standard naval-drafting convention for a symmetric hull) — mirror about the
centerline for full beam.

Because it's a raw scan of a damaged, 250-year-old wreck (plus surviving
fittings like a swivel-gun mount near the bow), the extracted curves have
noise: a couple of dips in the chine/plan curve (around the bow region), and
a likely bad final point or two in both profile curves near the stern
(probably the transom confusing the "local top" search rather than real
hull shape). **These are being manually faired out in LibreCAD** — see
Current Status below.

## File manifest

- `p1-Hull-83k-4096.glb` — original Smithsonian scan mesh. Reference only;
  not needed for the build123d work unless higher-fidelity detail is wanted
  later.
- `philadelphia_hull_lines.dxf` — the working lines-plan file, contains:
  - **Plan view** (drawn near Y = 0 to Y ≈ 2500 in the DXF): layers
    `SHEER_TOP`, `CHINE_BOTTOM` (raw curves, LWPOLYLINE, X = length from bow,
    Y = half-width from centerline), `CENTERLINE` (reference line, dashed).
  - **Profile view** (offset below the plan view by **Y = −3200mm** so the
    two views don't overlap): layers `SHEER_PROFILE`, `BASE_PROFILE` (raw
    curves, X = length from bow, Y = height-above-keel + (−3200) offset —
    **subtract the −3200 offset to recover true height above baseline**),
    `BASELINE` (reference line at the offset height, dashed).
  - `NOTES` layer — text annotations, not geometry.
  - All units mm, bow = X:0 in both views.
- Any LibreCAD-faired curves will be added by the user as new layers in this
  same file (likely named something like `SHEER_FAIR` / `CHINE_FAIR` —
  **confirm actual layer names with the user**, they were not finalized as of
  this handoff).

**Note on paths:** these files currently exist in a Claude.ai sandbox. The
user will need to place copies into the Claude Code project directory and
these instructions should be adapted to wherever they land.

## Glossary (for quick reference)

- **Half-breadth plan**: top-down view of a hull, showing width-from-centerline
  vs. length. Only half the beam is drawn by convention (hulls are symmetric).
- **Sheer line**: the top edge of the hull's side, i.e. the rail/gunwale, as
  a fore-aft curve. Rises toward bow/stern in this hull.
- **Chine line**: on a hard-chine hull, the line where the flat bottom panel
  meets the angled/flared side. Its plan-view shape is the outline of the
  flat bottom.
- **Profile view**: side view — height vs. length, as opposed to the
  half-breadth plan's width vs. length.
- **Baseline**: the height-datum (here, the lowest point of the keel) that
  profile-view heights are measured from.
- **Fairing**: smoothing a lofted curve so it flows without lumps or
  reversals, traditionally done by bending a flexible batten through
  reference points; here, done by hand in LibreCAD.

## Current status (as of handoff)

- Raw curves are extracted and in the DXF (done).
- User is manually fairing the curves in LibreCAD, tracing new spline-through-points
  curves on new layers over the raw data, skipping known-noisy points (in
  progress — **check with the user whether this is finished, and get the
  final layer names, before assuming the DXF has fair curves ready to
  consume**).

## build123d integration — recommended approach

1. **Get clean point data out of the DXF.** Recommend using `ezdxf` to read
   the faired-curve LWPOLYLINE/SPLINE entities directly rather than relying
   on build123d's own DXF import (verify current build123d DXF import support
   first — as of last check it's not a strong/native feature, so parsing with
   `ezdxf` into plain point lists and feeding those to build123d's own
   `Spline`/`Bezier`/`Polyline` sketch primitives is likely the more robust
   path). If the fair curves are LWPOLYLINE, `entity.get_points()` gives you
   what you need directly; if true SPLINE entities, sample them via
   `entity.flattening(distance)`.

2. **Reconstruct true 3D curves from the two 2D views.** The plan view gives
   `(length, half_width)` for the sheer and chine edges. The profile view
   gives `(length, height)` for the same two edges. Combine by length
   position to get 3D points: sheer edge = `(length, ±half_width_sheer,
   height_sheer)`, chine edge = `(length, ±half_width_chine, height_chine)`.
   Interpolate one curve onto the other's length sampling if the point sets
   don't align exactly.

3. **Build the hull as a loft/shell**, roughly:
   - Flat bottom panel: a face bounded by the mirrored chine curve (at its
     recorded heights — there's a slight rocker, not perfectly flat).
   - Sides: ruled/lofted surface between the chine curve and the sheer curve
     at each length station.
   - Mirror the starboard-half geometry across the centerline (Y=0 plane) to
     get the full hull, or model both halves directly if the fair curves were
     drawn as full curves already.
   - Cap bow and stern (likely simple closing faces, since a toy doesn't need
     the real transom/stem detail).
   - Shell the solid to a printable wall thickness if a hollow hull is
     desired (confirm with user), or keep solid if that's easier to print
     reliably at toy scale.

4. **Scale down for the toy.** Source geometry is 1:1 (real mm). Apply a
   uniform scale factor once the target size is decided — do this as a single
   transform at the end, not by re-deriving geometry, so the shape stays
   consistent with what was faired in CAD.

5. **Orient for printing.** This is a flat-bottomed hull — printing bottom-down
   with no supports needed for the hull body is the obvious orientation;
   confirm before assuming.

## Open questions to resolve with the user before/while building

- Target print scale (final size / scale ratio)?
- Solid hull, or shelled/hollow with a wall thickness?
- Keep the historical proportions faithfully, or take further creative
  liberties for toy durability/playability (wider flat bottom for stability,
  thicker walls, rounded edges for a kid's toy, etc.)?
- Any added features wanted (mast socket, cannon, simplified deck, etc.) or
  hull-only?
- Confirm the final fair-curve layer names in the DXF, and confirm fairing is
  complete before treating that data as final.
- Does the print bed / printer have a size constraint that requires splitting
  the hull into sections?

## Known data-quality caveats to double check against the fair curves

- Chine/plan curve: noticeable dips in the raw data around two stations in
  the forward half of the hull (scan gaps, not real hull features) — confirm
  these were faired out.
- Profile curves (both sheer and base): the last 1–2 stations near the stern
  looked like scan/data artifacts rather than true hull shape (an abrupt
  height change inconsistent with the surrounding curve) — confirm the faired
  version smooths through this rather than following it literally.
- Base profile near the very bow read as near-zero height for the first
  couple of stations, which may be a scan gap rather than the bottom truly
  meeting the baseline that early — worth a sanity check against the plan
  view's bow taper.
