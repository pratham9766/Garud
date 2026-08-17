"""
test_everything.py
------------------
Full Garud HAT hardware regression suite.  Runs every subsystem once
(BNO085, BMP388, PCA9685 servos ch0-2, ULN2003 stepper, buzzer, XBee
probe, gimbal sanity) and logs PASS/FAIL + verification numbers for each.

Run with:  python3 test_everything.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "libraries"))


import math
import sys
import time
import traceback

import bus_manager
import config

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def report(name, status, detail=""):
    results.append((name, status, detail))
    mark = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "SKIP": "[ n/a]"}[status]
    print(f"{mark} {name:18s} {detail}")


def scan_i2c(i2c):
    """Return set of 7-bit addresses on the bus.

    Uses `i2cdetect` as the source of truth (adasomething probe() fails
    on this designware controller even when i2cdetect finds devices),
    falling back to python probing if i2cdetect is unavailable.
    """
    import subprocess
    found = set()
    try:
        out = subprocess.run(["i2cdetect", "-y", "-r", "1"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines()[1:]:
            for tok in line.split()[1:]:
                if tok != "--":
                    try:
                        found.add(int(tok, 16))
                    except ValueError:
                        pass
        return found
    except Exception:
        pass
    try:
        if not i2c.try_lock():
            return found
        for addr in range(0x03, 0x78):
            try:
                if i2c.probe(addr):
                    found.add(addr)
            except Exception:
                continue
        i2c.unlock()
    except Exception:
        pass
    return found


def servo_sweep(pwm, channels):
    for ch in channels:
        for a in (0, 45, 90, 135, 180, 0):
            pwm.set_angle(ch, a)
            time.sleep(0.15)


def main():
    print("=" * 60)
    print("Garud HAT - full subsystem verification")
    print("=" * 60 + "\n")

    # ---------------- 1. I2C bus probe (retry in case it re-enumerates)
    i2c = None
    found = set()
    for attempt in range(1, 5):
        try:
            i2c = bus_manager.get_i2c()
            found = scan_i2c(i2c)
            if found:
                break
        except Exception:
            found = set()
        if attempt < 4:
            print(f"  bus probe attempt {attempt}/4 - bus empty, retrying...")
            time.sleep(2.0)

    if not found:
        report("I2C bus", FAIL, "no devices (expect 0x40 PCA9685, 0x4a BNO085)")
    else:
        hexstr = ", ".join(f"0x{a:02X}" for a in sorted(found))
        report("I2C bus", PASS, f"scan: {hexstr}")

    bno_ok = 0x4A in found
    pwm_ok = 0x40 in found

    # ---------------- 2. BNO085 - quaternion fusion sanity
    imu = None
    if bno_ok:
        try:
            from sensors.bno085_sensor import BNO085Sensor
            imu = BNO085Sensor(i2c)
            time.sleep(0.5)
            d = imu.read()
            ax, ay, az = d["accel_ms2"]
            gmag = math.sqrt(ax * ax + ay * ay + az * az)
            qn = math.sqrt(sum(v * v for v in d["quaternion"]))
            valid = 8.0 < gmag < 11.0 and abs(qn - 1.0) < 1e-2
            report("BNO085 IMU", PASS if valid else FAIL,
                   f"|g|={gmag:.2f} m/s2 |q|={qn:.4f} cal={imu.bno.calibration_status}/3")
        except Exception as e:
            report("BNO085 IMU", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("BNO085 IMU", SKIP, "0x4a not on bus")

    # ---------------- 3. BMP388 - baro sanity (SPI, independent)
    try:
        from sensors.bmp388_sensor import BMP388Sensor
        spi = bus_manager.get_spi()
        baro = BMP388Sensor(spi)
        time.sleep(0.5)
        b = baro.read()
        press, temp = b["pressure_hpa"], b["temperature_c"]
        valid = 850 < press < 1100 and -10 < temp < 60
        report("BMP388 baro", PASS if valid else FAIL,
               f"P={press:.1f} hPa T={temp:.1f} C alt={b['altitude_m']:.1f} m")
    except Exception as e:
        report("BMP388 baro", FAIL, f"{type(e).__name__}: {e}")

    # ---------------- 4. PCA9685 - servo sweep ch0..2
    if pwm_ok:
        try:
            from actuators.servo_driver import PCA9685Driver
            pwm = PCA9685Driver(i2c)
            pwm.enable_outputs()
            print("  sweeping servos ch0..2 ...")
            servo_sweep(pwm, (0, 1, 2))
            pwm.disable_outputs()
            pwm.deinit()
            report("Servos ch0-2", PASS, "0->180->0 sweep ok")
        except Exception as e:
            report("Servos ch0-2", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("Servos ch0-2", SKIP, "0x40 not on bus")

    # ---------------- 5. ULN2003 stepper - timing accuracy
    try:
        from actuators.stepper_driver import ULN2003Stepper
        s = ULN2003Stepper()
        t0 = time.monotonic()
        s.step(200)
        elapsed = time.monotonic() - t0
        expect = 200 * s.step_delay
        valid = abs(elapsed - expect) < 0.2
        s.step(-200)
        s.release()
        report("ULN2003 stepper", PASS if valid else FAIL,
               f"+/-200 steps {elapsed:.2f}s vs {expect:.2f}s expected")
    except Exception as e:
        report("ULN2003 stepper", FAIL, f"{type(e).__name__}: {e}")

    # ---------------- 6. Buzzer - 3-pip
    try:
        from actuators.buzzer import Buzzer
        bz = Buzzer()
        bz.beep_pattern(count=3, on_time=0.1, off_time=0.1)
        report("Buzzer", PASS, "3-beep pattern sent (audible?)")
    except Exception as e:
        report("Buzzer", FAIL, f"{type(e).__name__}: {e}")

    # ---------------- 7. Gimbal - 3 s orientation-hold sanity
    if bno_ok and pwm_ok:
        try:
            from actuators.gimbal import GimbalController
            from actuators.servo_driver import PCA9685Driver
            from actuators.stepper_driver import ULN2003Stepper
            pwm = PCA9685Driver(i2c)
            pwm.enable_outputs()
            g = GimbalController(imu, pwm, ULN2003Stepper())
            gdt = 1.0 / 50
            t0 = time.monotonic()
            peak = 0.0
            while time.monotonic() - t0 < 3.0:
                roll, tilt, rrate, steps, state, terr = g.update(gdt)
                peak = max(peak, abs(rrate))
                time.sleep(gdt)
            g.release()
            pwm.deinit()
            report("Gimbal loop", PASS,
                   f"3 s @ {gdt * 1000:.0f} ms ticks, peak {peak:.1f} dps, {state}")
        except Exception as e:
            report("Gimbal loop", FAIL, f"{type(e).__name__}: {e}")
    else:
        report("Gimbal loop", SKIP, "needs IMU 0x4a + PCA9685 0x40")

    # ---------------- 8. XBee probe (non-destructive)
    try:
        import serial
        ser = serial.Serial(config.XBEE_SERIAL_PORT, config.XBEE_BAUDRATE,
                            timeout=1.0)
        ser.reset_input_buffer()
        time.sleep(1.5)              # guard-time silence before +++
        ser.write(b"+++")
        time.sleep(1.0)
        ack = ser.read(3).strip()   # expect b'OK' (may carry \r)
        if ack == b"OK":            # leave command mode immediately
            ser.write(b"ATVR\r")
            time.sleep(0.3)
            ver = ser.read(32)
            ser.write(b"CN\r")
            ser.close()
            report("XBee probe", PASS, f"+++ ack=OK, fw {ver.strip()!r}")
        else:
            ser.write(b"CN\r")       # radio may have entered cmd mode despite bad read
            time.sleep(0.2)
            ser.close()
            report("XBee probe", FAIL, f"+++ ack={ack!r}")
    except Exception as e:
        report("XBee probe", FAIL, f"{type(e).__name__}: {e}")

    # ---------------- summary
    print(f"\n{'=' * 60}")
    n_pass = sum(1 for _, st, _ in results if st == PASS)
    n_fail = sum(1 for _, st, _ in results if st == FAIL)
    n_skip = sum(1 for _, st, _ in results if st == SKIP)
    print(f"SUMMARY: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    log = open("/tmp/opencode/test_everything.log", "w")
    orig = sys.stdout

    class Tee:
        def write(self, s):
            orig.write(s)
            log.write(s)
        def flush(self):
            orig.flush()
            log.flush()

    sys.stdout = Tee()
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        log.close()
        sys.stdout = orig
        sys.exit(1 if any(s == FAIL for _, s, _ in results) else 0)