# Felipe Robotics Archive

Robotics and embedded-systems projects, 2020–2026: international competition robots, a self-built experimental physics apparatus, and embedded control systems. Built across Taiwan, Japan, Korea, Australia, and Spain.

**About this archive.** I build physical systems and debug them until they work: sensor-driven robots, microcontroller timing systems, and electromechanical builds. My recent work centers on measurement and systematic-error analysis (Arduino photogate investigation, 2026) and embedded integration (ESP32 hovercraft, UPM Madrid, 2026). Earlier competition projects (2020–2023) document the progression from guided sensor/DC-motor builds to independently designed and coded robots.

## Engineering Progression

| Year | Project | Main engineering area | Evidence in repo |
|------|---------|----------------------|------------------|
| 2026 | Arduino Photogate — g measurement | Experimental design, systematic error analysis, embedded timing | Raw data (45 trials), source code, results summary, follow-up analysis, video |
| 2026 | ESP32 Hovercraft (UPM Madrid) | Embedded networking, ESC/servo integration, assembly | Code, CAD, videos, camp reference repo |
| 2024 | Humanoid Hand (incomplete) | Servo control, guided ML build | Photos, video |
| 2023 | Flame Guardian | Camera-based detection, IoT alerting | Detection model, alert code, demo video (YouTube) |
| 2023 | URC Australia — Mechanical Crank (1st place) | Mechanical design, threshold tuning | Design files, photos |
| 2021 | Korea RoboSTEAM — Patient Transfer (1st place) | Line-tracing algorithms, route strategy | Design files, videos, photos |
| 2020 | Japan — Light Adventurer (1st place) | Sensor zoning concept, DC motor control | Photos, video |

---

##  Flagship: [Arduino Photogate — Measuring g and Diagnosing Systematic Timing Error (2026)](photogate-free-fall/)

**Fully solo project** (IB Physics Internal Assessment): designed, built, coded, and analyzed over ~3 months of near-daily lab sessions.

A servo-release + LDR photogate free-fall rig, timed by an Arduino at microsecond resolution. Rather than a single measurement, the investigation used release height (20–100 cm, 9 heights × 5 trials) as a **diagnostic variable** to expose a systematic timing error.

**Key results:**
- Naive model (x = ½gt²): g = 8.46 m/s² — 13.8% below accepted value despite r² = 0.999
- Corrected model (t = √(2x/g) + Δt, from inspecting my own control code): **g = 9.14 ± 0.16 m/s², r² = 0.9995** (6.8% difference)
- The systematic delay was traced to a specific design decision: one button press both starts the µs timer and commands the servo release, so every trial includes the servo's rotation time
- Delay quantified two independent ways: **28 ms** (regression intercept) vs **40 ± 3.6 ms** (comparison against SUVAT-predicted times) — consistent order of magnitude from different assumptions

**What I would change:** log the servo's actual release moment via a limit switch to separate mechanical delay from LDR detection lag; replace the shared start signal with a break-beam at the release point, removing the offset at its source.

 Raw data, source code, results summary, and follow-up analysis in the [`photogate-free-fall`](photogate-free-fall/) folder. (Full report to be added after IB submission.)

---

##  [ESP32 Hovercraft — UPM Madrid Summer Camp (2026)](esp32-hovercraft-upm/)

Phone-controlled hovercraft: the ESP32 broadcasts its own Wi-Fi access point and serves a control page — thrust slider drives a brushless motor through an ESC (0–180 mapped to 1000–2000 µs pulses); steering drives a rudder servo (software-limited 45°–135°).

**My role & attribution:** Built at ETSII UPM's summer camp under instructor guidance ([camp reference repo](https://github.com/JaimeBravoAlgaba/campamento_verano_ETSII_2026)). The Wi-Fi/web framework was instructor-provided as a starter template; I completed the ESC and servo integration (pin config, pulse-width setup, control loop), and led the physical design, assembly, ESC calibration, and flight tuning within my team. Our team's own CAD variants remained on camp laptops; the archived CAD files are the camp reference designs.

---

##  [Flame Guardian (2023)](2023-flame%20guardian/)

Wildfire detection and alert system: camera-based fire detection triggering automatic email alerts with location data, designed for remote assessment and response via a web interface.

**My role:** Team of four. I led research, wrote the code, built and assembled the hardware, and integrated and tested the fire-detection model. Kristy built the demonstration diorama; a third teammate wrote the research report.

**What survives in this repo vs. the original system:** the light-sensor email-alert module (`FireDefenderMailSending.py`), the detection model (`fire_detection.xml`), and a supporting script. The integrated competition system (camera pipeline + GPS tagging + web control) is documented in the [demo video](https://www.youtube.com/watch?v=Y2XW8qYtMfY) but its full code is not archived.

**Known limitations I'd fix today:** the sensor module detects brightness *change* (1 Hz sampling), not fire directly; SMTP sending blocks execution; no Wi-Fi retry logic; detection accuracy was never formally measured.

---

##  Competition Robots (2020–2023)

### [Korea RoboSTEAM 2021 — Autonomous Patient Transfer Robot (1st place)](2021%20Korea%20Champion%20-%20Autonomous%20Patient%20Transfer%20Robot/)
Line-following robot that locates colored blocks (representing patients) and delivers each to its matching zone.
**My role:** Largely solo — pandemic restrictions meant near-daily individual lab sessions. I built the robot and wrote the tracing code, including escape functions for recovery and route strategy optimized for time-based scoring. The hardest part was tuning: the robot doesn't learn, so behavior was refined through repeated simulated runs and threshold iteration.

### [URC Australia, September 2023 — Mechanical Crank System (1st place)](2023%20Australia%20Champion%20-%20Mechanical%20Crank%20System/)
Rebuild campaign after losing at Osaka 2023 earlier that summer.
**My role:** I designed and built the new robot, wrote roughly half the code, and did all threshold tuning and testing; my teammate wrote the remaining functions.

### [Japan 2020 — Light Adventurer (1st place)](2020%20Japan%20Champion%20-%20Automatic%20Plant%20Watering%20Robot/)
A robot that moves a plant toward optimal light, then waters it automatically.
**My role:** I proposed the concept and the core sensing idea — splitting a servo's 180° sweep into three 60° zones and comparing light readings to pick a direction. My teacher taught me the implementation, building the code with me line-by-line; I did most of the physical build. Included here as the starting point of the progression, not as evidence of current ability.

---

##  [Humanoid Hand (2024, incomplete)](humanoid-hand/)

Guided self-taught build of a sensor-mimicking humanoid hand from an online tutorial. Left incomplete when I moved to Spain — archived honestly as such.

## License
MIT — see [LICENSE](LICENSE).
