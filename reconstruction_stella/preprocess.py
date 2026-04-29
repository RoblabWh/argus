import json
import os
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)



def check_h264_codec(video_path: str) -> bool:
    """
    Checks the video codec. If HEVC, transcodes to H.264 in-place for browser compatibility.
    Preserves all metadata. Returns True if conversion was performed.
    """
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True,
        text=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams or video_streams[0].get("codec_name") != "hevc":
        return False
    return True

def convert_to_h264(video_path: str) -> bool:
    try:
        logger.info(f"[STELLA] Converting video to H.264: {video_path}")
        tmp_path = video_path + ".converting.mp4"
        subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "copy",
                "-map_metadata", "0",
                "-y", tmp_path,
            ],
            check=True,
        )
        shutil.move(tmp_path, video_path)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[STELLA] Error converting video to H.264: {e}")
        return False


def flip_video_180(video_path: str) -> str:
    """
    Creates a 180°-rotated copy of the video (true rotation, not a mirror).
    Saves as {stem}_flipped{ext} next to the original.
    Returns the path to the flipped file.
    If the flipped file already exists, skips re-encoding and returns immediately.
    """
    base, ext = os.path.splitext(video_path)
    flipped_path = base + "_flipped" + ext
    logger.info(f"[STELLA] Flipping video: {video_path} → {flipped_path}")  
    if os.path.isfile(flipped_path):
        logger.info(f"[STELLA] Flipped video already exists: {flipped_path}")
        return flipped_path
    logger.info(f"[STELLA] Running ffmpeg to flip video: {video_path}")
    #os.system( f"ffmpeg -i {video_path} -metadata:s:v rotate=180 -codec copy {flipped_path}",)
    #new command is "ffmpeg -display_rotation:v:0 180 -i {video_path} -c copy {flipped_path}"
    subprocess.run(
        [
            "ffmpeg", 
            "-display_rotation:v:0", "180", 
            "-i", video_path, 
            "-c", "copy", 
            "-y", flipped_path
        ],
        check=True,
    )
    logger.info(f"[STELLA] Video flipped successfully: {flipped_path}")
    return flipped_path
