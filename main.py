import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from moviepy.editor import VideoFileClip
from googleapiclient.http import MediaFileUpload

# Yahan apni Folder ID dalein
FOLDER_ID = '1on5Irr1KN_IXvgNukLG9HpN1XRUX-xy2'

def start_process():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    else:
        print("Error: token.json nahi mili!")
        return

    service = build('drive', 'v3', credentials=creds)

    # 1. Folder ki saari files ki list mangwana
    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed = false",
        fields="files(id, name, mimeType)").execute()
    all_files = results.get('files', [])

    # 2. Pehle se maujood MP3 files ke naam ek list mein rakhna
    existing_mp3s = [f['name'] for f in all_files if f['mimeType'] == 'audio/mpeg']
    # 3. Videos ki list banana
    videos = [f for f in all_files if f['mimeType'] == 'video/mp4']

    if not videos:
        print("Folder mein koi MP4 video nahi mili.")
        return

    for video in videos:
        video_name = video['name']
        video_id = video['id']
        expected_mp3_name = video_name.rsplit('.', 1)[0] + '.mp3'

        # --- LOGIC START ---
        if expected_mp3_name in existing_mp3s:
            print(f"Skipping: {expected_mp3_name} pehle se maujood hai.")
            continue
        # --- LOGIC END ---

        print(f"Processing: {video_name} (MP3 nahi mili, bana raha hoon...)")
        
        # Download
        request = service.files().get_media(fileId=video_id)
        with open(video_name, 'wb') as f:
            f.write(request.execute())

        # Convert
        video_clip = VideoFileClip(video_name)
        video_clip.audio.write_audiofile(expected_mp3_name)
        video_clip.close()

        # Upload
        file_metadata = {'name': expected_mp3_name, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(expected_mp3_name, mimetype='audio/mp3')
        service.files().create(body=file_metadata, media_body=media).execute()

        # Safayi
        os.remove(video_name)
        os.remove(expected_mp3_name)
        print(f"Success: {expected_mp3_name} upload ho gayi!")

if __name__ == '__main__':
    start_process()
