import time

_OPEN_UNTIL = 0.0
COOLDOWN_SECONDS = 30


def is_open() -> bool:
  return time.monotonic() < _OPEN_UNTIL


def trip() -> None:
  global _OPEN_UNTIL
  _OPEN_UNTIL = time.monotonic() + COOLDOWN_SECONDS


def reset() -> None:
  global _OPEN_UNTIL
  _OPEN_UNTIL = 0.0
