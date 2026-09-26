"""The solid.

Most of these exist because the thing they check went wrong once. Every failure
this code has had looked fine from outside -- a hull that was never hollowed, a
deck left skinned over, a cavity whose extent moved with the station count --
so these look inside and measure rather than trusting that it built at all.
"""

from __future__ import annotations

import numpy as np
import pytest
from build123d import Plane, Vector
from conftest import DECKS

from hull import (
    Bulge,
    Deck,
    HullSpec,
    _cavity_span,
    _inner_section,
    _section,
    _station_positions,
    build,
    open_stretches,
)

STATIONS = 12


def _section_area(part, x: float) -> float:
    cut = Plane.YZ.offset(x).intersect(part)
    return sum(f.area for f in (cut.faces() if hasattr(cut, "faces") else []))


def _top_of_material(part, x: float, ceiling: float) -> float:
    """Height at which material stops on the centreline, searching down."""
    z = ceiling
    while z > 0.0 and not part.is_inside(Vector(x, 0.0, z)):
        z -= 0.05
    return z


def test_hull_is_one_watertight_solid(open_hull):
    assert open_hull.is_valid
    assert len(open_hull.solids()) == 1
    assert len(open_hull.shells()) == 1


def test_scaled_to_the_requested_length(open_hull):
    box = open_hull.bounding_box().size
    assert pytest.approx(HullSpec().length, abs=0.5) == box.X


def test_hollowing_actually_removes_material(open_hull, solid_hull):
    """OCCT's thick-solid used to fail by handing back the solid, valid and
    unchanged, with no exception. A hull that is quietly solid looks right in
    the viewer and only announces itself as hours of print time."""
    assert open_hull.volume < 0.4 * solid_hull.volume


def test_the_deck_is_open_where_it_should_be(open_hull, lines):
    """The wrong face was once opened -- an end instead of the deck -- which
    leaves a lid on and a hole in the end, watertight and plausible."""
    factor = HullSpec().length / lines.length
    for fraction in (0.35, 0.5, 0.65):
        x = HullSpec().length * fraction
        rail = lines.sheer_height.value(x / factor) * factor
        assert not open_hull.is_inside(Vector(x, 0.0, rail - 1.0))


def test_wall_is_the_thickness_asked_for(open_hull, lines):
    """Insetting the sections by hand is easy to get wrong: shifting a rail
    straight up also pushes the flared side out, which measured 2.8mm for a
    2mm request."""
    spec = HullSpec()
    factor = spec.length / lines.length
    for fraction in (0.3, 0.5, 0.7):
        x = spec.length * fraction
        source = x / factor
        y_sheer = lines.sheer_half_width.value(source) * factor
        z_sheer = lines.sheer_height.value(source) * factor
        y_chine = lines.chine_half_width.value(source) * factor
        z_chine = lines.chine_height.value(source) * factor
        slant = float(np.hypot(y_sheer - y_chine, z_sheer - z_chine))
        # A U of wall thickness t: the floor, both sides, less the corners.
        expected = (2 * y_chine + 2 * slant) * spec.wall - 2 * spec.wall**2
        assert _section_area(open_hull, x) == pytest.approx(expected, rel=0.06)


def test_cavity_ends_do_not_move_with_the_station_count(lines):
    """Sections should buy smoothness and nothing else.

    When the cavity stopped at whichever station happened to fall nearest, the
    solid end plugs ranged over most of a metre and the volume swung 11% -- print weight
    moving with a setting that is supposed to be cosmetic."""
    spec = HullSpec()
    wall = spec.wall / (spec.length / lines.length)
    x0, x1 = lines.sheer_half_width.span
    spans = set()
    for count in (8, 12, 24, 48):
        stations = _station_positions(x0, x1, count)
        first, last = _cavity_span(lines, wall, float(stations[0]), float(stations[-1]))
        spans.add((round(first, 3), round(last, 3)))
    assert len(spans) == 1, f"cavity extent moved with the station count: {spans}"


def test_volume_converges_with_more_sections(lines):
    coarse = build(HullSpec(stations=8), lines).volume
    fine = build(HullSpec(stations=32), lines).volume
    assert coarse == pytest.approx(fine, rel=0.02)


