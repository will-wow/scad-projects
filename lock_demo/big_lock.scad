include <BOSL2/std.scad>;

$fa = $preview ? 1 : .1;
$fs = $preview ? 2 : .1;

CLEARANCE = 0.2;
SOLID_WALL = 3;

/* Inputs */

show_on_key = true;
key_code = [true, false, true, false];

pin_s = 10; // side-to-side width of a pin
pin_chamfer_h = 2;

plug_d = 50;

key_hole_bottom = 2; // Space from bottom of plug to bottom of key hole

cutout_vertical_padding = 4;
cutout_start_from_shell = 10;

compartment_l = 30;

/* Derived */

// Pin count (from key code)
pin_n = len(key_code);

pin_space = pin_s + CLEARANCE * 2 + pin_s;

plug_l = pin_space * (pin_n) + pin_s + CLEARANCE * 2 + pin_s / 2;

key_w = pin_s;
key_h = plug_d / 2 + 4;
key_l = pin_space * (pin_n + 0.5) + pin_s / 2 - CLEARANCE * 3;

cap_l = pin_s + CLEARANCE * 2 + SOLID_WALL + compartment_l;

sm_pin_travel_l = pin_chamfer_h * 2;
lg_pin_travel_l = sm_pin_travel_l * 2;
pin_travel_l = sm_pin_travel_l * 4;

// Top of the pin bar, from the bottom of the plug.
key_hole_pin_bar_top = key_hole_bottom + key_h - pin_travel_l;

key_hole_w = key_w + CLEARANCE * 2;
key_hole_h = key_h + CLEARANCE * 2;
key_hole_pin_bar_thickness = SOLID_WALL;
// The bin bar should take up half the pin width, minus clearance,
// so the key can be the full width of the pin.
key_hole_pin_bar_overhang = pin_s / 2 - CLEARANCE * 2;
key_hole_pin_bar_bottom = key_hole_pin_bar_top - key_hole_pin_bar_thickness;

pin_bar_base_h = SOLID_WALL;
// The wide part should have the small part in the middle, plus the same on each side.
pin_bar_base_w = SOLID_WALL * 3;
pin_bar_extra_depth = SOLID_WALL;

driver_pin_l = plug_d / 2;
shell_inner_d = plug_d + CLEARANCE * 2;
shell_wall = SOLID_WALL;
shell_d = shell_inner_d + shell_wall * 2;
shell_l = plug_l + cap_l + CLEARANCE * 2 + SOLID_WALL;

pin_d = diag(pin_s, pin_s);
chamber_pin_container_w = pin_d + CLEARANCE * 2 + SOLID_WALL * 2;

plug_pin_bar_x = -key_hole_w / 2;
plug_pin_bar_y = -plug_d / 2 + key_hole_pin_bar_bottom;
plug_pin_bar_tab_w = cutout_vertical_padding;

driver_pin_hole_l = driver_pin_l + pin_travel_l;

// The diagonal length of a right triangle given two sides
function diag(a, b) = sqrt(a * a + b * b);
// The diagonal leg cut off from the side of a square to make an octagon
function octagon_leg(square_side) = square_side / (2 + sqrt(2));
// The edge length of an octagon inscribed in a square
function octagon_edge(square_side) = (sqrt(2) - 1) * square_side;

// Conditional mirroring module
// Also supports optional duplication of children when mirrored.
module mirror_if(v = [0, 0, 0], copy = false, condition = true) {
  if (condition) {
    mirror(v)
      children();

    if (copy) {
      children();
    }
  } else {
    children();
  }
}

module for_pins(n = 4, start = 1) {
  for (i = [start:n]) {
    up(pin_space * i)
      children();
  }
}

// Polygon for octagonal pin holes
// with a triangle on top for printing,
// and on the back for the stopper.
module pin_hole_poly(side, stopper_slot = true) {
  leg = octagon_leg(side);
  edge = octagon_edge(side);

  union() {
    regular_ngon(n=8, id=side, realign=true);
    // Triangle at the top of the octagon
    octagon_triangle(s=side, edge_n=4);

    // Triangle at the back of the octagon
    if (stopper_slot) {
      octagon_triangle(s=side, edge_n=6);
    }
  }
}

