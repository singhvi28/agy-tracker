import sys
import os
import argparse
import subprocess
import shutil
from datetime import datetime
from .db import (
    get_all_conversations,
    get_conversation,
    delete_side_questions,
    delete_subagents_and_side_questions,
    update_conversation_title,
)
from .scanner import scan_all
from .exporter import export_all
from .hook import run_hook

# Terminal Colors & OSC 8 Hyperlink support
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
RESET = "\033[0m"

def osc8_link(uri: str, label: str) -> str:
    return f"\033]8;;{uri}\033\\{label}\033]8;;\033\\"

def format_relative_time(iso_str: str) -> str:
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            m = seconds // 60
            return f"{m}m ago"
        elif seconds < 86400:
            h = seconds // 3600
            return f"{h}h ago"
        elif seconds < 604800:
            d = seconds // 86400
            return f"{d}d ago"
        else:
            return dt.strftime("%b %d")
    except Exception:
        return iso_str[:10]

def cmd_list(args):
    conversations = get_all_conversations()
    if not conversations:
        print(f"{YELLOW}No conversations tracked yet.{RESET} Running sync to check past chats...")
        scan_all()
        export_all()
        conversations = get_all_conversations()

    if not conversations:
        print(f"{DIM}No Antigravity CLI conversations found.{RESET}")
        return

    total = len(conversations)
    limit = getattr(args, "limit", 0) if args else 0
    show_full = getattr(args, "full", False) if args else False
    is_wide = getattr(args, "wide", False) if args else False

    # Dynamic terminal width detection
    term_cols = shutil.get_terminal_size(fallback=(120, 24)).columns

    idx_width = max(len(str(total)), 3) + 1
    time_width = 9
    ws_width = 14
    link_width = 14
    fixed_overhead = idx_width + 1 + time_width + 1 + ws_width + 1 + link_width + 1

    if show_full:
        max_title_len = max(len((c.get("title") or c.get("first_prompt") or "").replace("\n", " ").strip()) for c in conversations)
        title_width = max(70, max_title_len)
    elif is_wide:
        title_width = max(85, term_cols - fixed_overhead)
    else:
        # Scale title column width generously with terminal size (min 65, up to 95)
        title_width = max(65, min(term_cols - fixed_overhead, 95))

    divider_len = idx_width + 1 + time_width + 1 + title_width + 1 + ws_width + 1 + link_width

    display_count = f"{limit} of {total}" if (limit and 0 < limit < total) else str(total)
    print(f"\n{BOLD}{CYAN}🚀 Antigravity CLI Tracked Conversations ({display_count}){RESET}")
    print(f"{DIM}{'─' * divider_len}{RESET}")
    print(f"{BOLD}{'#':<{idx_width}} {'WHEN':<{time_width}} {'TITLE / PROMPT':<{title_width}} {'WORKSPACE':<{ws_width}} {'RESUME LINK'}{RESET}")
    print(f"{DIM}{'─' * divider_len}{RESET}")

    start_i = (min(total, limit) - 1) if (limit and limit > 0) else (total - 1)
    for i in range(start_i, -1, -1):
        c = conversations[i]
        idx = i + 1
        cid = c["conversation_id"]
        title = (c.get("title") or c.get("first_prompt") or "Untitled Chat").replace("\n", " ").strip()
        
        if not show_full and len(title) > title_width:
            display_title = title[:title_width - 3] + "..."
        else:
            display_title = title

        rel_time = format_relative_time(c.get("updated_at") or c.get("created_at"))
        ws = c.get("workspace") or "~"
        ws_short = os.path.basename(ws) if ws != os.path.expanduser("~") else "~"
        if len(ws_short) > (ws_width - 2):
            ws_short = ws_short[:ws_width - 4] + ".."

        uri = f"agy://resume/{cid}"
        link_str = osc8_link(uri, f"{GREEN}[Resume #{idx}]{RESET}")

        print(f"{BOLD}{idx:<{idx_width}}{RESET} {rel_time:<{time_width}} {display_title:<{title_width}} {DIM}{ws_short:<{ws_width}}{RESET} {link_str}")

    print(f"{DIM}{'─' * divider_len}{RESET}")
    print(f"💡 {DIM}Run {BOLD}agy-tracker resume <#> [--danger]{RESET}{DIM} to open in terminal, or click the links above.{RESET}\n")

def resolve_conversation(id_or_num: str):
    conversations = get_all_conversations()
    if not conversations:
        scan_all()
        conversations = get_all_conversations()
    
    if id_or_num.isdigit():
        idx = int(id_or_num) - 1
        if 0 <= idx < len(conversations):
            return conversations[idx]
        else:
            print(f"{YELLOW}Error: Index #{id_or_num} out of range (1-{len(conversations)}){RESET}")
            sys.exit(1)
    
    # Try exact match or prefix
    for c in conversations:
        if c["conversation_id"].lower() == id_or_num.lower() or c["conversation_id"].startswith(id_or_num):
            return c

    print(f"{YELLOW}Error: Conversation '{id_or_num}' not found.{RESET}")
    sys.exit(1)