class TestDecks:
    def test_open_stretches_reach_the_bottom(self, decked_hull, lines):
        factor = HullSpec().length / lines.length
        for fraction in (8 / 24, 16 / 24):  # middles of the two open stretches
            x = HullSpec().length * fraction
            rail = lines.sheer_height.value(x / factor) * factor
            floor = lines.chine_height.value(x / factor) * factor
            top = _top_of_material(decked_hull, x, rail)
            assert top == pytest.approx(floor + HullSpec().wall, abs=0.5)

    def test_each_deck_sits_at_its_own_height(self, decked_hull, lines):
        """The three platforms are at three heights, not one shared drop.

        Height is measured from the bottom as a fraction of the hull's depth,
        so the check is against that fraction rather than against the local
        rail -- which is the whole difference from the version that hung every
        deck the same distance below the sheer.
        """
        factor = HullSpec().length / lines.length
        depth = lines.depth * factor
        for deck in DECKS:
            x = HullSpec().length * 0.5 * (deck.start + deck.end)
            rail = lines.sheer_height.value(x / factor) * factor
            top = _top_of_material(decked_hull, x, rail + 1.0)
            assert top == pytest.approx(deck.height * depth, abs=0.3), (
                f"deck {deck.start:.2f}..{deck.end:.2f}"
            )

    def test_the_platforms_step_down_from_bow_to_stern(self, decked_hull, lines):
        """The forecastle is highest and the quarterdeck lowest."""
        factor = HullSpec().length / lines.length
        tops = []
        for deck in DECKS:
            x = HullSpec().length * 0.5 * (deck.start + deck.end)
            rail = lines.sheer_height.value(x / factor) * factor
            tops.append(_top_of_material(decked_hull, x, rail + 1.0))
        assert tops[0] > tops[1] > tops[2], f"platforms do not step down: {tops}"

    def test_a_deck_leaves_the_sides_standing_as_bulwarks(self, decked_hull, lines):
        """The hull carries on above each platform rather than filling to the rail."""
        factor = HullSpec().length / lines.length
        for deck in DECKS:
            x = HullSpec().length * 0.5 * (deck.start + deck.end)
            rail = lines.sheer_height.value(x / factor) * factor
            top = _top_of_material(decked_hull, x, rail + 1.0)
            assert rail - top > 1.0, f"no bulwark over deck {deck.start:.2f}..{deck.end:.2f}"

    def test_decking_adds_material(self, decked_hull, open_hull):
        assert decked_hull.volume > 1.5 * open_hull.volume


@pytest.mark.parametrize(
    ("decks", "expected"),
    [
        (((0.0, 1.0),), []),
        (((0.2, 0.4),), [(0.0, 0.2), (0.4, 1.0)]),
        (((0.2, 0.4), (0.6, 0.8)), [(0.0, 0.2), (0.4, 0.6), (0.8, 1.0)]),
        (((0.0, 0.5),), [(0.5, 1.0)]),
    ],
)
def test_open_stretches_are_the_complement_of_the_decks(decks, expected):
    assert open_stretches([Deck(a, b, 0.5) for a, b in decks]) == expected


def test_a_backwards_deck_is_refused():
    with pytest.raises(ValueError, match="increasing"):
        Deck(0.6, 0.2, 0.5)


def test_a_deck_height_outside_the_hull_is_refused():
    with pytest.raises(ValueError, match="height"):
        Deck(0.0, 0.5, 1.5)


def test_overlapping_decks_are_refused(lines):
    """Two heights over one stretch has no answer, so it is not guessed at."""
    with pytest.raises(ValueError, match="overlap"):
        build(HullSpec(stations=8, decks=(Deck(0.2, 0.6, 0.5), Deck(0.4, 0.8, 0.3))), lines)


