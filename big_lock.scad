include <BOSL2/std.scad>;

plug_l = 100;
plug_d = 50;
key_w = 10;
key_h = plug_d / 2 - 0.8;
key_l = plug_l - 2;
key_pin_bar_h = 4;
key_pin_bar_bottom = plug_d / 4;

pin_s = 10;
pin_d = sqrt(pin_s * pin_s + pin_s * pin_s); // diagonal of pin square

key_hole_w = key_w + 0.4;
key_hole_h = key_h + 0.8;
key_hole_bottom = 2;
key_hole_pin_bar_h = 3;
key_hole_pin_bar_w = key_hole_w / 4;
key_hole_pin_bar_bottom = plug_d / 4;

cutout_vertical_padding = 4;

key_hole_pin_bar_top = key_hole_pin_bar_bottom + key_hole_pin_bar_h;

driver_pin_l = plug_d / 2;
chamber_inner_d = plug_d + 0.4;
chamber_d = chamber_inner_d + 4;
chamber_pin_container_w = pin_s + 8;

pin_travel_l = key_h - key_hole_pin_bar_top;
sm_pin_travel_l = pin_travel_l / 4;
lg_pin_travel_l = pin_travel_l / 4 * 2;

driver_pin_hole_l = driver_pin_l + pin_travel_l + 0.4;
key_pin_hole_l = plug_d - key_h - key_hole_bottom;

module for_pins(n = 4) {
  for (i = [1:4]) {
    up((plug_l / (n + 1)) * i)
      children();
  }
}

module pin_holes(bottom = 0, top = 0, pin_n = 4) {
  module pin_hole() {
    translate([0, bottom - 0.1, 0])
      rotate([-90, 0, 0])
        linear_extrude(height=top - bottom + 0.1)
          rotate([0, 0, 45])
            square(size=pin_s, anchor=CENTER);
  }

  // Pin holes
  for_pins(pin_n) {
    pin_hole();
  }
}

module plug() {
  color("yellow")
    difference() {
      // Plug barrel
      linear_extrude(height=plug_l)
        circle(d=plug_d, anchor=CENTER);

      // Viewing cutout
      up(cutout_vertical_padding)
        linear_extrude(height=plug_l - cutout_vertical_padding + 0.1)
          union() {
            fwd(chamber_d / 2 - 10)
              square([plug_d / 2, plug_d - (plug_d / 2)+5], anchor=LEFT + BOTTOM);
            back(16)
              square([plug_d / 2, plug_d - (plug_d / 2)], anchor=LEFT + BOTTOM);
          }

      // Keyhole
      down(0.1)
        fwd(plug_d / 2 - key_hole_bottom)
          linear_extrude(height=key_l + 0.1)
            difference() {
              // key hole cutout
              square([key_hole_w, key_hole_h], anchor=BOTTOM);
              // Pin bar
              translate([-key_hole_w / 2, key_hole_pin_bar_bottom, 0])
                square([key_hole_pin_bar_w, key_hole_pin_bar_h], anchor=BOTTOM + LEFT);
            }

      pin_holes(bottom=-plug_d / 2 + key_hole_bottom + key_hole_pin_bar_bottom + key_hole_pin_bar_h + 0.1, top=plug_d / 2);
    }
}

module chamber(pin_n = 4) {
  color("green")
    difference() {
      // Chamber body
      linear_extrude(height=plug_l + 3)
        union() {
          circle(d=chamber_d);
          // Driver pin container
          back(chamber_inner_d / 2)
            square([chamber_pin_container_w, driver_pin_hole_l], anchor=BOTTOM);
          back((chamber_inner_d / 2) + driver_pin_hole_l)
            circle(d=chamber_pin_container_w);
        }

      down(0.1)
        linear_extrude(height=plug_l - cutout_vertical_padding + 0.1) {
          union() {
            // Viewing cutout
            fwd(chamber_d / 2 - 10)
              square([chamber_d / 2, chamber_d - 10 + (driver_pin_hole_l / 2) - 2], anchor=LEFT + BOTTOM);

            back(chamber_d / 2 + driver_pin_hole_l / 2 + 2)
              square([chamber_d / 2 - cutout_vertical_padding * 2, (driver_pin_hole_l / 2) - 4], anchor=LEFT + BOTTOM);
          }
        }

      // Plug hole
      down(0.1)
        linear_extrude(height=plug_l + 0.4 + 0.1)
          circle(d=chamber_inner_d, anchor=CENTER);
      // Pin holes
      pin_holes(bottom=plug_d / 2 - 1, top=plug_d / 2 + driver_pin_hole_l, pin_n=4);
    }
}

