"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints
    just preview    # or, with no browser around, render to preview/

Adjust HULL below and save to see it change.
"""

from build123d import Part
from ocp_vscode import show_object

from hull import HullSpec, OpenSpan, build
from preview import preview_mode

HULL = HullSpec(
    length=300.0,  # printed length, mm (source data is the real 16.4m boat)
    wall=2.0,  # wall thickness, mm
    # Sections in the loft. Only smoothness depends on this -- the hull's
    # dimensions and its solid bow and stern plugs are solved from the geometry
    # -- so a preview can afford far fewer and still show the real shape.
    stations=12 if preview_mode() else 48,
    # Decked forward and aft, open waist between -- everything outside these
    # spans is solid from the bottom up. The fractions are eyeballed off the
    # scan; measure them properly against the deck beams and adjust.
    open_spans=(OpenSpan(0.30, 0.74),),
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
