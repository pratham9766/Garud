"""
sc16is750_i2c_test.py
---------------------
Test B: verify an SC16IS750 breakout on I2C1 (GPIO2=SCL, GPIO3=SDA).

BEFORE RUNNING (hardware):
  1. Move the module's I2C/nSPI strap jumper from GND to 3V3 (I2C mode).
  2. POWER-CYCLE the module (unplug + replug VIN) - the strap is only
     sampled at power-up.

The chip answers at a 7-bit address in the 0x48-0x57 strap range
(0x40=PCA9685 and 0x4A=BNO085 already occupy I2C1 and are never touched).
Register access is two I2C transactions: write the register pointer, then
read/write data (the chip keeps the pointer across STOP).

Steps: scan, SPR probe, register readback, 9600 8N1 config (DLL=0x60),
FIFO checks, internal UART loopback (MCR[4]) and GPIO readback.

Run with: python3 sc16is750_i2c_test.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))

import time

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

SC16IS750_ADDR_MIN = 0x48
SC16IS750_ADDR_MAX = 0x57
KNOWN_ADDRS = {0x40: "PCA9685", 0x4A: "BNO085"}

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def report(name, status, detail=""):
    results.append((name, status, detail))
    mark = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "SKIP": "[ n/a]"}[status]
    print(f"{mark} {name:22s} {detail}")


class I2CSC16IS750:
    """Bare SC16IS750 register access over I2C."""

    def __init__(self, i2c, address):
        self._i2c = i2c
        self._addr = address

    def wr(self, reg, value):
        self._i2c.writeto(self._addr, bytes([reg & 0xFF, value & 0xFF]))

    def rd(self, reg, repeat_start=True):
        """Read back a register.

        Primary: single transaction with a repeated START (the pattern in
        the SC16IS750 datasheet, via writeto_then_readfrom).
        Fallback: two separate transactions (pointer persists across STOP).
        """
        buf = bytearray(1)
        if repeat_start:
            try:
                self._i2c.writeto_then_readfrom(self._addr, bytes([reg & 0xFF]), buf)
                return buf[0]
            except OSError:
                pass
        self._i2c.writeto(self._addr, bytes([reg & 0xFF]))
        self._i2c.readfrom_into(self._addr, buf)
        return buf[0]


def compute_divisor():
    return max(1, int(round(config.GPS_SC16IS750_CRYSTAL_HZ / (16.0 * config.GPS_BAUDRATE))))


def find_chip(i2c):
    """Scan for the chip; returns (addr, uart) or (None, None)."""
    found = sorted(i2c.scan())
    print(f"  I2C1 scan: {[hex(a) for a in found] if found else 'nothing responding'}")
    for a in found:
        if a in KNOWN_ADDRS:
            print(f"    {hex(a)}: {KNOWN_ADDRS[a]} (left alone)")
    for addr in found:
        if addr < SC16IS750_ADDR_MIN or addr > SC16IS750_ADDR_MAX:
            continue
        if addr in KNOWN_ADDRS:
            continue
        try:
            u = I2CSC16IS750(i2c, addr)
            u.wr(REG_SPR, 0x5A)
            r_rs = u.rd(REG_SPR, repeat_start=True)
            r_2t = u.rd(REG_SPR, repeat_start=False)
            iir = u.rd(REG_IIR, repeat_start=True)
            txlvl = u.rd(REG_TXLVL, repeat_start=True)
            print(f"    {hex(addr)}: SPR write=0x5A -> rs=0x{r_rs:02X} "
                  f"2tx=0x{r_2t:02X} IIR=0x{iir:02X} TXLVL={txlvl}")
            if r_rs == 0x5A or r_2t == 0x5A:
                return addr, u
        except OSError as e:
            print(f"    {hex(addr)}: OSError {e} - no ACK on probe")
            continue
    return None, None


def thr_write(u, data):
    for b in data:
        deadline = time.monotonic() + 0.5
        while u.rd(REG_TXLVL) == 0:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.001)
        u.wr(REG_THR, b)
    return True


def thr_read(u, n, timeout=2.0):
    out = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and len(out) < n:
        rxlvl = u.rd(REG_RXLVL)
        if rxlvl > 0:
            for _ in range(min(rxlvl, n - len(out))):
                out += bytes([u.rd(REG_RHR)])
        else:
            time.sleep(0.01)
    return out


def main():
    print("=" * 60)
    print("SC16IS750 I2C test - I2C1 (GPIO2/3)")
    print("=" * 60 + "\n")

    i2c = bus_manager.get_i2c()

    # ---------------- 1. scan + SPR probe --------------------------
    addr, u = None, None
    try:
        addr, u = find_chip(i2c)
    except Exception as e:
        report("I2C bus scan", FAIL, f"{type(e).__name__}: {e}")

    if u is None:
        report("SC16IS750 found", FAIL,
               "no SPR-verified address in 0x48-0x57 - check strap (3V3 for "
               "I2C), power-cycle, VIN voltage, or module health")
        print_summary()
        return

    report("SC16IS750 found", PASS, f"address {hex(addr)} (SPR=0x5A round-trip)")

    # ---------------- 2. register verification ----------------------
    spr_ok = True
    for probe in (0x5A, 0xAA, 0x00):
        u.wr(REG_SPR, probe)
        if u.rd(REG_SPR) != probe:
            spr_ok = False
            break
    iir = u.rd(REG_IIR)
    lcr = u.rd(REG_LCR)
    mcr = u.rd(REG_MCR)
    lsr = u.rd(REG_LSR)
    ier = u.rd(REG_IER)
    txlvl = u.rd(REG_TXLVL)
    rxlvl = u.rd(REG_RXLVL)
    detail = (f"SPR={'OK' if spr_ok else 'BAD'} IIR=0x{iir:02X} LCR=0x{lcr:02X} "
              f"MCR=0x{mcr:02X} LSR=0x{lsr:02X} IER=0x{ier:02X} "
              f"TXLVL={txlvl} RXLVL={rxlvl}")
    report("Register readback", PASS if spr_ok else FAIL, detail)

    # ---------------- 3. UART config (9600 8N1) ---------------------
    div = compute_divisor()
    u.wr(REG_LCR, 0x80)
    u.wr(REG_DLL, div & 0xFF)
    u.wr(REG_DLH, (div >> 8) & 0xFF)
    u.wr(REG_LCR, 0xBF)
    u.wr(REG_EFR, 0x10)
    u.wr(REG_LCR, 0x03)
    u.wr(REG_IER, 0x00)
    u.wr(REG_MCR, 0x00)
    u.wr(REG_FCR, 0x07)
    time.sleep(0.01)
    u.wr(REG_LCR, 0x80)
    dll, dlh = u.rd(REG_DLL), u.rd(REG_DLH)
    u.wr(REG_LCR, 0x03)
    iir2 = u.rd(REG_IIR)
    txlvl2 = u.rd(REG_TXLVL)
    cfg_ok = (dll == (div & 0xFF) and dlh == ((div >> 8) & 0xFF)
              and (iir2 & 0xC0) == 0xC0 and txlvl2 == 64)
    report("UART config 9600 8N1", PASS if cfg_ok else FAIL,
           f"DLL=0x{dll:02X} DLH=0x{dlh:02X} (expect 0x{div & 0xFF:02X}/"
           f"0x{(div >> 8) & 0xFF:02X}) IIR=0x{iir2:02X} TXLVL={txlvl2}")

    # ---------------- 4. internal UART loopback ---------------------
    if cfg_ok:
        try:
            payload = b"GPS-TEST-1234\r\n"
            u.wr(REG_MCR, 0x10)
            ok_w = thr_write(u, payload)
            echo = thr_read(u, len(payload)) if ok_w else b""
            u.wr(REG_MCR, 0x00)
            report("UART engine (loopback)", PASS if echo == payload else FAIL,
                   f"echo {echo!r}")
        except Exception as e:
            report("UART engine (loopback)", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("UART engine (loopback)", SKIP, "UART config failed")

    # ---------------- 5. GPIO via readback --------------------------
    try:
        u.wr(REG_IODIR, 0xFF)
        u.wr(REG_IOSTATE, 0xFF)
        io_hi = u.rd(REG_IOSTATE)
        u.wr(REG_IOSTATE, 0x00)
        io_lo = u.rd(REG_IOSTATE)
        ok = (u.rd(REG_IODIR) == 0xFF and io_hi == 0xFF and io_lo == 0x00)
        report("GPIO write/read", PASS if ok else FAIL,
               f"IODIR=0x{u.rd(REG_IODIR):02X} IOSTATE hi=0x{io_hi:02X} "
               f"lo=0x{io_lo:02X}")
    except Exception as e:
        report("GPIO write/read", FAIL, f"{type(e).__name__}: {e}")

    print_summary()


def print_summary():
    print(f"\n{'=' * 60}")
    n_pass = sum(1 for _, st, _ in results if st == PASS)
    n_fail = sum(1 for _, st, _ in results if st == FAIL)
    n_skip = sum(1 for _, st, _ in results if st == SKIP)
    print(f"SUMMARY: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP")
    if n_fail == 0 and n_pass > 0:
        print("=> Module healthy on I2C. Next: GPS-over-I2C driver fallback,")
        print("   or return to SPI mode (strap -> GND + power-cycle).")
    elif n_fail > 0:
        print("=> Module found but failing - see details above.")
    else:
        print("=> Module not found - see scan details above.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        sys.exit(1 if any(s == FAIL for _, s, _ in results) else 0)