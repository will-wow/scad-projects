include <BOSL2/std.scad>;
include <BOSL2/screws.scad>;

$fn = 96; // smoothness
$fa = 1;
$fs = 0.4;

base_d = 6;
base_h = 6;

cone_h = 18; // rounded cone height
cone_base_d = base_d - 2;
cone_bulge_d = 12;
bulge_point = 0.3;
cone_tip_d = 0.8;

module bulged_cone(h, r_base, r_bulge, r_tip, bulge_pt) {
  rotate_extrude(convexity=10)
    polygon(
      concat(
        [[0, 0]], // axis bottom
        bezier_curve(
          [
            [r_base, 0], // base radius
            [r_bulge, h * bulge_pt], // control point (bulge)
            [r_tip, h], // tip radius
          ],
        ),
        [[0, h]] // axis top
      )
    );
}

module christmas_light() {
  union() {
    // 1) Base cylinder
    screw(spec="M6", length=base_h, anchor=BOTTOM, bevel=false);

    up(base_h)
      bulged_cone(
        h=cone_h,
        r_base=cone_base_d / 2,
        r_bulge=cone_bulge_d / 2,
        r_tip=cone_tip_d / 2,
        bulge_pt=bulge_point
      );
  }
}

difference() {
  christmas_light();
  translate([0, 0, 2])
    rotate([45, 0, 0])
      cuboid([base_d * 2, 1.5, 1.5]);
}
