import os
import json
import sqlite3
import re
from datetime import datetime
from .db import upsert_conversation
from .filters import get_all_subagent_cids, is_side_question, is_subagent

def clean_user_prompt(text: str) -> str:
    if not text:
        return ""
    if "<USER_REQUEST>" in text and "</USER_REQUEST>" in text:
        text = text.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0]
    # Remove excessive newlines
    return text.strip()

def generate_smart_title(prompt: str, workspace: str = "", default_title: str = "") -> str:
    if not prompt or not prompt.strip():
        return default_title or "Active Chat"
    
    clean = clean_user_prompt(prompt).strip()

    # Slash commands: /plan, /boost, /browser, /learn, etc.
    clean = re.sub(r"^/(plan|boost|browser|learn|goal|teamwork|grill-me)\s+", "", clean, flags=re.I)

    # File annotations: @[/path/to/file:L1-L10]
    m_file = re.match(r"^@\[([^\]]+)\]\s*(.*)", clean)
    if m_file:
        fpath = m_file.group(1).split(":")[0]
        fname = os.path.basename(fpath)
        rest = m_file.group(2).strip()
        if rest:
            clean = f"{fname}: {rest}"
        else:
            clean = f"Review {fname}"

    clean = " ".join(clean.split())
    if clean and clean[0].islower():
        clean = clean[0].upper() + clean[1:]

    if len(clean) > 65:
        cutoff = clean[:62].rfind(" ")
        if cutoff > 35:
            clean = clean[:cutoff] + "..."
        else:
            clean = clean[:62] + "..."

    return clean or default_title or "Chat"

