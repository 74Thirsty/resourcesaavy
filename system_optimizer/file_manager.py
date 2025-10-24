"""File management utilities for the System Optimizer."""

from __future__ import annotations

import heapq
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

from .logging_config import get_logger

file_logger = get_logger("File Management")


@dataclass
class FileInfo:
    path: Path
    size: int


class DiskScanner:
    """Scan for large files and directories."""

    def __init__(self, root: Path, max_results: int = 50) -> None:
        self.root = root
        self.max_results = max_results

    def scan(self) -> List[FileInfo]:
        heap: List[Tuple[int, Path]] = []
        for path in self._walk_paths():
            try:
                size = path.stat().st_size
            except (PermissionError, FileNotFoundError):
                continue
            heapq.heappush(heap, (size, path))
            if len(heap) > self.max_results:
                heapq.heappop(heap)
        results = [FileInfo(path=p, size=s) for s, p in sorted(heap, reverse=True)]
        file_logger.info("Identified %d large files", len(results))
        return results

    def _walk_paths(self) -> Iterator[Path]:
        for dirpath, _, filenames in os.walk(self.root):
            for filename in filenames:
                yield Path(dirpath) / filename


class FileSearch:
    """Search for files matching a term."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def search(self, name: str = "", extension: str = "", min_size: int = 0) -> List[FileInfo]:
        matches: List[FileInfo] = []
        for path in self._walk_paths():
            if name and name.lower() not in path.name.lower():
                continue
            if extension and not path.name.lower().endswith(extension.lower()):
                continue
            try:
                size = path.stat().st_size
            except (PermissionError, FileNotFoundError):
                continue
            if size < min_size:
                continue
            matches.append(FileInfo(path=path, size=size))
        file_logger.info("Found %d files for search criteria", len(matches))
        return matches

    def _walk_paths(self) -> Iterator[Path]:
        for dirpath, _, filenames in os.walk(self.root):
            for filename in filenames:
                yield Path(dirpath) / filename


def delete_files(paths: Iterable[Path]) -> List[Path]:
    removed: List[Path] = []
    for path in paths:
        try:
            path.unlink()
            removed.append(path)
            file_logger.info("Deleted file %s", path)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            file_logger.error("Failed to delete %s: %s", path, exc)
    return removed
