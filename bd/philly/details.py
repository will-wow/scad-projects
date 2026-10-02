"""The boat's joinery: knees, benches and the keelson.

None of it changes how the hull works; it is what makes the model read as the
boat in the scan rather than a hollow shape. Each piece is sized from the
Smithsonian's scan (see designs/measure_scan.py) and fitted to the hull's own
lines, the way the mast step and the gun slides are:

- **Knees** on the middle platform: L-shaped timbers against the inside of the
  side, a tall arm up the bulwark and a low one along the deck. The platform's
  ends carry a cross-beam each, with a knee either side standing on it.
- **Benches** along both sides of the quarterdeck, solid down to the deck as
  the scan's front boards make them look.
- **The keelson**, the top of the backbone, showing along the centreline of
  each well.

Everything is merged into the hull, so it prints with it. A piece that meets
the side reaches `OVERLAP` into the planking -- the side flares, so it follows
the inside face up rather than standing square -- and one that stands on a
deck is sunk `SINK` into it. Both are well under the planking, so nothing shows
through outside.

Millimetres of the finished model throughout, as in rig.py.
"""

from __future__ import annotations

import numpy as np
from build123d import Box, Part, Polyline, Pos, extrude, loft, make_face

from hull import (
    Deck,
    HullSpec,
    Knee,
    Scaled,
    _cavity_span,
    as_part,
    clear_of_seams,
    deck_at,
    open_stretches,
)
from lines import HullLines

# How far a piece reaches into the planking or the deck it is merged with.
OVERLAP = 0.3
SINK = 0.3

# A knee, from the scan's middle platform. The tall arm stops a little under
# the rail, which the scan has within a few centimetres of it.
KNEE_BELOW_RAIL = 0.5
KNEE_ARM = 1.8
"""the low arm's top, above the deck"""
KNEE_REACH = 15.6
"""how far the low arm runs inboard of the inside face"""
KNEE_TAPER = 3.7
"""the low arm's last stretch, sloping down to the deck"""
KNEE_MOULDED = (2.3, 1.6)
"""the tall arm, moulded, at the foot of its curve and at its top"""
KNEE_SIDING = 1.6
KNEE_THROAT = 5.0
"""the radius of the curve at the throat, the knee's inside corner"""

# The cross-beam across each end of a knee'd platform, flush with its edge.
# Sided fore and aft, moulded in depth, as any timber is.
BEAM_SIDING = 2.5
BEAM_MOULDED = 1.9

# The quarterdeck benches: the scan puts the seat 340mm above the deck and
# 420-540mm out from the side, which is 6.2 and 7.7-9.9 here.
BENCH_SEAT = 6.2
BENCH_REACH = 8.8

# The keelson stands this far proud of a well's ceiling, and is this wide.
KEELSON_PROUD = 1.8
KEELSON_WIDTH = 4.0

# Sections along a bench, and points up a flared side.
BENCH_SECTIONS = 8
SIDE_POINTS = 5


def _side(hull: Scaled, x: float, low: float, high: float) -> list[tuple[float, float]]:
    """The inside face from `low` up to `high`, reached into by `OVERLAP`, as (y, z)."""
    return [
        (hull.inside(x, float(z)) + OVERLAP, float(z)) for z in np.linspace(low, high, SIDE_POINTS)
    ]


def _deck_at(spec: HullSpec, fraction: float) -> Deck:
    """As `hull.deck_at`, but nothing here can stand over open bilge."""
    deck = deck_at(spec, fraction)
    if deck is None:
        raise ValueError(f"there is no deck at {fraction:.3f} to stand anything on")
    return deck


def _transverse(profile: list[tuple[float, float]], x: float, side: int, siding: float) -> Part:
    """A (y, z) outline, starboard side up, extruded `siding` along the boat from `x`."""
    points = [(x, side * y, z) for y, z in profile]
    face = make_face(Polyline(*points, close=True))
    return Part(extrude(face, siding, dir=(1.0, 0.0, 0.0)).wrapped)


def knee(hull: Scaled, x: float, side: int, platform: Deck) -> Part:
    """One knee, centred on station `x`, standing on `platform`."""
    deck = hull.deck(platform)
    top = hull.sheer(x) - KNEE_BELOW_RAIL
    arm = deck + KNEE_ARM
    throat = arm + KNEE_THROAT
    if top <= throat:
        raise ValueError(f"the bulwark at {x:.1f}mm is too low for a knee")

    def moulded(z: float) -> float:
        return KNEE_MOULDED[0] + (KNEE_MOULDED[1] - KNEE_MOULDED[0]) * (z - throat) / (top - throat)

    tall = [
        (hull.inside(x, float(z)) - moulded(float(z)), float(z))
        for z in np.linspace(top, throat, SIDE_POINTS)
    ]
    # The throat's curve, from the tall arm's inside face round onto the low arm's top.
    corner = tall[-1][0] - KNEE_THROAT
    curve = [
        (corner + KNEE_THROAT * np.cos(t), throat + KNEE_THROAT * np.sin(t))
        for t in np.linspace(0.0, -np.pi / 2.0, 7)[1:]
    ]
    face = hull.inside(x, deck)
    end = face - KNEE_REACH
    end += clear_of_seams(hull.spec, platform, (end,))
    profile = [
        *_side(hull, x, deck - SINK, top),
        *tall,
        *((float(y), float(z)) for y, z in curve),
        (end + KNEE_TAPER, arm),
        (end, deck),
        (end, deck - SINK),
    ]
    if curve[-1][0] <= end + KNEE_TAPER:
        raise ValueError(f"the knee at {x:.1f}mm has no low arm left past its curve")
    return _transverse(profile, x - KNEE_SIDING / 2.0, side, KNEE_SIDING)


