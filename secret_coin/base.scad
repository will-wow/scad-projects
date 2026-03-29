include <BOSL2/std.scad>;
include <BOSL2/threading.scad>

$fa = $preview ? 1 : .1;
$fs = $preview ? 2 : .1;

solid_wall = 1.2;
tweak = 0.01;
clearance = 0.2;

outer_diameter = 35;
inner_diameter = outer_diameter - solid_wall * 2 - clearance * 2;
inner_height = 4;
outer_height = 10 + solid_wall * 2;
pitch = inner_height / 2;

line_width = 0.8;

texture = "wave_ribs";

module Top() {
  union() {
    translate([0, 0, inner_height]) {
      difference() {
        cyl(
          h=solid_wall, d=outer_diameter, texture=texture,
          anchor=BOTTOM + CENTER
        );
        translate([0, 0, solid_wall - 0.2]) {
          linear_extrude(0.3) {
            top_image();
          }
        }
      }
    }

    difference() {
      threaded_rod(d=inner_diameter, l=inner_height, pitch=pitch, anchor=BOTTOM + CENTER);

      translate([0, 0, -tweak]) {
        linear_extrude(height=inner_height + tweak * 2) {
          circle(d=inner_diameter - pitch - solid_wall);
        }
      }
    }
  }
}

module Bottom() {
  translate([0, 0, -solid_wall - clearance]) {
    difference() {
      cyl(
        h=inner_height + solid_wall,
        d=inner_diameter + solid_wall * 2 + clearance * 2,
        texture=texture,
        anchor=BOTTOM + CENTER
      );

      translate([0, 0, -tweak]) {
        linear_extrude(0.3 + tweak) {
          bottom_image();
        }
      }

      translate([0, 0, solid_wall]) {
        threaded_rod(d=inner_diameter + clearance * 2, l=inner_height + tweak, pitch=pitch, anchor=BOTTOM + CENTER, internal=true);
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
      circle(d=inner_diameter);
      circle(d=inner_diameter - line_width);
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

    translate([0, 8, 0]) {
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

    translate([-0.5, -3, 0]) {
      scale(0.4) {
        import("./treasure.svg", center=true);
      }
    }

    difference() {
      circle(d=inner_diameter);
      circle(d=inner_diameter - line_width);
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
