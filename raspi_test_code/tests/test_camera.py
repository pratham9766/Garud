"""Interactive Raspberry Pi camera tests."""

from __future__ import annotations

from config import AppConfig
from hardware.camera import CameraController
from utils.helpers import HardwareError
from utils.logger import ToolkitLogger


def run(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Run the camera test menu."""
    camera = CameraController(config.camera)
    while True:
        print("\nCamera Test")
        print("1 Capture Image")
        print("2 Preview Camera")
        print("3 Record 10 sec Video")
        print("4 Continuous Capture")
        print("0 Back")
        choice = input("Select: ").strip()

        try:
            if choice == "1":
                path = camera.capture_image()
                logger.success(f"Image saved: {path}")
            elif choice == "2":
                camera.preview()
                logger.success("Preview completed")
            elif choice == "3":
                path = camera.record_video(config.camera.video_seconds)
                logger.success(f"Video saved: {path}")
            elif choice == "4":
                camera.continuous_capture()
            elif choice == "0":
                return True
            else:
                logger.warning("Invalid camera menu option")
        except HardwareError as exc:
            logger.error(str(exc))
            return False
        finally:
            camera.close()


def quick_check(logger: ToolkitLogger, config: AppConfig) -> bool:
    """Detect whether the camera can be initialized."""
    camera = CameraController(config.camera)
    try:
        camera.connect()
        logger.success("Camera detected")
        return True
    except HardwareError as exc:
        logger.error(f"Camera not detected: {exc}")
        return False
    finally:
        camera.close()
