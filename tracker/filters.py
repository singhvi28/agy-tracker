import os
import glob
import json
import re
from typing import Set, Optional

CLI_DIR = os.path.expanduser("~/.gemini/antigravity-cli")

def get_all_subagent_cids() -> Set[str]:
    """Retrieve all known subagent conversation IDs from brain subagent descriptors."""
    pattern = os.path.join(CLI_DIR, "brain", "*", ".system_generated", "subagents", "*.json")
    subagent_files = glob.glob(pattern)
    return {os.path.splitext(os.path.basename(f))[0] for f in subagent_files}

def is_side_question(
    title_or_text: Optional[str] = "",
    first_prompt: Optional[str] = "",
    last_prompt: Optional[str] = "",
    turn_count: Optional[int] = None
) -> bool:
    """Check if the conversation represents an ephemeral side question, ping, or smoke test."""
    # A conversation with many turns is typically a legitimate project chat
    if turn_count is not None and turn_count > 5:
        return False

    texts = [t for t in (title_or_text, first_prompt, last_prompt) if t]
    if not texts:
        return True

    combined = " ".join(texts).lower().strip()

    # Empty or generic placeholder titles
    fp_strip = (first_prompt or (title_or_text if not first_prompt else "")).strip()
    t_strip = (title_or_text or "").strip()
    if not fp_strip or not t_strip or t_strip.lower() in ("chat", "active chat", "untitled chat", "untitled"):
        return True

    # Ephemeral side-question phrasing
    side_patterns = [
        "side question from the user",
        "this is a side question",
        "answer the following quickly within 30 seconds",
        "answer the following quickly",
        "quickly within 30 seconds",
        "within 30 seconds",
        "within 15 seconds",
        "answer quickly in 30",
        "answer in 30s",
        "answer quickly within",
        "answer quickly",
        "answer in 30 seconds",
        "answer in 15 seconds",
        "do you have the capability to launch browser subagent",
    ]
    if any(p in combined for p in side_patterns):
        return True
    if any(txt.lower().strip().startswith("/btw") or txt.lower().strip() == "/btw" for txt in texts):
        return True

    # Automated smoke tests & ping echoes
    fp_lower = fp_strip.lower()
    title_lower = t_strip.lower()

    if re.search(r"^(say\s+(exactly:?\s*)?pong(_test)?|hello,?\s*please\s+answer\s+with\s+pong|reply\s+with\s+single\s+word\s+pong)$", fp_lower):
        return True
    if re.search(r"^reply\s+with\s+exactly\s+one\s+word:\s*success$", fp_lower):
        return True
    if "remember the secret word: elephant" in fp_lower:
        return True
    if fp_lower in ("say 'test-passed'", "say test-passed", "pong test response", "distributed token bucket state management"):
        return True
    if "you are an expert system design interviewer" in fp_lower and (turn_count is None or turn_count <= 5):
        return True
    if fp_lower.startswith("this version of antigravity is no longer supported"):
        return True

    # Known titles for automated smoke tests
    smoke_titles = [
        "sd interview: agysession ping smoke",
        "sd interview: latency & echo smoke",
        "sd interview: streaming greeting",
        "sd interview: single-word ping test",
        "sd interview: single-word output validation",
        "sd interview: multi-turn memory & context retention",
        "sd interview: live generation smoke",
        "sd interview: backend agysession smoke",
        "sd interview: live turn smoke test",
        "latency & echo smoke test (pong)",
        "testing agent connectivity",
    ]
    if any(st in title_lower for st in smoke_titles):
        return True

    # Standalone slash command echoes with <= 2 turns
    if (turn_count is None or turn_count <= 2) and fp_lower in ("/usage", "/config", "/model", "/help"):
        return True

    return False

def is_subagent(
    cid: Optional[str],
    text: Optional[str] = "",
    transcript_path: Optional[str] = "",
    subagent_cids: Optional[Set[str]] = None,
    turn_count: Optional[int] = None
) -> bool:
    """Check if the conversation is a subagent (worker/investigator/watchdog/persona)."""
    if not cid:
        return False
    
    if subagent_cids is None:
        subagent_cids = get_all_subagent_cids()
    if cid in subagent_cids:
        return True

    t = (text or "").lower().strip()
    if (
        t.startswith("you are tasked with")
        or "<original_task>" in t
        or "<prior_attempt>" in t
        or "deepinvestigatorworker" in t
        or "deepcoderworker" in t
        or "watchdog monitor" in t
        or t.startswith("[interviewer persona profile:")
        or "persona session" in t
        or "persona profile" in t
    ):
        return True

    # Automated persona or evaluation worker sessions
    if "dr. sarah chen persona" in t:
        return True
    if (
        ("you are a principal software engineer & bar raiser" in t
         or "you are a principal software engineer / staff" in t
         or "staff technical bar raiser evaluation" in t
         or "sd interview: distributed rate limiter" in t
         or "sd interview: staff bar raiser review" in t)
        and (turn_count is None or turn_count <= 10)
    ):
        return True

    # Check transcript header if accessible
    if not transcript_path:
        transcript_path = os.path.join(CLI_DIR, "brain", cid, ".system_generated", "logs", "transcript.jsonl")
    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line:
                    d = json.loads(first_line)
                    content = d.get("content", "")
                    if d.get("source") == "SYSTEM" and (
                        "sender=" in content
                        or "<original_task>" in content
                        or "task id" in content.lower()
                        or "subagent" in content.lower()
                    ):
                        return True
                    if "[INTERVIEWER PERSONA PROFILE:" in content:
                        return True
        except Exception:
            pass

    return False