def cmd_resume(args):
    conversations = get_all_conversations()
    if not conversations:
        scan_all()
        export_all()
        conversations = get_all_conversations()

    target_id = args.target
    if not target_id:
        if not conversations:
            print("No conversations to resume.")
            return
        target_conv = conversations[0] # most recent
    else:
        target_conv = resolve_conversation(target_id)

    cid = target_conv["conversation_id"]
    ws = target_conv.get("workspace") or os.path.expanduser("~")
    is_danger = getattr(args, "danger", False) or getattr(args, "top_danger", False)

    if getattr(args, "window", False):
        # Open in separate terminal window
        opener = os.path.expanduser("~/.gemini/antigravity-cli/bin/agy-open-url")
        cmd = [opener, f"agy://resume/{cid}"]
        if is_danger:
            cmd.append("--danger")
        subprocess.Popen(cmd)
        mode_str = " in danger mode" if is_danger else ""
        print(f"{GREEN}✓ Launched conversation {cid[:8]}{mode_str} in new terminal window.{RESET}")
    else:
        # Resume right here in current terminal
        mode_str = f" {YELLOW}(--danger){RESET}" if is_danger else ""
        print(f"{CYAN}Resuming conversation {cid}...{RESET}{mode_str}")
        if os.path.isdir(ws):
            os.chdir(ws)
        exec_args = ["agy", "--conversation", cid]
        if is_danger:
            exec_args.append("--danger")
        os.execvp("agy", exec_args)

def cmd_sync(args):
    print(f"{CYAN}Scanning past Antigravity CLI conversations...{RESET}")
    count = scan_all()
    export_all()
    html_file = os.path.expanduser("~/.gemini/antigravity-cli/chat_history.html")
    md_file = os.path.expanduser("~/.gemini/antigravity-cli/CHATS.md")
    print(f"{GREEN}✓ Successfully synced and tracked {count} conversations!{RESET}")
    print(f"📁 Web Dashboard: {BLUE}file://{html_file}{RESET}")
    print(f"📄 Markdown:      {BLUE}file://{md_file}{RESET}")

