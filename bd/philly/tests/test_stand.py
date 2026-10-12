"""The stand: the sketch's X, a cradle the hull lifts in and out of, and lettering that prints.

A stand that misses the hull still builds a valid solid, so the cradle is
checked against the built hull itself: resting in it, free to move by the
clearance, and no further.
"""

from __future__ import annotations

import math
import os
from dataclasses import replace

import numpy as np
import pytest
from build123d import Part, Pos, Vector
from scipy import ndimage

# Before main is imported, whose HULL reads this.
os.environ.setdefault("PREVIEW", "1")

from conftest import steepest_overhang  # noqa: E402

import stand as stands  # noqa: E402
from export import write_3mf  # noqa: E402
from hull import Scaled  # noqa: E402
from main import HULL, STAND  # noqa: E402

BARE = replace(STAND, lettering=None)

# Pixel size when rasterising letters, in millimetres.
PIXEL = 0.02

# The narrowest stroke a 0.4mm nozzle lays down reliably.
STROKE = 0.4


@pytest.fixture(scope="module")
def at(lines):
    return Scaled(HULL, lines)


@pytest.fixture(scope="module")
def frame(at):
    """Where the stand stands: its forward end, its middle, and the bottom of it."""
    middle = at.station(STAND.station)
    return middle - STAND.length / 2.0, middle, at.bottom(middle) - STAND.floor


@pytest.fixture(scope="module")
def lettered(lines):
    return stands.placed(HULL, lines, STAND)


@pytest.fixture(scope="module")
def bare(lines):
    return stands.placed(HULL, lines, BARE)


def _overlap(a: Part, b: Part) -> float:
    return sum(s.volume for s in (a & b).solids())


def test_the_printed_stand_is_one_solid_of_the_size_drawn(lines):
    part = stands.printed(HULL, lines, STAND)
    assert part.is_valid
    assert len(part.solids()) == 1
    size = part.bounding_box().size
    assert pytest.approx((STAND.height, STAND.breadth, STAND.length), abs=1e-3) == (
        size.X,
        size.Y,
        size.Z,
    )


def test_the_section_is_the_sketch(bare, frame):
    """Solid bars and neck, and the two triangles open right through."""
    x0, _, z0 = frame

    def solid(y: float, z: float) -> bool:
        return bare.is_inside(Vector(x0 + 5.0, y, z0 + z))

    inboard = STAND.breadth / 2.0 - 26.0
    lower = STAND.base + STAND.base_slope * inboard
    upper = STAND.height - STAND.top - STAND.cradle_slope * inboard
    for side in (-1.0, 1.0):
        assert solid(side * 30.0, STAND.base / 2.0), "the base"
        assert solid(side * 39.0, STAND.height - STAND.top / 2.0), "the top, outboard of the cradle"
        assert solid(side * 26.0, lower - 0.5), "under the lower arm"
        assert not solid(side * 26.0, (lower + upper) / 2.0), "the open triangle"
        assert solid(side * 26.0, upper + 0.5), "over the upper arm"
        assert not solid(side * (STAND.neck / 2.0 + 0.5), STAND.crossing), (
            "just outboard of the neck"
        )
        assert solid(side * (STAND.neck / 2.0 - 0.5), STAND.crossing), "just inboard of it"
    assert solid(0.0, STAND.crossing), "the neck"


def test_the_hull_rests_on_the_cradle_floor(built_hull, bare):
    assert _overlap(built_hull, bare) < 1e-3
    lifted = Pos(0.0, 0.0, 0.3) * built_hull
    assert bare.distance_to(lifted) == pytest.approx(0.3, abs=0.02)


def test_the_hull_has_its_clearance_and_little_more(built_hull, bare):
    """It moves sideways by less than the clearance freely, and not by much more."""
    for side in (-1.0, 1.0):
        assert _overlap(Pos(0.0, side * 0.5, 0.0) * built_hull, bare) < 1e-3
        assert _overlap(Pos(0.0, side * 1.5, 0.0) * built_hull, bare) > 1.0


def test_the_hull_cannot_slide_out_fore_and_aft(built_hull, bare):
    """It narrows both ways from its greatest breadth, which lies within the cradle.

    Only slowly, though -- a twelfth of a millimetre per millimetre at the
    cradle's ends -- so the clearance lets it shuffle about 7mm forward and 10mm
    aft before its sides bear.
    """
    for shift in (-12.0, 12.0):
        assert _overlap(Pos(shift, 0.0, 0.0) * built_hull, bare) > 1.0