def beam(hull: Scaled, x: float, deck: float) -> Part:
    """A cross-beam from `x` aft by its siding, side to side on the deck at height `deck`."""
    top = deck + BEAM_MOULDED
    # The narrower of its two faces, so it reaches into the side at both.
    near = min((x, x + BEAM_SIDING), key=lambda s: hull.inside(s, deck))
    starboard = _side(hull, near, deck - SINK, top)
    profile = [*starboard, *((-y, z) for y, z in reversed(starboard))]
    return _transverse(profile, x, 1, BEAM_SIDING)


def bench(hull: Scaled, start: float, end: float, deck: float, side: int) -> Part:
    """A bench from station `start` to `end` along one side, solid down to the deck."""
    seat = deck + BENCH_SEAT
    sections = []
    for x in np.linspace(start, end, BENCH_SECTIONS):
        x = float(x)
        front = hull.inside(x, seat) - BENCH_REACH
        profile = [*_side(hull, x, deck - SINK, seat), (front, seat), (front, deck - SINK)]
        sections.append(make_face(Polyline(*[(x, side * y, z) for y, z in profile], close=True)))
    return Part(loft(sections).wrapped)


def bench_top(spec: HullSpec, lines: HullLines, fraction: float) -> float | None:
    """The seat's height where a bench covers `fraction`, or None where none does."""
    covering = next((b for b in spec.benches if b.start <= fraction <= b.end), None)
    if covering is None:
        return None
    return Scaled(spec, lines).deck(_deck_at(spec, fraction)) + BENCH_SEAT


def keelson(hull: Scaled, start: float, end: float) -> Part:
    """The keelson from `start` to `end` along the centreline, on a well's ceiling."""
    ceiling = hull.ceiling(0.5 * (start + end))
    height = KEELSON_PROUD + SINK
    return Pos(0.5 * (start + end), 0.0, ceiling - SINK + height / 2.0) * Box(
        end - start, KEELSON_WIDTH, height
    )


def _platform_knees(hull: Scaled, spec: HullSpec) -> tuple[list[Part], list[tuple[Knee, Deck]]]:
    """Each knee'd platform's cross-beams, and every knee with the deck it stands on.

    A platform is knee'd if any of `spec.knees` stands on it, and then its end
    pairs come with it: the beams are its edges, so they move when it does.
    """
    beams: list[Part] = []
    knees: list[tuple[Knee, Deck]] = []
    platforms = {_deck_at(spec, k.station) for k in spec.knees}
    for platform in sorted(platforms, key=lambda d: d.start):
        height = hull.deck(platform)
        length = hull.station(1.0) - hull.station(0.0)
        for edge, inward in ((platform.start, 1.0), (platform.end, -1.0)):
            x = hull.station(edge)
            beams.append(beam(hull, x if inward > 0 else x - BEAM_SIDING, height))
            middle = (x + inward * BEAM_SIDING / 2.0 - hull.station(0.0)) / length
            knees += [(Knee(middle, s), platform) for s in (-1, 1)]
    knees += [(k, _deck_at(spec, k.station)) for k in spec.knees]
    return beams, knees


def fit_details(hull: Part, spec: HullSpec, lines: HullLines) -> Part:
    """Merge the knees, benches and keelson into a finished hull.

    Runs after `build`, like every fitting, and before the awning's: its
    sockets are bored into the benches where a pair of stanchions stands on one.
    """
    at = Scaled(spec, lines)
    pieces: list[Part] = []

    beams, knees = _platform_knees(at, spec)
    pieces += beams
    pieces += [knee(at, at.station(k.station), k.side, platform) for k, platform in knees]

    for b in spec.benches:
        deck = _deck_at(spec, b.start)
        if deck is not _deck_at(spec, b.end):
            raise ValueError(f"the bench {b.start}..{b.end} does not stand on one deck")
        for side in (-1, 1):
            pieces.append(bench(at, at.station(b.start), at.station(b.end), at.deck(deck), side))

    if spec.keelson:
        planking = spec.planking / at.factor
        first, last = _cavity_span(lines, planking, *lines.span)
        for a, b in open_stretches(sorted(spec.decks, key=lambda d: d.start)):
            # Into the bulkhead at each end, or as far as the hull has a ceiling.
            start = max(at.station(a) - OVERLAP, first * at.factor)
            end = min(at.station(b) + OVERLAP, last * at.factor)
            if end > start:
                pieces.append(keelson(at, start, end))

    if not pieces:
        return hull
    # One fuse with every piece as its own tool: the end knees overlap their
    # beams, which a single compound tool could not have, and a fuse apiece
    # costs a whole hull's worth of boolean each time.
    return as_part(Part([hull.fuse(*pieces)]), "fitting the joinery")
