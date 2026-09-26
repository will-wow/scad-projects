"""Measure the Smithsonian's scan of the Philadelphia, for the numbers the model uses.

    uv run --no-project --with dracopy --with numpy designs/measure_scan.py

Standalone on purpose: the model never reads the scan, so neither dracopy nor
the meshes are project dependencies. Put the two GLBs in designs/scan/ first --
designs/scan/README.md says which and where from.

The scan is in millimetres, Y up, Z along the length and X across. The bow is
at the Z-max end; the first thing this prints is the check that says so.

What it prints:

- which end is the bow: the fuller, lower one;
- the deck surface along the centreline, grouped into platforms and wells;
- each gun's axis height, elevation and muzzle radius, fitted as circles
  through sections of the barrel, and the rail beside it.

Every length is also given as a fraction of the boat's length from the bow,
which is how `main.py` places things, and heights as a fraction of the depth,
which is how a `Deck` takes them.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import DracoPy
import numpy as np

SCAN = Path(__file__).parent / "scan"
DECK = SCAN / "p0-Deck-89k-512.glb"
HULL = SCAN / "p1-Hull-83k-512.glb"

# The model's printed length, for the millimetres a number comes to on the toy.
PRINTED_LENGTH = 300.0

# Each gun's rough position, read off the scan's top view; the fits find the
# rest. Stations are fractions of the length from the bow; side is the sign of
# X, which facing the bow is port for +X.
NINE_POUNDERS = ((0.48, +1), (0.607, -1))

# The 12-pounder's length, and where its trunnions are: 3/7 of the length
# forward of the breech, the founders' rule cannon/cannon.py uses too.
TWELVE_POUNDER_LENGTH = 2438.0
TRUNNIONS_FROM_BREECH = 3.0 / 7.0

# How thick a section is sliced to fit a circle through, and how good a fit has
# to be to count: the barrel is a clean surface, and anything else the slice
# catches (a carriage, a rope) fits badly.
SLICE = 25.0
FIT = 10.0
BARREL_RADIUS = (80.0, 180.0)


def vertices(path: Path) -> np.ndarray:
    """The mesh's vertex positions. Every vertex is on the surface, which is
    all that heights and sections need -- no faces required."""
    if not path.exists():
        raise SystemExit(f"{path} is missing -- see {SCAN / 'README.md'}")
    data = path.read_bytes()
    size = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20 : 20 + size])
    binary = data[20 + size + 8 :]
    primitive = gltf["meshes"][0]["primitives"][0]
    view = gltf["bufferViews"][primitive["extensions"]["KHR_draco_mesh_compression"]["bufferView"]]
    start = view.get("byteOffset", 0)
    mesh = DracoPy.decode(binary[start : start + view["byteLength"]])
    return np.asarray(mesh.points, dtype=float).reshape(-1, 3)


def circle(u: np.ndarray, v: np.ndarray) -> tuple[float, float, float, float]:
    """Least-squares circle through points: centre, radius, mean miss."""
    a = np.c_[2 * u, 2 * v, np.ones_like(u)]
    (cu, cv, k), *_ = np.linalg.lstsq(a, u * u + v * v, rcond=None)
    r = float(np.sqrt(k + cu * cu + cv * cv))
    return float(cu), float(cv), r, float(np.abs(np.hypot(u - cu, v - cv) - r).mean())


class Boat:
    def __init__(self, deck: np.ndarray, hull: np.ndarray) -> None:
        self.deck, self.hull = deck, hull
        self.keel = float(hull[:, 1].min())
        self.stern, self.bow = float(hull[:, 2].min()), float(hull[:, 2].max())
        self.length = self.bow - self.stern
        middle = hull[np.abs(hull[:, 2] - self.z(0.5)) < self.length / 6]
        self.centre = float(middle[:, 0].min() + middle[:, 0].max()) / 2.0
        self.depth = float(hull[:, 1].max()) - self.keel

    def z(self, fraction: float) -> float:
        return self.bow - fraction * self.length

    def fraction(self, z: float) -> float:
        return (self.bow - z) / self.length

    def printed(self, mm: float) -> float:
        return mm * PRINTED_LENGTH / self.length

    def near(self, points: np.ndarray, z: float, half: float) -> np.ndarray:
        return points[np.abs(points[:, 2] - z) < half]

    def rail(self, z: float, side: float = 0.0) -> tuple[float, float]:
        """Rail height above the keel, and the half-breadth, near `z`."""
        band = self.near(self.hull, z, 0.004 * self.length)
        if side:
            band = band[np.sign(band[:, 0] - self.centre) == side]
        return float(band[:, 1].max()) - self.keel, float(np.abs(band[:, 0] - self.centre).max())

    def surface(self, z: float, below: float | None = None) -> float | None:
        """The deck (or bilge) along the centreline: the commonest height of
        the deck mesh in a strip down the middle, which is the flat of the
        planking rather than whatever stands on it."""
        strip = self.near(self.deck, z, 0.005 * self.length)
        heights = strip[np.abs(strip[:, 0] - self.centre) < 600][:, 1] - self.keel
        if below is not None:
            heights = heights[heights < below]
        if len(heights) < 50:
            return None
        counts, edges = np.histogram(heights, bins=np.arange(0.0, 2000.0, 25.0))
        return float(edges[counts.argmax()] + 12.5)


def orientation(boat: Boat) -> None:
    print("Which end is the bow (2m in from each end):")
    for name, z in (("Z-max end", boat.bow - 2000.0), ("Z-min end", boat.stern + 2000.0)):
        rail, half = boat.rail(z)
        print(f"  {name}: half-breadth {half:5.0f}, rail {rail:5.0f} above the keel")
    print("  The bow is the fuller, lower end. Facing it, +x is port.\n")


def decks(boat: Boat) -> None:
    print(f"Deck surface along the centreline (depth {boat.depth:.0f}):")
    stations = np.arange(0.05, 0.955, 0.01)
    heights = [boat.surface(boat.z(f)) for f in stations]
    runs: list[list[tuple[float, float]]] = []
    for f, h in zip(stations, heights, strict=True):
        if h is None:
            continue
        if runs and abs(h - np.median([p[1] for p in runs[-1]])) < 60.0:
            runs[-1].append((f, h))
        else:
            runs.append([(f, h)])
    for run in runs:
        if len(run) < 2:
            continue  # a single station is a hatch, a beam or a gun, not a deck
        height = float(np.median([h for _, h in run]))
        print(
            f"  {run[0][0]:.2f} - {run[-1][0]:.2f}: {height:4.0f} above the keel"
            f" = {height / boat.depth:.2f} of the depth"
        )
    print("  Edges are good to about a station (0.01) either way.\n")


def fitted(sections: list[tuple[float, float, float, float, float]]):
    """Keep the sections that look like barrel, and fit a line to their axis."""
    good = [s for s in sections if s[4] < FIT and BARREL_RADIUS[0] <= s[3] <= BARREL_RADIUS[1]]
    if len(good) < 4:
        return None
    along = np.array([s[0] for s in good])
    axis = np.array([s[2] for s in good])
    slope, intercept = np.polyfit(along, axis, 1)
    return good, float(slope), float(intercept)


def bow_gun(boat: Boat) -> None:
    sections = []
    for back in np.arange(0.0, 1300.0, 50.0):
        z = boat.bow - back
        s = boat.deck[
            (np.abs(boat.deck[:, 2] - z) < SLICE)
            & (np.abs(boat.deck[:, 0] - boat.centre) < 400.0)
            & (boat.deck[:, 1] - boat.keel > 1300.0)
        ]
        if len(s) >= 8:
            x, y, r, miss = circle(s[:, 0], s[:, 1] - boat.keel)
            sections.append((float(back), x, y, r, miss))
    result = fitted(sections)
    if result is None:
        print("12-pounder: no clean barrel sections found\n")
        return
    good, slope, at_stem = result
    muzzle = boat.deck[
        (np.abs(boat.deck[:, 0] - boat.centre) < 300.0) & (boat.deck[:, 1] - boat.keel > 1300.0)
    ][:, 2].max()
    rail, _ = boat.rail(boat.bow - 300.0)
    trunnions = (boat.bow - muzzle) + (1.0 - TRUNNIONS_FROM_BREECH) * TWELVE_POUNDER_LENGTH
    at_trunnions = at_stem + slope * trunnions
    stand = boat.surface(boat.bow - trunnions, below=at_trunnions - 300.0) or float("nan")
    print("12-pounder, on the centreline in the bow:")
    print(f"  muzzle {muzzle - boat.bow:+.0f} past the stem")
    print(f"  largest barrel section radius {max(s[3] for s in good):.0f}")
    print(f"  elevation {np.degrees(np.arctan(-slope)):.1f} deg (from {len(good)} sections)")
    print(f"  axis at the stem {at_stem:.0f} above the keel; rail there {rail:.0f}")
    print(
        f"  trunnions {trunnions:.0f} aft of the stem ({boat.fraction(boat.bow - trunnions):.3f}),"
        f" axis {at_trunnions:.0f} above the keel"
    )
    print(
        f"  deck under them {stand:.0f}; axis {at_trunnions - stand:.0f} above it"
        f" = {boat.printed(at_trunnions - stand):.1f}mm printed\n"
    )


def nine_pounders(boat: Boat) -> None:
    for station, side in NINE_POUNDERS:
        z = boat.z(station)
        rail, half = boat.rail(z, side)
        sections = []
        for out in np.arange(1300.0, 3000.0, 100.0):
            x = boat.centre + side * out
            s = boat.deck[
                (np.abs(boat.deck[:, 0] - x) < SLICE)
                & (np.abs(boat.deck[:, 2] - z) < 350.0)
                & (boat.deck[:, 1] - boat.keel > 1200.0)
            ]
            if len(s) >= 8:
                along, y, r, miss = circle(s[:, 2], s[:, 1] - boat.keel)
                sections.append((float(out), along, y, r, miss))
        result = fitted(sections)
        name = "port" if side > 0 else "starboard"
        if result is None:
            reach = max((s[0] for s in sections if s[4] < FIT), default=0.0)
            print(f"9-pounder, {name}, near {station}:")
            print(f"  too little clean barrel to fit -- traced to {reach:.0f} from the centreline,")
            print(f"  inboard of the rail at {half:.0f}, so it is scanned run in\n")
            continue
        good, slope, intercept = result
        at_rail = intercept + slope * half
        radius = max(s[3] for s in good)
        deck = boat.surface(z, below=rail) or float("nan")
        reach = max(s[0] for s in good)
        print(f"9-pounder, {name}:")
        print(
            f"  station {boat.fraction(float(np.median([s[1] for s in good]))):.3f} of the length"
        )
        print(f"  elevation {np.degrees(np.arctan(slope)):.1f} deg (from {len(good)} sections)")
        print(f"  barrel traced out to {reach:.0f} from the centreline; the rail is at {half:.0f}")
        print(f"  muzzle radius {radius:.0f}")
        print(f"  axis at the rail line {at_rail:.0f} above the keel, rail {rail:.0f}")
        print(f"  so the barrel's underside clears the rail by {at_rail - radius - rail:.0f}")
        print(f"  deck under it {deck:.0f}; axis {at_rail - deck:.0f} above it at the rail line")
        print(f"    = {boat.printed(at_rail - deck):.1f}mm printed\n")


def main() -> None:
    boat = Boat(vertices(DECK), vertices(HULL))
    print(
        f"Length {boat.length:.0f}, depth {boat.depth:.0f} (keel to highest rail); "
        f"1mm printed is {boat.length / PRINTED_LENGTH:.1f}mm full size\n"
    )
    orientation(boat)
    decks(boat)
    bow_gun(boat)
    nine_pounders(boat)


if __name__ == "__main__":
    main()
