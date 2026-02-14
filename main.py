import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from moviepy.editor import VideoFileClip

# 1. Folder ki ID yahan daalein (Drive link se milti hai)
INPUT_FOLDER = '1on5Irr1KN_IXvgNukLG9HpN1XRUX-xy2' 

def start_process():
    # Login process
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', ['https://www.googleapis.com/auth/drive'])
    creds = flow.run_local_server(port=0)
    service = build('drive', 'v3', credentials=creds)

    # Video dhundna
    results = service.files().list(q=f"'{INPUT_FOLDER}' in parents").execute()
    for file in results.get('files', []):
        if file['name'].endswith('.mp4'): # Agar video hai
            print(f"Converting: {file['name']}")
            
            # DOWNLOAD VIDEO
            request = service.files().get_media(fileId=file['id'])
            with open("temp_video.mp4", "wb") as f:
                f.write(request.execute())

            # CONVERT TO MP3
            video = VideoFileClip("temp_video.mp4")
            video.audio.write_audiofile("output.mp3")
            video.close()

            # UPLOAD MP3
            meta = {'name': file['name'].replace('.mp4', '.mp3'), 'parents': [INPUT_FOLDER]}
            media = MediaFileUpload("output.mp3", mimetype='audio/mpeg')
            service.files().create(body=meta, media_body=media).execute()
            
            print("Done!")

start_process()