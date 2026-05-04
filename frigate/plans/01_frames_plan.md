# Plan: SVG Frame Lines → frames.scad

## Context
The user has traced ship frame cross-sections over a historical body plan drawing in Inkscape, producing `frigate/reference/lines.svg`. The traced paths are **polylines connecting control points** — the straight-line segments in the body plan that define the frame curves. The actual smooth hull curves will be generated in OpenSCAD from these control points (e.g. via BOSL2 bezier/spline functions).

The SVG structure:
- Group `g16415` — **fore frames** (right side of body plan, 6 paths)
- Group `g16425` — **aft frames** (left side of body plan, 8 paths)
- Circle `path16755` at `cx=101.64681, cy=190.91103` — **origin** (keel centerline)
- Layer transform: ignored

Coordinate transform needed:
- Translate all points by `-(origin_x, origin_y)`
- Flip Y axis (`y_out = -y_svg`) because SVG Y increases downward

## Output
Create `frigate/svg_to_frames.py` that reads `frigate/reference/lines.svg` and writes `frigate/frames.scad`.

### frames.scad format
```
// Generated from lines.svg
fore_frames = [
    // path1060
    [[x0,y0], [x1,y1], ...],
    // path1152
    [...],
    ...
];

aft_frames = [
    // path1793
    [[x0,y0], [x1,y1], ...],
    ...
];
```

Points are in mm, origin at keel/centerline, Y-up. Fore frames have positive X (starboard side). Aft frames have negative X (port side of the body plan drawing).

## Implementation

### svg_to_frames.py

**Dependencies:** stdlib only (`xml.etree.ElementTree`, `re`)

**Steps:**

1. **Parse SVG** with `xml.etree.ElementTree`, respecting the SVG namespace `{http://www.w3.org/2000/svg}`.

2. **Find origin**: read `cx`, `cy` from the circle element. Apply layer group transform.

3. **Extract vertices from path `d` attribute** — write a minimal path command parser that walks SVG path commands and emits only the vertices (endpoints). Commands to handle:
   - `M`/`m` — moveto (absolute/relative)
   - `L`/`l` — lineto (absolute/relative); implicit L after M
   - `C`/`c` — cubic bezier: extract only the **endpoint** (3rd coordinate pair per segment), ignore handles
   - `S`/`s` — smooth cubic: extract only endpoint (2nd pair)
   - `Z`/`z` — closepath: skip
   - Track current position for relative commands

4. **Transform points**:
   ```python
   x_out = x_svg - origin_x
   y_out = -(y_svg - origin_y)
   ```

6. **Collect frames** by iterating paths in `g16415` (fore) then `g16425` (aft), in SVG document order.

7. **Write frames.scad** with `fore_frames` and `aft_frames` arrays, with path ID as a comment per frame.

## Critical Files
- `frigate/reference/lines.svg` — input
- `frigate/svg_to_frames.py` — to create
- `frigate/frames.scad` — to generate

## Verification
Run `python frigate/svg_to_frames.py` and check:
- `frames.scad` is created with 6 fore frames and 8 aft frames
- Spot-check a known point: path1060 starts near `(103.79, 190.76)` in SVG → should become approx `(2.14, 0.15)` after transform
- Origin circle is at SVG `(101.65, 190.91)` → should map to `(0, 0)`
- In OpenSCAD, `include <frames.scad>` and echo a frame to verify point values are plausible hull coordinates
