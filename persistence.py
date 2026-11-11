"""PostgreSQL persistence for python-telegram-bot on stateless runtimes."""

import json
from typing import Any, Dict, Optional, Tuple

import psycopg2
from psycopg2.extras import Json
from telegram.ext import BasePersistence, PersistenceInput


class PostgresPersistence(BasePersistence):
    """Store PTB user/chat/bot data and ConversationHandler states in PostgreSQL.

    A new Vercel invocation may run on a different instance, so PicklePersistence
    and process memory cannot be used for conversation state.
    """

    def __init__(self, dsn: str) -> None:
        super().__init__(store_data=PersistenceInput(callback_data=False), update_interval=0)
        self.dsn = dsn
        self._ensure_tables()

    def _connect(self):
        return psycopg2.connect(self.dsn)

    def _ensure_tables(self) -> None:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ptb_persistence (
                    scope TEXT PRIMARY KEY,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb
                );
                CREATE TABLE IF NOT EXISTS ptb_conversations (
                    handler_name TEXT NOT NULL,
                    conversation_key JSONB NOT NULL,
                    state JSONB,
                    PRIMARY KEY (handler_name, conversation_key)
                );
                """
            )

    def _read_scope(self, scope: str) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT payload FROM ptb_persistence WHERE scope = %s", (scope,))
            row = cursor.fetchone()
            return row[0] if row else {}

    def _write_scope(self, scope: str, payload: Dict[str, Any]) -> None:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ptb_persistence (scope, payload) VALUES (%s, %s)
                ON CONFLICT (scope) DO UPDATE SET payload = EXCLUDED.payload
                """,
                (scope, Json(payload)),
            )

    async def get_user_data(self) -> Dict[int, Dict[str, Any]]:
        return {int(key): value for key, value in self._read_scope("user_data").items()}

    async def get_chat_data(self) -> Dict[int, Dict[str, Any]]:
        return {int(key): value for key, value in self._read_scope("chat_data").items()}

    async def get_bot_data(self) -> Dict[str, Any]:
        return self._read_scope("bot_data")

    async def get_callback_data(self):
        return None

    async def get_conversations(self, name: str) -> Dict[Tuple[Any, ...], Any]:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT conversation_key, state FROM ptb_conversations WHERE handler_name = %s",
                (name,),
            )
            return {tuple(row[0]): row[1] for row in cursor.fetchall()}

    async def update_user_data(self, user_id: int, data: Dict[str, Any]) -> None:
        all_data = self._read_scope("user_data")
        all_data[str(user_id)] = data
        self._write_scope("user_data", all_data)

    async def update_chat_data(self, chat_id: int, data: Dict[str, Any]) -> None:
        all_data = self._read_scope("chat_data")
        all_data[str(chat_id)] = data
        self._write_scope("chat_data", all_data)

    async def update_bot_data(self, data: Dict[str, Any]) -> None:
        self._write_scope("bot_data", data)

    async def update_callback_data(self, data) -> None:
        return None

    async def update_conversation(self, name: str, key: Tuple[Any, ...], new_state: Optional[object]) -> None:
        with self._connect() as conn, conn.cursor() as cursor:
            if new_state is None:
                cursor.execute(
                    "DELETE FROM ptb_conversations WHERE handler_name = %s AND conversation_key = %s::jsonb",
                    (name, json.dumps(list(key))),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO ptb_conversations (handler_name, conversation_key, state)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (handler_name, conversation_key) DO UPDATE SET state = EXCLUDED.state
                    """,
                    (name, Json(list(key)), Json(new_state)),
                )

    async def drop_user_data(self, user_id: int) -> None:
        all_data = self._read_scope("user_data")
        all_data.pop(str(user_id), None)
        self._write_scope("user_data", all_data)

    async def drop_chat_data(self, chat_id: int) -> None:
        all_data = self._read_scope("chat_data")
        all_data.pop(str(chat_id), None)
        self._write_scope("chat_data", all_data)

    async def refresh_user_data(self, user_id: int, user_data: Dict[str, Any]) -> None:
        user_data.clear()
        user_data.update(self._read_scope("user_data").get(str(user_id), {}))

    async def refresh_chat_data(self, chat_id: int, chat_data: Dict[str, Any]) -> None:
        chat_data.clear()
        chat_data.update(self._read_scope("chat_data").get(str(chat_id), {}))

    async def refresh_bot_data(self, bot_data: Dict[str, Any]) -> None:
        bot_data.clear()
        bot_data.update(self._read_scope("bot_data"))

    async def flush(self) -> None:
        return None
