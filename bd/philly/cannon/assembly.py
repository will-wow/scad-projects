"""The three printed parts, put together: gun, carriage and two trunnion pegs.

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
from cannon.cap_square import CapSquareSpec, cap_square
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
    RevoluteJoint(
        "elevation", truck, axis=Axis((0, 0, axis_height), (0, 1, 0)), angular_range=(-10, 10)
    )
    for side in (1, -1):
        RigidJoint(
            f"trunnion{side:+d}",
            truck,
            Plane(
                origin=(0, side * (spec.gap / 2 - pegs.stand_off - pegs.into_barrel), axis_height),
                z_dir=(0, side, 0),
            ).location,
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

    parts: list[Part] = [truck, gun]
    straps = CapSquareSpec(carriage=spec)
    rail_top = spec.rail_top
    for side in (1, -1):
        peg = trunnion(pegs)
        peg.color = BRASS
        peg.label = f"trunnion{side:+d}"
        RigidJoint("seat", peg, Plane(origin=(0, 0, 0)).location)
        truck.joints[f"trunnion{side:+d}"].connect_to(peg.joints["seat"])
        parts.append(peg)

        # Turned back the right way up -- it prints groove-up -- and slid
        # home: aft of the detent, against the step.
        strap = Rot(180, 0, 0) * cap_square(straps)
        if side < 0:
            strap = strap.mirror(Plane.XZ)
        strap = (
            Pos(
                spec.rail_end - straps.length / 2,
                side * (spec.gap / 2 + straps.stand_off + straps.width / 2),
                rail_top - spec.flare + straps.height,
            )
            * strap
        )
        strap.color = IRON
        strap.label = f"cap square{side:+d}"
        parts.append(strap)

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
