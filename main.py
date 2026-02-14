import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from moviepy.editor import VideoFileClip
from googleapiclient.http import MediaFileUpload

# --- Yahan apni IDs dalein ---
VIDEO_FOLDER_ID = '1on5Irr1KN_IXvgNukLG9HpN1XRUX-xy2'
MP3_FOLDER_ID = '1vF65MjK3dY8Y5dWFJkNh-kyt5hitXSNP'
# -----------------------------

def start_process():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    else:
        print("Error: token.json nahi mili!")
        return

    service = build('drive', 'v3', credentials=creds)

    # 1. MP3 Folder se list mangwana (Check karne ke liye ki kya pehle se bana hai)
    mp3_results = service.files().list(
        q=f"'{MP3_FOLDER_ID}' in parents and trashed = false",
        fields="files(name)").execute()
    existing_mp3s = [f['name'].lower() for f in mp3_results.get('files', [])]

    # 2. Video Folder se MP4 files mangwana
    video_results = service.files().list(
        q=f"'{VIDEO_FOLDER_ID}' in parents and mimeType = 'video/mp4' and trashed = false",
        fields="files(id, name)").execute()
    videos = video_results.get('files', [])

    if not videos:
        print("Video folder khali hai.")
        return

    for video in videos:
        video_name = video['name']
        video_id = video['id']
        expected_mp3_name = video_name.rsplit('.', 1)[0] + '.mp3'

        # Agar dusre folder mein MP3 pehle se hai, toh skip karo
        if expected_mp3_name.lower() in existing_mp3s:
            print(f"Skipping: {expected_mp3_name} dusre folder mein pehle se hai.")
            continue

        print(f"Processing: {video_name} -> {expected_mp3_name}")
        
        # Download
        request = service.files().get_media(fileId=video_id)
        with open(video_name, 'wb') as f:
            f.write(request.execute())

        # Convert
        video_clip = VideoFileClip(video_name)
        video_clip.audio.write_audiofile(expected_mp3_name)
        video_clip.close()

        # Upload (MP3_FOLDER_ID mein)
        file_metadata = {'name': expected_mp3_name, 'parents': [MP3_FOLDER_ID]}
        media = MediaFileUpload(expected_mp3_name, mimetype='audio/mp3')
        service.files().create(body=file_metadata, media_body=media).execute()

        # Safayi
        os.remove(video_name)
        os.remove(expected_mp3_name)
        print(f"Success: {expected_mp3_name} MP3 folder mein upload ho gayi!")

if __name__ == '__main__':
    start_process()
