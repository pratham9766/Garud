"""Entry point for the Raspberry Pi hardware test utility."""

from __future__ import annotations

from config import ConfigurationError, load_config
from menu import run_menu
from utils.logger import build_logger


def main() -> int:
    """Load configuration, initialize logging, and start the menu."""
    try:
        config = load_config()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2

    logger = build_logger(
        save_logs=config.logging.save_logs,
        log_dir=config.logging.directory,
        level=config.logging.level,
    )
    logger.info("Loaded settings.yaml")
    run_menu(config, logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
