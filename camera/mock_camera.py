"""
Mock camera — generates placeholder JPEG images with timestamp text.

Uses Pillow to create simple annotated frames saved to data/images/.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

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
    """
    Placeholder for Raspberry Pi HQ / Arducam via picamera2 or OpenCV.

    Implement when the camera module arrives.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or config.IMAGE_SAVE_PATH
        self.save_path.mkdir(parents=True, exist_ok=True)
        logger.warning("RealCamera is a stub — implement picamera2/OpenCV capture.")

    def capture(self, latitude: float = 0.0, longitude: float = 0.0) -> str:
        raise NotImplementedError("Real camera driver not yet implemented.")

    def close(self) -> None:
        pass
