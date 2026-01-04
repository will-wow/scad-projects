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
key_hole_pin_bar_h = 3;
key_hole_pin_bar_w = key_hole_w / 4;
key_hole_pin_bar_bottom = key_pin_bar_bottom + 0.4;

module for_pins() {
  for (i = [1:4]) {
    up((plug_l / 5) * i)
      children();
  }
}

module pin_holes(bottom = 0, top = 0) {
  module pin_hole() {
    translate([0, bottom - 0.1, 0])
      rotate([-90, 0, 0])
        linear_extrude(height=top - bottom + 0.1)
          rotate([0, 0, 45])
            square(size=pin_s, anchor=CENTER);
  }

  // Pin holes
  for_pins() {
    pin_hole();
  }
}

module plug() {
  color("yellow")
    difference() {
      // Plug barrel
      linear_extrude(height=plug_l)
        difference() {
          circle(d=plug_d, anchor=CENTER);
          right(0.9)
            square([plug_d / 2, plug_d], anchor=LEFT);
        }

      // Keyhole
      translate([0, -plug_d / 2, -0.1])
        linear_extrude(height=key_l + 0.1)
          difference() {
            // key hole cutout
            square([key_hole_w, key_hole_h], anchor=BOTTOM);
            // Pin bar
            translate([-key_hole_pin_bar_w, key_hole_pin_bar_bottom, 0])
              square([key_hole_pin_bar_w, key_hole_pin_bar_h], anchor=BOTTOM);
          }

      pin_holes(bottom=-( (plug_d / 2) - key_hole_h), top=plug_d / 2);
    }
}

driver_pin_l = plug_d / 2;
chamber_inner_d = plug_d + 0.4;
chamber_d = chamber_inner_d + 4;
chamber_pin_container_w = pin_s + 8;

module chamber() {
  color("green")
    difference() {
      // Chamber body
      linear_extrude(height=plug_l + 3)
        difference() {
          union() {
            circle(d=chamber_d);
            // Driver pin container
            back(chamber_inner_d / 2)
              square([chamber_pin_container_w, driver_pin_l], anchor=BOTTOM);
            back((chamber_inner_d / 2) + driver_pin_l)
              circle(d=chamber_pin_container_w);
          }

          // Viewing cutout
          right(1)
            fwd(chamber_d / 2)
              square([chamber_d / 2, chamber_d + driver_pin_l + chamber_pin_container_w / 2], anchor=LEFT + BOTTOM);
        }
      // Plug cutout
      down(0.1)
        linear_extrude(height=plug_l + 0.4 + 0.1)
          circle(d=chamber_inner_d, anchor=CENTER);
      // Pin holes
      pin_holes(bottom=plug_d / 2, top=(plug_d / 2) + driver_pin_l + 4 + 0.4);
    }
}

module driver_pins() {
  for_pins() {
    back(chamber_inner_d / 2)
      rotate([-90, 0, 0])
        color("blue")
          linear_extrude(height=driver_pin_l)
            rotate([0, 0, 45])
              square([pin_s, pin_s], anchor=CENTER);
  }
}

module key_pins(lengths = [false, true, true, false]) {
  for (i = [1:4]) {
    up((plug_l / 5) * i)
      back(plug_d / 2)
        rotate([90, 0, 0])
          color("red") let (length = lengths[i - 1] ? 10 : 5) {
            linear_extrude(height=length+18)
              rotate([0, 0, 45])
                square([pin_s, pin_s], anchor=CENTER);
          }
  }
}

module key(lengths = [false, true, true, false]) {
  color("gray")
    rotate([0, -90, 0])
      union() {
        down(key_w / 2)
          linear_extrude(height=key_w)
            union() {
              // keyway
              fwd(key_pin_bar_bottom)
                square([key_l, key_h - key_pin_bar_bottom], anchor=TOP + LEFT);
              // key handle
              fwd(key_h / 2)
                square(size=key_h * 1.5, anchor=CENTER + RIGHT);
            }
        down(key_w / 2)
          linear_extrude(height=key_w - key_hole_pin_bar_w - 1.8)
            union() {
              fwd(key_pin_bar_bottom)
                square([key_l, key_hole_pin_bar_h], anchor=BOTTOM + LEFT);
              for (i = [1:4]) {
                let (length = lengths[i - 1] ? 5 : 10) {
                  right((plug_l / 5) * i)
                    fwd(key_pin_bar_bottom - key_hole_pin_bar_h)
                      square([pin_d+1, length], anchor=BOTTOM + CENTER);
                }
              }
            }
      }
}

key_code = [false, true, true, false];

plug();
chamber();
driver_pins();
key_pins(lengths=key_code);
key(lengths=key_code);
