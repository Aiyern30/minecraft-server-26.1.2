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

# Used to coordinate "save finished" signal between the log reader thread
# and whichever thread issued the save command.
save_complete_event = threading.Event()

def send_to_server(command):
    """Send a command to the Minecraft server console"""
    global server_proc
    if server_proc and server_proc.poll() is None:
        server_proc.stdin.write(command + "\n")
        server_proc.stdin.flush()

def check_clean_working_tree():
    """Check for uncommitted/untracked local changes. Returns True if clean."""
    print("[GitSave] Checking for uncommitted local changes...")
    r = subprocess.run(["git", "status", "--porcelain"], cwd=SERVER_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        print("[GitSave] ERROR: git status failed:")
        print(r.stderr.strip())
        return False
    if r.stdout.strip():
        print("[GitSave] ERROR: Uncommitted local changes detected!")
        print("[GitSave] This usually means the server stopped/crashed before the last backup finished.")
        print("[GitSave] Changed files:")
        print(r.stdout.strip())
        print("\n[GitSave] Refusing to start until this is resolved. Options:")
        print("  1. Run the backup manually:  git add . && git commit -m \"manual save\" && git push")
        print("  2. Discard local changes (DANGER, loses data):  git checkout -- . && git clean -fd")
        return False
    print("[GitSave] Working tree clean.")
    return True

def git_pull():
    """Pull latest changes from GitHub before starting the server. Returns True on success."""
    print("[GitSave] Pulling latest changes from GitHub...")
    r = subprocess.run(["git", "pull", "--ff-only"], cwd=SERVER_DIR, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip())
    if r.returncode != 0:
        print("[GitSave] ERROR: git pull failed! (conflicts or diverged history?)")
        print("[GitSave] Refusing to start with potentially stale/conflicting world data.")
        print("[GitSave] Resolve manually (check 'git status' / 'git log') then restart.")
        return False
    print("[GitSave] Pull complete.\n")
    return True

def get_git_status_snapshot():
    """Returns the current 'git status --porcelain' output as a string."""
    r = subprocess.run(["git", "status", "--porcelain"], cwd=SERVER_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout

def wait_for_disk_to_settle(max_wait=120, poll_interval=2, stable_checks=2):
    """
    Poll git status repeatedly until the set of changed files stops growing
    and stays identical across several checks in a row. This protects against
    cases where the server log says "Saved the game" but the OS is still
    flushing region files to disk underneath it (common on Windows) -- if we
    git add/commit/push too early, we capture a partial, inconsistent set of
    files and the rest only show up later (or on the next backup), which
    looks like "it didn't push" even though a push did happen.

    Returns once status is stable, or after max_wait seconds as a fallback.
    """
    print("[GitSave] Waiting for world files to finish writing to disk...")
    start = time.time()
    last_status = None
    stable_count = 0

    while time.time() - start < max_wait:
        status = get_git_status_snapshot()
        if status is None:
            print("[GitSave] WARNING: git status failed while waiting for disk to settle.")
            time.sleep(poll_interval)
            continue

        if status == last_status:
            stable_count += 1
            if stable_count >= stable_checks:
                print(f"[GitSave] Disk appears settled after {int(time.time() - start)}s.")
                return
        else:
            stable_count = 0  # status changed, reset the stability counter

        last_status = status
        time.sleep(poll_interval)

    print(f"[GitSave] WARNING: Disk did not settle within {max_wait}s, proceeding anyway.")

def git_backup(triggered_by=None):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[GitSave] Running git backup at {date}...")

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

    if success:
        send_to_server(f'broadcast &a[GitSave] &fDone! Pushed to GitHub ({date})')
    else:
        send_to_server('broadcast &c[GitSave] &fGit push failed! Check console FAILED')

    print(f"[GitSave] Finished: {date}\n")

def wait_for_save_then_backup(triggered_by=None, timeout=60):
    """
    Block until the server logs that the save actually finished, then wait
    for the filesystem to stop changing (see wait_for_disk_to_settle), then
    run the git backup.
    """
    save_complete_event.clear()
    got_it = save_complete_event.wait(timeout=timeout)
    if not got_it:
        print("[GitSave] WARNING: Timed out waiting for 'Saved the game' message. "
              "Proceeding with backup anyway, but world files may still be mid-write.")
    wait_for_disk_to_settle()
    git_backup(triggered_by)

def run_server():
    global server_proc
    print("[GitSave] Starting Minecraft server...")
    print("[GitSave] /save-all in-game OR 'save-all' in console will force a full flush and push to GitHub\n")

    if not check_clean_working_tree():
        sys.exit(1)

    if not git_pull():
        sys.exit(1)

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

            # Detect in-game /save-all and grab who typed it.
            # Players can only type the plain "/save-all" command -- they can't
            # pass the "flush" argument themselves. So when we see this, we
            # issue "save-all flush" to the console on their behalf, which
            # forces Paper to immediately write every loaded chunk's region
            # files to disk instead of relying on its normal lazy save
            # scheduling. This is what was causing overworld .mca files to
            # not show as changed until a full server shutdown.
            if "issued server command: /save-all" in line:
                try:
                    player = line.split("]: ")[1].split(" issued")[0].strip()
                except Exception:
                    player = None
                print(f"[GitSave] Detected /save-all from: {player} -- forcing full flush...")
                send_to_server("save-all flush")
                threading.Thread(target=wait_for_save_then_backup, args=(player,), daemon=True).start()

            # Paper/Spigot logs this once the world(s) are actually flushed to disk.
            # Different forks phrase it slightly differently, so we check a couple of variants.
            lowered = line.lower()
            if "saved the game" in lowered or "saved the world" in lowered:
                save_complete_event.set()

            # Catch in-game /stop too (an op typing it directly, not through
            # your console). Vanilla/Paper triggers its own save on shutdown,
            # but that save happens AFTER the "stopping the server" message
            # and isn't guaranteed to finish before the process exits -- so
            # we still want our safety-net backup at the bottom of run_server
            # to fire once the process actually ends.
            if "issued server command: /stop" in line or "stopping the server" in lowered:
                print("[GitSave] Server is shutting down -- will run safety-net backup once it exits.")

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    while server_proc.poll() is None:
        try:
            user_input = input()
        except EOFError:
            break

        cmd_lower = user_input.strip().lower()

        if cmd_lower in ("save-all", "/save-all"):
            server_proc.stdin.write("save-all flush\n")
            server_proc.stdin.flush()
            print("[GitSave] Issued save-all flush from console -- waiting for save to finish...")
            threading.Thread(target=wait_for_save_then_backup, daemon=True).start()

        elif cmd_lower in ("stop", "/stop", "end", "shutdown"):
            # Force a final save BEFORE the server shuts down, wait for it to
            # actually finish, THEN let the server stop, THEN do one last
            # synchronous backup. This is the step that was missing -- without
            # it, anything that happened after your last manual /save-all
            # (which is almost always overworld activity, since players are
            # there) never gets committed.
            print("[GitSave] Shutdown requested -- saving world before stopping...")
            save_complete_event.clear()
            server_proc.stdin.write("save-all flush\n")
            server_proc.stdin.flush()
            got_it = save_complete_event.wait(timeout=60)
            if not got_it:
                print("[GitSave] WARNING: save confirmation timed out before shutdown; "
                      "proceeding anyway.")
            wait_for_disk_to_settle()

            print("[GitSave] Stopping server...")
            server_proc.stdin.write("stop\n")
            server_proc.stdin.flush()
            server_proc.wait()  # block here until the process actually exits

            print("[GitSave] Server stopped. Running final backup...")
            git_backup("shutdown")
            break

        else:
            server_proc.stdin.write(user_input + "\n")
            server_proc.stdin.flush()

    # Catch-all: if the loop exited some other way (e.g. server crashed,
    # or stdin closed via EOF) and the process has already ended without
    # us running a shutdown backup above, still try to save what we can.
    if server_proc.poll() is not None:
        print("[GitSave] Server process has exited. Running safety-net backup...")
        git_backup("process-exit")

    server_proc.wait()

if __name__ == "__main__":
    run_server()