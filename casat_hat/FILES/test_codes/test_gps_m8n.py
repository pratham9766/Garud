"""
test_gps_m8n.py
---------------
Verification for the NEO-M8N GPS link through the SC16IS750
UART-over-SPI bridge (SPI0.CE1 = GPIO7, header pin 26).

Tests:
  1. SC16IS750 SPI link   - SPR scratchpad round-trip + TX FIFO level
  2. UART path (loopback) - internal MCR[4] loopback echo (no GPS needed)
  3. GPS NMEA link        - checksum-valid GGA/RMC + PMTK ACK (needs M8N)

Run with:  python3 test_gps_m8n.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))

import time

import bus_manager
import config

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def report(name, status, detail=""):
    results.append((name, status, detail))
    mark = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "SKIP": "[ n/a]"}[status]
    print(f"{mark} {name:18s} {detail}")


def main():
    print("=" * 60)
    print("Garud HAT - NEO-M8N GPS via SC16IS750 (SPI0 CE1)")
    print("=" * 60 + "\n")

    bridge_ok = False
    uart = None

    # ---------------- 1. SC16IS750 SPI link -----------------------
    try:
        from sensors.sc16is750 import SC16IS750UART
        spi = bus_manager.get_spi()
        uart = SC16IS750UART(spi)
        time.sleep(0.05)
        spr_ok = True
        for probe in (0x5A, 0xAA, 0x00):
            uart.scratchpad(probe)
            if uart.scratchpad() != probe:
                spr_ok = False
                break
        iir = uart.interrupt_status
        lcr = uart.line_control
        txlvl = uart.tx_fifo_level
        ok = spr_ok and (iir & 0xC0) == 0xC0 and lcr == 0x03 and txlvl == 64
        if ok:
            detail = (f"SPR ok IIR=0x{iir:02X} LCR=0x{lcr:02X} "
                      f"TXLVL={txlvl}")
        elif not spr_ok:
            detail = "SPR round-trip failed - chip not responding on SPI0 CE1"
        elif (iir & 0xC0) != 0xC0:
            detail = (f"FIFO disabled (IIR=0x{iir:02X}, expect 0xC1) - "
                      "run sc16is750_diag.py")
        else:
            detail = (f"config mismatch LCR=0x{lcr:02X} TXLVL={txlvl} "
                      "(expect 0x03, 64)")
        report("SC16IS750 SPI link", PASS if ok else FAIL, detail)
        bridge_ok = ok
    except Exception as e:
        report("SC16IS750 SPI link", FAIL, f"{type(e).__name__}: {e}")

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

    # ---------------- summary --------------------------------------
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