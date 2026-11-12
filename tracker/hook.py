import sys
import os
import json
from datetime import datetime
from .db import upsert_conversation, init_db
from .exporter import export_all
from .filters import is_subagent, is_side_question
from .scanner import clean_user_prompt, generate_smart_title

def run_hook():
    init_db()
    input_data = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                input_data = json.loads(raw)
    except Exception:
        pass

    cid = input_data.get("conversationId")
    if cid:
        transcript_path = input_data.get("transcriptPath")
        if is_subagent(cid, transcript_path=transcript_path):
            print(json.dumps({}))
            return

        ws_paths = input_data.get("workspacePaths", [])
        workspace = ws_paths[0] if ws_paths and len(ws_paths) > 0 else os.path.expanduser("~")
        model = input_data.get("modelName", "default")
        
        first_prompt = ""
        last_prompt = ""
        turn_cnt = 0
        c_at = None
        u_at = None

        if transcript_path and os.path.exists(transcript_path):
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            item = json.loads(line.strip())
                            if item.get("type") == "USER_INPUT" and "content" in item:
                                turn_cnt += 1
                                p = clean_user_prompt(item["content"])
                                if not first_prompt and p:
                                    first_prompt = p
                                    c_at = item.get("created_at")
                                if p:
                                    last_prompt = p
                                    u_at = item.get("created_at")
                        except Exception:
                            pass
            except Exception:
                pass

        # If transcript was empty or didn't have user input yet, check history.jsonl
        if not first_prompt:
            history_file = os.path.expanduser("~/.gemini/antigravity-cli/history.jsonl")
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                d = json.loads(line.strip())
                                if d.get("conversationId") == cid:
                                    p = clean_user_prompt(d.get("display", ""))
                                    if not first_prompt and p:
                                        first_prompt = p
                                    if p:
                                        last_prompt = p
                            except Exception:
                                pass
                except Exception:
                    pass

        if (
            is_subagent(cid, f"{first_prompt} {last_prompt}", transcript_path, turn_count=turn_cnt)
            or is_side_question(title="", first_prompt=first_prompt, last_prompt=last_prompt, turn_count=turn_cnt)
        ):
            print(json.dumps({}))
            return

        if not first_prompt or not first_prompt.strip():
            print(json.dumps({}))
            return

        title = generate_smart_title(first_prompt, workspace)
        now_iso = datetime.now().isoformat()
        
        upsert_conversation(
            conversation_id=cid,
            title=title,
            first_prompt=first_prompt,
            last_prompt=last_prompt,
            workspace=workspace,
            created_at=c_at or now_iso,
            updated_at=u_at or now_iso,
            turn_count=max(turn_cnt, 1),
            model=model,
            status="active"
        )
        try:
            export_all()
        except Exception:
            pass

    # Always return valid JSON object to agent loop
    print(json.dumps({}))
