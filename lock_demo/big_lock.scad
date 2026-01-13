include <BOSL2/std.scad>;

plug_l = 100;
plug_d = 50;

key_w = 10;
key_h = plug_d / 2 - 0.8;
key_l = plug_l - 2;
key_pin_bar_h = 4;
key_pin_bar_bottom = plug_d / 4;

pin_s = 10;

pin_d = diag(pin_s, pin_s); // diagonal of pin square

key_hole_w = key_w + 0.4;
key_hole_h = key_h + 0.8;
key_hole_bottom = 2;
key_hole_pin_bar_h = 3;
key_hole_pin_bar_w = key_hole_pin_bar_h + 1.8;
key_hole_pin_bar_bottom = plug_d / 4;

cutout_vertical_padding = 4;

key_hole_pin_bar_top = key_hole_pin_bar_bottom + key_hole_pin_bar_h;

driver_pin_l = plug_d / 2;
shell_inner_d = plug_d + 0.4;
shell_wall = 2;
shell_d = shell_inner_d + shell_wall * 2;
chamber_pin_container_w = pin_s + 14; // TODO: tune

pin_travel_l = key_h - key_hole_pin_bar_top;
sm_pin_travel_l = pin_travel_l / 4;
lg_pin_travel_l = pin_travel_l / 4 * 2;

driver_pin_hole_l = driver_pin_l + pin_travel_l + 0.4;
key_pin_hole_l = plug_d - key_h - key_hole_bottom;

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
// with a triangle on top for printing.
module pin_hole_poly(side) {
  leg = octagon_leg(side);
  edge = octagon_edge(side);

  union() {
    regular_ngon(n=8, id=side, realign=true);
    // Triangle at the top of the octagon
    fwd(side / 2)
      rotate([0, 0, 45])
        square(leg, anchor=CENTER);
    // spinal slot
    rotate([0, 0, 45])
      translate([0, edge, 0])
        square([edge, edge * 2], anchor=BOTTOM);
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
  s = side + thickness;
  d = diag(s, s);
  difference() {
    // Draw a diamond shape
    rotate([0, 0, 45])
      square(s, anchor=CENTER);
    // Cut out the pin hole again.
    pin_hole_poly(side);
    // cut off the top, for viewing
    square([d, d / 2], anchor=TOP);
  }
}

// Re-add clamps about the bottom half of the pin holes
// To hold the pins in place, while still showing half the pin.
module pin_clamps(bottom = 0, top = 0, thickness = 3, pin_n = 4, reverse = false) {
  s = pin_s + 3;
  d = diag(s, s);

  module pin_clamp() {
    translate([0, bottom, 0])
      mirror_if([0, 0, 1], condition=reverse)
        rotate([-90, 0, 0])
          linear_extrude(height=top - bottom)
            clamp_poly(side=pin_s, thickness=3);
  }

  for_pins(pin_n) {
    pin_clamp();
  }
}

// The plug of the lock (the part the key goes into).
module plug(pin_n = 4) {
  union() {
    difference() {
      // Plug barrel
      linear_extrude(height=plug_l)
        circle(d=plug_d, anchor=CENTER);

      // Viewing cutout
      up(cutout_vertical_padding)
        linear_extrude(height=plug_l - cutout_vertical_padding + 0.1)
          union() {
            fwd(shell_d / 2 - 10)
              square([plug_d / 2, plug_d - 10 + shell_wall + 0.1], anchor=LEFT + BOTTOM);
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

      pin_holes(bottom=-plug_d / 2 + key_hole_bottom + key_hole_pin_bar_bottom + key_hole_pin_bar_h + 0.1, top=plug_d / 2, pin_n=pin_n);
    }

    intersection() {
      pin_clamps(bottom=key_hole_bottom, top=plug_d / 2);
      // round to match plug
      linear_extrude(height=plug_l)
        circle(d=plug_d, anchor=CENTER);
    }
  }
}

// The shell of the lock
// (the outer casing that holds the driver pins).
module lock_shell(pin_n = 4) {
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
          fwd(shell_d / 2 - 10)
            square([shell_d / 2, shell_d - 10 - shell_wall + driver_pin_hole_l], anchor=LEFT + BOTTOM);
        }
    }

