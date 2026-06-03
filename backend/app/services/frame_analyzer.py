import os
import base64
import tempfile
from typing import List, Dict
import asyncio
import ffmpeg
import imageio_ffmpeg as iio_ffmpeg
from app.client import client
from app.core.config import settings

os.environ["FFMPEG_BINARY"] = iio_ffmpeg.get_ffmpeg_exe()

try:
    from app.services.frame_extractor_hybrid import extract_frames_hybrid
    USE_HYBRID = True
except ImportError:
    USE_HYBRID = False

try:
    from app.services.frame_extractor_ffmpeg import extract_frames_ffmpeg
    USE_SUBPROCESS = True
except ImportError:
    USE_SUBPROCESS = False

try:
    from app.services.frame_extractor_cv2 import extract_frames_cv2
    USE_OPENCV = True
except ImportError:
    USE_OPENCV = False

print(f"Frame extraction methods: hybrid={USE_HYBRID}, subprocess={USE_SUBPROCESS}, opencv={USE_OPENCV}")

def extract_frame(
    video_bytes: bytes,
    interval_seconds: int = 10,
    max_frames: int = 30
) -> List[Dict[str, any]]:

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
        video_file.write(video_bytes)
        video_path = video_file.name

    ffmpeg_path = os.environ["FFMPEG_BINARY"]
    ffprobe_path = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")


    try:
        probe = ffmpeg.probe(video_path, cmd=ffprobe_path)
        duration = float(probe["format"]["duration"])
    except Exception as e:
        print(f"FFprobe failed, using alternative method: {e}")
        duration = 600.0

    actual_interval = max(interval_seconds, duration / max_frames)

    frames = []
    temp_frame_paths = []

    try:
        timestamp = 0
        frame_index = 0

        while timestamp < duration and frame_index < max_frames:
            frame_path = f"{video_path}_frame_{frame_index}.jpg"
            temp_frame_paths.append(frame_path)

            try:
                (
                    ffmpeg
                    .input(video_path, ss=timestamp)
                    .output(
                        frame_path,
                        vframes=1,
                        format="image2",
                        vcodec="mjpeg",
                        **{"q:v":"2"}
                    )
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True, cmd=os.environ["FFMPEG_BINARY"])
                )

                with open(frame_path, "rb") as f:
                    frames.append({
                        "timestamp": timestamp,
                        "image_bytes": f.read()
                    })

            except ffmpeg.Error as e:
                print(f"Failed to extract frame at {timestamp}s: {e}")

            timestamp += actual_interval
            frame_index += 1

    finally:
        if os.path.exists(video_path):
            os.unlink(video_path)
        for frame_path in temp_frame_paths:
            if os.path.exists(frame_path):
                os.unlink(frame_path)

    return frames


async def analyze_frame_with_vision(
    image_bytes: bytes,
    timestamp: float,
    prompt: str = None
) -> str:
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    if prompt is None:
        prompt = """
            Describe this educational video frame in 2-3 sentences. 
            Include: any visible text/code (language + purpose), key visual elements, and the concept being demonstrated. Be concise
        """

    try:
        response = await client.chat.completions.create(
            model=settings.MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        description = response.choices[0].message.content
        return description

    except Exception as e:
        print(f"Vision analysis failed for frame at {timestamp}s: {e}")
        return ""


async def analyze_video_frames(
    video_bytes: bytes,
    interval_seconds: int = 10,
    max_frames: int = 30
) -> List[Dict[str, any]]:
    print(f"Extracting frames from video (every {interval_seconds}s, max {max_frames})...")

    if USE_HYBRID:
        try:
            print("Using hybrid (ffmpeg-python + subprocess) for frame extraction...")
            frames = await asyncio.to_thread(extract_frames_hybrid, video_bytes, interval_seconds, max_frames)
        except Exception as e:
            print(f"Hybrid method failed: {e}")
            if USE_OPENCV:
                print("Falling back to OpenCV...")
                frames = await asyncio.to_thread(extract_frames_cv2, video_bytes, interval_seconds, max_frames)
            else:
                print("Falling back to ffmpeg-python...")
                frames = await asyncio.to_thread(extract_frame, video_bytes, interval_seconds, max_frames)
    elif USE_SUBPROCESS:
        try:
            print("Using subprocess + ffmpeg for frame extraction...")
            frames = await asyncio.to_thread(extract_frames_ffmpeg, video_bytes, interval_seconds, max_frames)
        except Exception as e:
            print(f"Subprocess ffmpeg failed: {e}")
            if USE_OPENCV:
                print("Falling back to OpenCV...")
                frames = await asyncio.to_thread(extract_frames_cv2, video_bytes, interval_seconds, max_frames)
            else:
                print("Falling back to ffmpeg-python...")
                frames = await asyncio.to_thread(extract_frame, video_bytes, interval_seconds, max_frames)
    elif USE_OPENCV:
        try:
            print("Using OpenCV for frame extraction...")
            frames = await asyncio.to_thread(extract_frames_cv2, video_bytes, interval_seconds, max_frames)
        except Exception as e:
            print(f"OpenCV failed: {e}, trying ffmpeg-python...")
            frames = await asyncio.to_thread(extract_frame, video_bytes, interval_seconds, max_frames)
    else:
        print("Using ffmpeg-python for frame extraction...")
        frames = await asyncio.to_thread(extract_frame, video_bytes, interval_seconds, max_frames)

    if not frames:
        print("No frames extracted")
        return []

    print(f"Extracted {len(frames)} frames. Analyzing with vision model...")

    analyzed_frames = []

    batch_size = 5
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size]

        tasks = [
            analyze_frame_with_vision(frame['image_bytes'], frame['timestamp'])
            for frame in batch
        ]

        descriptions = await asyncio.gather(*tasks)

        for frame, description in zip(batch, descriptions):
            if description: 
                timestamp = frame['timestamp']
                analyzed_frames.append({
                    'timestamp': timestamp,
                    'start': timestamp,
                    'end': timestamp + interval_seconds,
                    'description': description
                })

    print(f"Successfully analyzed {len(analyzed_frames)} frames")
    return analyzed_frames


def format_timestamp(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

