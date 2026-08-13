# Flame Guardian (2023)

Fire detection system in two independent halves:

- **`fireDetect`** — runs on a laptop, watches a webcam with an OpenCV Haar cascade, draws a box around detected flame and sounds an alarm.
- **`FireDefenderMailSending.py`** — runs standalone on a Studuino:bit board, watches the on-board light sensor and sends a Gmail alert when the light level jumps.

The full competition build also included GPS location tagging, on-site image capture, and automatic extinguishing triggered through a web-based servo control interface — all demonstrated working at the time (see the servo-control webpage in the project demo). That code was never archived and no longer exists; only the two scripts above survive in this repo, and they don't communicate with each other (see Tested conditions & limitations below).

`fire_detection.xml` is the pre-trained Haar cascade used by the camera half.

## Running it

The camera half needs `opencv-python` and `pygame`, and must be run from inside this folder (it loads `fire_detection.xml` by relative path). The board half reads its wi-fi and Gmail credentials from environment variables — `WIFI_SSID`, `WIFI_PWD`, `GMAIL_ADDR`, `GMAIL_PWD`, `SEND_MAIL_ADDR` — so that no credentials live in this repo. `GMAIL_PWD` must be a Gmail App Password; with 2FA enabled Google rejects a plain account password over SMTP.

## Tested conditions & limitations

Everything in the **verifiable** list is read directly from the source in this folder. Everything after it is a real-world result that was never recorded.

**Verifiable from the code:**

- The two surviving halves never communicate. The camera half sounds an alarm but sends no email; the board half sends email but sees no camera. There is no combined mode in the code that remains in this repo.
- The board half triggers on the *change* in light level between one-second samples, not the absolute level — a jump greater than `threshold = 500` raw units. Consequences: a fire already burning when the script starts is never reported, and a fire that brightens gradually over more than a second may never produce a large enough single-sample jump.
- Sampling is 1 Hz, and `sendmail` blocks for the duration of the SMTP exchange, so detections during a send are missed.
- If wi-fi fails to connect the board shows `W` and exits — it does not retry.
- The camera half loads `audio.wav` (the alarm sound, committed alongside the script) by relative path, so it must be run from inside this folder or it will fail at startup.
- On each detection the camera half plays the alarm and sleeps 1 second, blocking the capture loop, so frames are dropped for as long as flame stays in view.
- The camera half never calls `cap.release()` or `cv2.destroyAllWindows()`; the webcam is freed only when the process exits.
- Haar cascade parameters are `scaleFactor 1.2`, `minNeighbors 5` — the false-alarm trade-off dial. It uses the default webcam (index 0).

**Not recorded anywhere in this repo:**

Detection distance, flame size and type, and the lighting conditions used in testing were not recorded at the time. Detection rate, miss rate and false-positive rate were never formally measured — the system was demonstrated rather than characterised, so there is no trial count to quote. Whether an alert email was confirmed to arrive end to end is not recorded either. The board is a Studuino:bit, identified from the `pystubit` imports; its firmware version was not noted. The GPS tagging, image capture, and servo-based extinguishing control shown in the competition demo video are not represented by any surviving code in this repo.
