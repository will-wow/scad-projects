include <Round-Anything/polyround.scad>

boxWidth = 10;
boxW = boxWidth / 2;
boxRadius = 0.4;
boxHeight = 4;


boxPoints = [
  [-boxW, -boxW, boxRadius],
  [boxW, -boxW, boxRadius],
  [boxW, boxW, boxRadius],
  [-boxW, boxW, boxRadius],
];
polyRoundExtrude(boxPoints, boxHeight, boxRadius, boxRadius, fn=10);

wrappingWidth = 2;
wrappingLength = boxWidth + 0.4;
wrappingHeight = boxHeight + 0.2;

verticalWrappingPoints = [
  [-wrappingWidth / 2, -wrappingLength / 2, boxRadius],
  [wrappingWidth / 2, -wrappingLength / 2, boxRadius],
  [wrappingWidth / 2, wrappingLength / 2, boxRadius],
  [-wrappingWidth / 2, wrappingLength / 2, boxRadius],
];
polyRoundExtrude(verticalWrappingPoints, wrappingHeight, boxRadius, boxRadius, fn=10);

hWrappingPoints = [
  [-wrappingLength / 2, -wrappingWidth / 2, boxRadius],
  [wrappingLength / 2, -wrappingWidth / 2, boxRadius],
  [wrappingLength / 2, wrappingWidth / 2, boxRadius],
  [-wrappingLength / 2, wrappingWidth / 2, boxRadius],
];
polyRoundExtrude(hWrappingPoints, wrappingHeight, boxRadius, boxRadius, fn=10);

ribbonW = 3;
ribbonH = 3;
ribbonInnerH = 0.8;
ribbonInnerW = 1;
ribbonKnotH = 1.6;

ribbonPts = [
  // Left side
  [-ribbonInnerW, ribbonKnotH, boxRadius],
  [-ribbonInnerW, ribbonInnerH, boxRadius],
  [-ribbonW, ribbonH, boxRadius],
  [-ribbonW, -ribbonH, boxRadius],
  [-ribbonInnerW, -ribbonInnerH, boxRadius],
  [-ribbonInnerW, -ribbonKnotH, boxRadius],
  // Right side
  [ribbonInnerW, -ribbonKnotH, boxRadius],
  [ribbonInnerW, -ribbonInnerH, boxRadius],
  [ribbonW, -ribbonH, boxRadius],
  [ribbonW, ribbonH, boxRadius],
  [ribbonInnerW, ribbonInnerH, boxRadius],
  [ribbonInnerW, ribbonKnotH, boxRadius],
];

rotate([0, 0, 45])
  polyRoundExtrude(ribbonPts, wrappingHeight + 0.2, boxRadius, boxRadius, fn=10);

top = sqrt(boxW * boxW + boxW * boxW);

hangerW = 1;
hangerH = 3;

hangerPoints = [
  [-hangerW, -hangerH, 0],
  [-hangerW, hangerH, hangerW],
  [hangerW, hangerH, hangerW],
  [hangerW, -hangerH, 0],
];

holeWidth = 1.5;

rotate([0, 0, 45])
  translate([0, top, 0])
    difference() {
      polyRoundExtrude(hangerPoints, boxHeight, boxRadius, boxRadius, fn=50);

      translate([0, 0, boxHeight / 2])
        translate([0, hangerH/3, 0])
          rotate([45, 0, 0])
            rotate([0, 90, 0])
              cube([holeWidth, holeWidth, hangerW * 2 + 1], center=true);
    }
