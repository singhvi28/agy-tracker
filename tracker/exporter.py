import os
import html
import json
import stat
from datetime import datetime
from typing import List, Dict, Any
from .db import get_all_conversations

def generate_shortcuts(conversations: List[Dict[str, Any]]):
    shortcuts_dir = os.path.expanduser("~/.gemini/antigravity-cli/shortcuts")
    os.makedirs(shortcuts_dir, exist_ok=True)
    
    # Remove stale shortcuts
    valid_cids = {conv["conversation_id"] for conv in conversations}
    if os.path.exists(shortcuts_dir):
        for fname in os.listdir(shortcuts_dir):
            if fname.endswith(".sh") or fname.endswith(".desktop"):
                cid_part = fname.rsplit(".", 1)[0]
                if cid_part not in valid_cids:
                    try:
                        os.remove(os.path.join(shortcuts_dir, fname))
                    except Exception:
                        pass

    for conv in conversations:
        cid = conv["conversation_id"]
        ws = conv.get("workspace") or os.path.expanduser("~")
        title = conv.get("title") or "Antigravity Chat"
        
        # 1. Shell script launcher
        sh_path = os.path.join(shortcuts_dir, f"{cid}.sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write(f"""#!/bin/bash
# Antigravity CLI Launcher for conversation {cid}
cd "{ws}" || cd "$HOME"
if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="{title}" -- /bin/bash -c "agy --conversation {cid}; exec /bin/bash"
elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e /bin/bash -c "agy --conversation {cid}; exec /bin/bash"
else
    agy --conversation {cid}
fi
""")
        # Make executable
        st = os.stat(sh_path)
        os.chmod(sh_path, st.st_mode | stat.S_IEXEC)

        # 2. .desktop launcher
        desktop_path = os.path.join(shortcuts_dir, f"{cid}.desktop")
        clean_title = title.replace("\n", " ").replace('"', '\\"')[:50]
        opener_bin = os.path.expanduser("~/.gemini/antigravity-cli/bin/agy-open-url")
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(f"""[Desktop Entry]
Name=AGY: {clean_title}
Comment=Resume Antigravity conversation {cid}
Exec={opener_bin} agy://resume/{cid}
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Development;
""")

def generate_markdown(conversations: List[Dict[str, Any]]):
    md_path = os.path.expanduser("~/.gemini/antigravity-cli/CHATS.md")
    lines = []
    lines.append("# 🚀 Antigravity CLI Chat History & Quick Links\n")
    lines.append("This document tracks all your Antigravity CLI conversations. Click **[Resume in Terminal]** on any conversation to resume it directly in your terminal, or click the log link to inspect its transcript.\n")
    lines.append("| # | Updated | Title / First Prompt | Workspace | Turns | Quick Actions |")
    lines.append("|---|---|---|---|---|---|")
    
    for idx, conv in enumerate(conversations, start=1):
        cid = conv["conversation_id"]
        title = html.escape((conv.get("title") or "Chat").replace("\n", " ").strip())
        if len(title) > 65:
            title = title[:62] + "..."
        ws = conv.get("workspace") or "~"
        turns = conv.get("turn_count", 1)
        
        updated = conv.get("updated_at", "")
        if updated:
            try:
                # Format friendly date
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                updated_str = dt.strftime("%b %d, %H:%M")
            except Exception:
                updated_str = updated[:16]
        else:
            updated_str = "N/A"
            
        transcript_path = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{cid}/.system_generated/logs/transcript.jsonl")
        log_link = f"[Logs](file://{transcript_path})" if os.path.exists(transcript_path) else "—"
        resume_link = f"[**Resume**](agy://resume/{cid})"
        sh_path = os.path.expanduser(f"~/.gemini/antigravity-cli/shortcuts/{cid}.sh")
        sh_link = f"[Launcher](file://{sh_path})"
        
        lines.append(f"| {idx} | `{updated_str}` | {title} | `{ws}` | {turns} | {resume_link} · {sh_link} · {log_link} |")
        
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def generate_html(conversations: List[Dict[str, Any]]):
    html_path = os.path.expanduser("~/.gemini/antigravity-cli/chat_history.html")
    
    chats_json = json.dumps(conversations)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity CLI Chat Tracker</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0f1117;
      --card-bg: #181b24;
      --card-border: #292d3e;
      --card-hover: #222634;
      --primary: #4a88ff;
      --primary-hover: #3b76e8;
      --primary-light: rgba(74, 136, 255, 0.15);
      --accent: #2dd4bf;
      --accent-light: rgba(45, 212, 191, 0.15);
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --code-bg: #12141c;
      --border: #292d3e;
      --success: #10b981;
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    
    body {{
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1.5rem;
      min-height: 100vh;
    }}
    
    .container {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
      gap: 1rem;
    }}
    
    .header-title {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}
    
    .logo-badge {{
      background: linear-gradient(135deg, #4a88ff, #a855f7);
      color: white;
      font-weight: 700;
      font-size: 1.1rem;
      padding: 0.5rem 0.8rem;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(74, 136, 255, 0.3);
    }}
    
    h1 {{
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    
    .stats-badge {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 0.5rem 1rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      color: var(--text-muted);
    }}
    
    .stats-badge span {{
      color: var(--primary);
      font-weight: 600;
    }}
    
    .controls {{
      display: flex;
      gap: 1rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
    }}
    
    .search-input {{
      flex: 1;
      min-width: 260px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 0.75rem 1.25rem;
      border-radius: 12px;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
    }}
    
    .search-input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 2px var(--primary-light);
    }}
    
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.65rem 1.15rem;
      border-radius: 10px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
      border: none;
      font-family: inherit;
    }}
    
    .btn-primary {{
      background: var(--primary);
      color: white;
    }}
    .btn-primary:hover {{
      background: var(--primary-hover);
      box-shadow: 0 4px 12px rgba(74, 136, 255, 0.35);
      transform: translateY(-1px);
    }}
    
    .btn-outline {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
    }}
    .btn-outline:hover {{
      border-color: var(--text-muted);
      color: var(--text);
      background: var(--card-hover);
    }}
    
    .btn-sm {{
      padding: 0.4rem 0.8rem;
      font-size: 0.82rem;
    }}
    
    .cards-grid {{
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}
    
    .chat-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 1.25rem 1.5rem;
      transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }}
    
    .chat-card:hover {{
      border-color: #3b425b;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    }}
    
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }}
    
    .card-title {{
      font-size: 1.05rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.4;
      flex: 1;
    }}
    
    .card-meta {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-shrink: 0;
    }}
    
    .time-badge {{
      font-size: 0.8rem;
      color: var(--text-dim);
      white-space: nowrap;
    }}
    
    .turns-badge {{
      background: var(--accent-light);
      color: var(--accent);
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
    }}
    
    .prompt-preview {{
      font-size: 0.9rem;
      color: var(--text-muted);
      background: var(--code-bg);
      padding: 0.75rem 1rem;
      border-radius: 8px;
      font-family: 'JetBrains Mono', monospace;
      white-space: pre-wrap;
      max-height: 100px;
      overflow-y: auto;
      border: 1px solid #1e2230;
    }}
    
    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 0.25rem;
    }}
    
    .workspace-path {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: var(--text-dim);
      display: flex;
      align-items: center;
      gap: 0.4rem;
      max-width: 400px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    
    .card-actions {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-left: auto;
    }}
    
    .toast {{
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: var(--success);
      color: white;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      font-weight: 500;
      font-size: 0.9rem;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
      opacity: 0;
      transition: opacity 0.2s, transform 0.2s;
      transform: translateY(10px);
      pointer-events: none;
      z-index: 1000;
    }}
    
    .toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    
    .empty-state {{
      text-align: center;
      padding: 4rem 2rem;
      color: var(--text-muted);
      background: var(--card-bg);
      border-radius: 16px;
      border: 1px dashed var(--border);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <div class="logo-badge">AGY</div>
        <div>
          <h1>Antigravity CLI Tracker</h1>
          <p style="font-size: 0.85rem; color: var(--text-dim);">Live terminal conversation tracker & link launcher</p>
        </div>
      </div>
      <div class="stats-badge">
        Tracked Conversations: <span id="total-count">0</span>
      </div>
    </header>
    
    <div class="controls">
      <input type="text" id="search" class="search-input" placeholder="🔍 Search conversations by prompt, keyword, workspace, or ID..." oninput="filterCards()">
      <button class="btn btn-outline" onclick="window.location.reload()">🔄 Refresh</button>
    </div>
    
    <div id="cards-container" class="cards-grid">
      <!-- Dynamic conversation cards inserted here -->
    </div>
  </div>
  
  <div id="toast" class="toast">Command copied to clipboard!</div>

  <script>
    const conversations = {chats_json};
    
    function formatDate(isoStr) {{
      if (!isoStr) return 'N/A';
      try {{
        const date = new Date(isoStr);
        return date.toLocaleDateString(undefined, {{
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        }});
      }} catch (e) {{
        return isoStr.substring(0, 16);
      }}
    }}
    
    function copyCommand(cid) {{
      const cmd = `agy --conversation ${{cid}}`;
      navigator.clipboard.writeText(cmd).then(() => {{
        showToast('📋 Copied: ' + cmd);
      }});
    }}
    
    function showToast(msg) {{
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2500);
    }}
    
    function renderCards(list) {{
      const container = document.getElementById('cards-container');
      document.getElementById('total-count').innerText = list.length;
      
      if (list.length === 0) {{
        container.innerHTML = `
          <div class="empty-state">
            <h3>No conversations found</h3>
            <p style="margin-top: 0.5rem;">Start a chat with <code>agy</code> in your terminal to see it here!</p>
          </div>
        `;
        return;
      }}
      
      container.innerHTML = list.map((c, i) => {{
        const title = c.title || c.first_prompt || 'Chat #' + (i + 1);
        const preview = c.first_prompt || c.last_prompt || 'No prompt preview available';
        const ws = c.workspace || '~';
        const updated = formatDate(c.updated_at || c.created_at);
        const turns = c.turn_count || 1;
        const cid = c.conversation_id;
        
        return `
          <div class="chat-card" data-search="${{(title + ' ' + preview + ' ' + ws + ' ' + cid).toLowerCase()}}">
            <div class="card-header">
              <div class="card-title">${{escapeHtml(title)}}</div>
              <div class="card-meta">
                <span class="turns-badge">${{turns}} ${{turns === 1 ? 'turn' : 'turns'}}</span>
                <span class="time-badge">🕒 ${{updated}}</span>
              </div>
            </div>
            
            <div class="prompt-preview">${{escapeHtml(preview)}}</div>
            
            <div class="card-footer">
              <div class="workspace-path" title="${{escapeHtml(ws)}}">
                📁 ${{escapeHtml(ws)}}
              </div>
              <div class="card-actions">
                <button class="btn btn-outline btn-sm" onclick="copyCommand('${{cid}}')">📋 Copy CLI Cmd</button>
                <a href="agy://resume/${{cid}}" class="btn btn-primary btn-sm">🚀 Resume in Terminal</a>
              </div>
            </div>
          </div>
        `;
      }}).join('');
    }}
    
    function escapeHtml(text) {{
      if (!text) return '';
      const div = document.createElement('div');
      div.innerText = text;
      return div.innerHTML;
    }}
    
    function filterCards() {{
      const query = document.getElementById('search').value.toLowerCase().trim();
      const filtered = conversations.filter(c => {{
        const haystack = ((c.title || '') + ' ' + (c.first_prompt || '') + ' ' + (c.workspace || '') + ' ' + (c.conversation_id || '')).toLowerCase();
        return haystack.includes(query);
      }});
      renderCards(filtered);
    }}
    
    // Initial Render
    renderCards(conversations);
  </script>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def export_all():
    conversations = get_all_conversations()
    generate_shortcuts(conversations)
    generate_markdown(conversations)
    generate_html(conversations)
