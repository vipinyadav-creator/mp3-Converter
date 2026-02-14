import os
import io
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from moviepy.video.io.VideoFileClip import VideoFileClip

# Yahan apni Folder ID dalein
FOLDER_ID = '1on5Irr1KN_IXvgNukLG9HpN1XRUX-xy2'

def start_process():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    else:
        print("Error: token.json nahi mili!")
        return

    service = build('drive', 'v3', credentials=creds)

    # Video files dhoondna
    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='video/mp4'",
        fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        print("Folder mein koi MP4 video nahi mili.")
        return

    for item in items:
        file_id = item['id']
        file_name = item['name']
        mp3_name = file_name.rsplit('.', 1)[0] + '.mp3'

        print(f"Downloading: {file_name}")
        
        # Download
        request = service.files().get_media(fileId=file_id)
        with open(file_name, 'wb') as f:
            f.write(request.execute())

        # Convert to MP3
        print(f"Converting to MP3...")
        video = VideoFileClip(file_name)
        video.audio.write_audiofile(mp3_name)
        video.close()

        # Upload MP3
        print(f"Uploading: {mp3_name}")
        from googleapiclient.http import MediaFileUpload
        file_metadata = {'name': mp3_name, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(mp3_name, mimetype='audio/mp3')
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Safayi (PC se delete karna)
        os.remove(file_name)
        os.remove(mp3_name)
        print(f"Done: {mp3_name} upload ho gayi!")

if __name__ == '__main__':
    start_process()

