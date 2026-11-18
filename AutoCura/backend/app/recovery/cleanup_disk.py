"""
AutoCura - Disk Cleanup Recovery Action

Safety-critical module: this must NEVER touch arbitrary paths on the
host machine. Cleanup only ever targets a project-local scratch
directory that AutoCura itself creates and fills for simulation
purposes (see api/simulation.py's disk-pressure endpoint), so it works
identically whether or not Docker is even installed -- there is no
"real disk" recovery target on a student's laptop that would be safe
to touch, so this module never widens scope to one.
"""

import os
import shutil

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Project-local only -- never derived from user input, never an absolute
# path outside the project, never widened by a caller-supplied argument.
_SCRATCH_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".autocura_scratch")


def scratch_dir() -> str:
    os.makedirs(_SCRATCH_DIR, exist_ok=True)
    return os.path.abspath(_SCRATCH_DIR)


def fill_scratch_dir(num_files: int = 20, size_mb: int = 5) -> dict:
    """Used by the disk-pressure simulation endpoint to create controlled junk to clean up."""
    path = scratch_dir()
    for i in range(num_files):
        with open(os.path.join(path, f"junk_{i}.bin"), "wb") as fh:
            fh.write(os.urandom(size_mb * 1024 * 1024))
    return {"files_created": num_files, "path": path}


def cleanup_disk() -> dict:
    path = scratch_dir()
    removed = 0
    freed_bytes = 0

    for entry in os.scandir(path):
        try:
            if entry.is_file():
                freed_bytes += entry.stat().st_size
                os.remove(entry.path)
                removed += 1
            elif entry.is_dir():
                freed_bytes += sum(
                    f.stat().st_size for f in os.scandir(entry.path) if f.is_file()
                )
                shutil.rmtree(entry.path)
                removed += 1
        except OSError as exc:
            logger.warning("Could not remove %s during disk cleanup: %s", entry.path, exc)

    logger.info("Disk cleanup removed %d items (%.1f MB) from %s", removed, freed_bytes / (1024 * 1024), path)
    return {
        "success": True,
        "simulated": False,
        "removed_items": removed,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "message": f"Removed {removed} item(s), freeing {round(freed_bytes / (1024 * 1024), 2)} MB.",
    }
