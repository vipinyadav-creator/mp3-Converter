import os
import re
import io
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# moviepy 1.x aur 2.x dono ke liye
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip

# --------- DRIVE FOLDER IDS ----------
VIDEO_FOLDER_ID = '1WmuW59DPlYSeO4s0Qp01zDNm3wOIQ4pC'   # NAYA source folder (subfolders bhi scan honge)
MP3_FOLDER_ID = '1YIbL1VXAn8lJSeqCVej_csoYWNgM236N'     # "Meeting MP3" (yahin MP3 jaayegi)
# -------------------------------------

FOLDER_MIME = "application/vnd.google-apps.folder"


def safe_filename(name):
    name = name.replace("/", "-").replace(":", "-")
    name = re.sub(r'[<>:"\\|?*]', '', name)
    return name


def download_file(service, file_id, filename):
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(filename, 'wb') as fh:          # file ab properly close hogi
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Downloading {filename}: {int(status.progress() * 100)}%")


def list_children(service, folder_id):
    """Ek folder ke seedhe andar ki saari files/folders (1000+ bhi)"""
    items = []
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return items


def get_all_videos_recursive(service, root_folder_id):
    """Folder aur uske ANDAR ke saare subfolders (kitne bhi level) se MP4 videos"""
    all_videos = []
    folders_to_scan = [(root_folder_id, "")]
    seen_folders = set()

    while folders_to_scan:
        folder_id, path = folders_to_scan.pop()
        if folder_id in seen_folders:
            continue
        seen_folders.add(folder_id)

        for f in list_children(service, folder_id):
            if f["mimeType"] == FOLDER_MIME:
                sub_path = f"{path}/{f['name']}" if path else f["name"]
                print(f"   📁 Subfolder mila: {sub_path}")
                folders_to_scan.append((f["id"], sub_path))
            elif f["mimeType"] == "video/mp4":
                f["path"] = path
                all_videos.append(f)

    return all_videos


def start_process():
    if not os.path.exists("token.json"):
        print("❌ token.json nahi mila")
        return

    creds = Credentials.from_authorized_user_file("token.json")
    service = build("drive", "v3", credentials=creds)

    # 1. MP3 folder ki existing files
    print("📂 Scanning MP3 folder for existing files...")
    existing_mp3_names = {
        f["name"].strip().lower()
        for f in list_children(service, MP3_FOLDER_ID)
        if f["mimeType"] != FOLDER_MIME
    }
    print(f"✅ Found {len(existing_mp3_names)} existing MP3s.")

    # 2. Video folder + saare subfolders
    print("📂 Scanning Video folder + all subfolders...")
    videos = get_all_videos_recursive(service, VIDEO_FOLDER_ID)
    print(f"✅ Found {len(videos)} total videos to check.")

    for video in videos:
        video_name = video["name"]
        video_id = video["id"]
        location = video["path"] or "(main folder)"

        base_name = os.path.splitext(video_name)[0]
        mp3_name = base_name.strip() + ".mp3"

        if mp3_name.lower() in existing_mp3_names:
            print(f"⏭ Skip (already exists): {mp3_name}")
            continue

        print(f"\n🎬 Processing: {location}/{video_name}")

        # Meet recordings ke naam mein ".mp4" nahi hota, isliye local file ko extension dena zaroori hai
        safe_video = safe_filename(base_name.strip()) + ".mp4"
        safe_mp3 = safe_filename(mp3_name)

        try:
            print("⬇ Downloading video...")
            download_file(service, video_id, safe_video)

            print("🎧 Converting to MP3...")
            video_clip = VideoFileClip(safe_video)
            if video_clip.audio is None:
                video_clip.close()
                print(f"⚠ Is video mein audio nahi hai, skip: {video_name}")
                continue
            video_clip.audio.write_audiofile(safe_mp3, logger=None)
            video_clip.close()

            print("⬆ Uploading MP3...")
            file_metadata = {"name": mp3_name, "parents": [MP3_FOLDER_ID]}
            media = MediaFileUpload(safe_mp3, mimetype="audio/mpeg")
            service.files().create(
                body=file_metadata, media_body=media, supportsAllDrives=True
            ).execute()
            del media   # file handle chhodo taaki delete ho sake

            existing_mp3_names.add(mp3_name.lower())
            print(f"✅ Success: {mp3_name}")

        except Exception as e:
            print(f"❌ Error with {video_name}: {e}")
        finally:
            if os.path.exists(safe_video):
                os.remove(safe_video)
            if os.path.exists(safe_mp3):
                os.remove(safe_mp3)


if __name__ == "__main__":
    start_process()
