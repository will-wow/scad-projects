"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints
    just preview    # or, with no browser around, render to preview/

Adjust HULL below and save to see it change.
"""

from build123d import Part, Pos
from ocp_vscode import show_object

import awning as awnings
import lines as hull_lines
import rig as rigging
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
    # bilge open between them. Lengthwise fractions measured off the scan;
    # heights as fractions of the hull's depth, and the platforms step down
    # from bow to stern.
    decks=(
        Deck(0.0, 7 / 24, 0.50),
        Deck(9 / 24, 15 / 24, 0.40),
        Deck(17 / 24, 1.0, 0.20),
    ),
    # How far the sides bow out between chine and rail, as a fraction of the
    # side's slant height. The lines plan gives straight panels; the scan's
    # topsides swell. Dial this by eye against the scan -- 0 is the old shape.
    bulge=Bulge(amount=0.06, peak=0.45),
)


RIG = rigging.Rig()

AWNING = awnings.Awning()


def model() -> Part:
    """The hull, with the mast's step and the awning's sockets fitted.

    Both fittings run after `build`, which is not optional: the cavity
    subtraction would carve away anything added before it.
    """
    lines = hull_lines.load()
    hull = rigging.fit_mast(build(HULL, lines), HULL, lines, RIG)
    return awnings.fit_awning(hull, HULL, lines, AWNING, RIG)


def mast() -> Part:
    """The mast, lying down ready to print."""
    return rigging.mast(HULL, hull_lines.load(), RIG)


def sails() -> Part:
    """Both sails, flat on the bed."""
    return rigging.sails(HULL, hull_lines.load(), RIG)


def awning() -> Part:
    """The awning frame, roof down ready to print."""
    return awnings.awning_part(HULL, hull_lines.load(), AWNING, RIG)


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


if __name__ == "__main__":
    main()
