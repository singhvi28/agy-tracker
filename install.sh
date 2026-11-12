#!/usr/bin/env bash
# ==============================================================================
# agy-tracker: Installer and Setup Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DEST="${HOME}/.local/bin"
AGY_CLI_DIR="${HOME}/.gemini/antigravity-cli"
APPS_DIR="${HOME}/.local/share/applications"

echo "=== Installing agy-tracker ==="

mkdir -p "${BIN_DEST}"
mkdir -p "${APPS_DIR}"
mkdir -p "${AGY_CLI_DIR}"

# 1. Symlink or copy binaries to ~/.local/bin
echo "[1/4] Installing executable scripts to ${BIN_DEST}..."
ln -sf "${SCRIPT_DIR}/bin/agy-tracker" "${BIN_DEST}/agy-tracker"
ln -sf "${SCRIPT_DIR}/bin/agy-open-url" "${BIN_DEST}/agy-open-url"
chmod +x "${SCRIPT_DIR}/bin/agy-tracker" "${SCRIPT_DIR}/bin/agy-open-url"

# Also symlink into ~/.gemini/antigravity-cli if that directory exists
if [[ -d "${AGY_CLI_DIR}" ]]; then
    mkdir -p "${AGY_CLI_DIR}/bin"
    ln -sf "${SCRIPT_DIR}/bin/agy-tracker" "${AGY_CLI_DIR}/bin/agy-tracker"
    ln -sf "${SCRIPT_DIR}/bin/agy-open-url" "${AGY_CLI_DIR}/bin/agy-open-url"
    
    # Ensure tracker package is accessible from ~/.gemini/antigravity-cli
    if [[ ! -e "${AGY_CLI_DIR}/tracker" ]]; then
        ln -sf "${SCRIPT_DIR}/tracker" "${AGY_CLI_DIR}/tracker"
    fi
fi

# 2. Register custom desktop protocol handler for agy:// and antigravity://
echo "[2/4] Registering desktop URL protocol handlers..."
DESKTOP_FILE="${APPS_DIR}/agy-url-handler.desktop"
cat << EOF > "${DESKTOP_FILE}"
[Desktop Entry]
Type=Application
Name=Antigravity Chat Launcher
Comment=Opens Antigravity CLI conversations in terminal
Exec=${BIN_DEST}/agy-open-url %u
Terminal=false
MimeType=x-scheme-handler/agy;x-scheme-handler/antigravity;
NoDisplay=true
Categories=Development;
EOF

if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default agy-url-handler.desktop x-scheme-handler/agy || true
    xdg-mime default agy-url-handler.desktop x-scheme-handler/antigravity || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" 2>/dev/null || true
fi

# 3. Verify PATH
echo "[3/4] Verifying PATH..."
if [[ ":$PATH:" != *":${BIN_DEST}:"* ]]; then
    echo "Notice: ${BIN_DEST} is not in your PATH. Add it to ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 4. Initial Sync
echo "[4/4] Running initial sync..."
"${SCRIPT_DIR}/bin/agy-tracker" sync || true

echo "=== Installation Complete! ==="
echo "Run 'agy-tracker list' to view recent sessions."
echo "Run 'agy-tracker web' to open the interactive dashboard."
echo "Run 'agy-tracker resume <ID> [--danger]' to resume a session."
