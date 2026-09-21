"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints
    just preview    # or, with no browser around, render to preview/

Adjust HULL below and save to see it change.
"""

from build123d import Part
from ocp_vscode import show_object

from hull import Bulge, HullSpec, OpenSpan, Planking, build
from preview import preview_mode

HULL = HullSpec(
    length=300.0,  # printed length, mm (source data is the real 16.4m boat)
    wall=2.0,  # wall thickness, mm
    # Sections in the loft. Only smoothness depends on this -- the hull's
    # dimensions and its solid bow and stern plugs are solved from the geometry
    # -- so a preview can afford far fewer and still show the real shape.
    stations=12 if preview_mode() else 48,
    # The real boat is decked in three stretches -- forecastle, a decked middle,
    # and the quarterdeck aft -- with an open slice between each. These are the
    # two open slices; everything else carries a deck.
    #
    # Fractions of the overall length, eyeballed off the scan. Measure them
    # against the deck beams and adjust.
    open_spans=(
        OpenSpan(0.18, 0.34),
        OpenSpan(0.58, 0.74),
    ),
    # How far the deck sits below the rail, in mm: the bulwark's height. The
    # deck parallels the sheer, so it rises toward bow and stern with it.
    bulwark=10.0,
    # Plank seams down the outside. The groove is a sawtooth so it prints
    # bottom-down without support: max_overhang caps how far the downward-facing
    # facet may lean, and the ramp back out is sized from the local flare.
    planking=Planking(count=6, depth=0.25, lip=0.20),
    # How far the sides bow out between chine and rail, as a fraction of the
    # side's slant height. The lines plan gives straight panels; the scan's
    # topsides swell. Dial this by eye against the scan -- 0 is the old shape.
    bulge=Bulge(amount=0.06, peak=0.45),
)


def model() -> Part:
    """The thing to render. `just preview` looks for this."""
    return build(HULL)


def main() -> None:
    hull = model()
    box = hull.bounding_box().size
    print(
        f"hull {box.X:.0f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"{hull.volume / 1000:.1f} cm^3 of material"
    )
    show_object(hull, name="hull")


if __name__ == "__main__":
    main()
