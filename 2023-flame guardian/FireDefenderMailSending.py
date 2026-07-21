from pystubit.board import display, Image, lightsensor
from pystubit_iot import *
import sys
import time

#wifi密碼與郵件帳密設定
WIFI_SSID = "ssid"  # Wi-Fi_SSID請修改
WIFI_PWD = "password"   #　Wi-Fi_password請修改
GMAIL_ADDR = "ecofirewatch@gmail.com" # GMail_帳號 請勿動
GMAIL_PWD = "nxnmfmtqbdoyuffl"  # GMail_密碼 請勿動
SEND_MAIL_ADDR = "oscarsaurs@gmail.com" #收信的郵件地址
SEND_MAIL_TITLE = "RPAtest"    #郵件主旨
SEND_MAIL_CONTENTS = "this ia a test letter, trail" #郵件內文
################################

# WiFi設定（SSID與連線密碼）
wifi_config(ssid=WIFI_SSID, pwd=WIFI_PWD)

#SMTP設定
smtp_config(username=GMAIL_ADDR, password=GMAIL_PWD)

#WiFi連線
if not wifi_connect():
    display.show('W')
    time.sleep(1)
    display.clear()
    sys.exit()

#初始設定
threshold = 500  #光感應器的閾値
prev_lv = lightsensor.get_value()

img = Image("00000:01110:01110:01110:00000", color=(10, 0, 0))

#程式開始
while True:
    #
    lv = lightsensor.get_value()  #現在的亮度
    diff = lv - prev_lv  #過去與現在的光感應器偵測值比較、變化量
    prev_lv = lv  #現在光感應器的值

    #變化量大於設定的閥值
    if diff > threshold:
        display.show(img)
        #呼叫發信的功能
        sendmail(SEND_MAIL_ADDR, SEND_MAIL_TITLE, SEND_MAIL_CONTENTS)
        display.clear()

    time.sleep(1)
