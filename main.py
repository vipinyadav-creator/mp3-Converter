import os
import re
import io
import sys
import time
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# moviepy 1.x aur 2.x dono ke liye
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip

# --------- DRIVE FOLDER IDS ----------
# Yahan jitne bhi source folder chahiye daal do (subfolders bhi scan honge)
VIDEO_FOLDER_IDS = [
    '1WmuW59DPlYSeO4s0Qp01zDNm3wOIQ4pC',   # purana source folder
    '1RmSCD8s-hdInRP45sHQiIYjZ_x428lWE',   # NAYA "Google Meet" folder
]
MP3_FOLDER_ID = '1YIbL1VXAn8lJSeqCVej_csoYWNgM236N'     # "Meeting MP3" (yahin MP3 jaayegi)
# -------------------------------------

RUN_EVERY_SECONDS = 5 * 60      # har 5 minute me check
LOCK_FILE = "mp4_to_mp3.lock"   # do copy ek saath na chalein
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def safe_filename(name):
    name = name.replace("/", "-").replace(":", "-")
    name = re.sub(r'[<>:"\\|?*]', '', name)
    return name


def get_service():
    """Har cycle me fresh service; token expire ho to refresh karke token.json me save"""
    creds = Credentials.from_authorized_user_file("token.json")
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download_file(service, file_id, filename):
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(filename, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Downloading {filename}: {int(status.progress() * 100)}%", flush=True)


def list_children(service, folder_id):
    """Ek folder ke seedhe andar ki saari files/folders (1000+ bhi)"""
    items = []
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return items


def get_all_videos_recursive(service, root_folder_ids):
    """Saare source folders + unke andar ke saare subfolders se MP4 videos"""
    all_videos = []
    seen_videos = set()
    seen_folders = set()
    folders_to_scan = [(fid, "") for fid in root_folder_ids]

    while folders_to_scan:
        folder_id, path = folders_to_scan.pop()
        if folder_id in seen_folders:
            continue
        seen_folders.add(folder_id)

        try:
            children = list_children(service, folder_id)
        except Exception as e:
            log(f"⚠ Folder open nahi hua ({folder_id}): {e}")
            continue

        for f in children:
            if f["mimeType"] == FOLDER_MIME:
                sub_path = f"{path}/{f['name']}" if path else f["name"]
                folders_to_scan.append((f["id"], sub_path))
            elif f["mimeType"] == "video/mp4" and f["id"] not in seen_videos:
                seen_videos.add(f["id"])          # ek hi video do folders me ho to bhi ek baar
                f["path"] = path
                all_videos.append(f)

    return all_videos


def start_process():
    if not os.path.exists("token.json"):
        log("❌ token.json nahi mila")
        return

    service = get_service()

    # 1. MP3 folder ki existing files
    log("📂 Scanning MP3 folder for existing files...")
    existing_mp3_names = {
        f["name"].strip().lower()
        for f in list_children(service, MP3_FOLDER_ID)
        if f["mimeType"] != FOLDER_MIME
    }
    log(f"✅ Found {len(existing_mp3_names)} existing MP3s.")

    # 2. Saare video folders + subfolders
    log(f"📂 Scanning {len(VIDEO_FOLDER_IDS)} video folders + all subfolders...")
    videos = get_all_videos_recursive(service, VIDEO_FOLDER_IDS)
    pending = [
        v for v in videos
        if (os.path.splitext(v["name"])[0].strip() + ".mp3").lower() not in existing_mp3_names
    ]
    log(f"✅ Total videos: {len(videos)} | Pending (MP3 nahi bani): {len(pending)}")

    for video in pending:
        video_name = video["name"]
        video_id = video["id"]
        location = video["path"] or "(main folder)"

        base_name = os.path.splitext(video_name)[0]
        mp3_name = base_name.strip() + ".mp3"

        log(f"🎬 Processing: {location}/{video_name}")

        # Meet recordings ke naam mein ".mp4" nahi hota, isliye local file ko extension dena zaroori hai
        safe_video = safe_filename(base_name.strip()) + ".mp4"
        safe_mp3 = safe_filename(mp3_name)

        try:
            log("⬇ Downloading video...")
            download_file(service, video_id, safe_video)

            log("🎧 Converting to MP3...")
            video_clip = VideoFileClip(safe_video)
            if video_clip.audio is None:
                video_clip.close()
                log(f"⚠ Is video mein audio nahi hai, skip: {video_name}")
                continue
            video_clip.audio.write_audiofile(safe_mp3, logger=None)
            video_clip.close()

            log("⬆ Uploading MP3...")
            file_metadata = {"name": mp3_name, "parents": [MP3_FOLDER_ID]}
            media = MediaFileUpload(safe_mp3, mimetype="audio/mpeg")
            service.files().create(
                body=file_metadata, media_body=media, supportsAllDrives=True
            ).execute()
            del media   # file handle chhodo taaki delete ho sake

            existing_mp3_names.add(mp3_name.lower())
            log(f"✅ Success: {mp3_name}")

        except Exception as e:
            log(f"❌ Error with {video_name}: {e}")
        finally:
            if os.path.exists(safe_video):
                os.remove(safe_video)
            if os.path.exists(safe_mp3):
                os.remove(safe_mp3)


def run_once_with_lock():
    """Lock: agar pichla run abhi chal raha hai to naya run skip"""
    if os.path.exists(LOCK_FILE):
        age = time.time() - os.path.getmtime(LOCK_FILE)
        if age < 6 * 60 * 60:          # 6 ghante se purana lock = atka hua maan ke hata do
            log("⏳ Pichla run abhi chal raha hai, is baar skip.")
            return
        os.remove(LOCK_FILE)
    open(LOCK_FILE, "w").close()
    try:
        start_process()
    except Exception as e:
        log(f"❌ Run fail hua (agle cycle me phir try hoga): {e}")
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


if __name__ == "__main__":
    # python mp4_to_mp3.py          -> har 5 min me lagatar chalega (band karne ke liye Ctrl+C)
    # python mp4_to_mp3.py --once   -> sirf ek baar (Task Scheduler / cron ke liye)
    if "--once" in sys.argv:
        run_once_with_lock()
    else:
        log(f"🔁 Auto mode: har {RUN_EVERY_SECONDS // 60} minute me check hoga. Band karne ke liye Ctrl+C")
        while True:
            started = time.time()
            run_once_with_lock()
            wait = max(0, RUN_EVERY_SECONDS - (time.time() - started))
            log(f"😴 Agla check {int(wait // 60)} min {int(wait % 60)} sec baad...\n")
            time.sleep(wait)
