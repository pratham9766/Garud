"""
sensors/sc16is750.py
--------------------
Minimal SC16IS750 (NXP) UART bridge driver for the Garud HAT, over SPI or
I2C (same register map; the transport only changes the low-level access).

SPI transport (SC16IS750UART): the SC16IS750 hangs off SPI0.CE1 (GPIO7,
header pin 26), sharing the bus with the BMP388 (CE0/GPIO8). Each SPI
transaction is an address byte followed by data bytes: address = register
<< 3, read flag = 0x80. SPI mode 0 only, max 4 MHz. 3.3 V logic only.

I2C transport (SC16IS750I2C): used when the module's I2C/nSPI mode strap
is HIGH (I2C mode) and SDA/SCL are wired to GPIO2/3. The chip answers at
a 7-bit address in the 0x48-0x57 strap range (0x4D on this module).

Wiring (Pi J1 -> SC16IS750 -> NEO-M8N):
    SCK=GPIO11 (pin23), MOSI=GPIO10 (pin19), MISO=GPIO9 (pin21),
    CS=GPIO7 (pin26), 3V3 (pin1), GND (pin9)
    SC16IS750.TXA -> M8N.RX ; SC16IS750.RXA <- M8N.TX

Requires: Adafruit-Blinka (busio, digitalio, adafruit_bus_device).
"""
import time

import digitalio
from adafruit_bus_device.spi_device import SPIDevice

import config

# 16C450-compatible register map (SPI address = register << 3)
REG_RHR = 0x00   # receive holding register (read)
REG_THR = 0x00   # transmit holding register (write)
REG_IER = 0x01   # interrupt enable
REG_FCR = 0x02   # FIFO control (write)
REG_IIR = 0x02   # interrupt identification (read)
REG_LCR = 0x03   # line control
REG_MCR = 0x04   # modem control
REG_LSR = 0x05   # line status
REG_MSR = 0x06   # modem status
REG_SPR = 0x07   # scratchpad
REG_TXLVL = 0x08 # TX FIFO free-slot count
REG_RXLVL = 0x09 # RX FIFO byte count
REG_IODIR = 0x0A # GPIO direction
REG_IOSTATE = 0x0B # GPIO state
REG_DLL = 0x00   # divisor latch low  (visible with LCR[7]=1)
REG_DLH = 0x01   # divisor latch high (visible with LCR[7]=1)
REG_EFR = 0x02   # enhanced features  (visible with LCR=0xBF)

LCR_8N1 = 0x03
LCR_DLAB = 0x80        # divisor latch access bit (LCR[7])
LCR_EFR_ACCESS = 0xBF  # LCR value exposing the enhanced register set
EFR_ENHANCED = 0x10    # EFR[4]: enable enhanced features (FCR[5:4] etc.)
MCR_LOOPBACK = 0x10    # MCR[4]: internal loopback, TX routed to RX
FCR_FIFO_ENABLE = 0x07 # FIFOs on, clear TX+RX, default 1-byte triggers

SPI_READ = 0x80
FIFO_SIZE = 64


