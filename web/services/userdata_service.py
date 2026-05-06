"""Read-only queries against game.db for the user viewer.

The connection is opened in URI read-only mode so even bugs in this module
cannot mutate the game database. WAL mode in lunar-tear means we can read
freely while the server is running.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from web import config


@dataclass(frozen=True)
class UserSummary:
    user_id: int
    uuid: str
    name: str
    level: int
    register_at: datetime | None
    last_login_at: datetime | None
    total_login_count: int


@dataclass(frozen=True)
class StackableSummary:
    label: str
    table: str
    distinct: int
    total: int | None  # None when the underlying "count" column is not a quantity


@dataclass(frozen=True)
class InventoryCount:
    label: str
    table: str
    count: int


@dataclass(frozen=True)
class ItemState:
    user_id: int
    name: str
    paid_gem: int
    free_gem: int
    consumables: dict[int, int]      # id -> count (gold lives at id=1)
    materials: dict[int, int]        # id -> count
    important_items: dict[int, int]  # id -> count


@dataclass(frozen=True)
class UserDetail:
    user_id: int
    uuid: str
    player_id: int
    name: str
    message: str
    register_at: datetime | None
    last_login_at: datetime | None
    total_login_count: int
    level: int
    exp: int
    paid_gem: int
    free_gem: int
    inventory_counts: list[InventoryCount]
    stackables: list[StackableSummary]


# Inventory tables to count for the detail page. Order matters — this is also
# the display order.
_INVENTORY_TABLES: tuple[tuple[str, str], ...] = (
    ("Characters", "user_characters"),
    ("Costumes", "user_costumes"),
    ("Weapons", "user_weapons"),
    ("Companions", "user_companions"),
    ("Thoughts (memoirs)", "user_thoughts"),
    ("Parts", "user_parts"),
)

# Stackable tables. "has_total" is False where the `count` column stores an
# acquisition timestamp instead of a quantity (premium_items).
_STACKABLE_TABLES: tuple[tuple[str, str, bool], ...] = (
    ("Consumable items", "user_consumable_items", True),
    ("Materials", "user_materials", True),
    ("Important items", "user_important_items", True),
    ("Premium items", "user_premium_items", False),
)


@contextmanager
def _readonly_conn() -> Iterator[sqlite3.Connection]:
    if not config.GAME_DB_PATH.exists():
        raise FileNotFoundError(f"Game database not found: {config.GAME_DB_PATH}")
    uri = f"{config.GAME_DB_PATH.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _millis_to_dt(ms: int | None) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OverflowError, OSError, ValueError):
        return None


def list_users() -> list[UserSummary]:
    """Return every user in game.db, ordered by user_id."""
    sql = """
        SELECT
            u.user_id,
            u.uuid,
            u.register_datetime,
            COALESCE(p.name, '')                  AS name,
            COALESCE(s.level, 0)                  AS level,
            COALESCE(l.last_login_datetime, 0)    AS last_login_datetime,
            COALESCE(l.total_login_count, 0)      AS total_login_count
        FROM users u
        LEFT JOIN user_profile p ON p.user_id = u.user_id
        LEFT JOIN user_status  s ON s.user_id = u.user_id
        LEFT JOIN user_login   l ON l.user_id = u.user_id
        ORDER BY u.user_id
    """
    out: list[UserSummary] = []
    with _readonly_conn() as conn:
        for row in conn.execute(sql):
            out.append(UserSummary(
                user_id=row["user_id"],
                uuid=row["uuid"],
                name=row["name"],
                level=row["level"],
                register_at=_millis_to_dt(row["register_datetime"]),
                last_login_at=_millis_to_dt(row["last_login_datetime"]),
                total_login_count=row["total_login_count"],
            ))
    return out


def get_user_detail(user_id: int) -> UserDetail | None:
    """Return a full read-only snapshot of one user, or None if not found."""
    with _readonly_conn() as conn:
        ident = conn.execute(
            """
            SELECT
                u.user_id, u.uuid, u.player_id, u.register_datetime,
                COALESCE(p.name, '')              AS name,
                COALESCE(p.message, '')           AS message,
                COALESCE(s.level, 0)              AS level,
                COALESCE(s.exp, 0)                AS exp,
                COALESCE(g.paid_gem, 0)           AS paid_gem,
                COALESCE(g.free_gem, 0)           AS free_gem,
                COALESCE(l.last_login_datetime, 0) AS last_login_datetime,
                COALESCE(l.total_login_count, 0)   AS total_login_count
            FROM users u
            LEFT JOIN user_profile p ON p.user_id = u.user_id
            LEFT JOIN user_status  s ON s.user_id = u.user_id
            LEFT JOIN user_gem     g ON g.user_id = u.user_id
            LEFT JOIN user_login   l ON l.user_id = u.user_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if ident is None:
            return None

        inventory: list[InventoryCount] = []
        for label, table in _INVENTORY_TABLES:
            sql = f"SELECT COUNT(*) AS c FROM {table} WHERE user_id = ?"
            row = conn.execute(sql, (user_id,)).fetchone()
            inventory.append(InventoryCount(label=label, table=table, count=row["c"]))

        stackables: list[StackableSummary] = []
        for label, table, has_total in _STACKABLE_TABLES:
            if has_total:
                sql = (
                    f"SELECT COUNT(*) AS d, COALESCE(SUM(count), 0) AS t "
                    f"FROM {table} WHERE user_id = ?"
                )
                row = conn.execute(sql, (user_id,)).fetchone()
                stackables.append(StackableSummary(
                    label=label, table=table, distinct=row["d"], total=row["t"],
                ))
            else:
                sql = f"SELECT COUNT(*) AS d FROM {table} WHERE user_id = ?"
                row = conn.execute(sql, (user_id,)).fetchone()
                stackables.append(StackableSummary(
                    label=label, table=table, distinct=row["d"], total=None,
                ))

        return UserDetail(
            user_id=ident["user_id"],
            uuid=ident["uuid"],
            player_id=ident["player_id"],
            name=ident["name"],
            message=ident["message"],
            register_at=_millis_to_dt(ident["register_datetime"]),
            last_login_at=_millis_to_dt(ident["last_login_datetime"]),
            total_login_count=ident["total_login_count"],
            level=ident["level"],
            exp=ident["exp"],
            paid_gem=ident["paid_gem"],
            free_gem=ident["free_gem"],
            inventory_counts=inventory,
            stackables=stackables,
        )


