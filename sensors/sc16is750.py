"""
Minimal SC16IS750 UART bridge driver for the Garud HAT GPS link.

The GPS NEO-M8N is connected through SC16IS750 on SPI0.CE1/GPIO7, sharing
SPI0 with the BMP388 barometer.
"""

from __future__ import annotations

import time

import config

REG_RHR = 0x00
REG_THR = 0x00
REG_IER = 0x01
REG_FCR = 0x02
REG_IIR = 0x02
REG_LCR = 0x03
REG_MCR = 0x04
REG_LSR = 0x05
REG_SPR = 0x07
REG_TXLVL = 0x08
REG_RXLVL = 0x09
REG_DLL = 0x00
REG_DLH = 0x01
REG_EFR = 0x02

LCR_8N1 = 0x03
LCR_DLAB = 0x80
LCR_EFR_ACCESS = 0xBF
EFR_ENHANCED = 0x10
FCR_FIFO_ENABLE = 0x07
SPI_READ = 0x80


class SC16IS750UART:
    """Polling UART bridge via SC16IS750 over SPI."""

    def __init__(
        self,
        spi_bus,
        cs_pin=config.GPS_SC16IS750_CS,
        baudrate=config.GPS_BAUDRATE,
        crystal_hz=config.GPS_SC16IS750_CRYSTAL_HZ,
        spi_baudrate=1_000_000,
    ):
        import digitalio
        from adafruit_bus_device.spi_device import SPIDevice

        self._cs = digitalio.DigitalInOut(cs_pin)
        self._cs.direction = digitalio.Direction.OUTPUT
        self._spi_dev = SPIDevice(
            spi_bus,
            self._cs,
            baudrate=spi_baudrate,
            polarity=0,
            phase=0,
        )
        self._configure(baudrate, crystal_hz)

    def _write_reg(self, reg, value):
        with self._spi_dev as spi:
            spi.write(bytes([reg << 3, value & 0xFF]))

    def _read_reg(self, reg):
        buf = bytearray(1)
        with self._spi_dev as spi:
            spi.write(bytes([(reg << 3) | SPI_READ]))
            spi.readinto(buf)
        return buf[0]

    def _read_fifo(self, n):
        buf = bytearray(n)
        with self._spi_dev as spi:
            spi.write(bytes([(REG_RHR << 3) | SPI_READ]))
            spi.readinto(buf)
        return bytes(buf)

    def _write_fifo_byte(self, value):
        with self._spi_dev as spi:
            spi.write(bytes([REG_THR << 3, value & 0xFF]))

    def _configure(self, baudrate, crystal_hz):
        divisor = max(1, int(round(crystal_hz / (16.0 * baudrate))))
        self._write_reg(REG_LCR, LCR_8N1 | LCR_DLAB)
        self._write_reg(REG_DLL, divisor & 0xFF)
        self._write_reg(REG_DLH, (divisor >> 8) & 0xFF)
        self._write_reg(REG_LCR, LCR_EFR_ACCESS)
        self._write_reg(REG_EFR, EFR_ENHANCED)
        self._write_reg(REG_LCR, LCR_8N1)
        self._write_reg(REG_IER, 0x00)
        self._write_reg(REG_MCR, 0x00)
        self._write_reg(REG_FCR, FCR_FIFO_ENABLE)
        time.sleep(0.001)
        self._check_fifos_enabled()

    def _check_fifos_enabled(self):
        iir = self._read_reg(REG_IIR)
        txlvl = self._read_reg(REG_TXLVL)
        if (iir & 0xC0) != 0xC0 or txlvl != 64:
            raise RuntimeError(
                f"SC16IS750 FIFO init failed: IIR=0x{iir:02X}, TXLVL={txlvl}"
            )

    @property
    def in_waiting(self):
        return self._read_reg(REG_RXLVL)

    def read(self, nbytes=1, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            avail = self.in_waiting
            if avail:
                return self._read_fifo(min(avail, nbytes))
            time.sleep(0.001)
        return b""

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("ascii")
        sent = 0
        for byte in data:
            deadline = time.monotonic() + 0.5
            while self._read_reg(REG_TXLVL) == 0:
                if time.monotonic() >= deadline:
                    return sent
                time.sleep(0.001)
            self._write_fifo_byte(byte)
            sent += 1
        return sent
