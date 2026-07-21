#include <Servo.h>

const int buttonPin = 13;
const int photoresistorPin = A0;

Servo myServo;

bool detecting = false;
bool at90 = false;
int lastButtonState = HIGH;

int threshold = 320;

unsigned long startTime = 0;
unsigned long ignoreUntil = 0;

void setup() {
  Serial.begin(115200); // faster serial speed

  pinMode(buttonPin, INPUT_PULLUP);

  myServo.attach(10);
  myServo.write(0);
}

void loop() {
  int buttonState = digitalRead(buttonPin);

  // Button press
  if (lastButtonState == HIGH && buttonState == LOW) {

    detecting = !detecting;
    at90 = !at90;

    // Move servo
    myServo.write(at90 ? 90 : 50);

    if (detecting) {
      startTime = micros();
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
    Serial.print(elapsed / 1000000.0, 6);

    Serial.print(" s   Light: ");
    Serial.println(light);

    // stop after ignore period
    if (currentTime > ignoreUntil && light < threshold) {

      detecting = false;

      Serial.println("Stopped: light below threshold");

      Serial.print("Final Time: ");
      Serial.print(elapsed / 1000000.0, 6);
      Serial.println(" s");
    }
  }

}