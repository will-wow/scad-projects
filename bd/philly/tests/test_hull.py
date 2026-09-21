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

from hull import (
    HullSpec,
    OpenSpan,
    Planking,
    _cavity_span,
    _decked,
    _station_positions,
    build,
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
    """The wrong face was once opened -- the stem instead of the deck -- which
    leaves a lid on and a hole in the bow, watertight and plausible."""
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
    solid bow plug ranged over 800mm and the volume swung 11% -- print weight
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
    def test_open_slices_reach_the_bottom(self, decked_hull, lines):
        factor = HullSpec().length / lines.length
        for fraction in (0.26, 0.66):  # middles of the two open spans
            x = HullSpec().length * fraction
            rail = lines.sheer_height.value(x / factor) * factor
            floor = lines.chine_height.value(x / factor) * factor
            top = _top_of_material(decked_hull, x, rail)
            assert top == pytest.approx(floor + HullSpec().wall, abs=0.5)

    def test_decked_stretches_carry_a_deck_below_the_rail(self, decked_hull, lines):
        """The deck used to fill to the rail, leaving no bulwark at all."""
        spec = HullSpec()
        factor = spec.length / lines.length
        for fraction in (0.10, 0.45, 0.85):
            x = spec.length * fraction
            rail = lines.sheer_height.value(x / factor) * factor
            top = _top_of_material(decked_hull, x, rail + 1.0)
            assert rail - top == pytest.approx(10.0, abs=0.3), "bulwark height"

    def test_the_deck_parallels_the_sheer(self, decked_hull, lines):
        """As a fraction of local depth the deck climbed faster than the sheer,
        because the forefoot sweeps up under the forecastle."""
        spec = HullSpec()
        factor = spec.length / lines.length
        drops = []
        for fraction in (0.10, 0.45, 0.85):
            x = spec.length * fraction
            rail = lines.sheer_height.value(x / factor) * factor
            drops.append(rail - _top_of_material(decked_hull, x, rail + 1.0))
        assert max(drops) - min(drops) < 0.3, f"deck drop varied along the length: {drops}"

    def test_decking_adds_material(self, decked_hull, open_hull):
        assert decked_hull.volume > 1.5 * open_hull.volume


@pytest.mark.parametrize(
    ("spans", "expected"),
    [
        (((0.0, 1.0),), []),
        (((0.2, 0.4),), [(0.0, 0.2), (0.4, 1.0)]),
        (((0.2, 0.4), (0.6, 0.8)), [(0.0, 0.2), (0.4, 0.6), (0.8, 1.0)]),
        (((0.0, 0.5),), [(0.5, 1.0)]),
        (((0.2, 0.5), (0.3, 0.7)), [(0.0, 0.2), (0.7, 1.0)]),  # overlapping
    ],
)
def test_decked_stretches_are_the_complement_of_the_open_ones(spans, expected):
    assert _decked(tuple(OpenSpan(a, b) for a, b in spans)) == expected


def test_a_backwards_span_is_refused(lines):
    with pytest.raises(ValueError, match="increasing"):
        build(HullSpec(stations=8, open_spans=(OpenSpan(0.6, 0.2),)), lines)


class TestPlanking:
    """Seams are cut into the section outlines, so they are geometry, not texture."""

    @pytest.fixture(scope="class")
    def planked(self, lines):
        return build(
            HullSpec(stations=STATIONS, planking=Planking(count=8, depth=0.35, width=0.8)),
            lines,
        )

    def test_a_groove_sits_at_every_seam(self, planked, lines):
        """Probe just inside the nominal side: material between seams, air at one."""
        spec = HullSpec()
        factor = spec.length / lines.length
        x = spec.length * 0.5
        source = x / factor
        y_chine = lines.chine_half_width.value(source) * factor
        z_chine = lines.chine_height.value(source) * factor
        run = lines.sheer_half_width.value(source) * factor - y_chine
        rise = lines.sheer_height.value(source) * factor - z_chine
        length = float(np.hypot(run, rise))
        normal_y, normal_z = -rise / length, run / length

        def solid_at(along: float, inset: float) -> bool:
            return planked.is_inside(
                Vector(
                    x,
                    y_chine + run * along + normal_y * inset,
                    z_chine + rise * along + normal_z * inset,
                )
            )

        probe = 0.15  # inside the surface, less than the 0.35mm groove
        for seam in range(1, 8):
            assert not solid_at(seam / 8, probe), f"no groove at seam {seam}"
            assert solid_at((seam - 0.5) / 8, probe), f"groove spread over plank {seam}"

    def test_planking_removes_only_the_grooves(self, planked, lines):
        """Grooves are detail, not a change of shape -- but they do cut material.

        Seven seams a side, each a notch of about width * depth / 2, over the
        length of the hull: a little under 1% of the volume. Anything larger
        means the side is being inset as a whole rather than grooved at the
        seams, which is what happens if the seam points are placed wrong.
        """
        plain = build(HullSpec(stations=STATIONS), lines)
        removed = plain.volume - planked.volume
        assert removed > 0, "grooves should cut material, not add it"
        assert removed < 0.02 * plain.volume, "the side looks inset, not grooved"

    def test_planking_leaves_one_watertight_solid(self, planked):
        assert planked.is_valid
        assert len(planked.solids()) == 1
