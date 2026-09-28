"""The three printed parts, put together: gun, carriage and the trunnion pin.

Nothing here is printed -- it is where the fits are checked, by eye in the
viewer and by the tests, which assert that no two parts share any volume.

The gun hangs off a `RevoluteJoint` on the trunnion axis, so `elevation`
swings it the way the real one swings on its trunnions.

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
    # Down as far as the bayonet's release angle, since that is a position the
    # gun is meant to reach; the quoin stops it going far the other way.
    RevoluteJoint(
        "elevation",
        truck,
        axis=Axis((0, 0, axis_height), (0, 1, 0)),
        angular_range=(pegs.release - 4.0, 10.0),
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

    # The pin is keyed to the gun, so it is placed in the gun's own frame and
    # carried wherever the elevation puts it: lying along the gun's y, turned so
    # its flats stand vertical at `release` and nowhere else. It prints lying on
    # a flat with that flat on the bed, which is why it has to be stood up here.
    pin = (
        gun.location
        * Pos(0, 0, trunnion_height(spec.gun))
        * Rot(0, -pegs.release, 0)
        * Rot(0, 0, 90)
        * Pos(0, 0, -pegs.waist / 2)
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
