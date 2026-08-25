"""
xbee_link.py
-------------
Minimal one-way XBee UART link over the Pi's primary UART
(GPIO14/TXD0 -> XBee DIN, XBee DOUT -> GPIO15/RXD0).

PAN ID / channel are pre-configured on the radio itself (XCTU),
so the Pi only needs to open the serial port and write frames.
"""
import serial

import config


class XBeeLink:
    """Serial port wrapper for the XBee modem (transmit-only for now)."""

    def __init__(self, port=config.XBEE_SERIAL_PORT,
                 baudrate=config.XBEE_BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def open(self):
        self.ser = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=1.0,
            write_timeout=1.0,
        )

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def send(self, frame: bytes):
        """Write a raw frame to the XBee (frame is sent as-is)."""
        if not self.connected:
            raise RuntimeError("XBee link is not open")
        self.ser.write(frame)

    def send_line(self, line: str):
        """Write one line to the XBee (terminator appended)."""
        self.send(line.encode("utf-8") + b"\n")

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None