def test_the_cradle_leaves_a_floor_and_a_rim(at, frame):
    """Material under the corners of the cradle's floor, and either side of its mouth."""
    x0, _, z0 = frame
    for x in np.linspace(x0, x0 + STAND.length, 13):
        corner = at.inside(float(x), at.bottom(float(x)), -STAND.clearance)
        underside = STAND.crossing + STAND.cradle_slope * corner
        assert STAND.floor - underside >= 2.0
        mouth = at.inside(float(x), z0 + STAND.height, -STAND.clearance)
        assert STAND.breadth / 2.0 - mouth >= 2.0


def test_the_stand_prints_on_end_without_overhang(lines):
    """Every wall stands within 10 degrees of upright.

    The lettering aside: its undersides are ledges 0.6mm deep.
    """
    part = stands.printed(HULL, lines, BARE)
    assert steepest_overhang(part) <= math.sin(math.radians(10.0))


def test_the_lettering_stands_on_both_sides(lettered, bare):
    assert lettered.is_valid
    letters = (lettered - bare).solids()
    port = sum(s.volume for s in letters if s.center().Y < 0.0)
    starboard = sum(s.volume for s in letters if s.center().Y > 0.0)
    assert port == pytest.approx(starboard, rel=1e-3)
    assert port > 150.0


def test_the_lettering_is_seen_from_above_and_stays_on_the_stand(frame):
    """Every letter clears the top bar for an eye 30 degrees up, and none runs off an end."""
    x0, middle, z0 = frame
    lettering = STAND.lettering
    assert lettering is not None
    half = STAND.breadth / 2.0
    eaves = z0 + STAND.height - STAND.top
    sight = math.tan(math.radians(30.0))
    for letter in stands._lettering(STAND, lettering, middle, z0):
        box = letter.bounding_box()
        inboard = half - max(abs(box.min.Y), abs(box.max.Y))
        assert box.max.Z + (half - min(abs(box.min.Y), abs(box.max.Y))) * sight <= eaves
        assert inboard >= 0.0
        assert x0 + 5.0 <= box.min.X and x0 + STAND.length - 5.0 >= box.max.X


def _raster(faces) -> np.ndarray:
    """The faces filled on a PIXEL grid, by crossings along each row."""
    segments = []
    for face in faces:
        for edge in face.edges():
            points = [edge.position_at(t) for t in np.linspace(0.0, 1.0, 40)]
            segments += [(a.X, a.Y, b.X, b.Y) for a, b in zip(points, points[1:], strict=False)]
    s = np.array(segments)
    x0, y0 = s[:, [0, 2]].min() - 0.5, s[:, [1, 3]].min() - 0.5
    xs = np.arange(x0, s[:, [0, 2]].max() + 0.5, PIXEL)
    ys = np.arange(y0, s[:, [1, 3]].max() + 0.5, PIXEL)
    image = np.zeros((len(ys), len(xs)), bool)
    for j, y in enumerate(ys):
        crossing = (s[:, 1] > y) != (s[:, 3] > y)
        c = s[crossing]
        at = np.sort(c[:, 0] + (y - c[:, 1]) * (c[:, 2] - c[:, 0]) / (c[:, 3] - c[:, 1]))
        for left, right in zip(at[::2], at[1::2], strict=True):
            image[j, int((left - x0) / PIXEL) : int((right - x0) / PIXEL)] = True
    return image


@pytest.mark.parametrize("line", STAND.lettering.lines if STAND.lettering else ())
def test_every_stroke_is_wide_enough_to_print(line):
    """Eroded by half a nozzle's width, no letter breaks in two; and no counter fills in."""
    lettering = STAND.lettering
    assert lettering is not None
    letters = stands.glyphs(line, lettering)
    plain = stands.glyphs(line, replace(lettering, grow=0.0))
    image = _raster(letters)
    counters = sum(len(face.inner_wires()) for face in plain)
    assert ndimage.label(~image)[1] - 1 == counters
    depth = ndimage.distance_transform_edt(image) * PIXEL
    assert ndimage.label(depth > STROKE / 2.0)[1] == len(letters)


@pytest.mark.parametrize("line", STAND.lettering.lines if STAND.lettering else ())
def test_no_two_letters_touch(line):
    lettering = STAND.lettering
    assert lettering is not None
    letters = stands.glyphs(line, lettering)
    for a, b in zip(letters, letters[1:], strict=False):
        assert a.distance_to(b) >= 0.3


def test_the_stand_exports_as_a_manifold_3mf(lines, tmp_path):
    vertices, triangles = write_3mf(stands.printed(HULL, lines, STAND), tmp_path / "stand.3mf")
    assert vertices > 0 and triangles > 0
