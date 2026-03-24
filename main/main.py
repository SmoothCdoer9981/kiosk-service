import os
import sys
import subprocess
import time
import threading
import requests
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load variables from .env
load_dotenv()

# --- CONFIGURATION ---
VERSION = "1.0.1"
VLC_PATH = os.getenv("VLC_PATH")
WATCH_FOLDER = os.getenv("WATCH_FOLDER")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 900))
GITHUB_VERSION_URL = os.getenv("GITHUB_VERSION_URL")
GITHUB_SCRIPT_URL = os.getenv("GITHUB_SCRIPT_URL")
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi')
# ---------------------

print("This brilliant solution was made by Alex Grimsey :)")

def check_for_script_updates(handler):
    """Checks GitHub, closes VLC, and restarts the script if an update is found."""
    try:
        print(f"Checking for script updates (Current v{VERSION})...")
        response = requests.get(GITHUB_VERSION_URL, timeout=10)
        remote_version = response.text.strip()

        if remote_version != VERSION:
            print(f"Update found: {remote_version}. Cleaning up...")
            
            # 1. Close VLC before updating
            if handler.process:
                print("Closing VLC for update...")
                handler.process.terminate()
                try:
                    handler.process.wait(timeout=3)
                except:
                    handler.process.kill()

            # 2. Download new version
            new_content = requests.get(GITHUB_SCRIPT_URL, timeout=20)
            with open(__file__, "wb") as f:
                f.write(new_content.content)
            
            print("Update applied. Restarting script...")
            # 3. Restart the script process
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"Script update check failed: {e}")

class VideoHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.current_video = self.get_latest_video()
        self.start_vlc(self.current_video)

    def get_latest_video(self):
        try:
            files = [os.path.join(WATCH_FOLDER, f) for f in os.listdir(WATCH_FOLDER) 
                     if f.lower().endswith(VIDEO_EXTENSIONS)]
            return max(files, key=os.path.getmtime) if files else None
        except Exception: return None

    def start_vlc(self, video_path):
        if not video_path: return
        
        if self.process:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except: self.process.kill()

        self.current_video = video_path
        
        cmd = [
            VLC_PATH, 
            "--loop", 
            "--fullscreen", 
            "--no-video-title-show", 
            "--no-qt-updates-notif", 
            "--no-qt-privacy-ask", 
            "--mouse-hide-timeout", "0",
            video_path
        ]
        self.process = subprocess.Popen(cmd)

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(VIDEO_EXTENSIONS):
            print(f"New video detected: {os.path.basename(event.src_path)}")
            time.sleep(10) 
            self.start_vlc(event.src_path)

def background_maintenance(handler):
    """Main loop for updates."""
    while True:
        time.sleep(UPDATE_INTERVAL)
        
        # Check for Script Updates (Pass handler to allow VLC closure)
        check_for_script_updates(handler)

        # Check for VLC software updates via Winget
        print("Checking for VLC software updates...")
        result = subprocess.run(
            ["winget", "upgrade", "--id", "VideoLAN.VLC", "--silent", "--accept-source-agreements"],
            capture_output=True, text=True
        )
        if "Successfully installed" in result.stdout:
            print("VLC updated. Restarting playback...")
            handler.start_vlc(handler.get_latest_video())

if __name__ == "__main__":
    if not WATCH_FOLDER or not os.path.exists(WATCH_FOLDER):
        print(f"Error: Folder {WATCH_FOLDER} not found.")
        exit()

    # Create handler first so update check can access it
    handler = VideoHandler()

    # Initial update check
    check_for_script_updates(handler)
    
    # Thread 1: Maintenance
    maint_thread = threading.Thread(target=background_maintenance, args=(handler,), daemon=True)
    maint_thread.start()

    # Thread 2: Monitor folder
    observer = Observer()
    observer.schedule(handler, WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            # Auto-restart VLC if it crashes or is closed
            if handler.process and handler.process.poll() is not None:
                handler.start_vlc(handler.get_latest_video())
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