module pin_hole(bottom = 0, top = 0, reverse = false, stopper_slot = true) {
  translate([0, bottom - 0.1, 0]) {
    mirror_if([0, 0, 1], condition=reverse) {
      rotate([-90, 0, 0]) {
        linear_extrude(height=top - bottom + 0.1) {
          pin_hole_poly(pin_s, stopper_slot);
        }
      }
    }
  }
}

// Polygon for octagonal pin clamps with a viewing hole
module clamp_poly(side, thickness = 3) {
  d = diag(side, side);

  leg = octagon_leg(side);
  edge = octagon_edge(side);

  union() {
    // Arm
    polygon(
      [
        [0, (d / 2)],
        [0, (d / 2 + thickness)],
        [d / 2 - edge / 2, (edge / 2 + thickness)],
        [d / 2 - edge / 2, edge / 2],
      ]
    );
    // Hook
    octagon_triangle(s=side, edge_n=1, spin=-90);

    // Close the open triangle below the arm
    octagon_triangle(s=side, edge_n=8);
  }
}

// Re-add a clamp around the bottom (as printed) half of the pin hole,
// to hold the pins in place while still showing half the pin.
module pin_clamp(bottom = 0, top = 0, thickness = 3, reverse = false, stoppers = false) {
  h = top - bottom;

  translate([0, bottom, 0]) {
    mirror_if([0, 0, 1], condition=reverse)
      union() {
        // Clamp
        rotate([-90, 0, 0])
          linear_extrude(height=h)
            clamp_poly(side=pin_s, thickness=3);

        // Stopper
        if (stoppers) {
          translate([0, h - thickness, 0])
            rotate([-90, 0, 0])
              linear_extrude(height=thickness)
                octagon_triangle(s=pin_s, edge_n=6);
        }
      }
  }
}

// Re-add a clamp around the bottom (as printed) half of the pin hole,
// to hold the pins in place while still showing half the pin.
module pin_full_clamp(bottom = 0, top = 0, thickness = 3) {
  h = top - bottom;

  translate([0, bottom, 0]) {
    // Clamp
    rotate([-90, 0, 0])
      linear_extrude(height=h)
        difference() {
          regular_ngon(n=8, id=pin_s + thickness, realign=true);
          regular_ngon(n=8, id=pin_s, realign=true);
        }
  }
}

// The plug of the lock (the part the key goes into).
module Plug(pin_n = 4) {
  cutout_start = cutout_start_from_shell - shell_wall - CLEARANCE;

  union() {
    difference() {
      // Plug barrel
      linear_extrude(height=plug_l)
        circle(d=plug_d, anchor=CENTER);

      // Viewing cutout
      up(cutout_vertical_padding)
        linear_extrude(height=plug_l - cutout_vertical_padding + 0.1)
          union() {
            fwd(plug_d / 2 - cutout_start)
              square([plug_d / 2, plug_d - cutout_start], anchor=LEFT + BOTTOM);
          }

      // Keyhole
      down(0.1)
        fwd(plug_d / 2 - key_hole_bottom)
          linear_extrude(height=plug_l + 0.2)
            // key hole cutout
            square([key_hole_w, key_hole_h], anchor=BOTTOM);

      // Pin holes
      for_pins(pin_n) {
        pin_hole(bottom=-plug_d / 2, top=plug_d / 2);
      }

      // Pin bar slot
      plug_pin_bar_slot();
    }

    // Retaining bar tab
    translate([plug_pin_bar_x, plug_pin_bar_y, 0]) {
      linear_extrude(plug_pin_bar_tab_w)
        square([key_hole_pin_bar_overhang, key_hole_pin_bar_thickness], anchor=BOTTOM + LEFT);
    }

    // Pin clamps
    intersection() {
      union() {
        for_pins(pin_n) {
          pin_clamp(bottom=-(plug_d / 2) + key_hole_h + key_hole_bottom, top=plug_d / 2, stoppers=true);
        }

        //for_pins(pin_n + 1, start=pin_n + 1) {
        //  pin_full_clamp(bottom=-(plug_d / 2) + key_hole_h + key_hole_bottom, top=plug_d / 2);
        //}
      }

      // round to match plug
      linear_extrude(height=plug_l) {
        circle(d=plug_d, anchor=CENTER);
      }
    }

    plug_cap_tab();
  }
}

cap_tab_x = plug_pin_bar_x - pin_bar_extra_depth - pin_bar_base_h * 2 - CLEARANCE; // aligns with the left of the pin bar slot.
cap_tab_w = SOLID_WALL;

