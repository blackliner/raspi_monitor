#!/usr/bin/env python3

import sys
import os
import argparse
import psutil
import time
import subprocess
import logging
import json
import paho.mqtt.client as mqtt
from math import log10, floor
from datetime import datetime

round_to_n = lambda x, n: 0 if x == 0 else round(float(x), -int(floor(log10(x))) + (n - 1))


def read_thermal_zone(thermal_zone_path):
    with open(thermal_zone_path) as f:
        line = f.readline()
        return int(line.strip()) / 1000.0


def read_cpu_temp():
    temperatures = {}

    thermal_zone_base_path = "/sys/class/thermal"
    for zone_name in sorted(os.listdir(thermal_zone_base_path)):
        temperature_path = os.path.join(thermal_zone_base_path, zone_name, "temp")
        if os.path.isfile(temperature_path):
            temperatures[zone_name] = read_thermal_zone(temperature_path)

    return temperatures


def read_cpu_speed():
    speed = subprocess.check_output(["vcgencmd", "measure_clock", "arm"]).decode("utf-8")[14:]
    return round(int(speed) / 1000000)


def get_throttled():
    def _check_bit(data, position):
        return int(bool(data & 2**position))
        
    """
    Bit     Hex value   Meaning
    0       1           Under-voltage detected
    1       2           Arm frequency capped
    2       4           Currently throttled
    3       8           Soft temperature limit active
    16      10000       Under-voltage has occurred
    17      20000       Arm frequency capping has occurred
    18      40000       Throttling has occurred
    19      80000       Soft temperature limit has occurred
    """
    raw_data = subprocess.check_output(["vcgencmd", "get_throttled"]).decode("utf-8").strip()
    data = int(raw_data[10:], 0)
    return {
        "Under-voltage detected": _check_bit(data, 0),
        "Arm frequency capped": _check_bit(data, 1),
        "Currently throttled": _check_bit(data, 2),
        "Soft temperature limit active": _check_bit(data, 3),
        "Under-voltage has occurred": _check_bit(data, 16),
        "Arm frequency capping has occurred": _check_bit(data, 17),
        "Throttling has occurred": _check_bit(data, 18),
        "Soft temperature limit has occurred": _check_bit(data, 19),
    }


def main():
    parser = argparse.ArgumentParser(description="Raspberry PI system monitoring to mqtt")
    parser.add_argument("-v", "--verbose", help="Verbose output", action="store_true")
    parser.add_argument("-o", "--offline", help="Offline mode", action="store_true")
    args = parser.parse_args()
    lvl = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=lvl)

    mqtt_client = mqtt.Client()

    def mqtt_connect():
        try:
            mqtt_client.connect(host="ubuntu-server-new")
            logging.info("mqtt broker available")
            return True
        except:
            logging.info("mqtt broker not available")
            return False

    mqtt_connected = mqtt_connect()

    while True:

        message = {}

        message["cpu"] = {
            "temp": read_cpu_temp()["thermal_zone0"],
            "util": psutil.cpu_percent(),
            "speed": read_cpu_speed(),
        }

        message["ram"] = {
            "util": psutil.virtual_memory().percent,
        }

        message.update(get_throttled())

        logging.info(message)

        if not args.offline:
            if mqtt_connected:
                try:
                    mqtt_client.publish("sensors/battery", json.dumps(message))
                except:
                    logging.warning("mqtt connection lost. Reconnecting ...")
                    mqtt_connected = mqtt_connect()
            else:
                logging.warning("Connecting to mqtt ...")
                mqtt_connected = mqtt_connect()

        time.sleep(1)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("CTRL + C: Shuting Down")
