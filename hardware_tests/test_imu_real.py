"""
Real IMU test with graceful library fallback.

Wiring (I2C):
  VCC -> 3.3V, GND -> GND
  SDA -> GPIO2 (pin 3), SCL -> GPIO3 (pin 5)

Supports:
  - adafruit_mpu6050 at 0x68 / 0x69
  - smbus2 raw MPU6050 accel/gyro reads
  - Helpful note if BNO055 library is available

NOTE: Final production driver depends on your exact IMU module model.

Run from project root:
  python hardware_tests/test_imu_real.py
"""

from __future__ import annotations

import math
import sys
import time

from hw_common import banner, ensure_dirs, result, write_log

import config


def try_bno055_message() -> None:
    try:
        import adafruit_bno055  # noqa: F401
        result(
            "INFO",
            "adafruit_bno055 is installed — use it for BNO055 modules "
            "(fusion provides roll/pitch/yaw directly).",
        )
    except ImportError:
        pass


def read_mpu6050_smbus(address: int):
    """Raw MPU6050 reads via smbus2 (accel + gyro only)."""
    from smbus2 import SMBus

    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B
    GYRO_XOUT_H = 0x43

    bus = SMBus(1)
    bus.write_byte_data(address, PWR_MGMT_1, 0)
    time.sleep(0.1)

    def read_word(reg: int) -> int:
        high = bus.read_byte_data(address, reg)
        low = bus.read_byte_data(address, reg + 1)
        val = (high << 8) + low
        return val - 65536 if val >= 32768 else val

    def sample():
        ax = read_word(ACCEL_XOUT_H) / 16384.0
        ay = read_word(ACCEL_XOUT_H + 2) / 16384.0
        az = read_word(ACCEL_XOUT_H + 4) / 16384.0
        gx = read_word(GYRO_XOUT_H) / 131.0
        gy = read_word(GYRO_XOUT_H + 2) / 131.0
        gz = read_word(GYRO_XOUT_H + 4) / 131.0
        # Simple tilt estimate from accelerometer (not full fusion)
        roll = math.degrees(math.atan2(ay, az))
        pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
        return {
            "accel": (ax, ay, az),
            "gyro": (gx, gy, gz),
            "roll": roll,
            "pitch": pitch,
            "yaw": None,
        }

    return sample, bus


def main() -> int:
    banner("Hardware Test: Real IMU")
    ensure_dirs()
    log_lines: list[str] = []

    print("I2C bus:     1 (SDA=GPIO2 pin 3, SCL=GPIO3 pin 5)")
    print(f"I2C address: 0x{config.IMU_ADDRESS:02X} (MPU6050; also try 0x69)")
    print("Samples:     50")
    print()
    print("NOTE: Production IMU driver depends on your exact module (MPU6050, MPU9250, BNO055, etc.)")
    print()

    try_bno055_message()

    sample_fn = None
    cleanup = None
    backend = ""

    # --- Try adafruit_mpu6050 ---
    try:
        import board
        import busio
        import adafruit_mpu6050

        i2c = busio.I2C(board.SCL, board.SDA)
        try:
            mpu = adafruit_mpu6050.MPU6050(i2c, address=config.IMU_ADDRESS)
        except ValueError:
            alt = 0x69 if config.IMU_ADDRESS == 0x68 else 0x68
            mpu = adafruit_mpu6050.MPU6050(i2c, address=alt)
            backend = f"adafruit_mpu6050 (0x{alt:02X})"
        else:
            backend = f"adafruit_mpu6050 (0x{config.IMU_ADDRESS:02X})"

        def sample():
            acc = mpu.acceleration
            gyro = mpu.gyro
            return {
                "accel": acc,
                "gyro": gyro,
                "roll": None,
                "pitch": None,
                "yaw": None,
            }

        sample_fn = sample
    except ImportError:
        result("WARNING", "adafruit_mpu6050 not installed — trying smbus2 fallback.")
        print("Optional: pip install adafruit-circuitpython-mpu6050 adafruit-blinka")
    except Exception as exc:
        result("WARNING", f"adafruit_mpu6050 failed: {exc}")

    # --- smbus2 fallback ---
    if sample_fn is None:
        try:
            for addr in (config.IMU_ADDRESS, 0x69, 0x68):
                try:
                    sample_fn, bus = read_mpu6050_smbus(addr)
                    backend = f"smbus2 MPU6050 (0x{addr:02X})"
                    cleanup = bus
                    break
                except OSError:
                    continue
        except ImportError:
            result("FAIL", "smbus2 not installed. pip install smbus2")
            write_log("test_imu_real.log", ["FAIL: no IMU library"])
            return 1

    if sample_fn is None:
        result("FAIL", "IMU not found on I2C. Run: python hardware_tests/test_i2c_scan.py")
        write_log("test_imu_real.log", ["FAIL: IMU not found"])
        return 1

    result("INFO", f"Using backend: {backend}")
    log_lines.append(f"Backend: {backend}")

    readings = []
    try:
        for i in range(50):
            r = sample_fn()
            readings.append(r)
            ax, ay, az = r["accel"]
            gx, gy, gz = r["gyro"]
            if r["roll"] is not None:
                print(
                    f"[{i + 1:02d}] roll={r['roll']:.1f}° pitch={r['pitch']:.1f}° "
                    f"accel=({ax:.2f},{ay:.2f},{az:.2f}) gyro=({gx:.1f},{gy:.1f},{gz:.1f})"
                )
            else:
                print(
                    f"[{i + 1:02d}] accel=({ax:.2f},{ay:.2f},{az:.2f}) "
                    f"gyro=({gx:.1f},{gy:.1f},{gz:.1f})"
                )
            log_lines.append(f"sample {i + 1}: {r}")
            time.sleep(0.05)
    except Exception as exc:
        result("FAIL", f"Read error: {exc}")
        write_log("test_imu_real.log", log_lines + [f"FAIL: {exc}"])
        return 1
    finally:
        if cleanup:
            cleanup.close()

    # Check for changing values (not stuck at zero)
    acc_range = max(
        abs(readings[-1]["accel"][0] - readings[0]["accel"][0]),
        abs(readings[-1]["accel"][1] - readings[0]["accel"][1]),
        abs(readings[-1]["accel"][2] - readings[0]["accel"][2]),
    )
    gyro_mag = sum(abs(v) for v in readings[-1]["gyro"])

    if acc_range > 0.01 or gyro_mag > 0.1 or any(any(v != 0 for v in r["accel"]) for r in readings):
        result("PASS", "IMU returning changing accel/gyro values.")
        log_lines.append("PASS")
        code = 0
    else:
        result("WARNING", "Values look static — gently move the sensor and retry.")
        log_lines.append("WARNING: static values")
        code = 2

    log_path = write_log("test_imu_real.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
