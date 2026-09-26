"""The boat with its rig on.

The parts are modelled apart and printed apart, so nothing else in the suite
ever puts them together. This does, and asks the one question that only has an
answer once they are in the same coordinates: do they actually fit?
"""

from __future__ import annotations

import os

import pytest
from build123d import Vector

# Before assembly imports main, whose HULL reads this. A coarse hull is the same
# hull, and these are about where the parts sit, not how smooth it is.
os.environ.setdefault("PREVIEW", "1")

import assembly  # noqa: E402
import rig as rigging  # noqa: E402
from main import HULL, RIG  # noqa: E402


@pytest.fixture(scope="module")
def assembled():
    return assembly.parts()


def _boxes_meet(first, second) -> bool:
    """Most pairs are nowhere near each other, and a boolean between them is slow."""
    one, other = first.bounding_box(), second.bounding_box()
    return all(
        low <= high and other_low <= other_high
        for low, other_high, other_low, high in zip(
            tuple(one.min), tuple(other.max), tuple(other.min), tuple(one.max), strict=True
        )
    )


def test_nothing_occupies_the_same_space_as_anything_else(assembled):
    """Parts that overlap in the model are parts that will not go together.

    The sails failed this when they were first hung: each had 130 cubic
    millimetres of itself inside the mast, because a flat plate spanning the
    whole yard passes straight through whatever is in the middle of it. The
    guns are here too, run out, which is what says the awning's legs, the mast
    and the sails all stand clear of them.
    """
    names = list(assembled)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            if not _boxes_meet(assembled[first], assembled[second]):
                continue
            shared = (assembled[first] & assembled[second]).volume
            assert shared == pytest.approx(0.0, abs=1e-6), (
                f"{first} and {second} share {shared:.3f} mm3"
            )


def test_the_mast_stands_on_the_bottom_of_its_bore(assembled, lines):
    seat = rigging.step(HULL, lines, RIG)
    box = assembled["mast"].bounding_box()
    assert pytest.approx(seat.floor, abs=1e-6) == box.min.Z
    assert pytest.approx(seat.floor + RIG.mast_length, abs=0.01) == box.max.Z


def test_the_mast_is_upright_on_the_centreline(assembled, lines):
    seat = rigging.step(HULL, lines, RIG)
    box = assembled["mast"].bounding_box()
    assert pytest.approx(seat.station, abs=0.01) == box.center().X
    assert pytest.approx(0.0, abs=0.01) == box.center().Y


def test_each_sail_hangs_between_the_yards_it_belongs_to(assembled, lines):
    """Yard heights and sail heights are computed from opposite ends, so this
    is what catches them drifting apart."""
    seat = rigging.step(HULL, lines, RIG)
    yards = rigging.yards(HULL, lines, RIG)
    for name, (low, high) in (("course", yards[:2]), ("topsail", yards[2:])):
        middle = seat.floor + 0.5 * (low[0] + high[0])
        assert pytest.approx(middle, abs=0.01) == assembled[name].bounding_box().center().Z


def test_the_sails_hang_forward_of_the_mast(assembled, lines):
    """On the bow side: a square sail's yard is slung forward of the mast.

    The eyes straddle the yard, so they reach aft of the station; it is the
    plate, and so the sail's bulk, that has to be forward of it.
    """
    seat = rigging.step(HULL, lines, RIG)
    for name in ("course", "topsail"):
        assert seat.station > assembled[name].bounding_box().center().X


def test_the_masthead_stands_clear_of_the_hull(assembled):
    """A sanity check on the whole thing: the rig is taller than the boat."""
    hull = assembled["hull"].bounding_box()
    assert assembled["mast"].bounding_box().max.Z > 5.0 * hull.max.Z


def test_the_bore_is_where_the_mast_is(assembled, lines):
    """The socket really does accept the mast, rather than the mast floating in
    a hull that never got bored."""
    seat = rigging.step(HULL, lines, RIG)
    inside = Vector(seat.station, 0.0, seat.floor + seat.socket / 2.0)
    assert assembled["mast"].is_inside(inside)
    assert not assembled["hull"].is_inside(inside)
