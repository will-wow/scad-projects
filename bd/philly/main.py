"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints
    just preview    # or, with no browser around, render to preview/

Adjust HULL below and save to see it change.
"""

from build123d import Part, Pos
from ocp_vscode import show_object

import awning as awnings
import guns as ordnance
import lines as hull_lines
import rig as rigging
from cannon.cannon import NINE_POUNDER
from cannon.carriage import CarriageSpec, carriage
from hull import Bulge, Deck, HullSpec, build
from preview import preview_mode

HULL = HullSpec(
    length=300.0,  # printed length, mm (source data is the real 16.4m boat)
    wall=2.0,  # wall thickness, mm
    # Sections in the loft. Only smoothness depends on this -- the hull's
    # dimensions and its solid bow and stern plugs are solved from the geometry
    # -- so a preview can afford far fewer and still show the real shape.
    stations=12 if preview_mode() else 48,
    # The real boat is decked in three stretches -- forecastle, a middle
    # platform, and the quarterdeck aft -- each at its own height, with the
    # bilge open between them. All measured off the Smithsonian scan (see
    # designs/measure_scan.py): lengths as fractions from the bow, heights as
    # fractions of the hull's depth. The scan puts the decks 850, 612 and 537mm
    # above the keel, stepping down from bow to stern.
    decks=(
        Deck(0.0, 0.31, 0.48),
        Deck(0.39, 0.655, 0.34),
        Deck(0.71, 1.0, 0.30),
    ),
    # How far the sides bow out between chine and rail, as a fraction of the
    # side's slant height. The lines plan gives straight panels; the scan's
    # topsides swell. Dial this by eye against the scan -- 0 is the old shape.
    bulge=Bulge(amount=0.06, peak=0.45),
)


RIG = rigging.Rig()

AWNING = awnings.Awning()

# The 12-pounder in the bow: the scan puts its axis 14.1mm above the forecastle
# at 4.1 degrees, which is CarriageSpec's default.
BOW_CHASER = CarriageSpec()

# The 9-pounders. The scan measured the starboard gun's axis 15.6mm above the
# platform where it crosses the rail, at 4.0 degrees; run out, that is 14.64 at
# the trunnions. The port gun was scanned run in, so it takes the same carriage.
BROADSIDE = CarriageSpec(gun=NINE_POUNDER, axis_height=14.64, elevation=4.0)

GUNS = (
    ordnance.Gun(station=0.083, side=0, carriage=BOW_CHASER),
    ordnance.Gun(station=0.483, side=-1, carriage=BROADSIDE),
    ordnance.Gun(station=0.606, side=1, carriage=BROADSIDE),
)


def fitted(lines: hull_lines.HullLines) -> Part:
    """The hull with the mast's step, the awning's sockets and the guns' slides.

    Every fitting runs after `build`, which is not optional: the cavity
    subtraction would carve away anything added before it.
    """
    hull = rigging.fit_mast(build(HULL, lines), HULL, lines, RIG)
    hull = awnings.fit_awning(hull, HULL, lines, AWNING, RIG)
    return ordnance.fit_guns(hull, HULL, lines, GUNS)


def model() -> Part:
    return fitted(hull_lines.load())


def mast() -> Part:
    """The mast, lying down ready to print."""
    return rigging.mast(HULL, hull_lines.load(), RIG)


def sails() -> Part:
    """Both sails, flat on the bed."""
    return rigging.sails(HULL, hull_lines.load(), RIG)


def awning() -> Part:
    """The awning frame, roof down ready to print."""
    return awnings.awning_part(HULL, hull_lines.load(), AWNING, RIG)


def canvas() -> Part:
    """The awning's canvas, flat on the bed like the sails."""
    return awnings.canvas(HULL, hull_lines.load(), AWNING, RIG)


def broadside_carriage() -> Part:
    """The 9-pounders' carriage; print two. The bow gun's is `cannon.carriage:model`."""
    return carriage(BROADSIDE)


def main() -> None:
    hull = model()
    box = hull.bounding_box().size
    print(
        f"hull {box.X:.0f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"{hull.volume / 1000:.1f} cm^3 of material"
    )
    show_object(hull, name="hull")
    # Alongside, not in place: these print as separate parts, and the mast is
    # two thirds as long as the boat, so it would swamp the view standing up.
    beside = hull.bounding_box().max.Y + 20.0
    show_object(Pos(0.0, beside, 0.0) * mast(), name="mast")
    show_object(Pos(0.0, beside + 60.0, 0.0) * sails(), name="sails")
    show_object(Pos(0.0, beside + 140.0, 0.0) * awning(), name="awning")
    show_object(Pos(0.0, beside + 230.0, 0.0) * canvas(), name="canvas")


if __name__ == "__main__":
    main()
