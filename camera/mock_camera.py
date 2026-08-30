"""Camera implementations used by the payload runtime and development tests."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)


class MockCamera:
    """Creates placeholder images for pre-hardware development."""

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or config.IMAGE_SAVE_PATH
        self.save_path.mkdir(parents=True, exist_ok=True)
        self._open = True
        logger.info("MockCamera ready — saving to %s", self.save_path)

    def capture(self, latitude: float = 0.0, longitude: float = 0.0) -> str:
        """
        Capture a placeholder image and return the filename.

        Args:
            latitude: GPS latitude for overlay text.
            longitude: GPS longitude for overlay text.

        Returns:
            Image filename (not full path).
        """
        if not self._open:
            raise RuntimeError("MockCamera is closed.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{timestamp}.jpg"
        filepath = self.save_path / filename

        try:
            img = Image.new("RGB", (640, 480), color=(30, 60, 90))
            draw = ImageDraw.Draw(img)
            text_lines = [
                "MOCK CAMERA",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                f"Lat: {latitude:.6f}",
                f"Lon: {longitude:.6f}",
            ]
            y = 20
            for line in text_lines:
                draw.text((20, y), line, fill=(255, 255, 255))
                y += 30
            img.save(filepath, "JPEG", quality=85)
            logger.debug("Captured mock image: %s", filename)
            return filename
        except Exception as exc:
            logger.error("Mock camera capture failed: %s", exc)
            raise

    def close(self) -> None:
        self._open = False
        logger.info("MockCamera closed.")


class RealCamera:
    """Capture frames from a Raspberry Pi camera or USB/OpenCV camera."""

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or config.IMAGE_SAVE_PATH
        self.save_path.mkdir(parents=True, exist_ok=True)
        self._backend = str(getattr(config, "CAMERA_BACKEND", "AUTO")).upper()
        self._picam2: Any | None = None
        self._opencv_capture: Any | None = None
        self._mode = ""
        self._open()

    def _open(self) -> None:
        if self._backend in ("AUTO", "PICAMERA2") and self._try_open_picamera2():
            return
        if self._backend in ("AUTO", "OPENCV") and self._try_open_opencv():
            return
        raise RuntimeError(
            "No real camera backend opened. Install/configure picamera2 for CSI "
            "camera or opencv-python with a visible camera device."
        )

    def _try_open_picamera2(self) -> bool:
        picam2 = None
        try:
            from picamera2 import Picamera2  # type: ignore
        except Exception as exc:
            logger.debug("Picamera2 unavailable: %s", exc)
            return False

        try:
            picam2 = Picamera2()
            size = (
                int(getattr(config, "CAMERA_FRAME_WIDTH", 1280)),
                int(getattr(config, "CAMERA_FRAME_HEIGHT", 720)),
            )
            picam2.configure(picam2.create_still_configuration(main={"size": size}))
            picam2.start()
            self._picam2 = picam2
            self._mode = "picamera2"
            logger.info("RealCamera ready with Picamera2 at %sx%s.", *size)
            return True
        except Exception as exc:
            logger.warning("Picamera2 camera open failed: %s", exc)
            if picam2 is not None:
                try:
                    picam2.close()
                except Exception:
                    pass
            return False

    def _try_open_opencv(self) -> bool:
        try:
            import cv2  # type: ignore
        except Exception as exc:
            logger.debug("OpenCV unavailable: %s", exc)
            return False

        try:
            cap = cv2.VideoCapture(int(getattr(config, "CAMERA_DEVICE_INDEX", 0)))
            if not cap.isOpened():
                cap.release()
                return False
            width = int(getattr(config, "CAMERA_FRAME_WIDTH", 1280))
            height = int(getattr(config, "CAMERA_FRAME_HEIGHT", 720))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._opencv_capture = cap
            self._mode = "opencv"
            logger.info("RealCamera ready with OpenCV device %s.", config.CAMERA_DEVICE_INDEX)
            return True
        except Exception as exc:
            logger.warning("OpenCV camera open failed: %s", exc)
            return False

    def capture(self, latitude: float = 0.0, longitude: float = 0.0) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{timestamp}.jpg"
        filepath = self.save_path / filename

        if self._mode == "picamera2" and self._picam2 is not None:
            self._picam2.capture_file(str(filepath))
            return filename

        if self._mode == "opencv" and self._opencv_capture is not None:
            import cv2  # type: ignore

            ok, frame = self._opencv_capture.read()
            if not ok or frame is None:
                raise RuntimeError("OpenCV camera frame read failed.")
            cv2.imwrite(str(filepath), frame)
            return filename

        raise RuntimeError("Real camera is not open.")

    def close(self) -> None:
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                logger.debug("Picamera2 close failed.", exc_info=True)
            self._picam2 = None
        if self._opencv_capture is not None:
            try:
                self._opencv_capture.release()
            except Exception:
                logger.debug("OpenCV camera close failed.", exc_info=True)
            self._opencv_capture = None
