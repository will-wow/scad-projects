import build123d as bd
from ocp_vscode import show_all

pip_count = 6

lego_unit_size = 8
pip_height = 1.8
pip_diameter = 4.8
block_length = lego_unit_size * pip_count
block_width = 16
base_height = 9.6
block_height = base_height + pip_height
support_outer_diameter = 6.5
support_inner_diameter = 4.8
ridge_width = 0.6
ridge_depth = 0.3
wall_thickness = 2

with bd.BuildPart() as lego:
    # Draw the bottom of the block
    with bd.BuildSketch() as plan:
        perimeter = bd.Rectangle(width=block_length, height=block_width)
        bd.offset(perimeter, wall_thickness, kind=bd.Kind.INTERSECTION, mode=bd.Mode.SUBTRACT)

        with bd.GridLocations(x_spacing=0, y_spacing=lego_unit_size, x_count=1, y_count=2):
            bd.Rectangle(width=block_length, height=ridge_width)
        with bd.GridLocations(lego_unit_size, 0, pip_count, 1):
            bd.Rectangle(width=ridge_width, height=block_width)
        # Subtract a rectangle leaving ribs on the block walls
        bd.Rectangle(
            block_length - 2 * (wall_thickness + ridge_depth),
            block_width - 2 * (wall_thickness + ridge_depth),
            mode=bd.Mode.SUBTRACT,
        )

        # Add a row of hollow circles to the center
        with bd.GridLocations(
            x_spacing=lego_unit_size, y_spacing=0, x_count=pip_count - 1, y_count=1
        ):
            bd.Circle(radius=support_outer_diameter / 2)
            bd.Circle(radius=support_inner_diameter / 2, mode=bd.Mode.SUBTRACT)
    # Extrude this base sketch to the height of the walls
    bd.extrude(amount=base_height - wall_thickness)

    with bd.Locations((0, 0, lego.vertices().sort_by(bd.Axis.Z)[-1].Z)):
        bd.Box(
            length=block_length,
            width=block_width,
            height=wall_thickness,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
        )

show_all()
