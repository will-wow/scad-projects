include <BOSL2/std.scad>;
include <BOSL2/threading.scad>

$fa = $preview ? 1 : .1;
$fs = $preview ? 2 : .1;

solid_wall = 1.2;
tweak = 0.01;
clearance = 0.2;

outer_diameter = 35;
inner_diameter = outer_diameter - solid_wall * 2 - clearance * 2;
inner_bottom_height = 4;
pitch = inner_bottom_height / 4;
inner_top_height = pitch * 3;
outer_height = 10 + solid_wall * 2;

line_width = 0.8;

texture = "wave_ribs";

module Top() {
  union() {
    translate([0, 0, inner_top_height + solid_wall - 0.4]) {
      intersection() {
        cyl(h=0.4, d=outer_diameter, texture=texture, anchor=BOTTOM + CENTER);
        linear_extrude(0.4) {
          top_image();
        }
      }
    }

    translate([0, 0, inner_top_height]) {
      cyl(h=solid_wall - 0.4, d=outer_diameter, texture=texture, anchor=BOTTOM + CENTER);
    }

    difference() {
      threaded_rod(
        d=inner_diameter,
        l=inner_top_height,
        pitch=pitch,
        end_len=pitch / 2,
        starts=2,
        anchor=BOTTOM + CENTER,
      );

      translate([0, 0, -tweak]) {
        linear_extrude(height=inner_top_height + tweak * 2) {
          circle(d=inner_diameter - pitch - solid_wall);
        }
      }
    }
  }
}

module Bottom() {
  translate([0, 0, -solid_wall - clearance]) {
    union() {
      intersection() {
        cyl(
          h=0.4,
          d=inner_diameter + solid_wall * 2 + clearance * 2,
          texture=texture,
          anchor=BOTTOM + CENTER
        );

        linear_extrude(0.4) {
          bottom_image();
        }
      }

      translate([0, 0, 0.4]) {
        difference() {
          cyl(
            h=inner_bottom_height + solid_wall,
            d=inner_diameter + solid_wall * 2 + clearance * 2,
            texture=texture,
            anchor=BOTTOM + CENTER
          );

          translate([0, 0, solid_wall]) {
            threaded_rod(
              d=inner_diameter + clearance * 2,
              l=inner_bottom_height + tweak,
              starts=2,
              pitch=pitch,
              end_len=pitch / 2,
              anchor=BOTTOM + CENTER,
              internal=true,
            );
          }
        }
      }
    }
  }
}

module Ring() {
  ring_inner_d = 15;
  ring_w = 3;
  ring_h = 4;

  difference() {
    cyl(
      d=ring_inner_d + ring_w,
      h=ring_h,
      chamfer=0.8,
    );

    cyl(
      d=ring_inner_d,
      h=ring_h + tweak,
      chamfer=-0.4
    );

    translate([0, -ring_inner_d / 2 - ring_w, -ring_h / 2 - tweak]) {
      linear_extrude(ring_h + tweak * 2) {
        square(ring_w * 2, anchor=BOTTOM + CENTER);
      }
    }
  }
}

module top_image() {
  union() {
    scale(0.8) {
      import("./pirate.svg", center=true);
    }

    difference() {
      circle(d=outer_diameter + 2);
      circle(d=inner_diameter);
    }

    difference() {
      circle(d=inner_diameter - 7);
      circle(d=inner_diameter - 7 - line_width);
    }

    difference() {
      circle(d=inner_diameter - 9);
      circle(d=inner_diameter - 9 - line_width);
    }
  }
}

module bottom_image() {
  union() {
    translate([3, 7, 0]) {
      rotate([0, 180, 0]) {
        text(
          "10",
          font="Noto Sans:style=Bold",
          size=3,
          valign="center",
          halign="center",
        );
      }
    }

    translate([-1, -2, 0]) {
      scale(0.75) {
        import("./treasure.svg", center=true);
      }
    }

    difference() {
      circle(d=outer_diameter + 2);
      circle(d=inner_diameter);
    }
  }
}