def get_owned_costume_ids(user_id: int) -> set[int]:
    """Return the set of costume_ids the user already has."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT costume_id FROM user_costumes WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["costume_id"] for row in rows}


def get_owned_weapon_ids(user_id: int) -> set[int]:
    """Return the distinct weapon_ids the user already owns at least one of.

    user_weapons is keyed by uuid (a player can own multiple copies of the same
    weapon_id), so DISTINCT is essential.
    """
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT weapon_id FROM user_weapons WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["weapon_id"] for row in rows}


def get_weapon_inventory_count(user_id: int) -> int:
    """Return the total number of weapon rows the user owns (counts duplicates).

    The game enforces a hard 999-row limit on user_weapons; the editor uses
    this to pre-flight grants and reject overflows.
    """
    with _readonly_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM user_weapons WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["c"])


def get_owned_character_ids(user_id: int) -> set[int]:
    """Return the set of character_ids the user owns."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT character_id FROM user_characters WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["character_id"] for row in rows}


def get_owned_companion_ids(user_id: int) -> set[int]:
    """Return the set of companion_ids the user has at least one of."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT companion_id FROM user_companions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["companion_id"] for row in rows}


def get_character_rebirths(user_id: int) -> dict[int, int]:
    """Return character_id -> current rebirth_count for the user."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT character_id, rebirth_count FROM user_character_rebirths "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["character_id"]: row["rebirth_count"] for row in rows}


def get_owned_important_item_ids(user_id: int) -> set[int]:
    """Return the set of important_item_ids the user has at least one of."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT important_item_id FROM user_important_items "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["important_item_id"] for row in rows}


def get_owned_thought_ids(user_id: int) -> set[int]:
    """Return the set of thought_ids (Debris) the user already has."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT thought_id FROM user_thoughts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["thought_id"] for row in rows}


def get_companion_count(user_id: int) -> int:
    """Total number of companion rows owned by the user."""
    with _readonly_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM user_companions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["c"])


