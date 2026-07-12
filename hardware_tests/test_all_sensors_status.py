"""
Overall hardware readiness check (no deep sensor testing).

Verifies project layout, config, libraries, and writable data folders.
Prints a readiness table: Module | Check | Status | Notes

Run from project root:
  python hardware_tests/test_all_sensors_status.py
"""

from __future__ import annotations

import importlib
import shutil
import sys

from hw_common import banner, ensure_dirs, is_raspberry_pi, result, write_log

import config


def check_import(module_name: str) -> tuple[str, str]:
    """Try importing a module; return (PASS/FAIL/WARNING, note)."""
    try:
        importlib.import_module(module_name)
        return "PASS", "imported"
    except ImportError as exc:
        return "FAIL", str(exc)


def check_path_exists(path: Path, label: str) -> tuple[str, str]:
    if path.exists():
        return "PASS", str(path)
    return "FAIL", f"missing: {path}"


def check_writable(path: Path) -> tuple[str, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return "PASS", "writable"
    except Exception as exc:
        return "FAIL", str(exc)


def check_i2c_tools() -> tuple[str, str]:
    if shutil.which("i2cdetect"):
        return "PASS", "i2cdetect available"
    return "WARNING", "install: sudo apt install -y i2c-tools"


def check_picamera2() -> tuple[str, str]:
    try:
        importlib.import_module("picamera2")
        return "PASS", "picamera2 available"
    except ImportError:
        return "WARNING", "sudo apt install -y python3-picamera2"


def main() -> int:
    banner("Hardware Test: All Sensors Status (readiness)")
    ensure_dirs()

    rows: list[tuple[str, str, str, str]] = []

    # --- Project structure ---
    folders = [
        ("Project", "core/", config.PROJECT_ROOT / "core"),
        ("Project", "sensors/", config.PROJECT_ROOT / "sensors"),
        ("Project", "camera/", config.PROJECT_ROOT / "camera"),
        ("Project", "hardware_tests/", config.PROJECT_ROOT / "hardware_tests"),
        ("Data", "data/images/", config.IMAGE_SAVE_PATH),
        ("Data", "data/logs/", config.LOG_SAVE_PATH),
        ("Data", "data/maps/", config.MAP_SAVE_PATH),
        ("Data", "hw test logs/", config.LOG_SAVE_PATH / "hardware_tests"),
    ]
    for module, check, path in folders:
        status, note = check_path_exists(path, check)
        rows.append((module, check, status, note))

    # --- Config ---
    try:
        _ = config.GPS_PORT, config.XBEE_PORT, config.BAROMETER_ADDRESS, config.IMU_ADDRESS
        rows.append(("Config", "import config.py", "PASS", f"GPS={config.GPS_PORT} XBEE={config.XBEE_PORT}"))
    except Exception as exc:
        rows.append(("Config", "import config.py", "FAIL", str(exc)))

    # --- Writable data ---
    for label, path in [
        ("Data", config.LOG_SAVE_PATH),
        ("Data", config.IMAGE_SAVE_PATH),
    ]:
        status, note = check_writable(path)
        rows.append((label, f"writable {path.name}", status, note))

    # --- Platform ---
    on_pi = is_raspberry_pi()
    rows.append((
        "Platform",
        "Raspberry Pi",
        "PASS" if on_pi else "WARNING",
        "detected" if on_pi else "not detected (dev PC?)",
    ))

    # --- I2C ---
    status, note = check_i2c_tools()
    rows.append(("I2C", "i2cdetect", status, note))

    # --- Python packages ---
    packages = [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("pyserial", "serial"),
        ("pynmea2", "pynmea2"),
        ("folium", "folium"),
        ("simplekml", "simplekml"),
        ("Pillow", "PIL"),
        ("opencv", "cv2"),
    ]
    for label, mod in packages:
        status, note = check_import(mod)
        rows.append(("Python", label, status, note))

    # --- Hardware-specific libraries (optional) ---
    status, note = check_picamera2()
    rows.append(("Camera", "picamera2", status, note))

    for label, mod in [
        ("GPIO", "gpiozero"),
        ("Barometer", "adafruit_bmp280"),
        ("IMU", "adafruit_mpu6050"),
    ]:
        status, note = check_import(mod)
        if status == "FAIL":
            status = "WARNING"
            note = f"optional — {note}"
        rows.append(("Hardware lib", label, status, note))

    # --- Print table ---
    col_w = [12, 22, 10, 40]
    header = ("Module", "Check", "Status", "Notes")
    print(f"{header[0]:<{col_w[0]}} | {header[1]:<{col_w[1]}} | {header[2]:<{col_w[2]}} | {header[3]}")
    print("-" * 90)

    log_lines = []
    fail_count = warn_count = 0
    for module, check, status, notes in rows:
        print(f"{module:<{col_w[0]}} | {check:<{col_w[1]}} | {status:<{col_w[2]}} | {notes}")
        log_lines.append(f"{module} | {check} | {status} | {notes}")
        if status == "FAIL":
            fail_count += 1
        elif status == "WARNING":
            warn_count += 1

    print()
    if fail_count == 0 and warn_count == 0:
        result("PASS", "All readiness checks passed.")
        code = 0
    elif fail_count == 0:
        result("WARNING", f"{warn_count} warning(s) — some hardware libs not installed yet.")
        code = 2
    else:
        result("FAIL", f"{fail_count} failed, {warn_count} warning(s).")
        code = 1

    log_path = write_log("test_all_sensors_status.log", log_lines)
    print(f"Log saved: {log_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