cap_tab_y = plug_pin_bar_y + key_hole_pin_bar_thickness / 2; // aligns with the top of the pin bar slot.
cap_tab_h = pin_bar_base_w + CLEARANCE * 2; // Width of the pin bar slot.

cap_tab_z = plug_l;

cap_pin_z = cap_tab_z + SOLID_WALL * 1.5;
cap_pin_l = ( (plug_d / 2 + cap_tab_x) + (cap_tab_w + CLEARANCE * 2) + SOLID_WALL); // tab_slot_w + 3

module CapPin() {
  translate(
    [
      cap_tab_x + (cap_tab_w + CLEARANCE * 2) + SOLID_WALL,
      cap_tab_y,
      cap_pin_z,
    ]
  ) {
    rotate([0, -90, 0]) {
      linear_extrude(cap_pin_l - 4) {
        rotate([0, 0, 45]) {
          square([SOLID_WALL, SOLID_WALL], anchor=CENTER);
        }
      }
    }
  }
}

module cap_pin_hole() {
  translate(
    [
      cap_tab_x,
      cap_tab_y,
      cap_pin_z,
    ]
  ) {
    right((cap_tab_w + CLEARANCE * 2) + SOLID_WALL) {
      rotate([0, -90, 0]) {
        linear_extrude((plug_d / 2 + cap_tab_x) + (cap_tab_w + CLEARANCE * 2) + SOLID_WALL) {
          rotate([0, 0, 45])
            square([SOLID_WALL + CLEARANCE, SOLID_WALL + CLEARANCE], anchor=CENTER);
        }
      }
    }
  }
}

module cap_tab_slot() {
  translate(
    [
      cap_tab_x - CLEARANCE,
      cap_tab_y - CLEARANCE,
      cap_tab_z - 0.1,
    ]
  ) {
    linear_extrude(cap_tab_h + CLEARANCE * 2 + 0.1) {
      square([cap_tab_w + CLEARANCE * 2, cap_tab_h + CLEARANCE * 2], anchor=CENTER + LEFT);
    }
  }
}

module plug_cap_tab() {
  // Tab for the slot cap
  difference() {
    translate(
      [
        cap_tab_x,
        cap_tab_y,
        cap_tab_z,
      ]
    ) {
      linear_extrude(cap_tab_h) {
        square([pin_bar_base_h, cap_tab_h], anchor=CENTER + LEFT);
      }
    }
    cap_pin_hole();
  }
}

// Top cap over the plug. To be printed in reverse, to allow for a square retaining pin slot.
module Cap() {
  union() {
    difference() {
      // Cap body
      translate([0, 0, plug_l]) {
        linear_extrude(cap_l) {
          circle(d=plug_d, anchor=CENTER);
        }
      }

      // Slot for the cap tab
      cap_tab_slot();
      // Hole for the cap tab pin
      cap_pin_hole();

      // Retaining pin hole (start)
      for_pins(pin_n + 1, pin_n + 1) {
        pin_hole(bottom=(plug_d / 2) - pin_s, top=plug_d / 2, reverse=true, stopper_slot=false);
      }

      // Retaining pin hole (end)
      rotate([0, 0, 90]) {
        for_pins(pin_n + 1, pin_n + 1) {
          pin_hole(bottom=(plug_d / 2) - pin_s, top=plug_d / 2, reverse=true, stopper_slot=false);
        }
      }

      // Retaining pin groove
      up(pin_space * (pin_n + 1) - pin_s / 2) {
        rotate([0, 0, 89.9]) {
          rotate_extrude(angle=90.01) {
            translate([plug_d / 2 + 0.1, 0, 0]) {
              union() {
                square([pin_s + 0.1, pin_s], anchor=BOTTOM + RIGHT);
              }
            }
          }
        }
      }

      // container
      up(plug_l + cap_l - compartment_l) {
        rotate([0, 0, 95]) {
          pie_slice(r=plug_d / 2 - SOLID_WALL, h=compartment_l + 0.1, a=85);
        }
      }
    }
  }
}

module pin_bar_poly() {
  top_bar_w = key_hole_pin_bar_overhang + pin_bar_extra_depth;

  union() {
    square([top_bar_w, key_hole_pin_bar_thickness], anchor=CENTER + LEFT);

