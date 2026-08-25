"""
sensors/gps_m8n.py
------------------
u-blox NEO-M8N GPS receiver via the SC16IS750 UART-over-SPI bridge.

UART path: SC16IS750.TXA -> M8N.RX, SC16IS750.RXA <- M8N.TX.
NMEA parsing covers the sentences the M8N emits by default (GGA/RMC);
a checksum is validated before any field is trusted.

Requires: sensors/sc16is750.py (no external GPS library).
"""
import time

import config
from sensors.sc16is750 import SC16IS750UART


def _nmea_checksum(body):
    """XOR of all chars between '$' and '*', as int."""
    c = 0
    for ch in body:
        c ^= ord(ch)
    return c


def _to_degrees(raw):
    """Convert NMEA ddmm.mmmm to decimal degrees (float)."""
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    deg = int(raw // 100)
    return deg + (raw - deg * 100) / 60.0


def _parse_gga(fields):
    # $GPGGA,hhmmss.ss,lat,N,lon,E,fix,sats,hdop,alt,M,geoid,M,...
    try:
        fix = int(fields[6])
        return {
            "type": "GPGGA",
            "utc": fields[1],
            "fixed": fix >= 1,
            "fix": fix,
            "satellites": int(fields[7]),
            "lat": _to_degrees(fields[2]),
            "lat_hemi": fields[3],
            "lon": _to_degrees(fields[4]),
            "lon_hemi": fields[5],
            "altitude_m": float(fields[9]) if fields[9] else None,
        }
    except (IndexError, ValueError):
        return None


def _parse_rmc(fields):
    # $GPRMC,hhmmss.ss,A,lat,N,lon,E,speed,course,ddmmyy,...
    try:
        return {
            "type": "GPRMC",
            "utc": fields[1],
            "fixed": fields[2] == "A",
            "active": fields[2] == "A",
            "lat": _to_degrees(fields[3]),
            "lat_hemi": fields[4],
            "lon": _to_degrees(fields[5]),
            "lon_hemi": fields[6],
            "speed_knots": float(fields[7]) if fields[7] else None,
            "date": fields[9],
        }
    except (IndexError, ValueError):
        return None


class GPS_M8N:
    """Thin NMEA wrapper around the SC16IS750 UART."""

    def __init__(self, spi_bus=None, uart=None,
                 cs_pin=config.GPS_SC16IS750_CS_PIN,
                 baudrate=config.GPS_BAUDRATE,
                 crystal_hz=config.GPS_SC16IS750_CRYSTAL_HZ):
        if uart is not None:
            self.uart = uart
        else:
            self.uart = SC16IS750UART(spi_bus, cs_pin=cs_pin,
                                      baudrate=baudrate,
                                      crystal_hz=crystal_hz)
        self._rx_buffer = b""

    # ------------------------------------------------------------ #
    # I/O
    # ------------------------------------------------------------ #
    def read_line(self, timeout=5.0):
        """Return one complete NMEA line (bytes, '\r' stripped) or None."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b"\n" in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
                line = line.strip(b"\r")
                if line.startswith(b"$"):
                    return line
            if self.uart.in_waiting:
                self._rx_buffer += self.uart.read(
                    min(self.uart.in_waiting, 64), timeout=1.0)
            else:
                time.sleep(0.01)
        return None

    def send_pmtk(self, body):
        """Send a PMTK command (e.g. 'PMTKQ,0100'); returns bytes written."""
        msg = "${}*{:02X}\r\n".format(body, _nmea_checksum(body))
        return self.uart.write(msg)

    # ------------------------------------------------------------ #
    # parsing
    # ------------------------------------------------------------ #
    @staticmethod
    def parse_nmea(line):
        """Validate the NMEA checksum and parse GGA/RMC. Returns dict or None."""
        if isinstance(line, bytes):
            try:
                line = line.decode("ascii")
            except UnicodeDecodeError:
                return None
        if not line.startswith("$"):
            return None
        star = line.rfind("*")
        if star < 0:
            return None
        body, chk = line[1:star], line[star + 1:]
        try:
            if int(chk, 16) != _nmea_checksum(body):
                return None
        except ValueError:
            return None
        fields = body.split(",")
        if fields[0] == "GPGGA":
            return _parse_gga(fields)
        if fields[0] == "GPRMC":
            return _parse_rmc(fields)
        return {"type": fields[0], "valid": True}

    def read_fix(self, timeout_s=config.GPS_NMEA_TIMEOUT_S):
        """Wait for the first checksum-valid GGA/RMC; returns dict or None."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self.read_line(timeout=min(5.0, deadline - time.monotonic()))
            if line is None:
                continue
            parsed = self.parse_nmea(line)
            if parsed and parsed.get("type") in ("GPGGA", "GPRMC"):
                return parsed
        return None