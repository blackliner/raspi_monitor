#!/usr/bin/env python3

import lcddriver
import sys
import psutil
import time
import os
import subprocess
import logging
import json
import paho.mqtt.client as mqtt
from math import log10, floor
from epsolar_tracer.client import EPsolarTracerClient
from epsolar_tracer.enums.RegisterTypeEnum import RegisterTypeEnum
from datetime import datetime

DATA_CYCLE_TIME = 0.25
PAGE_CYCLE_TIME = 4

round_to_n = lambda x, n: 0 if x == 0 else round(float(x), -int(floor(log10(x))) + (n - 1))


def read_cpu_temp():
    return float(subprocess.check_output(["vcgencmd", "measure_temp"]).decode("utf-8")[5:-5])


def read_cpu_speed():
    speed = subprocess.check_output(["vcgencmd", "measure_clock", "arm"]).decode("utf-8")[14:]
    return round(int(speed) / 1000000)


ep_solar_client = EPsolarTracerClient(port="/dev/ttyUSB0")


def read_ep_solar():

    message = {}
    message["name"] = "ep_solar"

    message["pv"] = {}
    message["pv"]["u"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_INPUT_VOLTAGE).value
    message["pv"]["i"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_INPUT_CURRENT).value
    message["pv"]["p"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_INPUT_POWER).value

    message["battery"] = {}
    message["battery"]["u"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_OUTPUT_VOLTAGE).value
    message["battery"]["i"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_OUTPUT_CURRENT).value
    message["battery"]["p"] = ep_solar_client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_OUTPUT_POWER).value
    message["battery"]["soc"] = ep_solar_client.read_input(RegisterTypeEnum.BATTERY_SOC).value

    message["load"] = {}
    message["load"]["u"] = ep_solar_client.read_input(RegisterTypeEnum.DISCHARGING_EQUIPMENT_OUTPUT_VOLTAGE).value
    message["load"]["i"] = ep_solar_client.read_input(RegisterTypeEnum.DISCHARGING_EQUIPMENT_OUTPUT_CURRENT).value
    message["load"]["p"] = ep_solar_client.read_input(RegisterTypeEnum.DISCHARGING_EQUIPMENT_OUTPUT_POWER).value

    return message


def main():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))

        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(message)s",
            # handlers=[logging.FileHandler(os.path.join(script_dir, "lcd.log")), logging.StreamHandler(),],
            level=logging.INFO,
        )

        try:
            lcd = lcddriver.lcd()
        except:
            lcd = None

        def lcd_print(data, line):
            if lcd is not None:
                lcd.lcd_display_string(data.ljust(16), line)

        def ep_solar_connect():
            if ep_solar_client.connect():
                logging.info("LCD connected to /dev/ttyUSB0")
                lcd_print(f"Connectd to:", 1)
                lcd_print(f"/dev/ttyUSB0", 2)
                return True
            else:
                logging.warning("Error connecting to /dev/ttyUSB0")
                lcd_print(f"Error connecting:", 1)
                lcd_print(f"/dev/ttyUSB0", 2)
                time.sleep(1)
                return False

        ep_solar_connected = ep_solar_connect()

        time.sleep(1)

        mqtt_client = mqtt.Client()

        def mqtt_connect():
            try:
                mqtt_client.connect(host="ubuntu-server")
                logging.info("mqtt broker available")
                return True
            except:
                logging.info("mqtt broker not available")
                return False

        mqtt_connected = mqtt_connect()

        page = 0
        page_step = DATA_CYCLE_TIME / PAGE_CYCLE_TIME

        while True:

            data = []
            message = {}

            now = datetime.now()
            now_f = now.strftime("%H:%M:%S")
            # print(now_f)

            cpu_util = psutil.cpu_percent()
            # print(f"CPU: {cpu_util}%")

            cpu_temp = read_cpu_temp()
            cpu_speed = read_cpu_speed()

            ram_util = psutil.virtual_memory().percent
            # print(f"RAM: {ram_util}%")

            data.extend(
                [f"{now_f} C:{cpu_util}%", f"C: {cpu_temp}C {cpu_speed}MHz",]
            )

            if ep_solar_connected:
                try:
                    message = read_ep_solar()

                    data.extend(
                        [
                            f'P: {message["pv"]["i"]:.3}A {message["pv"]["u"]:.3}V',
                            f'P: {message["pv"]["p"]:.3}W',
                            f'B: {message["battery"]["i"]:.3}A {message["battery"]["u"]:.3}V',
                            f'B: {message["battery"]["p"]:.3}W {message["battery"]["soc"]}%',
                            f'L: {message["load"]["i"]:.3}A {message["load"]["u"]:.3}V',
                            f'L: {message["load"]["p"]:.3}W',
                        ]
                    )
                except:
                    logging.warning("ep_solar connection lost")
                    ep_solar_connected = ep_solar_connect()
            else:
                ep_solar_connected = ep_solar_connect()

            message["cpu"] = {
                "temp": cpu_temp,
                "util": cpu_util,
                "speed": cpu_speed,
            }

            message["ram"] = {
                "util": ram_util,
            }

            logging.info(message)

            if mqtt_connected:
                try:
                    mqtt_client.publish("sensors/battery", json.dumps(message))
                except:
                    logging.warning("mqtt connection lost")
                    mqtt_connected = mqtt_connect()
            else:
                mqtt_connected = mqtt_connect()

            page = (page + page_step) % (len(data) / 2)

            lcd_print(data[2 * int(page)], 1)
            lcd_print(data[2 * int(page) + 1], 2)

            time.sleep(DATA_CYCLE_TIME)

    except KeyboardInterrupt:
        ep_solar_client.close()
        print("Shuting Down")


if __name__ == "__main__":
    # execute only if run as a script
    sys.exit(main())
