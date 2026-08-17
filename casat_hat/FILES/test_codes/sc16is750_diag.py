"""
sc16is750_diag.py
-----------------
Low-level diagnostic for a generic SC16IS750 breakout on SPI0.CE1 (GPIO7).

Tries four init sequences (A/B/C/D) and, after each, dumps the register
state and scores the result: SPR round-trip, FIFO status via IIR[7:6],
LCR=0x03 readback, TXLVL=64, and a THR write draining TXLVL to 63.

Run with:  python3 sc16is750_diag.py
Probe:     python3 sc16is750_diag.py --probe
           GPIO0 output toggle test - proves the chip is alive and
           receiving SPI writes even when the read path (MISO) is dead.
           Watch the module's IO0 pin with a multimeter/LED.

Note: after changing the I2C/SPI mode strap, POWER-CYCLE the module
(unplug + replug 3V3) - the strap is only sampled at power-up.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))

import time

import digitalio
from adafruit_bus_device.spi_device import SPIDevice

import bus_manager
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
REG_IODIR = 0x0A
REG_IOSTATE = 0x0B
REG_DLL = 0x00
REG_DLH = 0x01
REG_EFR = 0x02

SPI_READ = 0x80


class RawSC16IS750:
    """Bare register access so arbitrary init sequences can be tried."""

    def __init__(self, spi_bus, cs_pin, spi_baudrate=1000000):
        self._cs = digitalio.DigitalInOut(cs_pin)
        self._cs.direction = digitalio.Direction.OUTPUT
        self._spi_dev = SPIDevice(spi_bus, self._cs,
                                  baudrate=spi_baudrate,
                                  polarity=0, phase=0)

    def wr(self, reg, value):
        with self._spi_dev as spi:
            spi.write(bytes([reg << 3, value & 0xFF]))

    def rd(self, reg):
        buf = bytearray(1)
        with self._spi_dev as spi:
            spi.write(bytes([(reg << 3) | SPI_READ]))
            spi.readinto(buf)
        return buf[0]


def compute_divisor():
    return max(1, int(round(config.GPS_SC16IS750_CRYSTAL_HZ / (16.0 * config.GPS_BAUDRATE))))


def probe_gpio_output(u):
    """Test A: drive module GPIO0 as an output, toggle it, watch IO0.

    Proves the chip is alive, powered, selected, and receiving SPI writes
    even when the read path (MISO) is completely dead (all reads 0xFF).
    If IO0 does NOT toggle, the chip is not receiving writes at all -
    check power, the CS wire, and the I2C/SPI mode strap.
    """
    print("=" * 64)
    print("TEST A - GPIO0 output probe")
    print("=" * 64)
    print("  Find the pin labeled IO0 on the module (left header, near")
    print("  the VCC end). Measure it against GND with a DC multimeter,")
    print("  or clip on an LED + resistor. Watch it during this run:")
    print()
    u.wr(REG_IODIR, 0xFF)  # all 8 GPIOs -> outputs
    for state, label in ((0xFF, "HIGH  - expect ~3.3 V"),
                         (0x00, "LOW   - expect ~0 V"),
                         (0xFF, "HIGH again")):
        u.wr(REG_IOSTATE, state)
        time.sleep(3)
        print(f"  IOSTATE=0x{state:02X} -> IO0 should read: {label}")
    u.wr(REG_IOSTATE, 0x00)

    iodir = u.rd(REG_IODIR)
    iostate = u.rd(REG_IOSTATE)
    print(f"\n  readback: IODIR=0x{iodir:02X} IOSTATE=0x{iostate:02X}")
    if iodir == 0xFF:
        print("  (readback matches - the MISO read path works now)")
    else:
        print("  (0xFF readback = MISO/SO wire still not reaching the Pi)")
    print()
    print("  => IO0 toggled?  YES: chip is ALIVE; the SO<->Pi MISO (GPIO9)")
    print("     wire is the problem (check for swapped SI/SO).")
    print("     NO: chip is NOT getting writes - check CS wire, power,")
    print("     and the I2C/SPI strap (power-cycle after re-strapping).")
    print("=" * 64)


def variant_a(u, div):
    """Current driver sequence: FIFO reset first, then baud/format."""
    u.wr(REG_FCR, 0x06)
    time.sleep(0.01)
    u.wr(REG_FCR, 0x07)
    u.wr(REG_LCR, 0x03 | 0x80)
    u.wr(REG_DLL, div & 0xFF)
    u.wr(REG_DLH, (div >> 8) & 0xFF)
    u.wr(REG_LCR, 0x03)
    u.wr(REG_IER, 0x00)
    u.wr(REG_MCR, 0x00)


def variant_b(u, div):
    """No reset; baud/format first; FIFO enable written last."""
    u.wr(REG_LCR, 0x03 | 0x80)
    u.wr(REG_DLL, div & 0xFF)
    u.wr(REG_DLH, (div >> 8) & 0xFF)
    u.wr(REG_LCR, 0x03)
    u.wr(REG_IER, 0x00)
    u.wr(REG_MCR, 0x00)
    u.wr(REG_FCR, 0x07)


def variant_c(u, div):
    """Reset with a long settle, then baud/format, FIFO enable last."""
    u.wr(REG_FCR, 0x06)
    time.sleep(0.5)
    u.wr(REG_LCR, 0x03 | 0x80)
    u.wr(REG_DLL, div & 0xFF)
    u.wr(REG_DLH, (div >> 8) & 0xFF)
    u.wr(REG_LCR, 0x03)
    u.wr(REG_IER, 0x00)
    u.wr(REG_MCR, 0x00)
    u.wr(REG_FCR, 0x07)


def variant_d(u, div):
    """NXP reference order: baud -> EFR enhanced -> format -> FIFO last."""
    u.wr(REG_LCR, 0x80)
    u.wr(REG_DLL, div & 0xFF)
    u.wr(REG_DLH, (div >> 8) & 0xFF)
    u.wr(REG_LCR, 0xBF)
    u.wr(REG_EFR, 0x10)
    u.wr(REG_LCR, 0x03)
    u.wr(REG_IER, 0x00)
    u.wr(REG_MCR, 0x00)
    u.wr(REG_FCR, 0x07)


def evaluate(u, div):
    """Score the current register state; returns (ok, detail lines)."""
    lines = []

    spr_ok = True
    for probe in (0x5A, 0xAA, 0x00):
        u.wr(REG_SPR, probe)
        if u.rd(REG_SPR) != probe:
            spr_ok = False
    lines.append(f"SPR round-trip      : {'OK' if spr_ok else 'MISMATCH'}")

    iir = u.rd(REG_IIR)
    lcr = u.rd(REG_LCR)
    mcr = u.rd(REG_MCR)
    lsr = u.rd(REG_LSR)
    ier = u.rd(REG_IER)
    txlvl = u.rd(REG_TXLVL)
    rxlvl = u.rd(REG_RXLVL)
    lines.append(f"IIR=0x{iir:02X} FIFObits=0b{iir >> 6:02b} LCR=0x{lcr:02X} "
                 f"MCR=0x{mcr:02X} LSR=0x{lsr:02X} IER=0x{ier:02X}")
    lines.append(f"TXLVL={txlvl} RXLVL={rxlvl}")

    u.wr(REG_LCR, 0x03 | 0x80)
    dll, dlh = u.rd(REG_DLL), u.rd(REG_DLH)
    u.wr(REG_LCR, 0x03)
    lines.append(f"DLL=0x{dll:02X} DLH=0x{dlh:02X} (expect 0x{div & 0xFF:02X}/"
                 f"0x{(div >> 8) & 0xFF:02X} for {config.GPS_BAUDRATE} baud "
                 f"@ {config.GPS_SC16IS750_CRYSTAL_HZ} Hz)")

    txlvl2 = None
    if txlvl == 64:
        u.wr(REG_THR, ord("A"))
        time.sleep(0.01)
        txlvl2 = u.rd(REG_TXLVL)
    lines.append(f"TXLVL after THR     : {txlvl2 if txlvl2 is not None else 'n/a'} "
                 f"(expect 63)")

    ok = (spr_ok and (iir & 0xC0) == 0xC0 and lcr == 0x03
          and txlvl == 64 and txlvl2 == 63)
    return ok, lines


def main():
    print("=" * 64)
    print(f"SC16IS750 diag - SPI0 CE1 (GPIO7), {config.GPS_BAUDRATE} baud, "
          f"crystal {config.GPS_SC16IS750_CRYSTAL_HZ} Hz")
    print("=" * 64)

    div = compute_divisor()
    spi = bus_manager.get_spi()
    u = RawSC16IS750(spi, config.GPS_SC16IS750_CS_PIN)

    variants = [
        ("A current (reset first)", variant_a),
        ("B no reset, FCR last", variant_b),
        ("C reset + 500ms, FCR last", variant_c),
        ("D NXP order + EFR, FCR last", variant_d),
    ]

    first_ok = None
    for name, fn in variants:
        print(f"\n--- {name} ---")
        try:
            fn(u, div)
            time.sleep(0.05)
            ok, lines = evaluate(u, div)
        except Exception as e:
            ok, lines = False, [f"{type(e).__name__}: {e}"]
        for line in lines:
            print("   " + line)
        if ok and first_ok is None:
            first_ok = name
        print(f"   -> {'PASS' if ok else 'FAIL'}")

    print("\n" + "=" * 64)
    if first_ok:
        print(f"RECOMMENDATION: adopt init sequence '{first_ok}' in sc16is750.py")
    else:
        print("RECOMMENDATION: none passed - check module markings, the")
        print("  SPI/I2C strap, wiring, or retry with spi_baudrate=500000")
        print("  (RawSC16IS750(spi, cs, 500000)).")
    print("=" * 64)


if __name__ == "__main__":
    if "--probe" in sys.argv:
        spi = bus_manager.get_spi()
        u = RawSC16IS750(spi, config.GPS_SC16IS750_CS_PIN)
        probe_gpio_output(u)
    else:
        main()