def get_companion_levels(user_id: int) -> list[int]:
    """Return one entry per owned companion row, value = current level."""
    with _readonly_conn() as conn:
        rows = conn.execute(
            "SELECT level FROM user_companions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return [int(r["level"]) for r in rows]


def get_costume_count(user_id: int) -> int:
    """Total number of costume rows owned by the user."""
    with _readonly_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM user_costumes WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["c"])


def get_memoir_count(user_id: int) -> int:
    """Total number of memoir (parts) rows owned by the user."""
    with _readonly_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM user_parts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["c"])


@dataclass(frozen=True)
class MemoirRow:
    user_parts_uuid: str
    parts_id: int
    level: int
    parts_status_main_id: int


def list_owned_memoirs(user_id: int) -> list[MemoirRow]:
    """Return every memoir row the user owns, ordered by parts_id then uuid.

    Used by the editor's "Fix Slots" picker so the user can target a
    specific in-inventory memoir.
    """
    with _readonly_conn() as conn:
        rows = conn.execute(
            """
            SELECT user_parts_uuid, parts_id, level, parts_status_main_id
            FROM user_parts
            WHERE user_id = ?
            ORDER BY parts_id, user_parts_uuid
            """,
            (user_id,),
        ).fetchall()
    return [
        MemoirRow(
            user_parts_uuid=str(r["user_parts_uuid"]),
            parts_id=int(r["parts_id"]),
            level=int(r["level"]),
            parts_status_main_id=int(r["parts_status_main_id"]),
        )
        for r in rows
    ]


def get_empty_karma_slot_count(user_id: int) -> int:
    """Karma slots already unlocked but not yet rolled (OddsNumber == 0).

    Used by the Upgrade Manager to preview how many slots Fill All Karma
    Slots will populate. Existing player rolls (OddsNumber > 0) are
    preserved by the action and not counted here.
    """
    with _readonly_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM user_costume_lottery_effects "
            "WHERE user_id = ? AND odds_number = 0",
            (user_id,),
        ).fetchone()
    return int(row["c"])


def get_costume_karma_state(user_id: int) -> dict[int, dict[int, int]]:
    """costume_id -> slot_number -> odds_number.

    Joins user_costumes to user_costume_lottery_effects via the costume
    UUID. Only includes (costume_id, slot) combinations with an actual
    lottery_effects row — i.e., slots that have been unlocked. A slot
    with odds_number=0 means unlocked-but-unrolled.
    """
    with _readonly_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.costume_id, le.slot_number, le.odds_number
            FROM user_costumes c
            JOIN user_costume_lottery_effects le
              ON le.user_id = c.user_id AND le.user_costume_uuid = c.user_costume_uuid
            WHERE c.user_id = ?
            """,
            (user_id,),
        ).fetchall()
    out: dict[int, dict[int, int]] = {}
    for r in rows:
        out.setdefault(int(r["costume_id"]), {})[int(r["slot_number"])] = int(r["odds_number"])
    return out


def get_item_state(user_id: int) -> ItemState | None:
    """Snapshot every stackable category that the Item Editor manages."""
    with _readonly_conn() as conn:
        ident = conn.execute(
            """
            SELECT
                u.user_id,
                COALESCE(p.name, '')    AS name,
                COALESCE(g.paid_gem, 0) AS paid_gem,
                COALESCE(g.free_gem, 0) AS free_gem
            FROM users u
            LEFT JOIN user_profile p ON p.user_id = u.user_id
            LEFT JOIN user_gem     g ON g.user_id = u.user_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if ident is None:
            return None

        def _load(table: str, id_col: str) -> dict[int, int]:
            sql = f"SELECT {id_col} AS pid, count FROM {table} WHERE user_id = ?"
            return {row["pid"]: row["count"] for row in conn.execute(sql, (user_id,))}

        return ItemState(
            user_id=ident["user_id"],
            name=ident["name"],
            paid_gem=ident["paid_gem"],
            free_gem=ident["free_gem"],
            consumables=_load("user_consumable_items", "consumable_item_id"),
            materials=_load("user_materials", "material_id"),
            important_items=_load("user_important_items", "important_item_id"),
        )
