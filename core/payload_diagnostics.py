"""Payload-level diagnostic workers for image quality and storage checks."""

from __future__ import annotations

import csv
from pathlib import Path
import threading
import time

import config
from core.shared_data import SharedData


def _quality_for_image(path: Path) -> dict:
    try:
        import cv2  # type: ignore
        import numpy as np
    except Exception as exc:
        return {"status": "UNAVAILABLE", "reason": f"OpenCV unavailable: {exc}"}

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"status": "FAILED", "reason": "Latest image could not be read."}
    sharpness = float(cv2.Laplacian(image, cv2.CV_64F).var())
    brightness = float(image.mean())
    under = float(np.count_nonzero(image < 20)) / float(image.size)
    over = float(np.count_nonzero(image > 245)) / float(image.size)
    status = "HEALTHY"
    reasons = []
    if sharpness < config.IMAGE_QUALITY_BLUR_WARN_VARIANCE:
        status = "DEGRADED"
        reasons.append(f"sharpness {sharpness:.1f} below threshold")
    if brightness < config.IMAGE_QUALITY_BRIGHTNESS_LOW or brightness > config.IMAGE_QUALITY_BRIGHTNESS_HIGH:
        status = "DEGRADED"
        reasons.append(f"brightness {brightness:.1f} outside threshold")
    if under > config.IMAGE_QUALITY_CLIPPED_WARN_FRACTION:
        status = "DEGRADED"
        reasons.append(f"underexposed {under:.1%}")
    if over > config.IMAGE_QUALITY_CLIPPED_WARN_FRACTION:
        status = "DEGRADED"
        reasons.append(f"overexposed {over:.1%}")
    return {
        "status": status,
        "reason": "; ".join(reasons) if reasons else "Latest image quality acceptable.",
        "sharpness": sharpness,
        "brightness": brightness,
        "underexposed_fraction": under,
        "overexposed_fraction": over,
    }


def image_quality_worker(shared: SharedData, stop_event: threading.Event) -> None:
    """Low-rate, lightweight image-quality diagnostics for latest captured file."""
    last_image = ""
    if not config.IMAGE_QUALITY_ENABLE_LIVE:
        shared.set_worker_disabled("ImageQuality", "Disabled by config.")
        return
    while not stop_event.is_set():
        snap = shared.get_snapshot()
        if not snap.image_name or snap.image_name == last_image:
            stop_event.wait(1.0 / max(config.IMAGE_QUALITY_EXPECTED_HZ, 0.05))
            continue
        last_image = snap.image_name
        image_path = config.IMAGE_SAVE_PATH / Path(snap.image_name).name
        result = _quality_for_image(image_path)
        status = result.get("status", "UNAVAILABLE")
        shared.update(
            image_quality_sharpness=float(result.get("sharpness", 0.0) or 0.0),
            image_quality_brightness=float(result.get("brightness", 0.0) or 0.0),
            image_quality_underexposed_fraction=float(result.get("underexposed_fraction", 0.0) or 0.0),
            image_quality_overexposed_fraction=float(result.get("overexposed_fraction", 0.0) or 0.0),
            image_quality_status=status,
        )
        shared.record_worker_success(
            "ImageQuality",
            expected_hz=config.IMAGE_QUALITY_EXPECTED_HZ,
            reason=str(result.get("reason", "Image quality sampled.")),
            status=status if status in {"HEALTHY", "DEGRADED"} else "DISABLED",
            details=result,
        )
        if status == "DEGRADED":
            shared.record_event("IMAGE_QUALITY_WARNING", "ImageQuality", "WARN", str(result.get("reason", "")), result)
        stop_event.wait(1.0 / max(config.IMAGE_QUALITY_EXPECTED_HZ, 0.05))


def validate_storage(log_path: Path | None) -> dict:
    image_files = {
        path.name
        for path in config.IMAGE_SAVE_PATH.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    } if config.IMAGE_SAVE_PATH.exists() else set()
    referenced: set[str] = set()
    if log_path and log_path.exists():
        try:
            with log_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    name = (row.get("image_name") or "").strip()
                    if name:
                        referenced.add(Path(name).name)
        except Exception:
            pass
    missing = referenced - image_files
    orphan = image_files - referenced if referenced else set()
    return {
        "images_referenced": len(referenced),
        "images_present": len(image_files & referenced) if referenced else len(image_files),
        "images_missing": len(missing),
        "images_orphan": len(orphan),
        "missing_examples": sorted(missing)[:5],
        "orphan_examples": sorted(orphan)[:5],
    }


def storage_validation_worker(
    shared: SharedData,
    stop_event: threading.Event,
    log_path: Path | None,
) -> None:
    """Periodically compare image references in the log against stored files."""
    while not stop_event.is_set():
        result = validate_storage(log_path)
        shared.update(
            images_referenced=result["images_referenced"],
            images_present=result["images_present"],
            images_missing=result["images_missing"],
            images_orphan=result["images_orphan"],
        )
        status = "HEALTHY" if result["images_missing"] == 0 else "DEGRADED"
        reason = "Referenced images are present." if status == "HEALTHY" else f"{result['images_missing']} referenced images missing."
        shared.record_worker_success(
            "Storage",
            expected_hz=config.STORAGE_VALIDATION_EXPECTED_HZ,
            reason=reason,
            status=status,
            details=result,
        )
        if status == "DEGRADED":
            shared.record_event("STORAGE_IMAGE_MISSING", "Storage", "WARN", reason, result)
        stop_event.wait(config.STORAGE_VALIDATION_INTERVAL_SEC)
