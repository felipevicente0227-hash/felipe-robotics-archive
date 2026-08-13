// Photogate timer for a free-fall experiment (IB Physics IA).
//
// A servo holds a ball at the top of the drop. Pressing the button releases the
// ball and starts a timer in the same instant, so the timer measures the true
// fall time rather than a human's reaction to seeing the ball move. The ball
// falling past a photoresistor at the bottom casts a shadow, which stops the
// timer. Elapsed time is printed over serial for the g calculation.
//
// Timing is done in micros() rather than millis() because a ~0.5 s drop needs
// resolution far finer than 1 ms to keep the uncertainty in g acceptable.

#include <Servo.h>

const int buttonPin = 13;
const int photoresistorPin = A0; // analog: the gate reads a light *level*, not a digital edge

Servo myServo;

bool detecting = false;   // timer currently running
bool at90 = false;        // servo gate position: true = 90 (open), false = 50 (holding)
int lastButtonState = HIGH; // HIGH = released, because the button uses INPUT_PULLUP

// Light level below which the ball is considered to have passed the gate.
// Set from the raw analogRead values observed on the bench: well under the
// ambient reading, well above the reading with the ball blocking the sensor,
// so ordinary room-light flicker cannot trip it. Re-tune this if the lamp or
// the room changes.
int threshold = 320;

unsigned long startTime = 0;   // micros() at release
unsigned long ignoreUntil = 0; // blanking deadline; see below

void setup() {
  Serial.begin(115200); // faster serial speed

  // INPUT_PULLUP uses the internal resistor, so the button wires straight to
  // ground with no external pull-up on the breadboard. This is why the logic
  // below is inverted (pressed = LOW).
  pinMode(buttonPin, INPUT_PULLUP);

  myServo.attach(10);
  myServo.write(0);
}

void loop() {
  int buttonState = digitalRead(buttonPin);

  // Button press
  // Edge-triggered on HIGH->LOW: fires once on the press instead of
  // continuously for as long as the button is held down.
  if (lastButtonState == HIGH && buttonState == LOW) {

    detecting = !detecting;
    at90 = !at90;

    // Move servo
    // Releasing the ball and starting the clock happen in the same button
    // press, which is the whole point - it removes human reaction time from
    // the measurement.
    myServo.write(at90 ? 90 : 50);

    if (detecting) {
      startTime = micros();
      // Blanking window: ignore the photoresistor for the first 200 ms after
      // release. The servo arm sweeps across the sensor's view on its way out
      // and would otherwise cast a shadow that stops the timer immediately.
      // 200 ms comfortably outlasts the servo travel while still being far
      // shorter than the drop itself.
      ignoreUntil = micros() + 200000UL;

      Serial.println("Timer started");
    }
    else {
      Serial.println("Timer stopped");
    }
  }

  lastButtonState = buttonState;

  if (detecting) {

    unsigned long currentTime = micros();
    unsigned long elapsed = currentTime - startTime;

    int light = analogRead(photoresistorPin);

    Serial.print("Time: ");

    // convert microseconds to seconds
    // 6 decimal places: printing fewer would throw away the microsecond
    // resolution the whole timing approach exists to get.
    Serial.print(elapsed / 1000000.0, 6);

    Serial.print(" s   Light: ");
    Serial.println(light);

    // stop after ignore period
    // Both conditions matter: the blanking window must have expired *and* the
    // light must have dropped, otherwise the servo's own shadow ends the run.
    if (currentTime > ignoreUntil && light < threshold) {

      detecting = false;

      Serial.println("Stopped: light below threshold");

      // The number the experiment actually wants. Everything printed above is
      // a live trace for confirming the gate saw a clean single shadow.
      Serial.print("Final Time: ");
      Serial.print(elapsed / 1000000.0, 6);
      Serial.println(" s");
    }
  }

}
