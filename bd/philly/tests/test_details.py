"""The joinery: knees, beams, benches and keelson, merged into the hull.

Every piece is a union, and a union that misses -- a knee standing off the side,
a bench floating over the deck -- still builds a valid solid. So these probe the
fitted hull for material where each piece should be and air just beside it, and
check that nothing reached through to the outside of the planking.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
from build123d import Vector

# Before main is imported, whose HULL reads this.
os.environ.setdefault("PREVIEW", "1")

import details  # noqa: E402
from awning import frame  # noqa: E402
from export import write_3mf  # noqa: E402
from hull import Bench, Knee, Scaled, build, open_stretches  # noqa: E402
from main import AWNING, HULL, RIG  # noqa: E402


@pytest.fixture(scope="module")
def hull(fitted_hull):
    return fitted_hull


@pytest.fixture(scope="module")
def bare(built_hull):
    return built_hull


@pytest.fixture(scope="module")
def at(lines):
    return Scaled(HULL, lines)


def _solid(part, x: float, y: float, z: float) -> bool:
    return part.is_inside(Vector(x, y, z))


def _knees(at) -> list[tuple[Knee, float]]:
    return [(k, at.deck(platform)) for k, platform in details._platform_knees(at, HULL)[1]]


def test_the_fitted_hull_is_one_solid_that_still_sits_flat(hull, bare):
    assert hull.is_valid
    assert len(hull.solids()) == 1
    box, plain = hull.bounding_box(), bare.bounding_box()
    assert pytest.approx(plain.min.Z, abs=1e-6) == box.min.Z
    assert box.min.Y >= plain.min.Y - 1e-6 and box.max.Y <= plain.max.Y + 1e-6


def test_the_joinery_adds_material(lines, bare):
    """A fuse can hand back a shape whose volume reads as nothing; this one must not."""
    joined = details.fit_details(bare, HULL, lines)
    assert 4000.0 < joined.volume - bare.volume < 9000.0


def test_nothing_reaches_through_the_planking(lines, bare):
    """Everything the joinery added is inside the bare hull's outline.

    On the joinery alone: the mast's tube stands above the rail on purpose.
    """
    joined = details.fit_details(bare, HULL, lines)
    outline = build(replace(HULL, planking=0.0), lines)
    outside = (joined - outline).volume
    assert outside == pytest.approx(0.0, abs=1e-3), f"{outside:.4f}mm3 outside the hull"


def test_every_platform_has_its_end_pairs_and_its_own(at):
    stations = sorted((round(k.station, 3), k.side) for k, _ in _knees(at))
    assert len(stations) == len(HULL.knees) + 4
    ends = [s for s in stations if s[0] not in {k.station for k in HULL.knees}]
    assert len({s for s, _ in ends}) == 2


@pytest.mark.parametrize("index", range(10))
def test_each_knee_stands_against_the_side(hull, at, index):
    knee, deck = _knees(at)[index]
    x, s = at.station(knee.station), knee.side
    tall = deck + 9.0
    face = at.inside(x, tall)
    assert _solid(hull, x, s * (face - 0.8), tall), "no tall arm against the side"
    assert not _solid(hull, x, s * (face - 3.0), tall), "the tall arm is too thick"
    low = at.inside(x, deck) - 10.0
    assert _solid(hull, x, s * low, deck + 1.0), "no low arm along the deck"


@pytest.mark.parametrize("index", range(6))
def test_a_knee_between_the_ends_is_only_its_siding_thick(hull, at, index):
    knee = HULL.knees[index]
    x, deck = at.station(knee.station), at.deck(details._deck_at(HULL, knee.station))
    y = knee.side * (at.inside(x, deck) - 10.0)
    for off in (-1.2, 1.2):
        assert not _solid(hull, x + off, y, deck + 1.0)


def test_each_end_of_the_platform_has_a_beam(hull, at):
    platform = details._deck_at(HULL, HULL.knees[0].station)
    deck = at.deck(platform)
    for x in (at.station(platform.start) + 1.25, at.station(platform.end) - 1.25):
        assert _solid(hull, x, 0.0, deck + 1.5)
        assert not _solid(hull, x, 0.0, deck + details.BEAM_MOULDED + 0.3)


@pytest.mark.parametrize("side", [-1, 1])
def test_the_benches_are_solid_to_the_seat_and_no_higher(hull, at, lines, side):
    """Probed clear of the awning's bosses, which stand on the seat."""
    bench = HULL.benches[0]
    seat = details.bench_top(HULL, lines, bench.start)
    assert seat is not None
    for fraction in (bench.start + 0.004, 0.5 * (bench.start + bench.end), bench.end - 0.004):
        x = at.station(fraction)
        y = side * (at.inside(x, seat) - 0.5 * details.BENCH_REACH)
        assert _solid(hull, x, y, seat - 0.3), f"no bench at {fraction:.3f}"
        assert not _solid(hull, x, y, seat + 0.5), f"the bench at {fraction:.3f} is too high"
        front = side * (at.inside(x, seat) - details.BENCH_REACH - 0.5)
        assert not _solid(hull, x, front, seat - 0.3), f"the bench at {fraction:.3f} is too deep"


def test_the_aft_awning_legs_stand_on_the_benches(lines):
    bench = HULL.benches[0]
    seats = [
        f
        for f in frame(HULL, lines, AWNING, RIG).feet
        if bench.start <= f.station / HULL.length <= bench.end
    ]
    assert len(seats) == 2
    for foot in seats:
        seat = details.bench_top(HULL, lines, foot.station / HULL.length)
        assert seat is not None
        assert foot.step == pytest.approx(seat), "the pair does not step on the seat"
        # Socketed through the bench rather than onto it: the hole is bored from
        # the deck like every other, so the bench's own height is depth that
        # costs nothing to show above the seat.
        assert foot.deck < seat
        assert foot.socket_floor < foot.deck
        assert foot.boss < seat - foot.deck


def test_the_keelson_runs_down_each_well(hull, at):
    stretches = open_stretches(sorted(HULL.decks, key=lambda d: d.start))
    assert len(stretches) == 2
    for a, b in stretches:
        # A quarter of the way along, clear of the mast's tube in the forward well.
        x = at.station(a + 0.25 * (b - a))
        floor = at.floor(x)
        assert _solid(hull, x, 0.0, floor + 1.5), f"no keelson at {x:.1f}"
        assert not _solid(hull, x, 0.0, floor + details.KEELSON_PROUD + 0.3)
        for side in (-1.0, 1.0):
            assert not _solid(hull, x, side * (details.KEELSON_WIDTH / 2.0 + 0.5), floor + 1.0)


def test_a_bench_across_two_decks_is_refused(lines, bare):
    spec = replace(HULL, benches=(Bench(0.60, 0.75),))
    with pytest.raises(ValueError, match="deck"):
        details.fit_details(bare, spec, lines)


def test_a_knee_must_stand_to_one_side():
    with pytest.raises(ValueError, match="port or starboard"):
        Knee(0.5, 0)


def test_the_fitted_hull_exports_as_a_manifold_3mf(hull, tmp_path):
    """A strip of deck too thin to mesh, between a knee's end and a seam, drops out
    of the tessellation and leaves a hole the slicer would have to repair."""
    points, faces = write_3mf(hull, tmp_path / "hull.3mf")
    assert points and faces