    pin_clamps(bottom=shell_inner_d / 2, top=plug_d / 2 + driver_pin_hole_l, pin_n=pin_n, reverse=true);
  }
}

// A pin
module pin(h, w, tip_w, spine = true, hook_top = false) {
  chamfer_h = (w - tip_w) / 2;
  chamfer_scale = tip_w / w;

  edge = octagon_edge(w);

  middle_h = h - chamfer_h * 2;

  rotate([0, 0, 45])
    union() {
      // bottom bevel
      translate([0, 0, h - chamfer_h])
        linear_extrude(height=chamfer_h + 0.01, scale=tip_w / w)
          regular_ngon(n=8, id=w, realign=true);

      // middle
      translate([0, 0, chamfer_h])
        linear_extrude(height=middle_h)
          regular_ngon(n=8, id=w, realign=true);

      // spine 
      if (spine) {
        translate([-w / 2, 0, chamfer_h])
          linear_extrude(height=middle_h)
            square(edge, anchor=RIGHT + CENTER);

        translate([-w / 2, 0, chamfer_h])
          linear_extrude(height=edge)
            square([edge * 2, edge], anchor=RIGHT + CENTER);
      }

      // top bevel
      linear_extrude(height=chamfer_h + 0.01, scale=w / tip_w)
        regular_ngon(n=8, id=tip_w, realign=true);
    }
}

// Driver pins (in the shell)
module driver_pins(pin_n = 4) {
  for_pins(pin_n) {
    back(shell_inner_d / 2 + 0.2)
      rotate([-90, 0, 0])
        pin(h=driver_pin_l, w=pin_s - 0.4, tip_w=pin_s / 2);
  }
}

// Key pins (in the plug)
module key_pins(code = [false, true, true, false]) {
  for (i = [1:4]) {
    up((plug_l / 5) * i)
      back(plug_d / 2)
        rotate([90, 0, 0])
        // determine the pin travel.
        let (travel = code[i - 1] ? sm_pin_travel_l : lg_pin_travel_l) {
          pin(h=travel + key_pin_hole_l + sm_pin_travel_l, w=pin_s - 0.4, tip_w=pin_s / 2);
        }
  }
}

// Points for the key's pin cuts
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

// The key
module key(code = [false, true, true, false]) {
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
                  pts(code),
                  [
                    [key_l, 0],
                  ]
                )
              ) {
                back(key_hole_pin_bar_h)
                  polygon(points=points);
              }
            }
      }
}

/*
TODO:
- [x] square off the tops to the fins to be hexagons, to hold the pins in and be better shear lines
- [x] cut a square channel behind each pin slot. this will help hold the pin in place, and stop them from falling
	- [x] widen chamber to fit slots
- [x] add a small square to the spine of the key pins, to fit in the slot. the spine should get extra tall at the bottom, so it can be held in place
- somehow lock with the spine so that the pins don't slip out the front
- add a hole and square to the plug, such that when inserted it locks the key pins from falling out. this hole should not go all the way through the plug so it is not visible from the front
- add a 5th driver pin/slot to act as a "retainer pin".
	- this should have a printed spring to keep it pressed down.
	- add a hole in the bottom of the shell to access this pin with a tool, to pull it up and allow the plug to be removed
	- the shell and plug should otherwise be fully enclosed around the retainer pin.
	- add a cutout in the plug to allow this pin to hold it in place. this should only extend 45 degrees, so it stop over-rotation forwards, or any rotation backwards.
- make the travel a little more dramatic
- also square off the bottoms of the pin holes to be hexagons. This will require some math.
- attempt to simplify the params by deriving from the plug instead of the key.
*/

key_code = [true, false, true, false];
pin_n = len(key_code);

color("yellow") plug(pin_n=pin_n);
color("green") lock_shell(pin_n=pin_n);
color("blue") driver_pins(pin_n=pin_n);
color("red") key_pins(code=key_code);
down(25)
  color("gray") key(code=key_code);
