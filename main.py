import os
import re
import io
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from moviepy.editor import VideoFileClip

# --------- DRIVE FOLDER IDS ----------
VIDEO_FOLDER_ID = '1B-8digPGU9ZGFFfc56FEIg-suUvHYSRZ'
MP3_FOLDER_ID = '1YIbL1VXAn8lJSeqCVej_csoYWNgM236N'
# -------------------------------------

def safe_filename(name):
    name = name.replace("/", "-").replace(":", "-")
    name = re.sub(r'[<>:"\\|?*]', '', name)
    return name

def download_file(service, file_id, filename):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(filename, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        if status:
            print(f"Downloading {filename}: {int(status.progress() * 100)}%")

def get_all_files_in_folder(service, folder_id, mime_type=None):
    """Folder ki SARI files nikalne ke liye function (Handles 1000+ files)"""
    all_files = []
    page_token = None
    
    # Query build karein
    query = f"'{folder_id}' in parents and trashed=false"
    if mime_type:
        query += f" and mimeType='{mime_type}'"

    while True:
        results = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageToken=page_token
        ).execute()
        
        all_files.extend(results.get("files", []))
        
        page_token = results.get('nextPageToken', None)
        if not page_token:
            break
            
    return all_files

def start_process():
    if not os.path.exists("token.json"):
        print("❌ token.json nahi mila")
        return

    creds = Credentials.from_authorized_user_file("token.json")
    service = build("drive", "v3", credentials=creds)

    # 1. Pehle MP3 folder ki sari files scan karein
    print("📂 Scanning MP3 folder for existing files...")
    existing_mp3_files = get_all_files_in_folder(service, MP3_FOLDER_ID)
    existing_mp3_names = {f["name"].strip().lower() for f in existing_mp3_files}
    print(f"✅ Found {len(existing_mp3_names)} existing MP3s.")

    # 2. Phir Video folder ki sari videos scan karein (Even if 1000+)
    print("📂 Scanning Video folder (this may take a moment)...")
    videos = get_all_files_in_folder(service, VIDEO_FOLDER_ID, mime_type='video/mp4')
    print(f"✅ Found {len(videos)} total videos to check.")

    for video in videos:
        video_name = video["name"]
        video_id = video["id"]

        base_name = os.path.splitext(video_name)[0]
        mp3_name = base_name.strip() + ".mp3"

        # Duplicate Check: Agar naam match hota hai to skip
        if mp3_name.lower() in existing_mp3_names:
            print(f"⏭ Skip (already exists): {mp3_name}")
            continue

        print(f"\n🎬 Processing: {video_name}")
        
        safe_video = safe_filename(video_name)
        safe_mp3 = safe_filename(mp3_name)

        try:
            # DOWNLOAD
            print("⬇ Downloading video...")
            download_file(service, video_id, safe_video)

            # CONVERT
            print("🎧 Converting to MP3...")
            video_clip = VideoFileClip(safe_video)
            video_clip.audio.write_audiofile(safe_mp3, logger=None)
            video_clip.close()

            # UPLOAD
            print("⬆ Uploading MP3...")
            file_metadata = {"name": mp3_name, "parents": [MP3_FOLDER_ID]}
            media = MediaFileUpload(safe_mp3, mimetype="audio/mpeg")
            service.files().create(body=file_metadata, media_body=media).execute()
            
            # Local list update karein taaki loop mein dubara na aaye
            existing_mp3_names.add(mp3_name.lower())
            print(f"✅ Success: {mp3_name}")

        except Exception as e:
            print(f"❌ Error with {video_name}: {e}")
        finally:
            if os.path.exists(safe_video): os.remove(safe_video)
            if os.path.exists(safe_mp3): os.remove(safe_mp3)

if __name__ == "__main__":
    start_process()
