"""Constants and paths for Lunar Base.

All paths resolve relative to the lunar-base/ root, so the app works the same
no matter what cwd it is launched from.
"""

from __future__ import annotations

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

LUNAR_TEAR_DIR: Path = (ROOT.parent / "lunar-tear").resolve()
GAME_DB_PATH: Path = (LUNAR_TEAR_DIR / "server" / "db" / "game.db").resolve()
WIZARD_CONFIG_PATH: Path = (LUNAR_TEAR_DIR / "server" / ".wizard.json").resolve()

DATA_DIR: Path = ROOT / "data"
BACKUP_DIR: Path = DATA_DIR / "backups"
MASTERDATA_DIR: Path = DATA_DIR / "masterdata"
NAMES_DIR: Path = DATA_DIR / "names"

GRANT_EXE_PATH: Path = ROOT / "tools" / "grant" / "grant.exe"


def find_master_data_bin() -> Path | None:
    """Locate the encrypted master-data binary inside lunar-tear.

    The filename embeds a build timestamp and changes whenever the game data is
    repatched, so we glob for `*.bin.e` and take the most recently modified.
    Returns None if the file is missing — callers should surface that as a
    user-actionable error.
    """
    release_dir = LUNAR_TEAR_DIR / "server" / "assets" / "release"
    if not release_dir.is_dir():
        return None
    candidates = sorted(release_dir.glob("*.bin.e"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


BACKUP_RETENTION: int = 50

HOST: str = "127.0.0.1"
PORT: int = 8888

LUNAR_TEAR_DEFAULT_GRPC_PORT: int = 8003
