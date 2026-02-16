import os
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from moviepy.editor import VideoFileClip
from googleapiclient.http import MediaFileUpload

# --- Yahan apni IDs dalein ---
VIDEO_FOLDER_ID = '1B-8digPGU9ZGFFfc56FEIg-suUvHYSRZ'
MP3_FOLDER_ID = '1YIbL1VXAn8lJSeqCVej_csoYWNgM236N'
# -----------------------------

def safe_filename(name):
    # Linux/Windows me invalid characters replace kar deta hai
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def start_process():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    else:
        print("Error: token.json nahi mili!")
        return

    service = build('drive', 'v3', credentials=creds)

    # 1) MP3 folder me already existing mp3 list
    mp3_results = service.files().list(
        q=f"'{MP3_FOLDER_ID}' in parents and trashed = false",
        fields="files(name)"
    ).execute()

    existing_mp3s = [f['name'].lower() for f in mp3_results.get('files', [])]

    # 2) Video folder me mp4 list
    video_results = service.files().list(
        q=f"'{VIDEO_FOLDER_ID}' in parents and mimeType = 'video/mp4' and trashed = false",
        fields="files(id, name)"
    ).execute()

    videos = video_results.get('files', [])

    if not videos:
        print("Video folder khali hai.")
        return

    for video in videos:
        video_name = video['name']
        video_id = video['id']

        expected_mp3_name = video_name.rsplit('.', 1)[0] + '.mp3'

        # Agar MP3 already exist hai, skip
        if expected_mp3_name.lower() in existing_mp3s:
            print(f"Skipping: {expected_mp3_name} pehle se MP3 folder me hai.")
            continue

        print(f"Processing: {video_name} -> {expected_mp3_name}")

        # Local safe names (slash etc remove)
        local_video = safe_filename(video_name)
        local_mp3 = safe_filename(expected_mp3_name)

        # Download
        request = service.files().get_media(fileId=video_id)
        with open(local_video, 'wb') as f:
            f.write(request.execute())

        # Convert
        video_clip = VideoFileClip(local_video)
        video_clip.audio.write_audiofile(local_mp3)
        video_clip.close()

        # Upload (Drive me original mp3 name hi rahega)
        file_metadata = {'name': expected_mp3_name, 'parents': [MP3_FOLDER_ID]}
        media = MediaFileUpload(local_mp3, mimetype='audio/mpeg')
        service.files().create(body=file_metadata, media_body=media).execute()

        # Cleanup
        os.remove(local_video)
        os.remove(local_mp3)

        print(f"Success: {expected_mp3_name} MP3 folder me upload ho gayi!")

if __name__ == '__main__':
    start_process()
