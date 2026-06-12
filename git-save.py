import subprocess
import sys
import os
import time
from datetime import datetime

# ── Config ────────────────────────────────
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
JAR = "paper-26.1.2-69.jar"
# ──────────────────────────────────────────

def git_backup():
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[GitSave] Running git backup at {date}...")

    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", date],
        ["git", "push"],
    ]

    for cmd in commands:
        print(f"[GitSave] > {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=SERVER_DIR, capture_output=True, text=True)
        if result.stdout.strip(): print(result.stdout.strip())
        if result.stderr.strip(): print(result.stderr.strip())

    print(f"[GitSave] ✅ Done!\n")

def run_server():
    print("[GitSave] Starting Minecraft server...")
    print("[GitSave] Type 'save-all' to save AND push to GitHub\n")

    proc = subprocess.Popen(
        ["java", "-Xmx2G", "-Xms1G", "-jar", JAR, "nogui"],
        cwd=SERVER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    import threading

    # Thread to print server output
    def read_output():
        for line in proc.stdout:
            print(line, end="")
            sys.stdout.flush()

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    # Main loop: read your input and forward to server
    while proc.poll() is None:
        try:
            user_input = input()
        except EOFError:
            break

        if user_input.strip().lower() in ("save-all", "/save-all"):
            # Send save-all to server
            proc.stdin.write("save-all\n")
            proc.stdin.flush()
            time.sleep(2)  # wait for save to finish
            git_backup()
        else:
            proc.stdin.write(user_input + "\n")
            proc.stdin.flush()

    proc.wait()

if __name__ == "__main__":
    run_server()
