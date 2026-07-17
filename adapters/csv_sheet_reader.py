"""CSV adapter — reads client entries from a local CSV file with mtime caching.

The CSV must have a header row with `ip` and `nombre` columns. The file is
re-read only when its mtime changes, so repeated API calls don't pay the
parse cost.
"""

from __future__ import annotations

import csv
import ipaddress
import logging
from pathlib import Path

from core.interfaces import SheetReader
from core.models import SheetEntry

logger = logging.getLogger(__name__)


REQUIRED_HEADERS = ("ip", "nombre")


class CSVSheetReader(SheetReader):
    """Reads IP → client-name mappings from a local CSV file."""

    def __init__(self, csv_path: Path | None = None) -> None:
        from core.config import AppConfig

        self._csv_path: Path = csv_path or AppConfig().csv_path
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
                    f"CSV {path} is missing required headers: {missing}. Found: {reader.fieldnames}"
                )
            entries: list[SheetEntry] = []
            for line, row in enumerate(reader, start=2):
                ip = (row.get("ip") or "").strip()
                name = (row.get("nombre") or "").strip()
                if not ip and not name:
                    continue
                if not ip:
                    raise ValueError(f"CSV {path}, line {line}: IP is required")
                if not name:
                    raise ValueError(f"CSV {path}, line {line}: nombre is required")
                try:
                    network = (
                        ipaddress.ip_network(ip, strict=False)
                        if "/" in ip
                        else ipaddress.ip_address(ip)
                    )
                except ValueError as exc:
                    raise ValueError(f"CSV {path}, line {line}: invalid IP/CIDR {ip!r}") from exc
                entries.append(SheetEntry(ip=str(network), name=name, line=line))
            return entries
