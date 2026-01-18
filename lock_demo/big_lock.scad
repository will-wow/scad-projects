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

/* Derived */

// Pin count (from key code)
pin_n = len(key_code);

plug_l = (pin_n + 2) * pin_s * 2;
plug_l = 100;

key_w = pin_s;
key_h = plug_d / 2 + 4;
key_l = plug_l - 2;

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

module for_pins(n = 4) {
  for (i = [1:n]) {
    up((plug_l / (n + 1)) * i)
      children();
  }
}

// Polygon for octagonal pin holes
// with a triangle on top for printing,
// and on the back for stopping falling out
module pin_hole_poly(side) {
  leg = octagon_leg(side);
  edge = octagon_edge(side);

  union() {
    regular_ngon(n=8, id=side, realign=true);
    // Triangle at the top of the octagon
    octagon_triangle(s=side, edge_n=4);
    // Triangle at the back of the octagon
    octagon_triangle(s=side, edge_n=6);
  }
}

module pin_holes(bottom = 0, top = 0, pin_n = 4, reverse = false) {
  for_pins(pin_n) {
    translate([0, bottom - 0.1, 0])
      mirror_if([0, 0, 1], condition=reverse)
        rotate([-90, 0, 0])
          linear_extrude(height=top - bottom + 0.1)
            pin_hole_poly(pin_s);
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

// Re-add clamps around the bottom (as printed) half of the pin holes
// To hold the pins in place, while still showing half the pin.
module pin_clamps(bottom = 0, top = 0, thickness = 3, pin_n = 4, reverse = false, stoppers = false) {
  h = top - bottom;

  module pin_clamp() {
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

  for_pins(pin_n) {
    pin_clamp();
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
      pin_holes(bottom=-plug_d / 2, top=plug_d / 2, pin_n=pin_n);

      // Pin bar slot
      plug_pin_bar_slot();
    }

    translate([plug_pin_bar_x, plug_pin_bar_y, 0]) {
      linear_extrude(plug_pin_bar_tab_w)
        square([key_hole_pin_bar_overhang, key_hole_pin_bar_thickness], anchor=BOTTOM + LEFT);
    }

    // Pin clamps
    intersection() {
      pin_clamps(bottom=-(plug_d / 2) + key_hole_h + key_hole_bottom, top=plug_d / 2, pin_n=pin_n, stoppers=true);

      // round to match plug
      linear_extrude(height=plug_l)
        circle(d=plug_d, anchor=CENTER);
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

  // Pin bar
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
      linear_extrude(height=plug_l + 3)
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
        linear_extrude(height=plug_l + 0.4 + 0.1)
          circle(d=shell_inner_d, anchor=CENTER);

      // Pin holes
      pin_holes(bottom=plug_d / 2 - 10, top=plug_d / 2 + driver_pin_hole_l, pin_n=pin_n, reverse=true);

      // Viewing cutout
      down(0.1)
        linear_extrude(height=plug_l - cutout_vertical_padding + 0.1) {
          fwd(shell_d / 2 - cutout_start_from_shell)
            square([shell_d / 2, shell_d - cutout_start_from_shell - shell_wall + driver_pin_hole_l], anchor=LEFT + BOTTOM);
        }
    }

    pin_clamps(bottom=shell_inner_d / 2, top=plug_d / 2 + driver_pin_hole_l, pin_n=pin_n, reverse=true);
  }
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
      up((plug_l / 5) * i) {
        back((shell_inner_d / 2 + 0.2) - (show_on_key ? 0 : travel)) {
          rotate([-90, 0, 0]) {
            pin(height=driver_pin_l, width=pin_s, chamfer_h=pin_chamfer_h);
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
      up((plug_l / 5) * i) {
        back((plug_d / 2) - (show_on_key ? 0 : travel)) {
          rotate([90, 0, 0]) {
            // Pins are (the space from top of the key to the top of the slug) + (the full padded pin travel) - the actual travel expected from the key.
            pin(height=pin_above_key_l + pin_travel_l - travel, width=pin_s, chamfer_h=pin_chamfer_h, stopper=true);
          }
        }
      }
    }
  }
}

// Points for the key's pin cuts
function pts(code = [false, true, true, false], i = 0) =
  i == len(code) ? []
  : let (
    travel = code[i] ? lg_pin_travel_l : sm_pin_travel_l,
    center = plug_l / (len(code) + 1) * (i + 1)
  ) concat(
    [
      [center - pin_s / 2 - 3.5, travel + sm_pin_travel_l],
      [center - pin_s / 2 + 1, travel],
      [center + pin_s / 2 - 1, travel],
      [center + pin_s / 2 + 3.5, travel + sm_pin_travel_l],
    ],
    pts(code, i + 1)
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
          union() {
            // keyway
            square([key_l, keyway_h], anchor=BOTTOM + LEFT);
            // key handle
            fwd(key_h / 4)
              square(size=key_h * 1.5, anchor=BOTTOM + RIGHT);
          }
        // Key edges
        linear_extrude(height=key_ridges_width) {
          back(keyway_h) {
            union() {
              square([key_l, key_bar_h], anchor=BOTTOM + LEFT);

              back(key_bar_h)
                // The height of these points is pin_travel_l
                polygon(
                  points=concat(
                    [
                      [0, 0],
                      [0, key_ridges_h],
                    ],
                    pts(code),
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
- add a 5th driver pin/slot to act as a "retainer pin".
	- this should have a printed spring to keep it pressed down.
	- add a hole in the back of the shell to access this pin with a tool, to pull it up and allow the plug to be removed
	- the shell and plug should enclose the front of the pin slot
	- add a cutout in the plug to allow this pin to hold it in place. this should only extend 40 degrees, so it stop over-rotation forwards, or any rotation backwards.
- make a small turning box that is opened when the lock is turned.
*/

color("gold") Plug(pin_n=pin_n);
color("orange") PlugPinBar();
color("green") Shell(pin_n=pin_n);
color("blue") DriverPins(code=key_code);
color("red") KeyPins(code=key_code);
if (show_on_key) {
  color("gray") Key(code=key_code);
}
