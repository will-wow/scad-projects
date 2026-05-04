#!/usr/bin/env python3
"""Converts lines.svg frame control-point traces to frames.scad for BOSL2 skin()."""

import re
import xml.etree.ElementTree as ET

SVG_FILE  = "reference/lines.svg"
OUT_FILE  = "frames.scad"
NS        = "{http://www.w3.org/2000/svg}"

# ---------------------------------------------------------------------------
# SVG path parser — extracts only the endpoint vertices, ignoring bezier handles
# ---------------------------------------------------------------------------

def _nums(s):
    return [float(x) for x in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", s)]

def parse_vertices(d):
    """Return list of (x, y) vertices from an SVG path d-attribute."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", d)

    pts = []
    cx = cy = 0.0
    cmd = None
    nums = []

    def flush():
        nonlocal cx, cy, cmd, nums
        if cmd is None or not nums:
            return
        c = cmd
        while nums:
            if c in "Mm":
                x, y = nums.pop(0), nums.pop(0)
                if c == "m":
                    x += cx; y += cy
                pts.append((x, y))
                cx, cy = x, y
                c = "l" if cmd == "m" else "L"
            elif c in "Ll":
                x, y = nums.pop(0), nums.pop(0)
                if c == "l":
                    x += cx; y += cy
                pts.append((x, y))
                cx, cy = x, y
            elif c in "Cc":
                # 3 pairs per segment; only the 3rd is the endpoint
                x1, y1 = nums.pop(0), nums.pop(0)
                x2, y2 = nums.pop(0), nums.pop(0)
                x,  y  = nums.pop(0), nums.pop(0)
                if c == "c":
                    x1+=cx; y1+=cy; x2+=cx; y2+=cy; x+=cx; y+=cy
                pts.append((x, y))
                cx, cy = x, y
            elif c in "Ss":
                x2, y2 = nums.pop(0), nums.pop(0)
                x,  y  = nums.pop(0), nums.pop(0)
                if c == "s":
                    x2+=cx; y2+=cy; x+=cx; y+=cy
                pts.append((x, y))
                cx, cy = x, y
            elif c in "Qq":
                nums.pop(0); nums.pop(0)
                x, y = nums.pop(0), nums.pop(0)
                if c == "q":
                    x += cx; y += cy
                pts.append((x, y))
                cx, cy = x, y
            elif c in "Hh":
                x = nums.pop(0)
                if c == "h":
                    x += cx
                pts.append((x, cy))
                cx = x
            elif c in "Vv":
                y = nums.pop(0)
                if c == "v":
                    y += cy
                pts.append((cx, y))
                cy = y
            elif c in "Zz":
                break
            else:
                nums.clear()
                break
        nums = []

    for tok in tokens:
        if tok.isalpha():
            flush()
            cmd = tok
        else:
            nums.append(float(tok))
    flush()
    return pts

# ---------------------------------------------------------------------------
# SVG loading
# ---------------------------------------------------------------------------

def load_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()
    return root

def find_origin(root):
    for el in root.iter(f"{NS}circle"):
        return float(el.get("cx")), float(el.get("cy"))
    raise ValueError("Origin circle not found in SVG")

def all_groups(root):
    """Return direct-child groups of the layer, in document order."""
    layer = next(g for g in root.iter(f"{NS}g") if g.get("id") == "layer1")
    return [g for g in layer if g.tag == f"{NS}g"]

def group_paths(g):
    return [(p.get("id"), p.get("d")) for p in g.iter(f"{NS}path") if p.get("d")]

# ---------------------------------------------------------------------------
# Coordinate transform and cleanup
# ---------------------------------------------------------------------------

def transform(pts, ox, oy):
    return [((x - ox), -(y - oy)) for x, y in pts]

def ascending(pts):
    """Take points while Y is strictly increasing (keel→deck direction)."""
    out = [pts[0]]
    for p in pts[1:]:
        if p[1] <= out[-1][1]:
            break
        out.append(p)
    return out

def normalize(pts, pid):
    """Split a path into one or two keel→deck frames.

    A V-shaped path (deck→keel→deck) represents two frames joined at the keel;
    split it there. A simple one-direction path yields a single frame.
    """
    if not pts:
        return []
    keel_idx = min(range(len(pts)), key=lambda i: pts[i][1])
    if keel_idx == 0:
        # Already starts at keel, single frame
        return [ascending(pts)]
    if keel_idx == len(pts) - 1:
        # Ends at keel — reverse for single frame
        return [ascending(list(reversed(pts)))]
    # V-shape: split into two frames at the keel
    print(f"  {pid}: split at keel index {keel_idx}/{len(pts)-1}")
    left  = ascending(list(reversed(pts[:keel_idx+1])))  # first half, reversed → keel→deck
    right = ascending(pts[keel_idx:])                     # second half → keel→deck
    return [left, right]

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def fmt_frame(pts):
    inner = ", ".join(f"[{x:.4f},{y:.4f}]" for x, y in pts)
    return f"[{inner}]"

def write_scad(fore_frames, aft_frames, out_path, ox, oy):
    with open(out_path, "w") as f:
        f.write("// Generated by svg_to_frames.py\n")
        f.write(f"// SVG origin: ({ox:.5f}, {oy:.5f})\n")
        f.write("// Points in mm, Y-up, origin at keel/centreline\n")
        f.write("// Fore frames: +X (starboard).  Aft frames: -X (port side of body plan)\n\n")

        f.write("fore_frames = [\n")
        for pid, pts in fore_frames:
            f.write(f"    // {pid}\n    {fmt_frame(pts)},\n")
        f.write("];\n\n")

        f.write("aft_frames = [\n")
        for pid, pts in aft_frames:
            f.write(f"    // {pid}\n    {fmt_frame(pts)},\n")
        f.write("];\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = load_svg(SVG_FILE)
    ox, oy = find_origin(root)
    print(f"Origin: ({ox:.5f}, {oy:.5f})")

    groups = all_groups(root)
    fore_raw = group_paths(groups[0])
    aft_raw  = group_paths(groups[1])
    print(f"Groups: {[g.get('id') for g in groups]}")

    def process(raw):
        out = []
        for pid, d in raw:
            for i, pts in enumerate(normalize(transform(parse_vertices(d), ox, oy), pid)):
                label = pid if i == 0 else f"{pid}b"
                out.append((label, pts))
        return out

    fore_frames = process(fore_raw)
    aft_frames  = process(aft_raw)

    print(f"Fore frames: {len(fore_frames)}, Aft frames: {len(aft_frames)}")
    for pid, pts in fore_frames:
        print(f"  {pid}: {len(pts)} pts  first={pts[0]}")
    for pid, pts in aft_frames:
        print(f"  {pid}: {len(pts)} pts  first={pts[0]}")

    write_scad(fore_frames, aft_frames, OUT_FILE, ox, oy)
    print(f"Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
