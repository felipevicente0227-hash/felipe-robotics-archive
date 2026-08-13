# 2020 Japan Champion — Automatic Plant Watering Robot

Championship-winning robot that tracks a light source and waters a plant automatically. Built for a robotics competition in Japan, 2020.

This folder holds build photographs (August–December 2020) and a video demo. No source code was archived for this project.

## Files

- `automatic plant watering robot video demo.mp4` — the robot running end to end
- 10 build photographs documenting the mechanism and assembly

## Tested conditions & limitations

**Hardware disassembled — the behaviour described here is documented from the competition video and build photographs in this folder, not from a live re-test.** No source code was archived either.

Verifiable from the video: a servo-mounted light sensor sweeps 0°–180°, sampling three zones — left, front, and right — stored in the block code as variables `LA`, `FA`, and `RA`. The robot compares the three readings and drives toward whichever zone is brightest, then waters the plant automatically on arrival; watering duration is adjustable in the code. Two demonstration runs are shown, one with the light source to the right and one in front, and the robot reaches the correct zone both times.

Not recoverable: the controller platform, the specific light source used in testing, the watering mechanism's hardware, and the competition category it was entered under were never saved. No quantitative figures exist either — tracking range, response time, water volume per cycle, and reservoir run time were never measured, and the hardware no longer exists to measure them now.
