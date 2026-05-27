import os
import subprocess
import tempfile
import json
from typing import List, Dict
import ffmpeg
import shutil

def get_ffprobe_path():
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe

    try:
        import imageio_ffmpeg as iio_ffmpeg
        ffmpeg_path = iio_ffmpeg.get_ffmpeg_exe()
        ffprobe_path = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        if os.path.exists(ffprobe_path):
            return ffprobe_path
    except:
        pass

    return None


FFPROBE_PATH = get_ffprobe_path()
if FFPROBE_PATH:
    print(f"Found ffprobe at: {FFPROBE_PATH}")
    os.environ['FFPROBE_BINARY'] = FFPROBE_PATH
else:
    print("ffprobe not found - video info detection may fail")


def get_video_info_subprocess(video_path: str) -> dict:
    if not FFPROBE_PATH:
        print("ffprobe not available, using default video info")
        return {
            'duration': 600, 
            'fps': 30,
            'width': 1920,
            'height': 1080,
            'codec': 'unknown'
        }

    try:
        probe = ffmpeg.probe(video_path, cmd=FFPROBE_PATH)

        video_stream = next(
            (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
            None
        )

        if not video_stream:
            raise Exception("No video stream found")

        duration = float(probe['format'].get('duration', 0))

        fps_str = video_stream.get('r_frame_rate', '30/1')
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den > 0 else 30
        else:
            fps = float(fps_str)

        return {
            'duration': duration,
            'fps': fps,
            'width': video_stream.get('width', 0),
            'height': video_stream.get('height', 0),
            'codec': video_stream.get('codec_name', 'unknown')
        }

    except (ffmpeg.Error, FileNotFoundError) as e:
        error_msg = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)
        print(f"ffmpeg.probe() failed: {error_msg}")
        return get_video_info_manual(video_path)


def get_video_info_manual(video_path: str) -> dict:
    if not FFPROBE_PATH:
        print("No ffprobe available for manual fallback")
        return {
            'duration': 600,
            'fps': 30,
            'width': 1920,
            'height': 1080,
            'codec': 'unknown'
        }

    cmd = [
        FFPROBE_PATH,
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate,duration,width,height:format=duration',
        '-of', 'json',
        video_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )

        data = json.loads(result.stdout)

        stream = data['streams'][0] if data.get('streams') else {}
        format_info = data.get('format', {})

        fps_str = stream.get('r_frame_rate', '30/1')
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den > 0 else 30
        else:
            fps = float(fps_str)

        duration = float(format_info.get('duration') or stream.get('duration', 0))

        return {
            'duration': duration,
            'fps': fps,
            'width': stream.get('width', 0),
            'height': stream.get('height', 0),
            'codec': 'unknown'
        }

    except Exception as e:
        print(f"Manual ffprobe also failed: {e}")
        return {
            'duration': 600,  
            'fps': 30,
            'width': 1920,
            'height': 1080,
            'codec': 'unknown'
        }


def extract_frame_hybrid(
    video_path: str,
    timestamp: float,
    output_path: str
) -> bool:
    try:
        try:
            import imageio_ffmpeg as iio_ffmpeg
            ffmpeg_cmd = iio_ffmpeg.get_ffmpeg_exe()
        except:
            ffmpeg_cmd = 'ffmpeg'

        stream = (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(
                output_path,
                vframes=1,
                format='image2',
                vcodec='mjpeg',
                **{'q:v': 2}  # Quality
            )
            .overwrite_output()
        )

        cmd = ffmpeg.compile(stream, cmd=ffmpeg_cmd)

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=10
        )

        return os.path.exists(output_path)

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        print(f"Frame extraction failed at {timestamp}s: {stderr}")
        return False
    except subprocess.TimeoutExpired:
        print(f"Frame extraction timed out at {timestamp}s")
        return False
    except Exception as e:
        print(f"Unexpected error extracting frame: {e}")
        return False


def extract_frames_hybrid(
    video_bytes: bytes,
    interval_seconds: int = 10,
    max_frames: int = 30
) -> List[Dict[str, any]]:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
        video_file.write(video_bytes)
        video_path = video_file.name

    frames = []
    temp_frame_paths = []

    try:
        print("Analyzing video...")
        info = get_video_info_subprocess(video_path)
        duration = info['duration']
        fps = info['fps']

        print(f"Video: {duration:.1f}s, {fps:.1f} fps, {info['width']}x{info['height']}")

        actual_interval = max(interval_seconds, duration / max_frames)

        timestamp = 0
        frame_index = 0

        while timestamp < duration and frame_index < max_frames:
            frame_path = f"{video_path}_frame_{frame_index}.jpg"
            temp_frame_paths.append(frame_path)

            success = extract_frame_hybrid(video_path, timestamp, frame_path)

            if success:
                with open(frame_path, "rb") as f:
                    frames.append({
                        "timestamp": timestamp,
                        "image_bytes": f.read()
                    })
            else:
                print(f"Skipping frame at {timestamp}s due to extraction failure")

            timestamp += actual_interval
            frame_index += 1

        print(f"Successfully extracted {len(frames)} frames")

    except Exception as e:
        print(f"Frame extraction failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if os.path.exists(video_path):
            os.unlink(video_path)
        for frame_path in temp_frame_paths:
            if os.path.exists(frame_path):
                os.unlink(frame_path)

    return frames
