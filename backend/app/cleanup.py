"""Remove abandoned request directories older than 24 hours; never follow symlinks."""
from pathlib import Path
import shutil
import time

from .config import settings


def cleanup(root: Path | None = None, now: float | None = None) -> int:
    directory = (root or settings().upload_dir).resolve()
    if not directory.exists():
        return 0
    cutoff = (time.time() if now is None else now) - 86400
    count = 0
    for child in directory.iterdir():
        if child.is_symlink() or not child.name.startswith("request-") or not child.is_dir():
            continue
        target = child.resolve()
        if target.parent != directory or child.stat().st_mtime >= cutoff:
            continue
        shutil.rmtree(target)
        count += 1
    return count


if __name__ == "__main__":
    print(f"Removed {cleanup()} abandoned upload directories")
