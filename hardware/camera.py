"""Raspberry Pi Camera Module control using Picamera2."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from config import CameraConfig
from utils.helpers import HardwareError, ensure_directory, timestamp_slug


@dataclass
class CameraController:
    """Capture images, preview, and record video with Picamera2."""

    config: CameraConfig

    def __post_init__(self) -> None:
        self._camera = None

    def connect(self) -> None:
        """Initialize Picamera2."""
        if self._camera is not None:
            return
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise HardwareError("Picamera2 is not installed.") from exc

        try:
            camera = Picamera2()
            still_config = camera.create_still_configuration(
                main={"size": self.config.resolution}
            )
            camera.configure(still_config)
            self._camera = camera
        except Exception as exc:
            raise HardwareError(f"Camera initialization failed: {exc}") from exc

    def capture_image(self) -> Path:
        """Capture a timestamped image and return its path."""
        self.connect()
        directory = ensure_directory(self.config.image_dir)
        path = directory / f"image_{timestamp_slug()}.jpg"
        self._camera.start()
        try:
            self._camera.capture_file(str(path))
        finally:
            self._camera.stop()
        return path

    def preview(self, seconds: int | None = None) -> None:
        """Start camera preview until Enter is pressed or a timeout expires."""
        self.connect()
        self._camera.start_preview()
        self._camera.start()
        try:
            if seconds is None:
                input("Preview running. Press Enter to stop...")
            else:
                time.sleep(seconds)
        finally:
            self._camera.stop_preview()
            self._camera.stop()


    def record_video(self, seconds: int | None = None) -> Path:
        """Record a timestamped video and return its path."""
        self.connect()
        duration = seconds or self.config.video_seconds
        directory = ensure_directory(self.config.video_dir)
        path = directory / f"video_{timestamp_slug()}.h264"
        video_config = self._camera.create_video_configuration(
            main={"size": self.config.resolution}
        )
        self._camera.configure(video_config)
        try:
            from picamera2.encoders import H264Encoder
            from picamera2.outputs import FileOutput
        except ImportError as exc:
            raise HardwareError("Picamera2 H264 encoder support is unavailable.") from exc

        encoder = H264Encoder()
        output = FileOutput(str(path))
        self._camera.start_recording(encoder, output)
        try:
            time.sleep(duration)
        finally:
            self._camera.stop_recording()
        return path


    def continuous_capture(self) -> None:
        """Capture images repeatedly until interrupted."""
        self.connect()
        print("Continuous capture running. Press CTRL+C to stop.")
        try:
            while True:
                path = self.capture_image()
                print(f"Saved {path}")
                time.sleep(self.config.continuous_interval_seconds)
        except KeyboardInterrupt:
            print("Continuous capture stopped.")

    def close(self) -> None:
        """Close the camera if Picamera2 exposes a close method."""
        if self._camera is not None:
            close = getattr(self._camera, "close", None)
            if callable(close):
                close()
            self._camera = None

    def __enter__(self) -> "CameraController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
