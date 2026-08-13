from pystubit.board import display, Image, lightsensor
from pystubit_iot import *
import sys
import os
import time

# Wi-Fi and mail account settings — real values come from environment variables, never commit them
WIFI_SSID = os.environ.get("WIFI_SSID", "ssid")
WIFI_PWD = os.environ.get("WIFI_PWD", "password")
GMAIL_ADDR = os.environ.get("GMAIL_ADDR", "your_gmail_address_here")
GMAIL_PWD = os.environ.get("GMAIL_PWD", "your_app_password_here")
SEND_MAIL_ADDR = os.environ.get("SEND_MAIL_ADDR", "example@example.com")
SEND_MAIL_TITLE = "Flame Guardian - Fire Alert"
SEND_MAIL_CONTENTS = "Possible fire detected. Please check the monitoring interface."
################################

wifi_config(ssid=WIFI_SSID, pwd=WIFI_PWD)
smtp_config(username=GMAIL_ADDR, password=GMAIL_PWD)

if not wifi_connect():
    display.show('W')
    time.sleep(1)
    display.clear()
    sys.exit()

# Light sensor threshold — fires on rapid brightness change
threshold = 500
prev_lv = lightsensor.get_value()

img = Image("00000:01110:01110:01110:00000", color=(10, 0, 0))

while True:
    lv = lightsensor.get_value()
    diff = lv - prev_lv
    prev_lv = lv

    if diff > threshold:
        display.show(img)
        sendmail(SEND_MAIL_ADDR, SEND_MAIL_TITLE, SEND_MAIL_CONTENTS)
        display.clear()

    time.sleep(1)