    translate([-pin_bar_base_h, 0, 0]) {
      square([pin_bar_base_h, pin_bar_base_w], anchor=CENTER + LEFT);
    }
  }
}

module plug_pin_bar_slot() {
  tab_z = plug_pin_bar_tab_w;
  bar_l = plug_l - plug_pin_bar_tab_w + 0.1;

  translate([plug_pin_bar_x - pin_bar_extra_depth, plug_pin_bar_y + key_hole_pin_bar_thickness / 2, tab_z]) {
    linear_extrude(bar_l) {
      offset(delta=CLEARANCE)
        pin_bar_poly();
    }
  }
}

module PlugPinBar() {
  tab_z = plug_pin_bar_tab_w + CLEARANCE;
  bar_l = plug_l - tab_z;

  // Pin bar
  translate([plug_pin_bar_x - pin_bar_extra_depth, plug_pin_bar_y + key_hole_pin_bar_thickness / 2, tab_z]) {
    linear_extrude(bar_l) {
      pin_bar_poly();
    }
  }
}

// The shell of the lock
// (the outer casing that holds the driver pins).
module Shell(pin_n = 4) {
  union() {
    difference() {
      // Shell body
      linear_extrude(height=shell_l)
        union() {
          // Outer shell around the plug
          circle(d=shell_d);
          // Driver pin chamber
          back(shell_inner_d / 2)
            square([chamber_pin_container_w, driver_pin_hole_l], anchor=BOTTOM);
          // Top of the driver pin chamber
          back((shell_inner_d / 2) + driver_pin_hole_l)
            circle(d=chamber_pin_container_w);
        }

      // Plug hole
      down(0.1)
        linear_extrude(height=plug_l + cap_l + CLEARANCE * 2)
          circle(d=shell_inner_d, anchor=CENTER);

      // Pin holes
      for_pins(pin_n + 1) {
        pin_hole(bottom=shell_inner_d / 2, top=shell_inner_d / 2 + driver_pin_hole_l, reverse=true, stopper_slot=false);
      }

      // Viewing cutout
      down(0.1)
        linear_extrude(height=plug_l + pin_space - cutout_vertical_padding) {
          fwd(shell_d / 2 - cutout_start_from_shell)
            square([shell_d / 2, shell_d - cutout_start_from_shell - shell_wall + driver_pin_hole_l], anchor=LEFT + BOTTOM);
        }

      // container door
      up(shell_l - SOLID_WALL - 0.2)
        pie_slice(r=shell_inner_d / 2 - SOLID_WALL, h=SOLID_WALL + 0.3, a=90);
    }

    // Pin clamps
    for_pins(n=pin_n + 1) {
      pin_clamp(bottom=shell_inner_d / 2, top=plug_d / 2 + driver_pin_hole_l, reverse=true);
    }
  }
}

// a:angle, r:radius, h:height
module pie_slice(a, r, h) {
  rotate_extrude(angle=a) square([r, h]);
}

module on_octagon_edge(s, edge_n = 0) {
  leg = octagon_leg(s);
  edge = octagon_edge(s);

  rotate([0, 0, 180 - edge_n * 45])
    translate([0, -(leg + edge / 2), 0])
      children();
}

// Render a triangle polygon on edge_n of an octagon of square side s
// edge_n is 0-7. 0 is the top edge (y+), then clockwise.
module octagon_triangle(s, edge_n = 0, spin = 0, r_off = 0, l_off = 0, t_off = 0) {
  leg = octagon_leg(s);
  edge = octagon_edge(s);

  on_octagon_edge(s=s, edge_n=edge_n)
    rotate([0, 0, spin])
      difference() {
        right_triangle([leg, leg], spin=45, anchor="hypot");

        if (l_off > 0) {
          translate([edge / 2 - l_off, 0, 0])
            square([l_off, edge / 2], anchor=TOP + LEFT);
        }

        if (r_off > 0) {
          translate([edge / 2 - r_off, 0, 0])
            square([r_off, edge / 2], anchor=TOP + RIGHT);
        }

        if (t_off > 0) {
          square([edge, t_off], anchor=TOP + CENTER);
        }
      }
}

module pin_cross_section(s) {
  leg = octagon_leg(s);
  edge = octagon_edge(s);

