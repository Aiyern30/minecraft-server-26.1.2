import subprocess
import shutil
import os
from datetime import datetime

# ---- CONFIG: edit these two paths if your setup changes ----

# Your JourneyMap data folder for this server. This MUST point at the
# modpack profile's own journeymap folder under .minecraft/versions/<profile>/,
# not the root .minecraft/journeymap folder -- TLauncher modpack profiles
# keep their own separate game directory, and the root folder can contain
# stale/unrelated data from a different setup.
JOURNEYMAP_SOURCE = (
    r"C:\Users\ianbi\AppData\Roaming\.minecraft\versions"
    r"\Immersed With Shaders IWS 26.1.2 Fabric-v1"
    r"\journeymap\data\mp\Ian~Own~s~Server"
)

# Your server's git repo folder (same one git-save.py lives in).
SERVER_REPO_DIR = r"C:\Users\ianbi\Desktop\Ian Server"

# Where inside the repo this gets copied to. Kept separate from the server's
# own world/ folder so it never gets mixed up with actual world data.
DEST_FOLDER_NAME = os.path.join("client-map-backup", "YourSonGays")

# Folder names to skip entirely when copying. "chunk_cache" holds JourneyMap's
# internal per-chunk performance cache (.jmc files) -- it's regenerated
# automatically from world data and isn't the actual visible map, so backing
# it up just bloats the repo with thousands of small files for no benefit.
EXCLUDED_FOLDER_NAMES = {"chunk_cache"}

# ---- End of config ----

DEST_PATH = os.path.join(SERVER_REPO_DIR, DEST_FOLDER_NAME)


def _ignore_excluded(dir_path, names):
    return [n for n in names if n in EXCLUDED_FOLDER_NAMES]


def copy_map_data():
    print(f"[MapSave] Source: {JOURNEYMAP_SOURCE}")
    print(f"[MapSave] Destination: {DEST_PATH}")

    if not os.path.isdir(JOURNEYMAP_SOURCE):
        print("[MapSave] ERROR: Source JourneyMap folder not found. "
              "Did the path change? Check JOURNEYMAP_SOURCE in this script.")
        return False

    # Remove the old copy first so deleted/renamed tiles don't linger forever
    # as stale leftovers that never get cleaned up.
    if os.path.isdir(DEST_PATH):
        print("[MapSave] Removing previous copy before refreshing...")
        shutil.rmtree(DEST_PATH)

    os.makedirs(os.path.dirname(DEST_PATH), exist_ok=True)

    print("[MapSave] Copying map data (skipping chunk_cache)... "
          "this may take a moment for large maps")
    shutil.copytree(JOURNEYMAP_SOURCE, DEST_PATH, ignore=_ignore_excluded)
    print("[MapSave] Copy complete.")
    return True


def git_push():
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[MapSave] Running git backup at {date}...")

    r = subprocess.run(["git", "add", DEST_FOLDER_NAME], cwd=SERVER_REPO_DIR,
                        capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip())

    r = subprocess.run(["git", "commit", "-m", f"map backup {date}"], cwd=SERVER_REPO_DIR,
                        capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip())
    if "nothing to commit" in r.stdout:
        print("[MapSave] No changes since last backup -- nothing to push.")
        return

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(f"[MapSave] > git push (attempt {attempt}/{max_attempts})")
        r = subprocess.run(["git", "push"], cwd=SERVER_REPO_DIR, capture_output=True, text=True)
        if r.stdout.strip(): print(r.stdout.strip())
        if r.stderr.strip(): print(r.stderr.strip())

        if r.returncode == 0:
            print("[MapSave] Push successful.")
            return

        rejected = "[remote rejected]" in r.stdout or "cannot lock ref" in r.stderr \
            or "failed to push" in r.stderr or "Updates were rejected" in r.stderr
        if rejected and attempt < max_attempts:
            print("[MapSave] Push rejected, pulling with rebase and retrying...")
            rp = subprocess.run(["git", "pull", "--rebase"], cwd=SERVER_REPO_DIR,
                                 capture_output=True, text=True)
            if rp.stdout.strip(): print(rp.stdout.strip())
            if rp.stderr.strip(): print(rp.stderr.strip())
            if rp.returncode != 0:
                print("[MapSave] ERROR: git pull --rebase failed. Resolve manually.")
                return
            continue
        else:
            print("[MapSave] ERROR: push failed and is not auto-recoverable.")
            return


if __name__ == "__main__":
    if copy_map_data():
        git_push()
    print("[MapSave] Done.")