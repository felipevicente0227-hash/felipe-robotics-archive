#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebServer.h>

// ESP32 Wi-Fi network name and password
#define WIFI_SSID "any user name"
#define WIFI_PASSWORD "any password"

// Brushless ESC and servo pins
#define PIN_ESC 32
#define PIN_SERV 33

// Failsafe: if no message arrives from the phone for this long,
// the throttle is cut to zero. The web page sends a heartbeat every
// 300 ms, so this only triggers on a real disconnect.
#define FAILSAFE_TIMEOUT_MS 1000

Servo esc;
Servo servo;
WebServer server(80);

// ---------- ESC ----------
// ESC value received from the web interface (0 = motor off)
int escweb = 0;

// ---------- SERVO ----------
// Servo value received from the web interface (90 = rudder centered)
int servoweb = 90;

// ---------- FAILSAFE ----------
unsigned long lastContactMs = 0; // last time we heard from the client
bool linkActive = false; // true once a client has connected

// Web page (HTML)
const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brushless and Servo Control</title>
<style>
body {
font-family: Arial;
text-align: center;
margin: 0;
padding: 20px;
}
h2 { margin-bottom: 20px; }
.value { font-weight: bold; font-size: 1.3em; }

.control-block {
margin: 25px auto;
max-width: 500px;
}
.slider {
width: 90%;
height: 40px;
}
</style>
<script>
function updateESC(value) {
document.getElementById("escweb").innerText = value;
fetch("/set?device=esc&val=" + value);
}
function updateServo(value) {
document.getElementById("servoweb").innerText = value;
fetch("/set?device=servo&val=" + value);
}
// Heartbeat: tell the hovercraft we are still connected.
// If these stop arriving (phone left the network, browser
// closed), the failsafe cuts the motor within one second.
setInterval(function () {
fetch("/ping").catch(function () {});
}, 300);
</script>
</head>
<body>
<h2>Brushless and Servo Control</h2>

<div class="control-block">
<h3>Brushless Motor</h3>
<input type="range" min="0" max="180" value="0" class="slider"
oninput="updateESC(this.value)">
<div>Value: <span id="escweb" class="value">0</span></div>
</div>

<div class="control-block">
<h3>Servo</h3>
<input type="range" min="45" max="135" value="90" class="slider"
oninput="updateServo(this.value)">
<div>Value: <span id="servoweb" class="value">90</span></div>
</div>

</body>
</html>
)rawliteral";

void markContact() {
lastContactMs = millis();
linkActive = true;
}

void handleRoot() {
markContact();
server.send(200, "text/html", index_html);
}

void handlePing() {
// Heartbeat from the web page; refreshes the failsafe timer.
markContact();
server.send(200, "text/plain", "OK");
}

void handleNotFound() {
server.send(404, "text/plain", "Not found");
}

void handleSet() {
String device = server.arg("device"); // "servo" or "esc"
String valStr = server.arg("val");

markContact();

if (valStr.length() == 0) {
server.send(400, "text/plain", "Missing 'val' parameter");
return;
}

int newValue = valStr.toInt();

if (device == "esc") {
// Store the ESC value
escweb = constrain(newValue, 0, 180);
server.send(200, "text/plain", "OK");
}
else if (device == "servo") {
// Store the servo value
servoweb = constrain(newValue, 45, 135);
server.send(200, "text/plain", "OK");
}
else {
server.send(400, "text/plain", "Invalid device. Use 'esc' or 'servo'");
}
}

void setup() {
Serial.begin(115200);

// Attach ESC (minimum and maximum pulse widths in microseconds)
esc.attach(PIN_ESC, 1000, 2000);
servo.attach(PIN_SERV);

// Initialize ESC and servo positions (motor off, rudder centered)
esc.write(escweb);
servo.write(servoweb);

// -------- Wi-Fi Access Point Setup --------
WiFi.mode(WIFI_AP);
WiFi.softAP(WIFI_SSID, WIFI_PASSWORD); // Create its own Wi-Fi network

IPAddress apIP = WiFi.softAPIP(); // Assign the access point IP address
Serial.print("Access point IP: ");
Serial.println(apIP);

// Serve the web page when a client requests the root URL
server.on("/", handleRoot);

// Receive slider values and store them
server.on("/set", handleSet);

// Heartbeat endpoint for the failsafe
server.on("/ping", handlePing);

server.onNotFound(handleNotFound);

server.begin();
Serial.println("Web server started");
}

void loop() {
// Check for incoming HTTP client requests
server.handleClient();

// -------- Failsafe --------
// If the phone disconnects mid-flight, the last throttle value
// would otherwise be held forever. Cut the motor to zero if we
// haven't heard from the client within the timeout.
if (linkActive && (millis() - lastContactMs > FAILSAFE_TIMEOUT_MS)) {
escweb = 0;
linkActive = false;
Serial.println("Failsafe: connection lost, throttle cut to 0");
}

// Send the latest values to the ESC and servo
esc.write(escweb);
servo.write(servoweb);
}
