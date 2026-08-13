# Arduino Photogate: Measuring g and Diagnosing Systematic Timing Error

**Solo project** — designed, built, coded, and analyzed independently (IB Physics Internal Assessment, 2026). ~3 months of near-daily lab sessions.

## The question
Not just "measure g" — the investigation used release height as a **diagnostic variable**: if a fixed timing delay exists in the apparatus, it should distort short falls more than long ones. Varying height turns a nuisance error into something measurable.

## The apparatus
- Servo-controlled release arm at the top of a vertical stand
- Single LDR photogate above a catcher, read on Arduino analog pin A0 (threshold: 320/1023)
- One button press releases the sphere AND starts a microsecond timer (`micros()`)
- 200 ms ignore window after release, because the servo's own motion was found to disturb the light reading during preliminary testing
- Same metal sphere for all trials; heights 20–100 cm in 10 cm steps, 5 trials each (45 measurements)

## Key results
| Model | g (m/s²) | vs 9.81 | r² |
|---|---|---|---|
| Naive x = ½gt² | 8.46 | −13.8% | 0.9992 |
| Corrected t = √(2x/g) + Δt | **9.14 ± 0.16** | −6.8% | 0.9995 |

The corrected model came from **reading my own control code**: the timer starts at the button press, but the sphere only falls once the servo finishes rotating — so a fixed delay is added to *t*, not *t²*.

The delay was quantified two independent ways:
- **28 ms** — intercept of the t vs √x regression (no assumption about g)
- **40 ± 3.6 ms** — mean gap between measured times and SUVAT predictions (assumes g = 9.81)

Same order of magnitude from different assumptions → real, fixed offset.

## What went wrong along the way
- The servo's motion falsely triggered the LDR immediately after release → added the 200 ms ignore window
- Early trials showed derived g *rising* with height (7.16 → 8.23 m/s²) under the naive model — initially confusing, eventually the key clue that the error was a fixed additive delay

## Follow-up analysis
See [FOLLOWUP.md](FOLLOWUP.md): applying the correction flattens the per-height g values completely (σ = 0.09 m/s²), confirming the diagnosis — and reveals a residual ~6.8% systematic error the additive-delay model does not explain.

## What I would change (V2)
- Break-beam at the release point so timing starts when the fall actually starts — removing the offset at its source
- Log the servo's completion moment (limit switch / feedback pin) to separate mechanical delay from LDR lag
- More trials at 20–40 cm, where the offset is proportionally largest and most diagnostic

## Tested conditions & limitations

**Uncertainty:** timer resolution is negligible against the trial-to-trial spread. The dominant error was not random but systematic: the 28 ms to 40 ± 3.6 ms servo release delay described above.

**Verifiable from the code:**

- Timing uses `micros()` and is printed to 6 decimal places — chosen because a sub-second drop needs far finer resolution than `millis()` gives.
- `threshold = 320` is a raw `analogRead` value, calibrated against one specific lamp and room. It is not adaptive: move the rig to different ambient lighting and this must be re-tuned or the gate will either trip immediately or never trip.
- A 200 ms blanking window (`ignoreUntil`) after release ignores the photoresistor, because the servo arm sweeps through the sensor's view on its way out. Any drop that completes in under 200 ms therefore cannot be measured.
- The comparison `currentTime > ignoreUntil` is a direct unsigned comparison rather than a rollover-safe subtraction. `micros()` wraps roughly every 71 minutes of board uptime, so a run started near the wrap point can blank incorrectly. Power-cycling between sessions avoids this.
- Only one gate is present, so the device measures total time from release to the gate. It cannot measure instantaneous velocity or acceleration directly — those come from the drop height, which the sketch never knows.
- The sketch prints a serial line on every loop iteration while timing. At 115200 baud these writes block once the buffer fills, so the photoresistor sampling interval is bounded by serial throughput, not by the loop itself. This adds jitter to when the shadow is actually noticed.
- After a run auto-stops, the servo gate position and the timer state are tracked by two separate flags that are only toggled together on a button press — so the gate can end up in the opposite position from the one the next run expects. See "Known issue" below.

**Known issue (documented, not fixed):** `detecting` is cleared automatically when the ball is detected, but `at90` is not. The next button press therefore moves the servo to 50° instead of 90° while starting a new timing run, so the gate needs an extra press to resynchronise.

**Not measured:** the residual ~6.8% gap between the corrected g and 9.81 m/s² is unexplained by the additive-delay model. Separating LDR detection lag from height-measurement bias needs the V2 hardware changes above; neither was measured here.

## Files
- `final_project_code.ino` — release + timing code
- `raw_data.csv` — all 45 trial times
- `felipe 2026 physics ia free fall experiment using arduino.mp4` — video of the experiment running
- `FOLLOWUP.md` + `photogate_correction_followup.png` — post-IA correction analysis
- `generate_figure.py` — reproduces the figure from the data
- Full IA report: added after IB submission (academic integrity)

## TODO
- [ ] Apparatus photo at top
- [ ] t vs √x regression graph
