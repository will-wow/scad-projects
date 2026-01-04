include <BOSL2/std.scad>;

$fa = 1;
$fs = 0.4;

ir = 7;
or = 15;
fillet_r = 0.4;

trap_h = or - ir;
trap_w1 = 1;
trap_w2 = 5;

h = 0.4 * 4 * 4;
c_bottom = 0.4;
c_top = h - c_bottom - 0.4;

module chamfered_extrude(height, chamfer_top = 0, chamfer_bottom = 0, outer_r) {
  assert(height > chamfer_top + chamfer_bottom, "height must be > 2*chamfer");
  assert(outer_r > chamfer_top, "outer_r must be > chamfer");
  assert(outer_r > chamfer_bottom, "outer_r must be > chamfer");

  scale_top = (outer_r - chamfer_top) / outer_r;
  scale_bottom = (outer_r - chamfer_bottom) / outer_r;

  union() {
    // Bottom chamfer: small at z=0 -> full at z=chamfer
    linear_extrude(height=chamfer_bottom, scale=1 / scale_bottom)
      scale(scale_bottom)
        children();

    // Middle: full size
    translate([0, 0, chamfer_bottom])
      linear_extrude(height=height - chamfer_top - chamfer_bottom)
        children();

    // Top chamfer: full at z=height-chamfer -> small at z=height
    translate([0, 0, height - chamfer_top])
      linear_extrude(height=chamfer_top, scale=scale_top)
        children();
  }
}

module earring() {
  chamfered_extrude(height=h, chamfer_top=c_top, chamfer_bottom=c_bottom, outer_r=or)
    round2d(r=fillet_r)
      union() {
        star(n=5, ir=ir, or=or, align_tip=BACK)
          attach("pit2", FWD)
            trapezoid(h=trap_h, w1=trap_w1, w2=trap_w2, anchor=TOP);
      }
}

difference() {
  earring();
  translate([0, or - 6, -h / 2])
    cylinder(h=h * 2, d=1.5);
}