def cmd_web(args):
    html_path = os.path.expanduser("~/.gemini/antigravity-cli/chat_history.html")
    if not os.path.exists(html_path):
        scan_all()
        export_all()
    print(f"{GREEN}Opening Antigravity Chat History in default browser...{RESET}")
    subprocess.Popen(["xdg-open", html_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cmd_show(args):
    conv = resolve_conversation(args.target)
    cid = conv["conversation_id"]
    ws = conv.get("workspace") or "~"
    created = conv.get("created_at") or "N/A"
    updated = conv.get("updated_at") or "N/A"
    turns = conv.get("turn_count", 1)
    prompt = conv.get("first_prompt") or "N/A"
    last_p = conv.get("last_prompt") or "N/A"
    transcript_path = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{cid}/.system_generated/logs/transcript.jsonl")

    print(f"\n{BOLD}{CYAN}💬 Conversation Details: {cid}{RESET}")
    print(f"{DIM}{'─' * 60}{RESET}")
    print(f"{BOLD}Title:{RESET}       {conv.get('title')}")
    print(f"{BOLD}Created:{RESET}     {created}")
    print(f"{BOLD}Updated:{RESET}     {updated}")
    print(f"{BOLD}Workspace:{RESET}   {ws}")
    print(f"{BOLD}Turns:{RESET}       {turns}")
    print(f"{BOLD}Resume Link:{RESET} {osc8_link(f'agy://resume/{cid}', f'agy://resume/{cid}')}")
    print(f"{BOLD}Logs:{RESET}        {transcript_path}")
    print(f"\n{BOLD}Initial Prompt:{RESET}\n{DIM}{prompt}{RESET}")
    if last_p != prompt:
        print(f"\n{BOLD}Latest Prompt:{RESET}\n{DIM}{last_p}{RESET}")
    print(f"\n{DIM}{'─' * 60}{RESET}")
    print(f"Command to resume: {BOLD}agy --conversation {cid}{RESET}\n")

def cmd_title(args):
    conv = resolve_conversation(args.target)
    cid = conv["conversation_id"]
    new_title = " ".join(args.title).strip()
    if not new_title:
        print(f"{YELLOW}Error: Title cannot be empty.{RESET}")
        return
    update_conversation_title(cid, new_title)
    export_all()
    print(f"{GREEN}✓ Updated title for {cid[:8]}:{RESET} {BOLD}{new_title}{RESET}")

def cmd_autotitle(args):
    from .scanner import generate_smart_title
    limit = getattr(args, "limit", 50) or 50
    conversations = get_all_conversations()
    if not conversations:
        print("No conversations found.")
        return
    print(f"{CYAN}Auto-titling conversations (limit={limit})...{RESET}")
    count = 0
    generic_or_raw = {"active chat", "chat", "untitled chat", "untitled", ""}
    for i, c in enumerate(conversations[:limit]):
        cid = c["conversation_id"]
        cur_t = c.get("title") or ""
        p1 = c.get("first_prompt") or ""
        ws = c.get("workspace") or "~"
        
        # Check if current title is generic or just raw prompt prefix
        is_raw = (cur_t.strip().lower() in generic_or_raw or
                  cur_t.startswith("Say exactly: PONG") or
                  cur_t.startswith("Say PONG") or
                  cur_t.startswith("Hello, please answer with PONG") or
                  cur_t.startswith("[INTERVIEWER PERSONA") or
                  cur_t.startswith("You are an expert system design") or
                  cur_t.startswith("/plan ") or
                  cur_t.startswith("@[/"))
        if is_raw:
            smart_t = generate_smart_title(p1, ws)
            if smart_t and smart_t != cur_t:
                update_conversation_title(cid, smart_t)
                count += 1
                print(f"  {DIM}#{i+1}{RESET} {cur_t[:30]} -> {BOLD}{smart_t}{RESET}")
                
    export_all()
    print(f"{GREEN}✓ Successfully updated {count} conversation titles.{RESET}")

def cmd_clean(args):
    print(f"{CYAN}Cleaning up subagents, side questions and stale conversations...{RESET}")
    deleted = delete_subagents_and_side_questions()
    export_all()
    print(f"{GREEN}✓ Successfully cleaned up {deleted} subagents and side questions.{RESET}")

def main():
    parser = argparse.ArgumentParser(description="Antigravity CLI Chat Tracker & Launcher")
    parser.add_argument("-f", "--full", action="store_true", help="Display full untruncated titles")
    parser.add_argument("-w", "--wide", action="store_true", help="Display wider title column")
    parser.add_argument("-n", "--limit", type=int, default=0, help="Limit output to recent N conversations")
    parser.add_argument("-d", "--danger", dest="top_danger", action="store_true", help="Launch conversation in danger mode (auto-execute commands)")
    subparsers = parser.add_subparsers(dest="command")

    # list
    list_p = subparsers.add_parser("list", aliases=["ls"], help="List all tracked conversations")
    list_p.add_argument("-f", "--full", action="store_true", help="Display full untruncated titles")
    list_p.add_argument("-w", "--wide", action="store_true", help="Display wider title column")
    list_p.add_argument("-n", "--limit", type=int, default=0, help="Limit output to recent N conversations")
    
    # resume
    resume_p = subparsers.add_parser("resume", help="Resume a conversation by number (#) or ID")
    resume_p.add_argument("target", nargs="?", default="", help="Conversation index number (e.g. 1) or ID")
    resume_p.add_argument("-d", "--danger", action="store_true", help="Launch conversation in danger mode (auto-execute commands)")
    resume_p.add_argument("-w", "--window", action="store_true", help="Launch in a new terminal window")

    # sync
    subparsers.add_parser("sync", help="Scan and sync all conversation history")

    # web/open
    subparsers.add_parser("web", aliases=["open"], help="Open the interactive web dashboard")

    # show
    show_p = subparsers.add_parser("show", aliases=["info"], help="Show details of a specific conversation")
    show_p.add_argument("target", help="Conversation index number or ID")

    # title / rename
    title_p = subparsers.add_parser("title", aliases=["rename"], help="Assign or update title of a conversation")
    title_p.add_argument("target", help="Conversation index number or ID")
    title_p.add_argument("title", nargs="+", help="New title")

    # autotitle
    auto_p = subparsers.add_parser("autotitle", help="Automatically assign smart clean titles to conversations")
    auto_p.add_argument("-n", "--limit", type=int, default=50, help="Number of recent conversations to scan")

    # clean
    subparsers.add_parser("clean", help="Clean up subagents, side questions and stale entries")

    # hook (internal)
    subparsers.add_parser("hook", help="Internal lifecycle hook runner")

    args = parser.parse_args()

    if args.command in ("list", "ls") or args.command is None:
        cmd_list(args)
    elif args.command == "resume":
        cmd_resume(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command in ("web", "open"):
        cmd_web(args)
    elif args.command in ("show", "info"):
        cmd_show(args)
    elif args.command in ("title", "rename"):
        cmd_title(args)
    elif args.command == "autotitle":
        cmd_autotitle(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "hook":
        run_hook()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
