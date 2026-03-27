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
VERSION = "1.0.2"
VLC_PATH = os.getenv("VLC_PATH")
WATCH_FOLDER = os.getenv("WATCH_FOLDER")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 900))
GITHUB_VERSION_URL = os.getenv("GITHUB_VERSION_URL")
GITHUB_SCRIPT_URL = os.getenv("GITHUB_SCRIPT_URL")
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi')
# ---------------------

print("This brilliant solution was made by Alex Grimsey :)")


#I fixed this for you because I realised if the URL was wrong in the .env it would wipe the entire python file and replace it with 404: Not Found
def check_for_script_updates(handler):
    try:
        print(f"Checking for script updates (Current v{VERSION})...")
        response = requests.get(GITHUB_VERSION_URL, timeout=10)
        
        if response.status_code != 200:
            print(f"Update check failed: Server returned {response.status_code}")
            return

        remote_version = response.text.strip()

        if remote_version != VERSION:
            print(f"Update found: {remote_version}. Downloading...")
            
            # Download to memory first
            new_content = requests.get(GITHUB_SCRIPT_URL, timeout=20)
            
            if new_content.status_code == 200:
                #Close VLC before updating
                if handler.process:
                    print("Closing VLC for update...")
                    handler.process.terminate()
                    try:
                        handler.process.wait(timeout=3)
                    except:
                        handler.process.kill()
                temp_file = __file__ + ".tmp"
                with open(temp_file, "wb") as f:
                    f.write(new_content.content)
                os.replace(temp_file, __file__)
                
                print("Update applied successfully. Restarting script...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                print(f"Abort: Update file URL returned {new_content.status_code}")

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
            # Delay to allow file transfer to complete
            time.sleep(10) 
            self.start_vlc(event.src_path)

def background_maintenance(handler):
    """Main loop for updates."""
    while True:
        time.sleep(UPDATE_INTERVAL)
        check_for_script_updates(handler)

        print("Checking for VLC software updates...")
        try:
            result = subprocess.run(
                ["winget", "upgrade", "--id", "VideoLAN.VLC", "--silent", "--accept-source-agreements"],
                capture_output=True, text=True
            )
            if "Successfully installed" in result.stdout:
                print("VLC updated. Restarting playback...")
                handler.start_vlc(handler.get_latest_video())
        except FileNotFoundError:
            print("Winget not found. Skipping VLC software update.")

if __name__ == "__main__":
    if not WATCH_FOLDER or not os.path.exists(WATCH_FOLDER):
        print(f"Error: Folder {WATCH_FOLDER} not found.")
        exit()

    handler = VideoHandler()
    check_for_script_updates(handler)
    
    maint_thread = threading.Thread(target=background_maintenance, args=(handler,), daemon=True)
    maint_thread.start()

    observer = Observer()
    observer.schedule(handler, WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            if handler.process and handler.process.poll() is not None:
                handler.start_vlc(handler.get_latest_video())
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()