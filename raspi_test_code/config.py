"""Configuration loading for the Raspberry Pi hardware test toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = BASE_DIR / "settings.yaml"


class ConfigurationError(ValueError):
    """Raised when settings.yaml is missing required values."""


@dataclass(frozen=True)
class BoardConfig:
    pin_numbering: str
    spi0_mosi_gpio: int
    spi0_miso_gpio: int
    spi0_sclk_gpio: int


@dataclass(frozen=True)
class CameraConfig:
    resolution: tuple[int, int]
    preview: bool
    image_dir: Path
    video_dir: Path
    video_seconds: int
    continuous_interval_seconds: float


@dataclass(frozen=True)
class ServoConfig:
    gpio: int
    min_pulse: int
    max_pulse: int
    min_angle: int
    max_angle: int
    settle_seconds: float


@dataclass(frozen=True)
class BNO085Config:
    interface: str
    sck_gpio: int
    mosi_gpio: int
    miso_gpio: int
    cs_gpio: int
    reset_gpio: int
    int_gpio: int
    refresh_hz: int


@dataclass(frozen=True)
class BMP388Config:
    interface: str
    address: int
    sck_gpio: int
    mosi_gpio: int
    miso_gpio: int
    cs_gpio: int
    int_gpio: int
    sea_level_pressure_hpa: float
    refresh_hz: int


@dataclass(frozen=True)
class LoggingConfig:
    save_logs: bool
    level: str
    directory: Path


@dataclass(frozen=True)
class AppConfig:
    board: BoardConfig
    camera: CameraConfig
    servo: ServoConfig
    bno085: BNO085Config
    bmp388: BMP388Config
    logging: LoggingConfig


def _required(data: dict[str, Any], section: str, key: str) -> Any:
    try:
        return data[section][key]
    except KeyError as exc:
        raise ConfigurationError(f"Missing required setting: {section}.{key}") from exc


def _project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def _parse_i2c_address(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ConfigurationError(f"Invalid I2C address value: {value!r}")


def load_config(settings_path: str | Path = DEFAULT_SETTINGS_PATH) -> AppConfig:
    """Load and validate the YAML settings file."""
    path = Path(settings_path)
    if not path.exists():
        raise ConfigurationError(f"Settings file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}

    resolution = _required(raw, "camera", "resolution")
    if len(resolution) != 2:
        raise ConfigurationError("camera.resolution must contain width and height")

    return AppConfig(
        board=BoardConfig(
            pin_numbering=str(_required(raw, "board", "pin_numbering")),
            spi0_mosi_gpio=int(_required(raw, "board", "spi0_mosi_gpio")),
            spi0_miso_gpio=int(_required(raw, "board", "spi0_miso_gpio")),
            spi0_sclk_gpio=int(_required(raw, "board", "spi0_sclk_gpio")),
        ),
        camera=CameraConfig(
            resolution=(int(resolution[0]), int(resolution[1])),
            preview=bool(_required(raw, "camera", "preview")),
            image_dir=_project_path(_required(raw, "camera", "image_dir")),
            video_dir=_project_path(_required(raw, "camera", "video_dir")),
            video_seconds=int(_required(raw, "camera", "video_seconds")),
            continuous_interval_seconds=float(
                _required(raw, "camera", "continuous_interval_seconds")
            ),
        ),
        servo=ServoConfig(
            gpio=int(_required(raw, "servo", "gpio")),
            min_pulse=int(_required(raw, "servo", "min_pulse")),
            max_pulse=int(_required(raw, "servo", "max_pulse")),
            min_angle=int(_required(raw, "servo", "min_angle")),
            max_angle=int(_required(raw, "servo", "max_angle")),
            settle_seconds=float(_required(raw, "servo", "settle_seconds")),
        ),
        bno085=BNO085Config(
            interface=str(_required(raw, "bno085", "interface")).lower(),
            sck_gpio=int(_required(raw, "bno085", "sck_gpio")),
            mosi_gpio=int(_required(raw, "bno085", "mosi_gpio")),
            miso_gpio=int(_required(raw, "bno085", "miso_gpio")),
            cs_gpio=int(_required(raw, "bno085", "cs_gpio")),
            reset_gpio=int(_required(raw, "bno085", "reset_gpio")),
            int_gpio=int(_required(raw, "bno085", "int_gpio")),
            refresh_hz=int(_required(raw, "bno085", "refresh_hz")),
        ),
        bmp388=BMP388Config(
            interface=str(_required(raw, "bmp388", "interface")).lower(),
            address=_parse_i2c_address(_required(raw, "bmp388", "address")),
            sck_gpio=int(_required(raw, "bmp388", "sck_gpio")),
            mosi_gpio=int(_required(raw, "bmp388", "mosi_gpio")),
            miso_gpio=int(_required(raw, "bmp388", "miso_gpio")),
            cs_gpio=int(_required(raw, "bmp388", "cs_gpio")),
            int_gpio=int(_required(raw, "bmp388", "int_gpio")),
            sea_level_pressure_hpa=float(
                _required(raw, "bmp388", "sea_level_pressure_hpa")
            ),
            refresh_hz=int(_required(raw, "bmp388", "refresh_hz")),
        ),
        logging=LoggingConfig(
            save_logs=bool(_required(raw, "logging", "save_logs")),
            level=str(_required(raw, "logging", "level")).upper(),
            directory=_project_path(_required(raw, "logging", "directory")),
        ),
    )
