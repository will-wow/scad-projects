"""Render the Philadelphia's hull into the OCP CAD Viewer.

    just viewer     # once, in another terminal
    just watch      # then edit and save; the viewer repaints

Adjust HULL below and save to see it change.
"""

from ocp_vscode import show_object

from hull import HullSpec, build

HULL = HullSpec(
    length=300.0,  # printed length, mm (source data is the real 16.4m boat)
    wall=2.0,  # wall thickness, mm
    stations=48,  # sections in the loft; drop to ~24 for a faster edit loop
)


def main() -> None:
    hull = build(HULL)
    box = hull.bounding_box().size
    print(
        f"hull {box.X:.0f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"{hull.volume / 1000:.1f} cm^3 of material"
    )
    show_object(hull, name="hull")


if __name__ == "__main__":
    main()
