"""The guns in the boat: where they stand, and whether they can fire.

The carriages are tested on their own in test_carriage.py and test_slide.py.
This is about them in the hull, which is the only place two questions have an
answer: does each gun sit where the scan puts it, and does it fire over the
rail rather than into it -- run out, recoiled, and everywhere between.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
from build123d import Part

# Before main is imported, whose HULL reads this. These are about where the
# guns sit, which a coarse hull answers as well as a fine one.
os.environ.setdefault("PREVIEW", "1")

import guns  # noqa: E402
from hull import build  # noqa: E402
from main import BROADSIDE, GUNS, HULL, fitted  # noqa: E402


@pytest.fixture(scope="module")
def solved(lines):
    return {m.gun.side: m for m in guns.mounts(HULL, lines, GUNS)}


@pytest.fixture(scope="module")
def hull(lines):
    return fitted(lines)


def _pieces(m: guns.Mount, recoil: float = 0.0) -> dict[str, Part]:
    return {piece.label: piece for piece in guns.placed(m, recoil).children}


def test_every_gun_clears_its_rail(solved):
    for m in solved.values():
        assert m.clearance() >= guns.MARGIN


@pytest.mark.parametrize("side", [0, -1, 1], ids=["bow", "port", "starboard"])
@pytest.mark.parametrize("recoil", [0.0, 0.5, 1.0], ids=["run out", "halfway", "recoiled"])
def test_nothing_of_the_gun_is_in_the_hull(solved, hull, side, recoil):
    """The barrel over the rail, and the carriage clipped to its slide, at every
    point in its run. The carriage's jaws wrap the slide by a fit's width, so
    this is also what says they clear it."""
    m = solved[side]
    for name, piece in _pieces(m, recoil * m.travel).items():
        shared = (piece & hull).volume
        assert shared == pytest.approx(0.0, abs=1e-6), f"{name} is {shared:.3f}mm3 into the hull"


def test_the_bow_gun_stands_at_the_scans_height(solved):
    m = solved[0]
    peg = _pieces(m)["trunnion+1"].bounding_box().center()
    assert peg.Z - m.deck == pytest.approx(14.1, abs=0.1)


def test_the_broadside_guns_cross_the_rail_at_the_scans_height(solved):
    """The scan measured the starboard gun where it crosses the rail; the port
    gun shares its carriage, and its rail is near enough the same height."""
    assert solved[1].axis_over_rail() == pytest.approx(15.6, abs=0.1)
    assert solved[-1].axis_over_rail() == pytest.approx(15.6, abs=0.1)


def test_the_bow_gun_runs_out_over_the_stem(solved, lines):
    """The scan has its muzzle 0.7mm past the stem."""
    muzzle = _pieces(solved[0])["cannon"].bounding_box().min.X
    stem = lines.sheer_half_width.span[0] * HULL.length / lines.length
    assert stem - 1.5 < muzzle < stem


def test_the_broadside_guns_run_out_over_the_side(solved, lines):
    factor = HULL.length / lines.length
    for side in (-1, 1):
        m = solved[side]
        box = _pieces(m)["cannon"].bounding_box()
        muzzle = box.max.Y if side > 0 else -box.min.Y
        rail = lines.sheer_half_width.value(m.trunnions[0] / factor) * factor
        assert muzzle > rail + 5.0


def test_recoil_draws_the_muzzle_inboard(solved):
    for m in solved.values():
        out = _pieces(m)["cannon"].bounding_box().center()
        back = _pieces(m, m.travel)["cannon"].bounding_box().center()
        moved = (out.X - back.X) * m.outboard[0] + (out.Y - back.Y) * m.outboard[1]
        assert moved == pytest.approx(m.travel, abs=1e-6)


def test_the_fitted_hull_is_one_solid_no_wider_than_the_bare_one(hull, lines):
    """The slides are laid on the decks; none of them may reach the outside."""
    assert hull.is_valid
    assert len(hull.solids()) == 1
    bare = build(HULL, lines).bounding_box()
    box = hull.bounding_box()
    assert box.min.Y >= bare.min.Y - 1e-6 and box.max.Y <= bare.max.Y + 1e-6
    assert box.min.X >= bare.min.X - 1e-6 and box.min.Z >= bare.min.Z - 1e-6


def test_a_gun_too_low_to_clear_its_rail_is_refused(lines):
    low = replace(GUNS[2], carriage=replace(BROADSIDE, axis_height=12.5))
    with pytest.raises(ValueError, match="clears its rail"):
        guns.mounts(HULL, lines, (low,))


def test_a_gun_over_open_bilge_is_refused(lines):
    """Between the forecastle and the middle platform there is nothing to stand on."""
    with pytest.raises(ValueError, match="open bilge"):
        guns.mount(replace(GUNS[2], station=0.35), HULL, lines)