module pin(h, w, tip_w) {
  chamfer_h = (w - tip_w) / 2;
  chamfer_scale = tip_w / w;

  union() {
    translate([0, 0, h - chamfer_h])
      linear_extrude(height=chamfer_h + 0.01, scale=tip_w / w)
        regular_ngon(n=8, d=w, realign=true);

    translate([0, 0, chamfer_h])
      linear_extrude(height=h - chamfer_h * 2)
        regular_ngon(n=8, d=w, realign=true);

    linear_extrude(height=chamfer_h + 0.01, scale=w / tip_w)
      regular_ngon(n=8, d=tip_w, realign=true);
  }
}

module driver_pins(pin_n = 4) {
  for_pins(pin_n) {
    back(chamber_inner_d / 2 + 0.2)
      rotate([-90, 0, 0])
        color("blue")
          pin(h=driver_pin_l, w=pin_s - 0.4, tip_w=pin_s / 2);
  }
}

module key_pins(lengths = [false, true, true, false]) {
  for (i = [1:4]) {
    up((plug_l / 5) * i)
      back(plug_d / 2)
        rotate([90, 0, 0])
          color("red") let (travel = lengths[i - 1] ? sm_pin_travel_l : lg_pin_travel_l) {
            pin(h=travel + key_pin_hole_l + sm_pin_travel_l, w=pin_s - 0.4, tip_w=pin_s / 2);
          }
  }
}

function pts(lengths = [false, true, true, false], i = 0) =
  i == len(lengths) ? []
  : let (
    travel = lengths[i] ? lg_pin_travel_l : sm_pin_travel_l,
    center = plug_l / (len(lengths) + 1) * (i + 1)
  ) concat(
    [
      [center - pin_s / 2 - 3.5, travel + sm_pin_travel_l],
      [center - pin_s / 2 + 1, travel - 0.1],
      [center + pin_s / 2 - 1, travel - 0.1],
      [center + pin_s / 2 + 3.5, travel + sm_pin_travel_l],
    ],
    pts(lengths, i + 1)
  );

module key(lengths = [false, true, true, false]) {
  color("gray")
    translate([key_w / 2 + 0.1, -0.1, 0])
      rotate([0, -90, 0])
        union() {
          linear_extrude(height=key_w)
            union() {
              // keyway
              fwd(plug_d / 2 - key_hole_bottom - 0.8)
                square([key_l, key_h - key_hole_pin_bar_bottom], anchor=BOTTOM + LEFT);
              // key handle
              fwd(key_h / 2)
                square(size=key_h * 1.5, anchor=CENTER + RIGHT);
            }
          linear_extrude(height=key_w - key_hole_pin_bar_h - 1.8)
            fwd(plug_d / 2 - key_hole_bottom - key_hole_pin_bar_bottom)
              union() {
                square([key_l, key_hole_pin_bar_h], anchor=BOTTOM + LEFT);

                let (
                  points = concat(
                    [
                      [0, 0],
                      [0, pin_travel_l],
                    ],
                    pts(lengths),
                    [
                      [key_l, 0],
                    ],
                  )
                ) {
                  back(key_hole_pin_bar_h)
                    polygon(points=points);
                }
              }
        }
}

key_code = [true, false, true, false];

plug();
chamber();
driver_pins(pin_n=len(key_code));
key_pins(lengths=key_code);
key(lengths=key_code);