class SC16IS750UART:
    """Polling UART bridge via an SC16IS750 on SPI0."""

    def __init__(self, spi_bus, cs_pin=config.GPS_SC16IS750_CS_PIN,
                 baudrate=config.GPS_BAUDRATE,
                 crystal_hz=config.GPS_SC16IS750_CRYSTAL_HZ,
                 spi_baudrate=1000000):
        self._cs = digitalio.DigitalInOut(cs_pin)
        self._cs.direction = digitalio.Direction.OUTPUT
        self._spi_dev = SPIDevice(spi_bus, self._cs,
                                  baudrate=spi_baudrate,
                                  polarity=0, phase=0)
        self._configure(baudrate, crystal_hz)

    # ------------------------------------------------------------ #
    # low-level register access
    # ------------------------------------------------------------ #
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

    # ------------------------------------------------------------ #
    # init
    # ------------------------------------------------------------ #
    def _configure(self, baudrate, crystal_hz):
        divisor = max(1, int(round(crystal_hz / (16.0 * baudrate))))
        # NXP reference order (AN10462): baud rate -> enhanced features ->
        # character format -> FIFO control LAST. Writing FCR last avoids a
        # FIFO-reset/settle window (datasheet note: wait >= 2 x Tclk after a
        # FIFO reset before touching RHR/THR) discarding later config writes.
        self._write_reg(REG_LCR, LCR_8N1 | LCR_DLAB)
        self._write_reg(REG_DLL, divisor & 0xFF)
        self._write_reg(REG_DLH, (divisor >> 8) & 0xFF)
        self._write_reg(REG_LCR, LCR_EFR_ACCESS)
        self._write_reg(REG_EFR, EFR_ENHANCED)
        self._write_reg(REG_LCR, LCR_8N1)
        self._write_reg(REG_IER, 0x00)   # pure polling, no interrupts
        self._write_reg(REG_MCR, 0x00)   # no flow control, no loopback
        self._write_reg(REG_FCR, FCR_FIFO_ENABLE)
        time.sleep(0.001)
        self._check_fifos_enabled()

    def _check_fifos_enabled(self):
        iir = self._read_reg(REG_IIR)
        txlvl = self._read_reg(REG_TXLVL)
        if (iir & 0xC0) != 0xC0 or txlvl != 64:
            raise RuntimeError(
                f"SC16IS750 FIFOs not enabled after init: IIR=0x{iir:02X} "
                f"(expect 0xC1), TXLVL={txlvl} (expect 64)")

    # ------------------------------------------------------------ #
    # public UART API
    # ------------------------------------------------------------ #
    @property
    def in_waiting(self):
        """Number of bytes currently in the RX FIFO."""
        return self._read_reg(REG_RXLVL)

    @property
    def tx_fifo_level(self):
        """Free slots in the TX FIFO (64 = empty)."""
        return self._read_reg(REG_TXLVL)

    @property
    def interrupt_status(self):
        """IIR readback; bits[7:6] == 0b11 when the FIFOs are enabled."""
        return self._read_reg(REG_IIR)

    @property
    def line_control(self):
        """LCR readback (0x03 = 8N1)."""
        return self._read_reg(REG_LCR)

    @property
    def rx_fifo_level(self):
        """Bytes in the RX FIFO (same as in_waiting)."""
        return self._read_reg(REG_RXLVL)

    def read(self, nbytes=1, timeout=1.0):
        """Read up to nbytes bytes from the RX FIFO, waiting up to timeout s."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            avail = self.in_waiting
            if avail > 0:
                return self._read_fifo(min(avail, nbytes))
            time.sleep(0.001)
        return b""

    def readinto(self, buf, timeout=1.0):
        """Fill buf from the RX FIFO; returns bytes read."""
        data = self.read(len(buf), timeout)
        n = len(data)
        buf[:n] = data
        return n

    def write(self, data):
        """Write bytes to the TX FIFO (respects 64-byte capacity)."""
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

    # ------------------------------------------------------------ #
    # test / diagnostic helpers
    # ------------------------------------------------------------ #
    def scratchpad(self, value=None):
        """Read (or write-then-read) the SPR scratchpad register."""
        if value is not None:
            self._write_reg(REG_SPR, value & 0xFF)
        return self._read_reg(REG_SPR)

    def set_loopback(self, enable):
        """Internal loopback (MCR[4]): TXA is routed straight to RXA."""
        mcr = self._read_reg(REG_MCR)
        if enable:
            mcr |= MCR_LOOPBACK
        else:
            mcr &= ~MCR_LOOPBACK
        self._write_reg(REG_MCR, mcr)


class SC16IS750I2C(SC16IS750UART):
    """SC16IS750 over I2C (mode strap HIGH = I2C mode).

    Same public UART API as SC16IS750UART - only the low-level register
    primitives are replaced with I2C transactions. The register address
    byte uses the same reg<<3 encoding as SPI (no read-flag bit); this
    was confirmed empirically on this module - plain register-number
    addressing hits reserved registers and reads 0x00 everywhere.

    Reads use the repeated-START pattern from the datasheet, with a
    two-transaction fallback. FIFO reads are one byte at a time (the
    chip auto-increments the register pointer on multi-byte accesses).
    """

    def __init__(self, i2c, address=config.GPS_SC16IS750_I2C_ADDRESS,
                 baudrate=config.GPS_BAUDRATE,
                 crystal_hz=config.GPS_SC16IS750_CRYSTAL_HZ):
        self._i2c = i2c
        self._addr = address
        self._configure(baudrate, crystal_hz)

    def _addr_byte(self, reg):
        return (reg << 3) & 0xFF

    def _write_reg(self, reg, value):
        self._i2c.writeto(self._addr, bytes([self._addr_byte(reg), value & 0xFF]))

    def _read_reg(self, reg):
        buf = bytearray(1)
        try:
            self._i2c.writeto_then_readfrom(self._addr,
                                            bytes([self._addr_byte(reg)]), buf)
        except OSError:
            self._i2c.writeto(self._addr, bytes([self._addr_byte(reg)]))
            self._i2c.readfrom_into(self._addr, buf)
        return buf[0]

    def _read_fifo(self, n):
        out = bytearray()
        for _ in range(n):
            out.append(self._read_reg(REG_RHR))
        return bytes(out)

    def _write_fifo_byte(self, value):
        self._i2c.writeto(self._addr,
                          bytes([self._addr_byte(REG_THR), value & 0xFF]))