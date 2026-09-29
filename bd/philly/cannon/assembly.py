"""The three printed parts, put together: gun, carriage and the trunnion pin.

Nothing here is printed -- it is where the fits are checked, by eye in the
viewer and by the tests, which assert that no two parts share any volume.

The gun hangs off a `RevoluteJoint` on the trunnion axis, and the square bar
it is fixed on rides with it. The printed gun only ever sits at its carriage's
`elevation`; posing it anywhere else drives the bar into the brackets, which is
how the tests show that it cannot turn.

    just watch cannon/assembly.py
"""

from __future__ import annotations

from build123d import (
    Axis,
    Color,
    Compound,
    Part,
    Plane,
    Pos,
    RevoluteJoint,
    RigidJoint,
    Rot,
)

from cannon.cannon import cannon, trunnion_height
from cannon.carriage import CarriageSpec, carriage
from cannon.trunnion import trunnion

IRON = Color(0.35, 0.36, 0.38)
WOOD = Color(0.52, 0.37, 0.24)
BRASS = Color(0.72, 0.58, 0.28)


def assembly(spec: CarriageSpec | None = None, elevation: float | None = None) -> Compound:
    """The gun in its carriage, standing on the deck at z = 0 with its muzzle to -x.

    Positive `elevation` raises the muzzle; left out, the breech rests on the
    quoin, which is where the gun sits when nobody is holding it.
    """
    spec = spec or CarriageSpec()
    elevation = spec.elevation if elevation is None else elevation
    pegs = spec.pegs
    axis_height = spec.axis_height

    truck = carriage(spec)
    truck.color = WOOD
    truck.label = "carriage"
    # Down as far as the barrel goes before its underside meets the fore edge of
    # the bed, which is about 19 degrees; the quoin stops it going the other way
    # at `elevation`, and the range above that is for posing it in the viewer.
    RevoluteJoint(
        "elevation",
        truck,
        axis=Axis((0, 0, axis_height), (0, 1, 0)),
        angular_range=(-18.0, 10.0),
    )

    gun = cannon(spec.gun)
    gun.color = IRON
    gun.label = "cannon"
    RigidJoint(
        "trunnions",
        gun,
        Plane(origin=(0, 0, trunnion_height(spec.gun)), x_dir=(-1, 0, 0), z_dir=(0, 1, 0)).location,
    )
    truck.joints["elevation"].connect_to(gun.joints["trunnions"], angle=elevation)

    # The bar is keyed to the gun, so it is placed in the gun's own frame: lying
    # along the gun's y, stood on a corner to fill the gun's diamond. It prints
    # lying on a face, which is why it has to be turned here.
    pin = (
        gun.location
        * Pos(0, 0, trunnion_height(spec.gun))
        * Rot(0, 45, 0)
        * Rot(0, 0, 90)
        * Pos(0, 0, -pegs.side / 2)
        * trunnion(pegs)
    )
    pin.color = BRASS
    pin.label = "trunnion"

    parts: list[Part] = [truck, gun, pin]

    return Compound(children=parts)


def model() -> Compound:
    return assembly()


def main() -> None:
    whole = assembly()
    box = whole.bounding_box().size
    print(f"assembled {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm")
    from ocp_vscode import show_object

    for part in whole.children:
        show_object(part, name=part.label or "part")


if __name__ == "__main__":
    main()
