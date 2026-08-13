# ESP32 Hovercraft

A wi-fi controlled hovercraft built around an ESP32. The board broadcasts its own wi-fi access point and serves a control webpage — any phone that joins the network gets two sliders: one for thrust, one for steering. No app, no RC receiver, no pairing. The hovercraft is the network.

Origin & attribution: Built at ETSII UPM's summer camp under instructor guidance (camp reference repo). The Wi-Fi/web framework came as an instructor starter template; I completed the ESC and servo integration and led my team's physical design, assembly, calibration, and flight tuning. Our team's own CAD variants stayed on camp laptops — the .f3d files archived here are the camp's reference designs.

Built July 2026. Videos: hoverboard1.mp4, hoverboard2.mp4.

## How it works

The ESP32 runs in access-point mode (WiFi.softAP) and hosts a web server on port 80.

The served page has two sliders. Moving a slider sends `GET /set?device=esc&val=N` (or `device=servo`) to the board.

- Thrust: the value (0–180) drives a brushless motor through an ESC attached with 1000–2000 µs pulse widths.
- Steering: the value turns a rudder servo, constrained in software to 45°–135° so it can never slam past its physical limits.
- Failsafe: the web page sends a heartbeat ping every 300 ms. If the board hears nothing for 1 second (phone left the network, browser closed), the throttle is cut to zero automatically. Without this, a dropped connection would hold the motor at its last value forever.

## Hardware

| Part | Role |
|---|---|
| ESP32 dev board | Wi-fi access point + web server + control |
| Brushless motor + ESC | Thrust (ESC signal on GPIO 32) |
| Rudder servo | Steering (signal on GPIO 33) |
| LiPo battery | Power for ESC/motor; ESP32 powered per your setup |

## 3D-printed parts (Fusion 360)

All parts designed in Fusion 360 and 3D printed (.f3d source files in this repo):

- redirigir_aire.f3d — air-redirect duct
- soporterbrushless.f3d — brushless motor mount
- tubo.f3d — thrust tube
- timonV2.f3d — rudder (the camp's second-revision reference design)

## Setup

1. Open ESP_hovercraft.ino in the Arduino IDE with the ESP32 board package and the ESP32Servo library installed.
2. Set WIFI_SSID and WIFI_PASSWORD to whatever you want the hovercraft's network to be called.
3. Flash the board. Open the serial monitor at 115200 baud to see the access point IP (default 192.168.4.1).
4. On your phone, join the hovercraft's wi-fi network, open a browser, and go to the IP address. Slide to fly.

## Safety notes

- The throttle slider starts at 0 and the ESC arms at 0 on boot — but always treat a powered brushless motor as live. Keep fingers and loose clothing away from the fan.
- The failsafe cuts thrust on disconnect, but it does not brake the hovercraft; it will coast.
- Test with the propeller removed first when changing the code.

## Tested conditions & limitations

Everything in the **verifiable** list is read directly from `ESP_hovercraft.ino`. The second list is what has not been measured yet.

**Verifiable from the code:**

- Failsafe: the throttle is cut to zero after **1 second** without a heartbeat (`FAILSAFE_TIMEOUT_MS 1000`), with the page pinging every 300 ms — so up to three pings can be lost before it trips.
- After the failsafe fires it clears the link flag, so thrust stays at zero until the page reconnects and the slider is moved again. It does not resume on its own.
- The failsafe cuts thrust only. The rudder holds its last angle, and the hovercraft coasts rather than braking.
- Steering is constrained in software to **45°–135°**, so a malformed or out-of-range request cannot drive the rudder past its physical limits. Thrust is constrained to 0–180.
- The access point is open to anyone who joins the network and knows the IP: there is no authentication on `/set`, and traffic is plain HTTP. Anyone on the wi-fi can take control.
- **Not yet tested with two phones connected at once.** Nothing in the code arbitrates between clients, so the last request received wins and either phone's heartbeat keeps the failsafe from tripping for both.
- Control range is bounded by the ESP32's own access point, since the board makes the network rather than joining one.

**Not yet measured — the hardware remained at the UPM camp in Madrid and is no longer accessible, so these would require a rebuild:**

- Control range from the board — not yet measured
- Run time on a full battery, and the battery specification — not yet measured
- Total mass as flown — not yet measured
- Thrust value at which it lifts off the surface — not yet measured
- Failsafe behaviour in a real walk-away test, as opposed to on the bench — not yet recorded

Endurance beyond short demonstration runs was never characterised, and the two-client case noted above was never tested; with the hardware left behind at the camp, closing either gap would mean rebuilding the unit.
