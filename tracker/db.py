import sqlite3
import os
from typing import List, Dict, Optional, Any
from datetime import datetime

DB_PATH = os.path.expanduser("~/.gemini/antigravity-cli/chat_tracker.db")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                title TEXT,
                first_prompt TEXT,
                last_prompt TEXT,
                workspace TEXT,
                created_at TEXT,
                updated_at TEXT,
                turn_count INTEGER DEFAULT 1,
                model TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        conn.commit()

def upsert_conversation(
    conversation_id: str,
    title: Optional[str] = None,
    first_prompt: Optional[str] = None,
    last_prompt: Optional[str] = None,
    workspace: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    turn_count: Optional[int] = None,
    model: Optional[str] = None,
    status: Optional[str] = None
):
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
        row = cursor.fetchone()
        now_iso = datetime.now().isoformat()
        
        clean_title = title.replace("\n", " ").strip() if title else None
        clean_first = first_prompt.strip() if first_prompt else None
        clean_last = last_prompt.strip() if last_prompt else None

        if row is None:
            c_at = created_at or now_iso
            u_at = updated_at or now_iso
            t_cnt = turn_count if turn_count is not None else 1
            t_display = clean_title or (clean_first[:60] if clean_first else "Chat")
            cursor.execute("""
                INSERT INTO conversations (
                    conversation_id, title, first_prompt, last_prompt, workspace,
                    created_at, updated_at, turn_count, model, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                t_display,
                clean_first or "",
                clean_last or clean_first or "",
                workspace or os.path.expanduser("~"),
                c_at,
                u_at,
                t_cnt,
                model or "default",
                status or "active"
            ))
        else:
            # Preserve existing custom title if new title is just raw prompt preview or generic placeholder
            generic_placeholders = {"active chat", "chat", "untitled chat", "untitled", ""}
            if row["title"] and row["title"].strip().lower() not in generic_placeholders:
                new_title = row["title"]
            else:
                new_title = clean_title if clean_title is not None else row["title"]
            new_first = clean_first if clean_first is not None and clean_first != "" else row["first_prompt"]
            new_last = clean_last if clean_last is not None and clean_last != "" else (new_first or row["last_prompt"])
            new_ws = workspace if workspace is not None else row["workspace"]
            new_created = created_at if created_at is not None else row["created_at"]
            new_updated = updated_at or now_iso
            new_turn_count = turn_count if turn_count is not None else (row["turn_count"] + 1 if row["turn_count"] else 1)
            new_model = model if model is not None else row["model"]
            new_status = status if status is not None else row["status"]
            
            if not new_title and new_first:
                new_title = new_first[:60].replace("\n", " ").strip()

            cursor.execute("""
                UPDATE conversations SET
                    title = ?,
                    first_prompt = ?,
                    last_prompt = ?,
                    workspace = ?,
                    created_at = ?,
                    updated_at = ?,
                    turn_count = ?,
                    model = ?,
                    status = ?
                WHERE conversation_id = ?
            """, (
                new_title,
                new_first,
                new_last,
                new_ws,
                new_created,
                new_updated,
                new_turn_count,
                new_model,
                new_status,
                conversation_id
            ))
        conn.commit()

def get_all_conversations() -> List[Dict[str, Any]]:
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_conversation(conversation_id: str):
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
        conn.commit()

def delete_subagents_and_side_questions() -> int:
    init_db()
    from .filters import get_all_subagent_cids, is_subagent, is_side_question

    subagent_cids = get_all_subagent_cids()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT conversation_id, title, first_prompt, last_prompt, turn_count FROM conversations")
        rows = cursor.fetchall()

        to_delete = set()
        for row in rows:
            cid = row["conversation_id"]
            title = row["title"] or ""
            fp = row["first_prompt"] or ""
            lp = row["last_prompt"] or ""
            turns = row["turn_count"] if row["turn_count"] is not None else 1

            if (
                is_subagent(cid, f"{title} {fp} {lp}", subagent_cids=subagent_cids, turn_count=turns)
                or is_side_question(title, fp, lp, turn_count=turns)
            ):
                to_delete.add(cid)

        # Also purge any matching subagent/side-question entries from conversation_summaries.db
        summaries_db = os.path.expanduser("~/.gemini/antigravity-cli/conversation_summaries.db")
        if os.path.exists(summaries_db):
            try:
                with sqlite3.connect(summaries_db) as sum_conn:
                    sum_cur = sum_conn.cursor()
                    sum_cur.execute("SELECT conversation_id, preview, step_count FROM conversation_summaries")
                    for scid, preview, scnt in sum_cur.fetchall():
                        if not scid:
                            continue
                        if (
                            is_subagent(scid, preview or "", subagent_cids=subagent_cids, turn_count=scnt)
                            or is_side_question(preview or "", turn_count=scnt)
                        ):
                            sum_cur.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (scid,))
                    sum_conn.commit()
            except Exception:
                pass

        if not to_delete:
            return 0

        del_list = list(to_delete)
        chunk_size = 500
        for i in range(0, len(del_list), chunk_size):
            chunk = del_list[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"DELETE FROM conversations WHERE conversation_id IN ({placeholders})", chunk)

        conn.commit()

        # Clean shortcuts
        shortcuts_dir = os.path.expanduser("~/.gemini/antigravity-cli/shortcuts")
        if os.path.exists(shortcuts_dir):
            for del_cid in del_list:
                for ext in (".sh", ".desktop"):
                    fpath = os.path.join(shortcuts_dir, f"{del_cid}{ext}")
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except Exception:
                            pass

        return len(del_list)

def delete_side_questions() -> int:
    return delete_subagents_and_side_questions()

def update_conversation_title(conversation_id: str, new_title: str):
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE conversations SET title = ? WHERE conversation_id = ?", (new_title.strip(), conversation_id))
        conn.commit()