def scan_all():
    cli_dir = os.path.expanduser("~/.gemini/antigravity-cli")
    brain_dir = os.path.join(cli_dir, "brain")
    history_file = os.path.join(cli_dir, "history.jsonl")
    summaries_db = os.path.join(cli_dir, "conversation_summaries.db")

    subagent_cids = get_all_subagent_cids()

    # Map conversation_id -> dict of metadata
    conversations = {}

    # 1. Read conversation_summaries.db if exists
    if os.path.exists(summaries_db):
        try:
            conn = sqlite3.connect(summaries_db)
            cursor = conn.cursor()
            cursor.execute("SELECT conversation_id, preview, step_count, last_modified_time, workspace_uris FROM conversation_summaries")
            for cid, preview, step_count, last_mod, ws_uris in cursor.fetchall():
                if not cid or not preview or not preview.strip():
                    continue
                if is_side_question(preview, turn_count=step_count) or is_subagent(cid, preview, subagent_cids=subagent_cids, turn_count=step_count):
                    continue
                ws = os.path.expanduser("~")
                if ws_uris:
                    try:
                        uris = json.loads(ws_uris)
                        if uris and len(uris) > 0:
                            ws = uris[0].replace("file://", "")
                    except Exception:
                        pass
                conversations[cid] = {
                    "conversation_id": cid,
                    "title": preview or "",
                    "first_prompt": preview or "",
                    "last_prompt": preview or "",
                    "workspace": ws,
                    "created_at": last_mod,
                    "updated_at": last_mod,
                    "turn_count": step_count or 1
                }
            conn.close()
        except Exception:
            pass

    # 2. Read history.jsonl
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        cid = d.get("conversationId")
                        if cid:
                            prompt = clean_user_prompt(d.get("display", ""))
                            if not prompt or not prompt.strip() or is_side_question(prompt) or is_subagent(cid, prompt, subagent_cids=subagent_cids):
                                continue
                            ws = d.get("workspace", os.path.expanduser("~"))
                            ts_ms = d.get("timestamp")
                            ts_iso = datetime.fromtimestamp(ts_ms / 1000.0).isoformat() if ts_ms else datetime.now().isoformat()
                            
                            if cid not in conversations:
                                conversations[cid] = {
                                    "conversation_id": cid,
                                    "title": generate_smart_title(prompt, ws),
                                    "first_prompt": prompt,
                                    "last_prompt": prompt,
                                    "workspace": ws,
                                    "created_at": ts_iso,
                                    "updated_at": ts_iso,
                                    "turn_count": 1
                                }
                            else:
                                if prompt:
                                    if not conversations[cid]["first_prompt"]:
                                        conversations[cid]["first_prompt"] = prompt
                                        conversations[cid]["title"] = generate_smart_title(prompt, ws)
                                    conversations[cid]["last_prompt"] = prompt
                                if ws:
                                    conversations[cid]["workspace"] = ws
                                conversations[cid]["updated_at"] = ts_iso
                                conversations[cid]["turn_count"] = conversations[cid].get("turn_count", 0) + 1
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. Read brain transcripts
    if os.path.exists(brain_dir):
        for cid in os.listdir(brain_dir):
            cpath = os.path.join(brain_dir, cid)
            if not os.path.isdir(cpath):
                continue
            transcript_file = os.path.join(cpath, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(transcript_file):
                try:
                    first_p = ""
                    last_p = ""
                    c_at = None
                    u_at = None
                    turn_cnt = 0
                    with open(transcript_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                item = json.loads(line.strip())
                                if item.get("type") == "USER_INPUT" and "content" in item:
                                    turn_cnt += 1
                                    p = clean_user_prompt(item["content"])
                                    if not first_p and p:
                                        first_p = p
                                        c_at = item.get("created_at")
                                    if p:
                                        last_p = p
                                        u_at = item.get("created_at")
                            except Exception:
                                pass
                    if is_subagent(cid, f"{first_p} {last_p}", transcript_file, subagent_cids=subagent_cids, turn_count=turn_cnt):
                        continue
                    if is_side_question(title="", first_prompt=first_p, last_prompt=last_p, turn_count=turn_cnt):
                        continue
                    # Ignore subagents / background worker tasks that have no human user prompt
                    if not first_p or not first_p.strip():
                        continue
                    if cid not in conversations:
                        conversations[cid] = {
                            "conversation_id": cid,
                            "title": generate_smart_title(first_p, os.path.expanduser("~")),
                            "first_prompt": first_p,
                            "last_prompt": last_p or first_p,
                            "workspace": os.path.expanduser("~"),
                            "created_at": c_at or datetime.now().isoformat(),
                            "updated_at": u_at or c_at or datetime.now().isoformat(),
                            "turn_count": max(turn_cnt, 1)
                        }
                    else:
                        if first_p and not conversations[cid]["first_prompt"]:
                            conversations[cid]["first_prompt"] = first_p
                            conversations[cid]["title"] = generate_smart_title(first_p, conversations[cid].get("workspace", ""))
                        if last_p:
                            conversations[cid]["last_prompt"] = last_p
                        if c_at and not conversations[cid].get("created_at"):
                            conversations[cid]["created_at"] = c_at
                        if u_at:
                            conversations[cid]["updated_at"] = u_at
                        if turn_cnt > 0:
                            conversations[cid]["turn_count"] = max(conversations[cid].get("turn_count", 0), turn_cnt)
                except Exception:
                    pass

    # Save to database
    for cid, meta in conversations.items():
        fp = meta.get("first_prompt") or ""
        t = meta.get("title") or ""
        lp = meta.get("last_prompt") or ""
        turns = meta.get("turn_count", 1)
        if is_side_question(t, fp, lp, turn_count=turns) or is_subagent(cid, f"{t} {fp} {lp}", subagent_cids=subagent_cids, turn_count=turns):
            continue
        upsert_conversation(
            conversation_id=cid,
            title=meta.get("title"),
            first_prompt=meta.get("first_prompt"),
            last_prompt=meta.get("last_prompt"),
            workspace=meta.get("workspace"),
            created_at=meta.get("created_at"),
            updated_at=meta.get("updated_at"),
            turn_count=meta.get("turn_count")
        )
    return len(conversations)
