import os
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from moviepy.editor import VideoFileClip
import io

# ----------- YOUR FOLDER IDs -----------
VIDEO_FOLDER_ID = '1B-8digPGU9ZGFFfc56FEIg-suUvHYSRZ'
MP3_FOLDER_ID = '1YIbL1VXAn8lJSeqCVej_csoYWNgM236N'
# --------------------------------------

def safe_filename(name):
    # Date/time ko preserve karte hue filename safe banata hai
    name = name.replace("/", "-")
    name = name.replace(":", "-")
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


def start_process():

    if not os.path.exists("token.json"):
        print("❌ token.json nahi mila.")
        return

    creds = Credentials.from_authorized_user_file('token.json')
    service = build('drive', 'v3', credentials=creds)

    print("📂 MP3 folder check kar raha hai...")

    mp3_results = service.files().list(
        q=f"'{MP3_FOLDER_ID}' in parents and trashed=false",
        fields="files(name)"
    ).execute()

    existing_mp3s = {f['name'].lower() for f in mp3_results.get('files', [])}

    print("📂 Video folder scan ho raha hai...")

    video_results = service.files().list(
        q=f"'{VIDEO_FOLDER_ID}' in parents and mimeType='video/mp4' and trashed=false",
        fields="files(id,name)"
    ).execute()

    videos = video_results.get('files', [])

    if not videos:
        print("⚠ Video folder me koi MP4 nahi mila.")
        return

    for video in videos:

        video_name = video['name']
        video_id = video['id']

        mp3_name = video_name.rsplit(".", 1)[0] + ".mp3"

        if mp3_name.lower() in existing_mp3s:
            print(f"⏭ Skip (already exists): {mp3_name}")
            continue

        print(f"\n🎬 Processing: {video_name}")

        safe_video = safe_filename(video_name)
        safe_mp3 = safe_filename(mp3_name)

        try:

            # -------- DOWNLOAD VIDEO --------
            print("⬇ Downloading video...")
            download_file(service, video_id, safe_video)

            # -------- CONVERT --------
            print("🎧 Converting to MP3...")

            video_clip = VideoFileClip(safe_video)
            video_clip.audio.write_audiofile(safe_mp3)
            video_clip.close()

            # -------- UPLOAD --------
            print("⬆ Uploading MP3 to Drive...")

            file_metadata = {
                "name": mp3_name,
                "parents": [MP3_FOLDER_ID]
            }

            media = MediaFileUpload(safe_mp3, mimetype="audio/mpeg")

            service.files().create(
                body=file_metadata,
                media_body=media
            ).execute()

            print(f"✅ Success: {mp3_name} uploaded")

        except Exception as e:
            print(f"❌ Error processing {video_name}: {e}")

        finally:

            # -------- CLEANUP --------
            if os.path.exists(safe_video):
                os.remove(safe_video)

            if os.path.exists(safe_mp3):
                os.remove(safe_mp3)


if __name__ == "__main__":
    start_process()
