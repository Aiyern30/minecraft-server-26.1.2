import subprocess
import sys
import os
import time
import threading
from datetime import datetime

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
JAR = "paper-26.1.2-69.jar"

# Global reference to server process
server_proc = None

def send_to_server(command):
    """Send a command to the Minecraft server console"""
    global server_proc
    if server_proc and server_proc.poll() is None:
        server_proc.stdin.write(command + "\n")
        server_proc.stdin.flush()

def git_backup(triggered_by=None):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[GitSave] Running git backup at {date}...")

    # Notify in-game that backup started
    if triggered_by:
        send_to_server(f'tell {triggered_by} &a[GitSave] &fPushing to GitHub...')
    else:
        send_to_server('broadcast &a[GitSave] &fPushing to GitHub...')

    cmds = [["git", "add", "."], ["git", "commit", "-m", date], ["git", "push"]]
    success = True

    for cmd in cmds:
        print(f"[GitSave] > {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=SERVER_DIR, capture_output=True, text=True)
        if r.stdout.strip(): print(r.stdout.strip())
        if r.stderr.strip(): print(r.stderr.strip())
        # Allow "nothing to commit" but catch real failures
        if r.returncode != 0 and "nothing to commit" not in r.stdout and cmd[1] != "commit":
            success = False
            break

    # Notify in-game with real result
    if success:
        if triggered_by:
            send_to_server(f'tell {triggered_by} &a[GitSave] &fDone! Pushed to GitHub ✅ ({date})')
        else:
            send_to_server(f'broadcast &a[GitSave] &fDone! Pushed to GitHub ✅ ({date})')
    else:
        if triggered_by:
            send_to_server(f'tell {triggered_by} &c[GitSave] &fGit push failed! Check console ❌')
        else:
            send_to_server('broadcast &c[GitSave] &fGit push failed! Check console ❌')

    print(f"[GitSave] Finished: {date}\n")

def run_server():
    global server_proc
    print("[GitSave] Starting Minecraft server...")
    print("[GitSave] /save-all in-game OR 'save-all' in console will push to GitHub\n")

    server_proc = subprocess.Popen(
        ["java", "-Xmx2G", "-Xms1G", "-jar", JAR, "nogui"],
        cwd=SERVER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def read_output():
        for line in server_proc.stdout:
            print(line, end="")
            sys.stdout.flush()
            # Detect in-game /save-all and grab who typed it
            if "issued server command: /save-all" in line:
                # Extract player name from log line like:
                # [13:49:58 INFO]: PlayerName issued server command: /save-all
                try:
                    player = line.split("]: ")[1].split(" issued")[0].strip()
                except:
                    player = None
                print(f"[GitSave] Detected /save-all from: {player}")
                time.sleep(2)  # wait for world save to finish
                threading.Thread(target=git_backup, args=(player,), daemon=True).start()

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    while server_proc.poll() is None:
        try:
            user_input = input()
        except EOFError:
            break

        if user_input.strip().lower() in ("save-all", "/save-all"):
            server_proc.stdin.write("save-all\n")
            server_proc.stdin.flush()
            time.sleep(2)
            threading.Thread(target=git_backup, daemon=True).start()
        else:
            server_proc.stdin.write(user_input + "\n")
            server_proc.stdin.flush()

    server_proc.wait()

if __name__ == "__main__":
    run_server()
