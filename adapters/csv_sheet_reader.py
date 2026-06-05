"""CSV adapter — reads client entries from a local CSV file with mtime caching.

The CSV must have a header row with `ip` and `nombre` columns. The file is
re-read only when its mtime changes, so repeated API calls don't pay the
parse cost.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from core.models import SheetEntry
from core.interfaces import SheetReader

logger = logging.getLogger(__name__)


REQUIRED_HEADERS = ("ip", "nombre")


class CSVSheetReader(SheetReader):
    """Reads IP → client-name mappings from a local CSV file."""

    def __init__(self, csv_path: Path | None = None) -> None:
        from core.config import config
        self._csv_path: Path = csv_path or config.csv_path
        self._cached_mtime: float = 0.0
        self._cached_entries: list[SheetEntry] = []

    async def read_entries(self) -> list[SheetEntry]:
        path = self._csv_path

        if not path.exists():
            logger.warning("CSV not found at %s — returning empty list", path)
            return []

        mtime = path.stat().st_mtime
        if self._cached_entries and self._cached_mtime == mtime:
            return list(self._cached_entries)

        entries = self._parse(path)
        self._cached_mtime = mtime
        self._cached_entries = entries
        logger.info("Loaded %d entries from %s", len(entries), path)
        return list(entries)

    @staticmethod
    def _parse(path: Path) -> list[SheetEntry]:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                logger.warning("CSV %s is empty — returning empty list", path)
                return []
            missing = [h for h in REQUIRED_HEADERS if h not in reader.fieldnames]
            if missing:
                raise ValueError(
                    f"CSV {path} is missing required headers: {missing}. "
                    f"Found: {reader.fieldnames}"
                )
            return [
                SheetEntry(ip=row["ip"].strip(), name=row["nombre"].strip())
                for row in reader
                if row.get("ip") and row.get("ip", "").strip()
            ]
