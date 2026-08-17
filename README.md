# Garud

Garud is the flight-ready hardware and firmware project for the MRIC CanSat HAT, covering the Raspberry Pi-based sensor stack, actuator control, and test scripts used for the Garud payload board.

This repository includes the schematic files, board configuration, Python drivers, and validation/test scripts for the CanSat HAT.

## Hardware layout

The project is designed around the Garud HAT schematic and the following connected devices:

- BNO085 IMU on I2C1
- BMP388 barometer on SPI0
- PCA9685 servo driver on I2C1
- ULN2003 stepper motor driver on GPIO pins
- Active buzzer on GPIO16
- XBee telemetry interface

## Repository structure

```text
Garud/
├── README.md
├── config.py
├── FILES/
│   ├── README.md
│   ├── requirements.txt
│   ├── libraries/
│   │   ├── bus_manager.py
│   │   ├── config.py
│   │   ├── xbee_link.py
│   │   ├── actuators/
│   │   └── sensors/
│   └── test_codes/
├── schematics/
│   ├── DIGIXBEE3.kicad_sch
│   ├── Garud_HAT.kicad_sch
│   └── Sensor&Connector_Sections_HAT.kicad_sch
└── .gitignore
```

## Setup

1. Enable I2C and SPI on the Raspberry Pi:

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
# Interface Options -> SPI -> Enable
sudo reboot
```

2. Install Python dependencies from the project package list:

```bash
cd Garud
pip install -r FILES/requirements.txt --break-system-packages
```

3. Verify the sensor addresses with i2cdetect if needed:

```bash
sudo i2cdetect -y 1
```

## Run the main integration demo

```bash
cd Garud
python3 FILES/test_codes/main.py
```

To run the full validation suite from the repo root:

```bash
python3 FILES/test_codes/test_everything.py
```

## Notes

- `config.py` defines the board pin mapping and is the source of truth for the project wiring.
- All scripts under `FILES/test_codes/` add the local libraries path dynamically so they can be run from the repo root or from within the test folder.
- Before flight, update the local sea-level pressure for barometric altitude calibration as needed.

## Project status

This repository is intended for hardware validation, flight testing, and further mission software development for the Garud CanSat platform.
