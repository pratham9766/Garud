"""
sc16is750_probe_matrix.py
-------------------------
Brute-force register-access diagnostic for the SC16IS750 at
config.GPS_SC16IS750_I2C_ADDRESS (0x4D).

The chip ACKs on I2C but reads 0x00 and ignores writes under the plain
register-addressing scheme - because the register address byte uses the
SPI-style reg<<3 encoding (confirmed empirically: shl3 gives a working
SPR round-trip and write persistence). This script tries plain / <<1 /
<<2 / <<3 / |0x80 / |0x08 encodings and reports the true readbacks.

On a working encoding it configures 9600 8N1, verifies the FIFOs, runs
an internal UART loopback, then reads the live GPS stream (PMTK query +
raw byte dump for baud diagnosis first).

Run with:  python3 sc16is750_probe_matrix.py
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
REG_DLL = 0x00
REG_DLH = 0x01
REG_EFR = 0x02

LCR_DLAB = 0x80
LCR_EFR_ACCESS = 0xBF
EFR_ENHANCED = 0x10
FCR_FIFO_ENABLE = 0x07
MCR_LOOPBACK = 0x10

ENCODINGS = {
    "plain": lambda r: r & 0xFF,
    "shl1":  lambda r: (r << 1) & 0xFF,
    "shl2":  lambda r: (r << 2) & 0xFF,
    "shl3":  lambda r: (r << 3) & 0xFF,
    "or80":  lambda r: (r | 0x80) & 0xFF,
    "or08":  lambda r: (r | 0x08) & 0xFF,
}


class Dev:
    """Raw access with a pluggable address encoder."""

    def __init__(self, i2c, addr, enc):
        self._i2c = i2c
        self._addr = addr
        self.enc = enc

    def wr(self, reg, value):
        self._i2c.writeto(self._addr, bytes([self.enc(reg), value & 0xFF]))

    def wr_addr_only(self, reg):
        self._i2c.writeto(self._addr, bytes([self.enc(reg)]))

    def rd(self, reg, two_tx=False):
        buf = bytearray(1)
        if not two_tx:
            try:
                self._i2c.writeto_then_readfrom(self._addr, bytes([self.enc(reg)]), buf)
                return buf[0]
            except OSError:
                pass
        self._i2c.writeto(self._addr, bytes([self.enc(reg)]))
        self._i2c.readfrom_into(self._addr, buf)
        return buf[0]


def probe_encoding(i2c, addr, name, enc):
    """Returns a dict of readbacks for one encoding (or None on NACK)."""
    d = Dev(i2c, addr, enc)
    r = {"name": name}
    try:
        d.wr(REG_SPR, 0x5A)
        r["spr_rs"] = d.rd(REG_SPR)
        r["spr_2tx"] = d.rd(REG_SPR, two_tx=True)
        d.wr_addr_only(REG_SPR)
        d.wr_addr_only(0x5A)
        r["spr_split"] = d.rd(REG_SPR)
        r["ier_before"] = d.rd(REG_IER)
        d.wr(REG_IER, 0x00)
        r["ier_after"] = d.rd(REG_IER)
        r["lcr_before"] = d.rd(REG_LCR)
        d.wr(REG_LCR, 0x03)
        r["lcr_after"] = d.rd(REG_LCR)
        r["rxlvl"] = d.rd(REG_RXLVL)
    except OSError as e:
        r["error"] = str(e)
    return r


CANDIDATES = [
    ("1.8432M @9600", 1_843_200, 9600),
    ("3.072M @9600", 3_072_000, 9600),
    ("4.9152M @9600", 4_915_200, 9600),
    ("7.3728M @9600", 7_372_800, 9600),
    ("8.0M @9600", 8_000_000, 9600),
    ("9.8304M @9600", 9_830_400, 9600),
    ("11.0592M @9600", 11_059_200, 9600),
    ("12.288M @9600", 12_288_000, 9600),
    ("14.7456M @9600", 14_745_600, 9600),
    ("16.0M @9600", 16_000_000, 9600),
    ("18.432M @9600", 18_432_000, 9600),
    ("22.1184M @9600", 22_118_400, 9600),
    ("24.576M @9600", 24_576_000, 9600),
    ("29.4912M @9600", 29_491_200, 9600),
    ("14.7456M @4800", 14_745_600, 4800),
    ("14.7456M @19200", 14_745_600, 19_200),
    ("14.7456M @38400", 14_745_600, 38_400),
    ("14.7456M @57600", 14_745_600, 57_600),
    ("14.7456M @115200", 14_745_600, 115_200),
]


def find_valid_nmea(data):
    """First checksum-valid NMEA sentence in data, else None."""
    start = data.find(b"$")
    while start != -1:
        end = data.find(b"\n", start)
        if end == -1:
            return None
        line = data[start:end].strip(b"\r")
        star = line.rfind(b"*")
        if star != -1 and len(line) - star == 3:
            cksum = 0
            for c in line[1:star]:
                cksum ^= c
            try:
                if int(line[star + 1:], 16) == cksum:
                    return line.decode("ascii", "replace")
            except ValueError:
                pass
        start = data.find(b"$", start + 1)
    return None


def sweep_bauds(d):
    """Try every (crystal, baud) candidate; returns the winning tuple.

    Leaves the chip configured at the winning divisor. Returns
    (label, crystal, baud, divisor, first_valid_line) or None.
    """
    for label, crystal, baud in CANDIDATES:
        div = max(1, int(round(crystal / (16.0 * baud))))
        d.wr(REG_LCR, LCR_DLAB | 0x03)
        d.wr(REG_DLL, div & 0xFF)
        d.wr(REG_DLH, (div >> 8) & 0xFF)
        d.wr(REG_LCR, 0x03)
        while d.rd(REG_RXLVL) > 0:
            d.rd(REG_RHR)
        data = b""
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and len(data) < 512:
            if d.rd(REG_RXLVL) > 0:
                data += bytes([d.rd(REG_RHR)])
            else:
                time.sleep(0.005)
        line = find_valid_nmea(data)
        print(f"  {label:18s} div={div:4d} got {len(data):4d}B "
              f"{line[:40] if line else '-'}")
        if line:
            return label, crystal, baud, div, line
    return None


def main():
    print("=" * 64)
    print("SC16IS750 probe matrix - I2C mode, addr "
          f"{hex(config.GPS_SC16IS750_I2C_ADDRESS)}")
    print("=" * 64)

    i2c = bus_manager.get_i2c()
    addr = config.GPS_SC16IS750_I2C_ADDRESS
    try:
        found = sorted(i2c.scan())
    except Exception as e:
        print(f"scan failed: {type(e).__name__}: {e}")
        return
    print(f"scan: {[hex(a) for a in found]}")
    if addr not in found:
        print(f"FAIL: {hex(addr)} not on the bus")
        return

    winner = None
    rows = []
    for name, enc in ENCODINGS.items():
        r = probe_encoding(i2c, addr, name, enc)
        rows.append(r)
        if r.get("error"):
            print(f"{name:7s}: NACK {r['error']}")
            continue
        print(f"{name:7s}: SPR(5A) rs=0x{r['spr_rs']:02X} "
              f"2tx=0x{r['spr_2tx']:02X} split=0x{r['spr_split']:02X} | "
              f"IER {r['ier_before']:02X}->{r['ier_after']:02X} | "
              f"LCR {r['lcr_before']:02X}->{r['lcr_after']:02X} | "
              f"RXLVL={r['rxlvl']}")
        if (r["spr_rs"] == 0x5A or r["spr_2tx"] == 0x5A
                or r["spr_split"] == 0x5A):
            winner = name
            break

    if winner is None:
        print("\n" + "=" * 64)
        print("NO working encoding found. The chip ACKs but its core is not")
        print("functional under any register-addressing scheme. Options:")
        print("  1. nRESET: tie it back to 3V3 (active-low), power-cycle, rerun")
        print("  2. VIN: feed from 5V header pin (LDO input), power-cycle, rerun")
        print("  3. If both fail -> damaged module; replace it (~$5)")
        print("=" * 64)
        return

    print(f"\nWINNER: encoding '{winner}' - proceeding\n")
    d = Dev(i2c, addr, ENCODINGS[winner])

    div = max(1, int(round(config.GPS_SC16IS750_CRYSTAL_HZ / (16.0 * config.GPS_BAUDRATE))))
    d.wr(REG_LCR, LCR_DLAB | 0x03)
    d.wr(REG_DLL, div & 0xFF)
    d.wr(REG_DLH, (div >> 8) & 0xFF)
    d.wr(REG_LCR, LCR_EFR_ACCESS)
    d.wr(REG_EFR, EFR_ENHANCED)
    d.wr(REG_LCR, 0x03)
    d.wr(REG_IER, 0x00)
    d.wr(REG_MCR, 0x00)
    d.wr(REG_FCR, FCR_FIFO_ENABLE)
    time.sleep(0.01)
    iir = d.rd(REG_IIR)
    txlvl = d.rd(REG_TXLVL)
    lcr = d.rd(REG_LCR)
    print(f"post-config: IIR=0x{iir:02X} TXLVL={txlvl} LCR=0x{lcr:02X}")
    if (iir & 0xC0) != 0xC0 or txlvl != 64:
        print("FAIL: FIFOs not enabled after config - core still non-functional")
        return

    print("RXLVL trend over 1s (live GPS streaming check):")
    trend = []
    for _ in range(5):
        trend.append(d.rd(REG_RXLVL))
        time.sleep(0.2)
    print(f"  {trend}  <- non-zero / varying = GPS NMEA arriving in the FIFO")

    drained = 0
    while d.rd(REG_RXLVL) > 0:
        d.rd(REG_RHR)
        drained += 1
    if drained:
        print(f"drained {drained} stale RX bytes")

    print("\n-- UART engine loopback (no GPS needed) --")
    payload = b"GPS-TEST-1234\r\n"
    d.wr(REG_MCR, MCR_LOOPBACK)
    for b in payload:
        d.wr(REG_THR, b)
    echo = b""
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and len(echo) < len(payload):
        rxlvl = d.rd(REG_RXLVL)
        if rxlvl > 0:
            for _ in range(rxlvl):
                echo += bytes([d.rd(REG_RHR)])
        else:
            time.sleep(0.01)
    d.wr(REG_MCR, 0x00)
    print(f"  echo {echo!r}")
    print(f"  UART engine: {'PASS' if echo == payload else 'FAIL'}")

    print("\n-- GPS baud/crystal sweep (GPS confirmed 9600, finding chip rate) --")
    hit = sweep_bauds(d)
    if hit is None:
        print("no candidate produced checksum-valid NMEA - check GPS output/wiring")
        sys.exit(1)
    label, crystal, baud, div, first = hit
    print(f"\nFOUND: {label} (divisor {div})")

    class Shim:
        def __init__(self, dev):
            self._d = dev

        @property
        def in_waiting(self):
            return self._d.rd(REG_RXLVL)

        def read(self, nbytes=1, timeout=1.0):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._d.rd(REG_RXLVL) > 0:
                    return bytes([self._d.rd(REG_RHR)])
                time.sleep(0.001)
            return b""

        def write(self, data):
            if isinstance(data, str):
                data = data.encode("ascii")
            for b in data:
                deadline = time.monotonic() + 0.5
                while self._d.rd(REG_TXLVL) == 0:
                    if time.monotonic() >= deadline:
                        return
                    time.sleep(0.001)
                self._d.wr(REG_THR, b)

    from sensors.gps_m8n import GPS_M8N
    gps = GPS_M8N(uart=Shim(d))
    gps.send_pmtk("PMTKQ,0100")
    fix = gps.read_fix(timeout_s=config.GPS_NMEA_TIMEOUT_S)
    if fix is None:
        print(f"GPS: no checksum-valid GGA/RMC in {config.GPS_NMEA_TIMEOUT_S}s")
        sys.exit(1)
    pos = f"lat={fix.get('lat')} lon={fix.get('lon')}"
    sats = fix.get("satellites")
    sats = f"sats={sats}" if sats is not None else "nav-data"
    print(f"GPS: {fix['type']} {'FIX' if fix.get('fixed') else 'no-fix'} {sats} {pos}")
    print("ALL PASS")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(1)