Read system state (CPU/RAM util, CPU temp etc.) and publish to a mqtt topic.

For an automatic start:
- install this package to root with pip: `sudo python3 -m pip install .`
- place the raspi_monitor_init script to /etc/init.d/
- make sure its executable
- run `sudo update-rc.d raspi_monitor_init defaults`
- check status with `sudo service raspi_monitor_init status`

To upgrade the package:
- install this package to root with pip: `sudo python3 -m pip install .`
- sudo systemctl daemon-reload
