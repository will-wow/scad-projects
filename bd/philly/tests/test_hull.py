"""The solid.

Most of these exist because the thing they check went wrong once. Every failure
this code has had looked fine from outside -- a hull that was never hollowed, a
deck left skinned over, a cavity whose extent moved with the station count --
so these look inside and measure rather than trusting that it built at all.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from build123d import Plane, Vector
from conftest import DECKS, _main

from hull import (
    Bulge,
    Deck,
    HullSpec,
    Seams,
    Well,
    _bow,
    _cavity_span,
    _forefoot_positions,
    _inner_section,
    _outline,
    _section,
    _station_positions,
    build,
    inner_half_width,
    open_stretches,
)
from lines import STEM_DEPTH

STATIONS = 12


def _section_area(part, x: float) -> float:
    cut = Plane.YZ.offset(x).intersect(part)
    return sum(f.area for f in (cut.faces() if hasattr(cut, "faces") else []))


def _top_of_material(part, x: float, ceiling: float) -> float:
    """Height at which material stops on the centreline, searching down.

    Coarse steps find the first solid, then bisection pins its top. Stepping
    the whole way at the precision wanted cost 560 probes a search and most of
    a minute a test; this is under forty.
    """
    step = 0.5
    z = ceiling
    while z > 0.0 and not part.is_inside(Vector(x, 0.0, z)):
        z -= step
    if z <= 0.0:
        return z
    solid, air = z, min(z + step, ceiling)
    while air - solid > 0.01:
        middle = 0.5 * (solid + air)
        solid, air = (middle, air) if part.is_inside(Vector(x, 0.0, middle)) else (solid, middle)
    return solid


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
        # A U of planking thickness t: the floor, both sides, less the corners.
        expected = (2 * y_chine + 2 * slant) * spec.planking - 2 * spec.planking**2
        assert _section_area(open_hull, x) == pytest.approx(expected, rel=0.06)


def test_cavity_ends_do_not_move_with_the_station_count(lines):
    """Sections should buy smoothness and nothing else.

    When the cavity stopped at whichever station happened to fall nearest, the
    solid end plugs ranged over most of a metre and the volume swung 11% -- print weight
    moving with a setting that is supposed to be cosmetic."""
    spec = HullSpec()
    factor = spec.length / lines.length
    planking = spec.planking / factor
    bow = _bow(lines)
    x0, x1 = lines.span
    spans = set()
    for count in (8, 12, 24, 48):
        stations = _station_positions(x0, x1, count)
        first, last = _cavity_span(lines, planking, float(stations[0]), float(stations[-1]), bow)
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
            assert top == pytest.approx(floor + HullSpec().planking, abs=0.5)

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


class TestSeams:
    """The grooves between the planks of each deck."""

    DECKS = tuple(replace(d, plank=w) for d, w in zip(DECKS, (7.8, 8.0, 5.9), strict=True))

    @pytest.fixture(scope="class")
    def seamed(self, lines):
        return build(HullSpec(stations=STATIONS, decks=self.DECKS, seams=Seams()), lines)

    def _deck(self, lines, deck: Deck) -> tuple[float, float]:
        """The middle of the deck along the boat, and its height, in printed mm."""
        factor = HullSpec().length / lines.length
        x = HullSpec().length * 0.5 * (deck.start + deck.end)
        return x, deck.height * lines.depth * factor

    def test_a_seam_is_cut_into_every_planked_deck(self, seamed, lines):
        depth = Seams().depth
        for deck in self.DECKS:
            assert deck.plank is not None
            x, z = self._deck(lines, deck)
            for side in (-1.0, 1.0):
                assert not seamed.is_inside(Vector(x, side * 0.5 * deck.plank, z - 0.5 * depth))
                assert seamed.is_inside(Vector(x, side * 0.5 * deck.plank, z - 1.5 * depth))

    def test_the_planks_between_them_are_left_whole(self, seamed, lines):
        for deck in self.DECKS:
            x, z = self._deck(lines, deck)
            assert seamed.is_inside(Vector(x, 0.0, z - 0.05))
            assert deck.plank is not None
            assert seamed.is_inside(Vector(x, deck.plank, z - 0.05))

    def test_no_seam_runs_into_the_side(self, seamed, lines):
        spec = HullSpec()
        factor = spec.length / lines.length
        for deck in self.DECKS:
            x, z = self._deck(lines, deck)
            inside = (
                inner_half_width(lines, x / factor, spec.planking / factor, z / factor) * factor
            )
            for y in np.arange(inside - Seams().margin + 0.05, inside, 0.05):
                assert seamed.is_inside(Vector(x, float(y), z - 0.05))

    def test_a_seam_is_the_only_material_taken(self, seamed, decked_hull):
        """Grooves this small take a fraction of a percent; anything more is a cut gone astray."""
        lost = decked_hull.volume - seamed.volume
        assert 0.0 < lost < 0.01 * decked_hull.volume

    def test_a_seam_deep_enough_to_fool_the_guns_is_refused(self):
        with pytest.raises(ValueError, match="shallower"):
            Seams(depth=0.3)

    def test_a_plank_with_no_width_is_refused(self):
        with pytest.raises(ValueError, match="width"):
            Deck(0.0, 0.5, 0.5, plank=0.0)


class TestWellSeams:
    """The same grooves, on the floor of the open wells.

    Two things make a well not a deck: its floor is found from the chine rather
    than declared, and something stands on every one of them -- the keelson down
    the middle, and the mast's tube in the forward well -- so the innermost seam
    is placed clear of that rather than put half a plank out.
    """

    WELL = Well(plank=8.0, clear=6.0)

    @pytest.fixture(scope="class")
    def planked(self, lines):
        spec = HullSpec(stations=STATIONS, decks=TestSeams.DECKS, seams=Seams(), wells=self.WELL)
        return build(spec, lines)

    @pytest.fixture(scope="class")
    def bare_wells(self, lines):
        return build(HullSpec(stations=STATIONS, decks=TestSeams.DECKS, seams=Seams()), lines)

    def _floor(self, lines) -> float:
        """Both wells' floors, which the flat bottom puts at one height."""
        spec = HullSpec()
        factor = spec.length / lines.length
        return lines.chine_height.value(0.5 * lines.length) * factor + spec.planking

    def _middles(self) -> list[float]:
        return [HullSpec().length * 0.5 * (a + b) for a, b in open_stretches(list(DECKS))]

    def test_a_seam_is_cut_into_every_wells_floor(self, planked, lines):
        depth = Seams().depth
        floor = self._floor(lines)
        for x in self._middles():
            for side in (-1.0, 1.0):
                for y in (self.WELL.clear, self.WELL.clear + self.WELL.plank):
                    at = Vector(x, side * y, floor - 0.5 * depth)
                    assert not planked.is_inside(at), f"no seam {y:.1f} out at {x:.0f}mm"
                    under = Vector(x, side * y, floor - 1.5 * depth)
                    assert planked.is_inside(under), f"the seam {y:.1f} out went through the floor"

    def test_the_floor_inboard_of_the_first_seam_is_left_whole(self, planked, lines):
        """Where the keelson and the mast's tube stand. A seam closer than
        `Seams.clearance` to either leaves a strip too thin for the mesher, and
        the export a hole in the bottom of the boat."""
        floor = self._floor(lines)
        for x in self._middles():
            for y in np.arange(0.0, self.WELL.clear - Seams().width, 0.25):
                assert planked.is_inside(Vector(x, float(y), floor - 0.05)), (
                    f"the floor is cut {y:.2f} out at {x:.0f}mm"
                )

    def test_the_grooves_are_the_only_material_taken(self, planked, bare_wells):
        lost = bare_wells.volume - planked.volume
        assert 0.0 < lost < 0.01 * bare_wells.volume

    def test_bare_wells_are_the_default(self):
        assert HullSpec().wells is None

    def test_a_well_with_no_flat_ceiling_is_refused(self, lines):
        """Forward of where the bottom sweeps up round the forefoot a well's
        ceiling is a ramp, and one groove cut at one height would surface in the
        middle of it."""
        spec = HullSpec(
            stations=STATIONS, decks=(Deck(0.5, 1.0, 0.3),), seams=Seams(), wells=self.WELL
        )
        with pytest.raises(ValueError, match="flat ceiling"):
            build(spec, lines)

    def test_a_plank_with_no_width_is_refused(self):
        with pytest.raises(ValueError, match="width"):
            Well(plank=0.0, clear=6.0)


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
        bow = _bow(lines)
        stations = np.concatenate(
            [
                _forefoot_positions(bow),
                _station_positions(bow.start, lines.sheer_half_width.span[1], spec.stations),
            ]
        )
        counts = {
            len(face.edges())
            for x in stations
            if (face := _section(lines, float(x), spec.bulge, bow)) is not None
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
        planking = spec.planking / factor
        x0, x1 = lines.span

        for fraction in (0.3, 0.5, 0.7):
            x = x0 + (x1 - x0) * fraction
            y_chine = lines.chine_half_width.value(x)
            z_chine = lines.chine_height.value(x)
            run = lines.sheer_half_width.value(x) - y_chine
            rise = lines.sheer_height.value(x) - z_chine
            chord = float(np.hypot(run, rise))
            cavity = _inner_section(lines, x, planking, None, self.SPEC)
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
                # It is not the planking, though: across a side leaning `flare` off
                # vertical it measures planking / cos(flare), some 7% over. Lay it
                # back down on the chord's normal to recover the planking itself.
                gap = (outer - vertex.Y) * factor * rise / chord
                assert gap == pytest.approx(spec.planking, abs=0.02), (
                    f"planking is {gap:.3f}mm at t={at:.2f}"
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


class TestBow:
    """Forward of the flat bottom the planking sweeps up, and a stem is bent round it."""

    def test_the_bottom_stays_on_the_bed(self, solid_hull, lines):
        """Nothing dips below the flat, which is what the toy stands on."""
        factor = HullSpec().length / lines.length
        bottom = lines.chine_height.value(lines.length / 2) * factor
        assert pytest.approx(bottom, abs=0.01) == solid_hull.bounding_box().min.Z

    def test_the_bottom_rises_forward_of_the_flat(self, solid_hull, lines):
        """Clear of the stem, the flat stops where the chine's profile begins."""
        factor = HullSpec().length / lines.length
        start = lines.chine_height.span[0] * factor
        z = lines.chine_height.value(lines.length / 2) * factor + 0.5
        y = lines.chine_half_width.value(lines.chine_height.span[0]) * factor + 0.5
        assert solid_hull.is_inside(Vector(start + 2.0, y, z))
        assert not solid_hull.is_inside(Vector(start - 2.0, y, z))

    def test_the_stem_is_one_thickness_from_foot_to_head(self, solid_hull, lines):
        """A board bent round the face: its front stands the same distance out
        from the planking all the way up, which is what makes it a board rather
        than a wedge."""
        factor = HullSpec().length / lines.length
        bow = _bow(lines)
        depth = STEM_DEPTH * factor
        for u in (0.5, 0.7, 0.85, 0.95):
            x = bow.start - (bow.start - bow.tip) * u
            here = np.array([x, _outline(lines, x, bow).z_chine]) * factor
            ahead = np.array([x - 1.0, _outline(lines, x - 1.0, bow).z_chine]) * factor
            tx, tz = (ahead - here) / np.hypot(*(ahead - here))
            out = np.array([-tz, tx])  # forward and down, out of the hull
            for reach, inside in ((depth - 0.15, True), (depth + 0.15, False)):
                px, pz = here + reach * out
                assert solid_hull.is_inside(Vector(px, 0.0, pz)) == inside, f"u={u}, {reach:.2f}"

    def test_the_stem_is_as_wide_as_the_face_it_covers(self, solid_hull, lines):
        """Forward of the planking all there is is the stem, as wide as the lines'
        flat face at the bow."""
        factor = HullSpec().length / lines.length
        x = 0.5 * STEM_DEPTH * factor
        z = lines.sheer_height.value(x / factor) * factor - 2.0
        half = lines.chine_half_width.value(lines.chine_height.span[0]) * factor
        assert solid_hull.is_inside(Vector(x, half - 0.1, z))
        assert not solid_hull.is_inside(Vector(x, half + 0.1, z))

    def test_without_a_stem_the_planking_still_closes(self, lines):
        hull = build(HullSpec(stations=STATIONS, stem=False), lines)
        assert hull.is_valid
        assert len(hull.solids()) == 1


def test_the_forecastles_corners_run_on_along_the_sides(built_hull, lines):
    """As on the boat: past the forecastle's edge a square tab runs on along each
    side, with a quarter circle cut out of its inboard aft corner."""
    spec = _main().HULL
    deck = spec.decks[0]
    factor = spec.length / lines.length
    edge = deck.end * spec.length
    reach = deck.tab
    top = deck.height * lines.depth * factor
    z = top - 1.5
    # The side flares, so where it stands is taken at the probes' own height.
    face = inner_half_width(lines, edge / factor, spec.planking / factor, z / factor, spec.bulge)
    face *= factor

    def at(aft: float, inboard: float, side: float) -> Vector:
        return Vector(edge + aft * reach, side * (face - inboard * reach), z)

    for side in (-1.0, 1.0):
        assert built_hull.is_inside(at(0.9, 0.1, side)), "the tab along the side"
        assert built_hull.is_inside(at(0.1, 0.7, side)), "the tab against the edge"
        assert not built_hull.is_inside(at(0.9, 0.8, side)), "the notch"
        assert not built_hull.is_inside(at(1.2, 0.1, side)), "aft of the tab"
        assert not built_hull.is_inside(at(0.5, 1.5, side)), "inboard of the tab"
