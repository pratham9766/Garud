"""
NEO-M8N GPS reader using the Garud HAT SC16IS750 UART bridge.
"""

from __future__ import annotations

import time

import config
from sensors.sc16is750 import SC16IS750UART


def _nmea_checksum(body: str) -> int:
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return checksum


def _to_degrees(raw):
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    degrees = int(raw // 100)
    return degrees + (raw - degrees * 100) / 60.0


def _signed(value, hemisphere):
    if value is None:
        return None
    return -value if hemisphere in ("S", "W") else value


class GPSM8N:
    """Thin NMEA wrapper around the SC16IS750 UART."""

    def __init__(
        self,
        spi_bus,
        cs_pin=config.GPS_SC16IS750_CS,
        baudrate=config.GPS_BAUDRATE,
        crystal_hz=config.GPS_SC16IS750_CRYSTAL_HZ,
    ):
        self.uart = SC16IS750UART(
            spi_bus,
            cs_pin=cs_pin,
            baudrate=baudrate,
            crystal_hz=crystal_hz,
        )
        self._rx_buffer = b""

    def read_line(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b"\n" in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
                line = line.strip(b"\r")
                if line.startswith(b"$"):
                    return line
            if self.uart.in_waiting:
                self._rx_buffer += self.uart.read(
                    min(self.uart.in_waiting, 64),
                    timeout=1.0,
                )
            else:
                time.sleep(0.01)
        return None

    @staticmethod
    def parse_nmea(line):
        if isinstance(line, bytes):
            try:
                line = line.decode("ascii")
            except UnicodeDecodeError:
                return None
        if not line.startswith("$") or "*" not in line:
            return None
        body, checksum = line[1:].rsplit("*", 1)
        try:
            if int(checksum, 16) != _nmea_checksum(body):
                return None
        except ValueError:
            return None

        fields = body.split(",")
        sentence = fields[0]
        if sentence.endswith("GGA"):
            try:
                fix = int(fields[6])
                lat = _signed(_to_degrees(fields[2]), fields[3])
                lon = _signed(_to_degrees(fields[4]), fields[5])
                return {
                    "type": sentence,
                    "fixed": fix >= 1,
                    "fix": fix,
                    "satellites": int(fields[7]),
                    "hdop": float(fields[8]) if fields[8] else None,
                    "lat": lat,
                    "lon": lon,
                    "altitude_m": float(fields[9]) if fields[9] else None,
                }
            except (IndexError, ValueError):
                return None
        if sentence.endswith("RMC"):
            try:
                lat = _signed(_to_degrees(fields[3]), fields[4])
                lon = _signed(_to_degrees(fields[5]), fields[6])
                return {
                    "type": sentence,
                    "fixed": fields[2] == "A",
                    "lat": lat,
                    "lon": lon,
                    "altitude_m": None,
                    "ground_speed_mps": float(fields[7]) * 0.514444 if fields[7] else None,
                    "course_deg": float(fields[8]) if fields[8] else None,
                }
            except (IndexError, ValueError):
                return None
        return {"type": sentence, "valid": True}

    def read_fix(self, timeout_s=config.GPS_NMEA_TIMEOUT_S):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self.read_line(timeout=min(5.0, deadline - time.monotonic()))
            if line is None:
                continue
            parsed = self.parse_nmea(line)
            if parsed and parsed.get("type", "").endswith(("GGA", "RMC")):
                return parsed
        return None
