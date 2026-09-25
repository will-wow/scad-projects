"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints
    just preview    # or, with no browser around, render to preview/

Adjust HULL below and save to see it change.
"""

from build123d import Part
from ocp_vscode import show_object

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