  difference() {
    regular_ngon(n=8, id=s, realign=true);

    mirror_if([0, 1, 0], copy=true)
      on_octagon_edge(s=s, edge_n=7)
        right_triangle([leg, leg], spin=135, anchor="hypot");
  }
}

// A pin
module pin(height, width, chamfer_h = pin_chamfer_h, stopper = false, reverse_stopper = false) {
  w = width - CLEARANCE * 2;
  h = height - CLEARANCE * 2;
  // Top width is width minus a 45 chamfer on each side
  tw = w - chamfer_h * 2;

  chamfer_scale = tw / w;

  edge = octagon_edge(w);
  leg = octagon_leg(w);

  middle_h = h - chamfer_h * 2;

  scale_bottom = tw / w;
  scale_top = 1 / scale_bottom;

  rotate([0, 0, 45])
    difference() {
      union() {
        // bottom bevel
        translate([0, 0, h - chamfer_h])
          linear_extrude(height=chamfer_h, scale=scale_bottom)
            difference() {
              regular_ngon(n=8, id=w, realign=true);
            }

        // middle
        translate([0, 0, chamfer_h])
          linear_extrude(height=middle_h)
            regular_ngon(n=8, id=w, realign=true);

        // top bevel
        linear_extrude(height=chamfer_h, scale=scale_top)
          regular_ngon(n=8, id=tw, realign=true);

        // stopper
        if (stopper) {
          translate([0, 0, reverse_stopper ? chamfer_h : chamfer_h + middle_h - 3])
            linear_extrude(height=3)
              octagon_triangle(s=w, edge_n=7);
        }
      }

      // Cut out for hook
      linear_extrude(height=h)
        mirror_if([1, 1, 0], copy=true)
          offset(delta=CLEARANCE)
            octagon_triangle(s=width, edge_n=4, spin=45 * 2);
    }
}

// Driver pins (in the shell)
module DriverPins(code = [false, true, true, false]) {
  for (i = [1:len(code)]) {
    let (
      travel = code[i - 1] ? lg_pin_travel_l : sm_pin_travel_l,
    ) {
      up(pin_space * i) {
        back((shell_inner_d / 2 + 0.2) - (show_on_key ? 0 : travel)) {
          rotate([-90, 0, 0]) {
            pin(height=driver_pin_l, width=pin_s, chamfer_h=pin_chamfer_h);
          }
        }
      }
    }
  }
}

retaining_pin_y = (shell_inner_d / 2) - pin_s / 2;
retaining_pin_z = pin_space * (pin_n + 1);
retaining_pin_l = driver_pin_l;
retaining_spring_thickness = 1;
retaining_spring_rotation = 90;

module RetainingPin(pin_n = 4, chamfer_h = pin_chamfer_h) {
  translate([0, retaining_pin_y, retaining_pin_z]) {
    rotate([-90, 0, 0]) {
      difference() {
        pin(height=retaining_pin_l, width=pin_s, chamfer_h=chamfer_h);
        up(SOLID_WALL) {
          rotate([0, 0, retaining_spring_rotation]) {
            linear_extrude(retaining_pin_l - SOLID_WALL) {
              square([retaining_spring_thickness + CLEARANCE * 2, retaining_spring_thickness + CLEARANCE * 2], anchor=CENTER);
            }
          }
        }
      }
    }
  }
}

module RetainingSpring(pin_n = 4) {
  thickness = retaining_spring_thickness;
  stick_depth = driver_pin_l;
  edge = octagon_edge(pin_s);
  inner_width = pin_s - CLEARANCE * 2 - edge;

