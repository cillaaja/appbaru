import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
import datetime

# ==============================================================
# KONFIGURASI DASAR
# ==============================================================

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

# --------------------------------------------------------------
# AUTENTIKASI GOOGLE YOUTUBE API
# --------------------------------------------------------------
def get_authenticated_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)


# --------------------------------------------------------------
# FUNGSI UPLOAD VIDEO BESAR
# --------------------------------------------------------------
def upload_video(youtube, file_path, title, description, category_id="22", privacy_status="private"):
    request_body = {
        "snippet": {"title": title, "description": description, "categoryId": category_id},
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        response = None
        progress_bar = st.progress(0)
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                progress_bar.progress(progress)
                st.write(f"Progress: {progress}%")

        st.success("✅ Upload selesai!")
        st.write("Video ID:", response["id"])
        return response["id"]

    except HttpError as e:
        st.error(f"Terjadi error saat upload: {e}")
        return None


# --------------------------------------------------------------
# FUNGSI BUAT LIVE STREAM (AMBIL RTMP URL & STREAM KEY)
# --------------------------------------------------------------
def create_live_stream(youtube, title):
    try:
        # Buat stream
        stream_request = youtube.liveStreams().insert(
            part="snippet,cdn,contentDetails",
            body={
                "snippet": {"title": title},
                "cdn": {"frameRate": "30fps", "resolution": "1080p", "ingestionType": "rtmp"}
            }
        )
        stream_response = stream_request.execute()

        # Buat broadcast
        start_time = (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).isoformat() + "Z"
        broadcast_request = youtube.liveBroadcasts().insert(
            part="snippet,contentDetails,status",
            body={
                "snippet": {
                    "title": f"{title} Broadcast",
                    "scheduledStartTime": start_time
                },
                "status": {"privacyStatus": "public"}
            }
        )
        broadcast_response = broadcast_request.execute()

        # Hubungkan broadcast dengan stream
        bind_request = youtube.liveBroadcasts().bind(
            part="id,contentDetails",
            id=broadcast_response["id"],
            streamId=stream_response["id"]
        )
        bind_response = bind_request.execute()

        info = stream_response["cdn"]["ingestionInfo"]
        st.success("✅ Live Stream berhasil dibuat!")
        st.write("**RTMP URL:**", info["ingestionAddress"])
        st.write("**Stream Key:**", info["streamName"])
        st.info("Gunakan URL & Stream Key ini di encoder seperti OBS atau FFmpeg.")

    except HttpError as e:
        st.error(f"Terjadi error saat membuat live stream: {e}")


# ==============================================================
# STREAMLIT UI
# ==============================================================

st.title("🎥 YouTube Stream & Upload Tool")
st.write("Upload video besar atau buat live streaming langsung ke channel YouTube kamu.")

# Inisialisasi YouTube API
if st.button("🔐 Login / Hubungkan YouTube"):
    youtube = get_authenticated_service()
    st.success("Autentikasi berhasil! Akun YouTube terhubung.")
    st.session_state["youtube"] = youtube

if "youtube" in st.session_state:
    youtube = st.session_state["youtube"]

    mode = st.radio("Pilih Mode:", ["Upload Video", "Live Streaming"])

    if mode == "Upload Video":
        uploaded_file = st.file_uploader("Pilih file video", type=["mp4", "mov", "avi", "mkv"])
        title = st.text_input("Judul Video")
        description = st.text_area("Deskripsi Video")
        privacy = st.selectbox("Status Privasi", ["public", "private", "unlisted"])

        if st.button("🚀 Upload ke YouTube"):
            if uploaded_file and title:
                temp_path = os.path.join("temp_" + uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                video_id = upload_video(youtube, temp_path, title, description, privacy_status=privacy)
                os.remove(temp_path)
            else:
                st.warning("Pastikan file dan judul sudah diisi.")

    elif mode == "Live Streaming":
        stream_title = st.text_input("Judul Live Stream")
        if st.button("🎬 Buat Live Stream"):
            if stream_title:
                create_live_stream(youtube, stream_title)
            else:
                st.warning("Masukkan judul untuk live stream.")

else:
    st.warning("Silakan login terlebih dahulu untuk menghubungkan akun YouTube.")

