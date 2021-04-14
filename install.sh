#!/bin/bash

set -euxo pipefail

sudo python3 -m pip install .

sudo cp raspi_monitor.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable raspi_monitor.service
sudo systemctl restart raspi_monitor.service
