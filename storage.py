"""SQLite storage for member availability, scoped per guild."""

import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

BUSYNESS_MIN = 1
BUSYNESS_MAX = 5


@dataclass
class Status:
    guild_id: int
    user_id: int
    busyness: int
    note: Optional[str]
    updated_at: int  # unix timestamp (seconds)


class Storage:
    def __init__(self, path: str = "availability.db"):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS availability (
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                busyness   INTEGER NOT NULL,
                note       TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self.conn.commit()

    @staticmethod
    def _check_busyness(busyness: int) -> None:
        if not BUSYNESS_MIN <= busyness <= BUSYNESS_MAX:
            raise ValueError(f"busyness must be between {BUSYNESS_MIN} and {BUSYNESS_MAX}")

    def set_status(
        self, guild_id: int, user_id: int, busyness: int, note: Optional[str] = None,
        now: Optional[int] = None,
    ) -> Status:
        """Mark a member available (insert or replace their status)."""
        self._check_busyness(busyness)
        now = int(time.time()) if now is None else now
        self.conn.execute(
            """
            INSERT INTO availability (guild_id, user_id, busyness, note, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                busyness = excluded.busyness,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (guild_id, user_id, busyness, note, now),
        )
        self.conn.commit()
        return Status(guild_id, user_id, busyness, note, now)

    def update_busyness(
        self, guild_id: int, user_id: int, busyness: int, now: Optional[int] = None
    ) -> Optional[Status]:
        """Change only the busyness level. Returns None if the member isn't available."""
        self._check_busyness(busyness)
        now = int(time.time()) if now is None else now
        cur = self.conn.execute(
            "UPDATE availability SET busyness = ?, updated_at = ? WHERE guild_id = ? AND user_id = ?",
            (busyness, now, guild_id, user_id),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            return None
        return self.get_status(guild_id, user_id)

    def clear_status(self, guild_id: int, user_id: int) -> bool:
        """Remove a member from the available list. Returns True if they were on it."""
        cur = self.conn.execute(
            "DELETE FROM availability WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_status(self, guild_id: int, user_id: int) -> Optional[Status]:
        row = self.conn.execute(
            "SELECT guild_id, user_id, busyness, note, updated_at FROM availability "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        return Status(*row) if row else None

    def ranked(self, guild_id: int) -> list[Status]:
        """All available members, least busy first; ties go to the most recent update."""
        rows = self.conn.execute(
            "SELECT guild_id, user_id, busyness, note, updated_at FROM availability "
            "WHERE guild_id = ? ORDER BY busyness ASC, updated_at DESC",
            (guild_id,),
        ).fetchall()
        return [Status(*row) for row in rows]

    def close(self) -> None:
        self.conn.close()
