"""Interactive servo tests."""

from __future__ import annotations

from config import AppConfig
from hardware.servo import ServoController
from utils.helpers import HardwareError
from utils.logger import ToolkitLogger


def _move(logger: ToolkitLogger, servo: ServoController, angle: float) -> None:
    servo.move_to_angle(angle)
    logger.success(f"Servo moved to {angle:g} degrees")


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Run the servo test menu."""
    servo = ServoController(config.servo)
    while True:
        print("\nServo Test")
        print("1 Move to 0 degrees")
        print("2 Move to 45 degrees")
        print("3 Move to 90 degrees")
        print("4 Move to 135 degrees")
        print("5 Move to 180 degrees")
        print("6 Sweep Test")
        print("7 Custom Angle")
        print("8 Stop PWM")
        print("0 Back")
        choice = input("Select: ").strip()

        try:
            if choice == "1":
                _move(logger, servo, 0)
            elif choice == "2":
                _move(logger, servo, 45)
            elif choice == "3":
                _move(logger, servo, 90)
            elif choice == "4":
                _move(logger, servo, 135)
            elif choice == "5":
                _move(logger, servo, 180)
            elif choice == "6":
                servo.sweep()
                logger.success("Servo sweep completed")
            elif choice == "7":
                angle = float(input("Angle: ").strip())
                _move(logger, servo, angle)
            elif choice == "8":
                servo.stop()
                logger.success("Servo PWM stopped")
            elif choice == "0":
                return True
            else:
                logger.warning("Invalid servo menu option")
        except (HardwareError, ValueError) as exc:
            logger.error(str(exc))
            servo.close()
            return False
        finally:
            if choice in {"0", "8"}:
                servo.close()


def quick_check(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Move the servo through a small validation sequence."""
    servo = ServoController(config.servo)
    try:
        servo.move_to_angle(90)
        servo.stop()
        logger.success("Servo responded")
        return True
    except (HardwareError, ValueError) as exc:
        logger.error(f"Servo test failed: {exc}")
        return False
    finally:
        servo.close()
