import subprocess
import sys
import os
import time
import threading
from datetime import datetime

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
JAR = "paper-26.1.2-69.jar"

def git_backup():
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[GitSave] Running git backup at {date}...")
    cmds = [["git", "add", "."], ["git", "commit", "-m", date], ["git", "push"]]
    for cmd in cmds:
        print(f"[GitSave] > {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=SERVER_DIR, capture_output=True, text=True)
        if r.stdout.strip(): print(r.stdout.strip())
        if r.stderr.strip(): print(r.stderr.strip())
    print(f"[GitSave] Done! Pushed: {date}\n")

def run_server():
    print("[GitSave] Starting Minecraft server...")
    print("[GitSave] /save-all in-game OR 'save-all' in console will push to GitHub\n")

    proc = subprocess.Popen(
        ["java", "-Xmx2G", "-Xms1G", "-jar", JAR, "nogui"],
        cwd=SERVER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def read_output():
        for line in proc.stdout:
            print(line, end="")
            sys.stdout.flush()
            # Watch for in-game /save-all — Paper logs it like:
            # [INFO]: PlayerName issued server command: /save-all
            if "issued server command: /save-all" in line:
                print("[GitSave] Detected in-game /save-all!")
                time.sleep(2)  # wait for world to finish saving
                git_backup()

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    # Console input loop
    while proc.poll() is None:
        try:
            user_input = input()
        except EOFError:
            break

        if user_input.strip().lower() in ("save-all", "/save-all"):
            proc.stdin.write("save-all\n")
            proc.stdin.flush()
            time.sleep(2)
            git_backup()
        else:
            proc.stdin.write(user_input + "\n")
            proc.stdin.flush()

    proc.wait()

if __name__ == "__main__":
    run_server()