class TestBulge:
    """The sides bow outward between chine and rail, rather than running straight."""

    SPEC = Bulge(amount=0.06, peak=0.45)

    @pytest.fixture(scope="class")
    def bulged(self, lines):
        return build(HullSpec(stations=STATIONS, bulge=self.SPEC), lines)

    def test_the_side_stands_outside_the_chord(self, bulged, lines):
        """The point of the whole thing: probe where a straight side would be air.

        Halfway up the side, the swell should have carried material out past the
        line from chine to rail -- so a point just outside that line is inside
        the bulged hull and outside the straight one.
        """
        spec = HullSpec(stations=STATIONS)
        factor = spec.length / lines.length
        source = (spec.length * 0.5) / factor
        y_chine = lines.chine_half_width.value(source) * factor
        z_chine = lines.chine_height.value(source) * factor
        run = lines.sheer_half_width.value(source) * factor - y_chine
        rise = lines.sheer_height.value(source) * factor - z_chine

        at = self.SPEC.peak
        # Just outside the straight chord, by a fraction of the expected swell.
        swell = self.SPEC.amount * float(np.hypot(run, rise))
        probe = Vector(
            spec.length * 0.5,
            y_chine + run * at + 0.5 * swell,
            z_chine + rise * at,
        )
        assert bulged.is_inside(probe), "the side did not bow outward"
        assert not build(spec, lines).is_inside(probe), "a straight side already reached here"

    def test_the_chine_and_rail_stay_where_the_lines_plan_puts_them(self, bulged, lines):
        """The swell is pinned to zero at both ends, so it must not move either.

        The rail is the widest point, so the beam is the check: if the swell
        leaked past t=1 the hull would measure wider than its own sheer line.
        """
        plain = build(HullSpec(stations=STATIONS), lines).bounding_box()
        bowed = bulged.bounding_box()
        assert pytest.approx(plain.size.Y, abs=0.01) == bowed.size.Y
        assert pytest.approx(plain.size.Z, abs=0.01) == bowed.size.Z

    def test_every_station_has_the_same_vertex_count(self, lines):
        """Not cosmetic: unequal counts make the loft sixty times slower.

        Lofting between sections whose vertices do not correspond forces OCCT to
        build a common parameterisation, which took the outer hull from 0.12
        seconds to 7.5 and the whole build past eight minutes. It went unnoticed
        because the result was still correct -- just unusable -- so this asserts
        the invariant that keeps it fast rather than timing anything.
        """
        spec = HullSpec(stations=STATIONS, bulge=self.SPEC)
        x0, x1 = lines.sheer_half_width.span
        counts = {
            len(face.edges())
            for x in _station_positions(x0, x1, spec.stations)
            if (face := _section(lines, float(x), spec.bulge)) is not None
        }
        assert len(counts) == 1, f"sections disagree on vertex count: {sorted(counts)}"

    def test_the_wall_survives_the_swell(self, lines):
        """The cavity is bowed by the same amount at the same height as the hull.

        That is what lets this skip a real polyline offset. It only holds if the
        swell is applied horizontally: displacing along the surface normal moves
        points down the side as well as out, the two surfaces end up offset in
        z, and the cavity leans out through the hull.
        """
        spec = HullSpec(stations=STATIONS, bulge=self.SPEC)
        factor = spec.length / lines.length
        wall = spec.wall / factor
        x0, x1 = lines.sheer_half_width.span

        for fraction in (0.3, 0.5, 0.7):
            x = x0 + (x1 - x0) * fraction
            y_chine = lines.chine_half_width.value(x)
            z_chine = lines.chine_height.value(x)
            run = lines.sheer_half_width.value(x) - y_chine
            rise = lines.sheer_height.value(x) - z_chine
            chord = float(np.hypot(run, rise))
            cavity = _inner_section(lines, x, wall, None, self.SPEC)
            assert cavity is not None

            for vertex in cavity.vertices():
                if vertex.Y <= 0.0:
                    continue
                at = (vertex.Z - z_chine) / rise
                if not 0.0 <= at <= 1.0:
                    continue  # the cavity runs past the rail to open the deck
                outer = y_chine + run * at + self.SPEC.at(at) * self.SPEC.amount * chord
                # Both surfaces are displaced horizontally by the same amount,
                # so the horizontal gap between them is untouched by the swell.
                # It is not the wall, though: across a side leaning `flare` off
                # vertical it measures wall / cos(flare), some 7% over. Lay it
                # back down on the chord's normal to recover the wall itself.
                gap = (outer - vertex.Y) * factor * rise / chord
                assert gap == pytest.approx(spec.wall, abs=0.02), (
                    f"wall is {gap:.3f}mm at t={at:.2f}"
                )

    def test_a_bowed_and_decked_hull_is_still_one_solid(self, lines):
        """The decked cut against a bowed side is what cut the hull into pieces.

        The cavity grazing the bowed side sheds slivers -- six ten-thousandths
        of a cubic millimetre against thirty cubic centimetres -- which are
        discarded, but only after checking they are dust rather than the hull
        genuinely coming apart.
        """
        hull = build(
            HullSpec(
                stations=STATIONS,
                decks=DECKS,
                bulge=self.SPEC,
            ),
            lines,
        )
        assert hull.is_valid
        assert len(hull.solids()) == 1
