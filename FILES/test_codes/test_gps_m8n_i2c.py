"""
test_gps_m8n_i2c.py
-------------------
Verification for the NEO-M8N GPS link through the SC16IS750 UART bridge
in I2C mode (mode strap HIGH = I2C mode; SDA/SCL on GPIO2/3).

Talks directly to config.GPS_SC16IS750_I2C_ADDRESS (0x4D on this module,
found in earlier scans). No discovery gate: the raw register dump at the
start shows the true chip state - ACK-only with 0x00 readbacks means the
core is non-functional (held in reset or damaged).

Tests:
  1. SC16IS750 I2C link  - raw register dump + FIFO self-check
  2. UART path (loopback)- internal MCR[4] loopback echo (no GPS needed)
  3. GPS NMEA link       - checksum-valid GGA/RMC + PMTK ACK (needs M8N)

Run with:  python3 test_gps_m8n_i2c.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))

import time

import bus_manager
import config

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []

REG_SPR = 0x07
REG_IER = 0x01
REG_IIR = 0x02
REG_LCR = 0x03
REG_MCR = 0x04
REG_LSR = 0x05
REG_TXLVL = 0x08
REG_RXLVL = 0x09

KNOWN_ADDRS = {0x40: "PCA9685", 0x4A: "BNO085"}


def report(name, status, detail=""):
    results.append((name, status, detail))
    mark = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "SKIP": "[ n/a]"}[status]
    print(f"{mark} {name:22s} {detail}")


class RawI2C:
    """Raw register access for diagnostics (repeated-START reads).

    Register address byte uses the SPI-style reg<<3 encoding - confirmed
    empirically on this module (plain addressing reads reserved regs).
    """

    def __init__(self, i2c, addr):
        self._i2c = i2c
        self._addr = addr

    def wr(self, reg, value):
        self._i2c.writeto(self._addr, bytes([(reg << 3) & 0xFF, value & 0xFF]))

    def rd(self, reg):
        buf = bytearray(1)
        try:
            self._i2c.writeto_then_readfrom(self._addr,
                                            bytes([(reg << 3) & 0xFF]), buf)
        except OSError:
            self._i2c.writeto(self._addr, bytes([(reg << 3) & 0xFF]))
            self._i2c.readfrom_into(self._addr, buf)
        return buf[0]


def main():
    print("=" * 60)
    print("Garud HAT - NEO-M8N GPS via SC16IS750 (I2C mode)")
    print("=" * 60 + "\n")

    i2c = bus_manager.get_i2c()
    addr = config.GPS_SC16IS750_I2C_ADDRESS

    # ---------------- 0. bus scan ----------------------------------
    try:
        found = sorted(i2c.scan())
    except Exception as e:
        found = []
        report("I2C1 bus scan", FAIL, f"{type(e).__name__}: {e}")
    print(f"  I2C1 scan: {[hex(a) for a in found] if found else 'nothing responding'}")
    for a in found:
        if a in KNOWN_ADDRS:
            print(f"    {hex(a)}: {KNOWN_ADDRS[a]} (left alone)")
    if addr not in found:
        report("SC16IS750 I2C link", FAIL,
               f"address {hex(addr)} not ACKing on I2C1 (scan: "
               f"{[hex(a) for a in found] or 'empty'}) - check mode strap "
               "(3V3 = I2C), power-cycle, SDA/SCL on GPIO2/3, nRESET")
        print_summary()
        return

    # ---------------- 1. raw dump + link check ---------------------
    bridge_ok = False
    try:
        raw = RawI2C(i2c, addr)
        raw.wr(REG_SPR, 0x5A)
        spr = raw.rd(REG_SPR)
        iir = raw.rd(REG_IIR)
        lcr = raw.rd(REG_LCR)
        mcr = raw.rd(REG_MCR)
        lsr = raw.rd(REG_LSR)
        ier = raw.rd(REG_IER)
        txlvl = raw.rd(REG_TXLVL)
        rxlvl = raw.rd(REG_RXLVL)
        print(f"  {hex(addr)}: SPR(0x5A)={hex(spr)} IIR=0x{iir:02X} "
              f"LCR=0x{lcr:02X} MCR=0x{mcr:02X} LSR=0x{lsr:02X} "
              f"IER=0x{ier:02X} TXLVL={txlvl} RXLVL={rxlvl}")

        from sensors.sc16is750 import SC16IS750I2C
        uart = SC16IS750I2C(i2c)
        time.sleep(0.05)
        spr_ok = True
        for probe in (0x5A, 0xAA, 0x00):
            uart.scratchpad(probe)
            if uart.scratchpad() != probe:
                spr_ok = False
                break
        iir2 = uart.interrupt_status
        lcr2 = uart.line_control
        txlvl2 = uart.tx_fifo_level
        bridge_ok = spr_ok and (iir2 & 0xC0) == 0xC0 and lcr2 == 0x03 and txlvl2 == 64
        if bridge_ok:
            detail = f"SPR ok IIR=0x{iir2:02X} LCR=0x{lcr2:02X} TXLVL={txlvl2}"
        elif not spr_ok:
            detail = "SPR round-trip failed - chip ACKs but ignores writes"
        elif (iir2 & 0xC0) != 0xC0:
            detail = (f"FIFO disabled (IIR=0x{iir2:02X}, expect 0xC1) - "
                      "chip in reset or unpowered core")
        else:
            detail = f"config mismatch LCR=0x{lcr2:02X} TXLVL={txlvl2} (expect 0x03, 64)"
        report("SC16IS750 I2C link", PASS if bridge_ok else FAIL, detail)
    except RuntimeError as e:
        report("SC16IS750 I2C link", FAIL,
               f"FIFO self-check: {e} (raw dump above shows chip state)")
    except OSError as e:
        report("SC16IS750 I2C link", FAIL, f"{type(e).__name__}: {e}")

    # ---------------- 2. UART path (internal loopback) -------------
    if bridge_ok:
        try:
            uart.set_loopback(True)
            payload = b"GPS-TEST-1234\r\n"
            uart.write(payload)
            echo = b""
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and len(echo) < len(payload):
                echo += uart.read(16, timeout=0.5)
            uart.set_loopback(False)
            report("UART path (loopback)", PASS if echo == payload else FAIL,
                   f"echo {echo!r}")
        except Exception as e:
            report("UART path (loopback)", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("UART path (loopback)", SKIP, "bridge not responding")

    # ---------------- 3. GPS NMEA link -----------------------------
    if bridge_ok:
        try:
            from sensors.gps_m8n import GPS_M8N
            gps = GPS_M8N(uart=uart)
            fix = gps.read_fix(timeout_s=config.GPS_NMEA_TIMEOUT_S)
            if fix is None:
                report("GPS NMEA link", SKIP,
                       f"no checksum-valid GGA/RMC in {config.GPS_NMEA_TIMEOUT_S}s "
                       "(bridge OK - check antenna, sky view, 9600 baud)")
                report("GPS PMTK ack", SKIP, "GPS not talking")
            else:
                pos = f"lat={fix.get('lat')} lon={fix.get('lon')}"
                sats = fix.get("satellites")
                sats = f"sats={sats}" if sats is not None else "nav-data"
                report("GPS NMEA link", PASS,
                       f"{fix['type']} {'FIX' if fix.get('fixed') else 'no-fix'} "
                       f"{sats} {pos}")
                gps.send_pmtk("PMTKQ,0100")
                ack = None
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    line = gps.read_line(timeout=1.0)
                    if line is None:
                        continue
                    parsed = gps.parse_nmea(line)
                    if (parsed or {}).get("type") in ("PMTK001", "PMTK705"):
                        ack = line.decode("ascii", "replace")
                        break
                report("GPS PMTK ack (TX path)", PASS if ack else FAIL,
                       ack or "no PMTK001/PMTK705 within 3s")
        except Exception as e:
            report("GPS NMEA link", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("GPS NMEA link", SKIP, "bridge not responding")
        report("GPS PMTK ack", SKIP, "bridge not responding")

    print_summary()


def print_summary():
    print(f"\n{'=' * 60}")
    n_pass = sum(1 for _, st, _ in results if st == PASS)
    n_fail = sum(1 for _, st, _ in results if st == FAIL)
    n_skip = sum(1 for _, st, _ in results if st == SKIP)
    print(f"SUMMARY: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        sys.exit(1 if any(s == FAIL for _, s, _ in results) else 0)