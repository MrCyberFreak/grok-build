#!/usr/bin/env python3
"""One-click launcher for the Grok Chat History viewer.

ElevenLabs API key is ALWAYS read from PowerShell SecretStore at launch time.
It is injected only into the in-memory served page (never written to disk or localStorage).
"""
import os
import sys
import webbrowser
import threading
import time
import subprocess
import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

UI_DIR = Path(__file__).parent / "ui"
PORT = 8765

# Read the canonical name from the harness config for the-voice faculty.
# JARVIS (via the expert) confirmed this is the name the hooks and Jarvis2 use.
def _get_elevenlabs_secret_name() -> str:
    cfg_path = Path(r"X:\Grok_Build\.grok\hooks\jarvis-voice.config.json")
    try:
        if cfg_path.exists():
            import json
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            name = cfg.get("secret_name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:
        pass
    return "ElevenLabsApiKey"  # documented default for the-voice

# === Viewer-specific ElevenLabs key name (for separation) ===
# IMPORTANT: This is the name you must use when storing the key below.
VIEWER_ELEVENLABS_SECRET_NAME = "ChatHistoryElevenLabsKey"

ELEVENLABS_SECRET_NAMES = [VIEWER_ELEVENLABS_SECRET_NAME]

def get_key_from_secretstore():
    """Fetch ElevenLabs key from PowerShell SecretStore using the same logic as the official harness.
    This handles module path quirks (OneDrive etc).
    """
    for name in ELEVENLABS_SECRET_NAMES:
        for exe in ("pwsh", "powershell"):
            try:
                # Build a robust command that does the same path fix + import as elevenlabs-speak.ps1
                ps_code = f'''
function Get-ElevenKey([string]$name) {{
    if (-not (Get-Module -ListAvailable -Name Microsoft.PowerShell.SecretManagement)) {{
        $docs = @(
            [Environment]::GetFolderPath('MyDocuments'),
            (Join-Path $env:USERPROFILE 'Documents'),
            (Join-Path $env:USERPROFILE 'OneDrive\\Documents')
        ) | Where-Object {{ $_ }} | Select-Object -Unique
        foreach ($d in $docs) {{
            foreach ($sub in @('PowerShell\\Modules','WindowsPowerShell\\Modules')) {{
                $p = Join-Path $d $sub
                if (Test-Path -LiteralPath $p) {{ $env:PSModulePath = "$p;$($env:PSModulePath)" }}
            }}
        }}
    }}
    Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
    Get-Secret -Name $name -AsPlainText -ErrorAction Stop
}}
Get-ElevenKey '{name}'
'''
                cmd = [
                    exe, "-NoProfile", "-NonInteractive", "-Command", ps_code
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="ignore"
                )
                key = (result.stdout or "").strip()
                if key and len(key) > 10:
                    print(f"[secretstore] Loaded ElevenLabs key from secret name '{name}' using {exe}")
                    return key
                else:
                    # Print stderr for diagnosis if it failed
                    if result.stderr.strip():
                        print(f"[secretstore] {exe} stderr for {name}: {result.stderr.strip()[:200]}")
            except Exception as e:
                pass
    print("[secretstore] WARNING: Could not retrieve ElevenLabs key from SecretStore.")
    print("             Tried names:", ELEVENLABS_SECRET_NAMES)
    print("             Run this to test manually in pwsh:")
    print(f"             Get-Secret -Name '{ELEVENLABS_SECRET_NAMES[0]}' -AsPlainText")
    print("             If the above works but launcher fails, there may be a module path issue in subprocess.")
    print("             Read-aloud will be disabled until a key is available.")
    return None

class ElevenLabsHandler(SimpleHTTPRequestHandler):
    """Serves the UI with the ElevenLabs key injected from SecretStore at runtime only."""

    ELEVENLABS_KEY = None  # set at server start

    def log_message(self, format, *args):
        # Keep it quiet like before
        if any(x in args[0] for x in ["/data.json", "/index.html", "/"]):
            print(f"[server] {args[0]}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_index_with_key()
            return
        # Normal static serving for data.json, assets/, etc.
        super().do_GET()

    def _serve_index_with_key(self):
        index_path = UI_DIR / "index.html"
        if not index_path.exists():
            self.send_error(404, "index.html not found")
            return

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            self.send_error(500, f"Failed to read index: {e}")
            return

        key = self.ELEVENLABS_KEY or ""
        # Inject a tiny script early so the rest of the page's JS can read it.
        # This runs only in the browser tab for this launch.
        # Also provide the canonical voice_id from the same harness config JARVIS uses.
        voice_id = "JBFqnCBsd6RMkjVDRZzb"  # George (warm refined British male) - from jarvis-voice.config.json
        injection = f'''<script>
window.ELEVENLABS_API_KEY = {json.dumps(key)};
window.DEFAULT_ELEVENLABS_VOICE_ID = {json.dumps(voice_id)};
</script>
'''
        # The UI input will pick up the default on load if nothing in localStorage yet.

        # Insert right before </head> so it's available before other scripts.
        if "</head>" in html:
            html = html.replace("</head>", injection + "</head>", 1)
        else:
            # Fallback: put it at the very start of body
            html = injection + html

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def start_server():
    os.chdir(UI_DIR)
    ElevenLabsHandler.ELEVENLABS_KEY = get_key_from_secretstore()

    server = HTTPServer(("127.0.0.1", PORT), ElevenLabsHandler)
    print(f"Serving Grok Chat History at http://localhost:{PORT}")
    if ElevenLabsHandler.ELEVENLABS_KEY:
        print("ElevenLabs key injected from SecretStore (in-memory only for this session).")
    else:
        print("ElevenLabs key NOT available. Read-aloud will show an error.")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def main():
    if not (UI_DIR / "index.html").exists():
        print("ERROR: ui/index.html not found. Run from project root.")
        sys.exit(1)

    # Start server in background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Give server a moment then open browser
    time.sleep(1.0)
    url = f"http://localhost:{PORT}"
    print(f"Opening {url} ...")
    webbrowser.open(url)

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
