from app.core.config import settings

import os
import math
import tempfile
import asyncio
import httpx
import ffmpeg
import imageio_ffmpeg as iio_ffmpeg
import base64

MAX_FILE_SIZE = 23 * 1024 * 1024  # 23 MB

# Set ffmpeg binary for ffmpeg-python
os.environ["FFMPEG_BINARY"] = iio_ffmpeg.get_ffmpeg_exe()

def encode_audio_to_base64(audio_bytes):
    return base64.b64encode(audio_bytes).decode("utf-8")


def extract_audio(video_bytes: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
        video_file.write(video_bytes)
        video_path = video_file.name

    audio_path = video_path.replace(".mp4", ".mp3")
    try:
        (
            ffmpeg
            .input(video_path)
            .output(
                audio_path,
                format="mp3",
                acodec="libmp3lame",
                ar=16000,
                ac=1,
                audio_bitrate="32k"
            )
            .overwrite_output()
            .run(quiet=True, cmd=os.environ["FFMPEG_BINARY"])  
        )        #change the quiet to False, when you want to see the logs for debug
        with open(audio_path, "rb") as f:
            return f.read()
    except ffmpeg.Error as e:
        # e.stderr is bytes, decode it for readability
        error_message = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        raise Exception(f"ffmpeg extraction failed:\n{error_message}")
    finally:
        if os.path.exists(video_path):
            os.unlink(video_path)
        if os.path.exists(audio_path):
            os.unlink(audio_path)

def split_audio(audio_bytes: bytes, chunk_size: int = MAX_FILE_SIZE) -> list[bytes]:
    """Split audio bytes into chunks under the size limit."""
    if len(audio_bytes) <= chunk_size:
        return [audio_bytes]
    num_chunks = math.ceil(len(audio_bytes) / chunk_size)
    chunk_length = len(audio_bytes) // num_chunks
    chunks = []
    for i in range(num_chunks):
        start = i * chunk_length
        end = start + chunk_length if i < num_chunks - 1 else len(audio_bytes)
        chunks.append(audio_bytes[start:end])
    return chunks



#IMPORTANT
# the openrouter doesn't have model which support timestamps in trasnscription 
# so use the groq model to activate the transcription capabilies of this system
# replace the transcribe_audio_bytes function with this transcribe_groq in transcribe_video function

async def _transcribe_groq(audio_bytes: bytes, filename: str, language: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as http:
        response = await http.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            files={"file": (filename, audio_bytes, "audio/mpeg")},
            data={
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
                "language": language
            }
        )
        if response.status_code != 200:
            print(f"Groq STT error: {response.status_code} - {response.text}")
            response.raise_for_status()

        result = response.json()
        return {
            "text": result.get("text", ""),
            "segments": result.get("segments", [])  # ✅ actually works
        }



async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.mp3", language: str = "en") -> dict:
    async with httpx.AsyncClient(timeout=120) as http:
        response = await http.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            },
            files={"file": (filename, audio_bytes, "audio/mpeg")},
            data={
                "model": "whisper-1",
                "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            }
        )

        if response.status_code != 200:
            print(f"OpenAI STT error: {response.status_code} - {response.text}")
            response.raise_for_status()

        result = response.json()
        return {
            "text": result.get("text", ""),
            "segments": result.get("segments", []) 
        }
    


async def transcribe_video(video_bytes: bytes, language: str = "en") -> dict:
    """Accepts raw video bytes — works with Cloudinary or local storage"""

    audio_bytes = await asyncio.to_thread(extract_audio, video_bytes)

    if len(audio_bytes) <= MAX_FILE_SIZE:
        return await transcribe_audio_bytes(audio_bytes, language=language)
    
    chunks = split_audio(audio_bytes)
    all_segments = []
    full_text = []
    offset = 0.0

    for i, chunk in enumerate(chunks):
        result = await transcribe_audio_bytes(
            chunk, 
            filename=f"chunk_{i}.mp3",
            language=language
        )

        full_text.append(result["text"])

        for seg in result["segments"]:
            seg["start"] += offset
            seg["end"] += offset
        all_segments.extend(result["segments"])

        offset += len(chunk) / (32000 / 8)

    return {
        "text": " ".join(full_text),
        "segments": all_segments
    }