  translate([0, retaining_pin_y + driver_pin_l + SOLID_WALL, retaining_pin_z]) {
    translate([0, thickness * 2, -thickness / 2]) {
      rotate([0, retaining_spring_rotation, 0]) {
        linear_extrude(thickness) {
          union() {
            for (i = [0:pin_n]) {
              translate([0, (edge - thickness) * i, 0]) {
                translate([(inner_width / 2) * (i % 2 ? 1 : -1), 0, 0]) {
                  difference() {
                    circle(d=edge);
                    circle(d=edge - thickness * 2);
                    left(i % 2 == 0 ? 0 : edge / 2) {
                      square([edge / 2, edge], anchor=LEFT + CENTER);
                    }
                  }
                }
                back(edge / 2) {
                  square([inner_width, thickness], anchor=CENTER + TOP);
                }

                if (i == 0) {
                  ymove(-edge / 2) {
                    square([inner_width / 2, thickness], anchor=RIGHT + BOTTOM);
                  }

                  ymove(-(edge / 2 - thickness)) {
                    square([thickness, stick_depth], anchor=CENTER + TOP);
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

// Key pins (in the plug)
module KeyPins(code = [false, true, true, false]) {
  pin_above_key_l = plug_d - key_h - key_hole_bottom;

  for (i = [1:len(code)]) {
    let (
      travel = code[i - 1] ? lg_pin_travel_l : sm_pin_travel_l,
    ) {
      up(pin_space * i) {
        back((plug_d / 2) - (show_on_key ? 0 : travel)) {
          rotate([90, 0, 0]) {
            // Pins are (the space from top of the key to the top of the plug) + (the full padded pin travel) - the actual travel expected from the key.
            pin(height=pin_above_key_l + pin_travel_l - travel, width=pin_s, chamfer_h=pin_chamfer_h, stopper=true);
          }
        }
      }
    }
  }
}

// Points for the key's biting (notches and teeth)
function bitingPoly(code = [false, true, true, false], i = 0) =
  i == len(code) ? []
  : let (
    travel = code[i] ? lg_pin_travel_l : sm_pin_travel_l,
    center = pin_space * (i + 1)
  ) concat(
    [
      [center - pin_s / 2 - 3.5, travel + sm_pin_travel_l],
      [center - pin_s / 2 + 1, travel],
      [center + pin_s / 2 - 1, travel],
      [center + pin_s / 2 + 3.5, travel + sm_pin_travel_l],
    ],
    bitingPoly(code, i + 1)
  );

// The key
module Key(code = [false, true, true, false]) {
  // The section of the key over the bar + clearance above and below.
  key_bar_h = key_hole_pin_bar_thickness + CLEARANCE * 2;
  key_ridges_h = pin_travel_l + CLEARANCE;
  // The keyway is the remainder of the key, after the pin travel and the pin bar w/ clearance.
  keyway_h = key_h - key_ridges_h - key_bar_h;

  key_ridges_width = key_w - key_hole_pin_bar_overhang - CLEARANCE * 2;

  translate(
    [
      key_w / 2 + CLEARANCE / 2,
      // Move to the bottom of the key_hole + CLEARANCE
      -plug_d / 2 + key_hole_bottom + CLEARANCE,
      0,
    ]
  ) {
    rotate([0, -90, 0]) {
      union() {
        linear_extrude(height=key_w)
          difference() {
            union() {
              // keyway
              square([key_l, keyway_h], anchor=BOTTOM + LEFT);
              // key handle
              fwd(key_h / 4)
                square(size=key_h * 1.5, anchor=BOTTOM + RIGHT);
            }
            right(key_l) {
              right_triangle([keyway_h - 1, keyway_h - 1], spin=90, anchor=BOTTOM + LEFT);
            }
          }
        // Over the pin bar.
        linear_extrude(height=key_ridges_width) {
          back(keyway_h) {
            union() {
              square([key_l, key_bar_h], anchor=BOTTOM + LEFT);

              back(key_bar_h)
                // The top height of the biting in the pin_travel_l.
                polygon(
                  points=concat(
                    [
                      [0, 0],
                      [0, key_ridges_h],
                    ],
                    bitingPoly(code),
                    [
                      [key_l, 0],
                    ]
                  )
                );
            }
          }
        }
      }
    }
  }
}

/*
TODO:
x connect shell clamps with the shell top
- add tweezer slots around cap bar
- increase length of key front, to make it easier to move pins
- prettier handle on key
- groove in top of shell to slide a cover on
- lock picking tools
- increase clearance on pin clamp holes?
- stronger shorter retaining pin spring. spring can got to half length.
- shorter driver pins.
- a "bad" key with a different code
*/ 

color("gold") Plug(pin_n=pin_n);
color("yellow") Cap();
color("orange") CapPin();
color("orange") PlugPinBar();
color("teal") RetainingPin(pin_n=pin_n, chamfer_h=0.4);
color("aqua") RetainingSpring(pin_n=pin_n);
color("green") Shell(pin_n=pin_n);
color("blue") DriverPins(code=key_code);
color("red") KeyPins(code=key_code);
up(show_on_key ? 0 : -plug_l) color("gray") Key(code=key_code);
