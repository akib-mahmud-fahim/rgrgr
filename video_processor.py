import os
import subprocess
import json
import re
import math
import shutil
import time
import imageio_ffmpeg

def get_ffmpeg_executable():
    """Finds system ffmpeg on Linux/Render or bundled binary from imageio-ffmpeg."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_executable()

def get_video_info(video_path):
    """
    Extracts video duration and basic metadata using FFmpeg.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    cmd = [
        FFMPEG_PATH,
        "-i", video_path,
        "-hide_banner"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    _, stderr = process.communicate()
    
    # Parse duration: Duration: 00:01:23.45
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if not duration_match:
        raise ValueError("Could not parse video duration from FFmpeg output.")
    
    hours, minutes, seconds = duration_match.groups()
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    
    # Parse resolution: 1920x1080
    res_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", stderr)
    resolution = f"{res_match.group(1)}x{res_match.group(2)}" if res_match else "Unknown"
    
    return {
        "duration": total_seconds,
        "duration_formatted": format_seconds(total_seconds),
        "resolution": resolution,
        "filesize": os.path.getsize(video_path)
    }

def format_seconds(seconds):
    """Formats seconds into HH:MM:SS or MM:SS."""
    seconds = max(0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def calculate_segments(total_duration, segment_length=60.0):
    """
    Calculates clip segments.
    Each segment is up to `segment_length` seconds.
    The final remainder (e.g. 3s, 5s, 10s) is kept as the last clip.
    """
    if total_duration <= 0:
        return []
    
    segments = []
    current_start = 0.0
    index = 1
    
    while current_start < total_duration:
        current_end = min(current_start + segment_length, total_duration)
        clip_dur = current_end - current_start
        
        segments.append({
            "index": index,
            "clip_id": f"clip_{index:03d}",
            "start": current_start,
            "end": current_end,
            "duration": clip_dur,
            "start_formatted": format_seconds(current_start),
            "end_formatted": format_seconds(current_end),
            "duration_formatted": format_seconds(clip_dur),
            "is_remainder": (current_end == total_duration and clip_dur < segment_length)
        })
        
        current_start += segment_length
        index += 1
        
    return segments

def extract_thumbnail(video_path, output_thumb_path, timestamp=0.5):
    """Generates a JPEG thumbnail from a video at a given timestamp."""
    os.makedirs(os.path.dirname(output_thumb_path), exist_ok=True)
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(max(0.0, timestamp)),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale='min(480,iw)':-2",
        output_thumb_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def slice_single_clip(input_video, output_dir, segment):
    """Slices a single clip segment and generates its thumbnail."""
    clip_filename = f"{segment['clip_id']}.mp4"
    clip_path = os.path.join(output_dir, clip_filename)
    thumb_filename = f"{segment['clip_id']}_thumb.jpg"
    thumb_path = os.path.join(output_dir, thumb_filename)
    
    start_sec = segment["start"]
    clip_dur = segment["duration"]
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start_sec),
        "-i", input_video,
        "-t", str(clip_dur),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        clip_path
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    extract_thumbnail(clip_path, thumb_path, timestamp=min(0.5, clip_dur / 2.0))
    
    return {
        "clip_id": segment["clip_id"],
        "index": segment["index"],
        "title": f"Clip {segment['index']:02d}",
        "filename": clip_filename,
        "thumb_filename": thumb_filename,
        "start": segment["start"],
        "end": segment["end"],
        "duration": segment["duration"],
        "start_formatted": segment["start_formatted"],
        "end_formatted": segment["end_formatted"],
        "duration_formatted": segment["duration_formatted"],
        "is_remainder": segment["is_remainder"],
        "is_replaced": False,
        "replaced_filename": None,
        "original_filename": clip_filename,
        "filesize": os.path.getsize(clip_path) if os.path.exists(clip_path) else 0,
        "status": "ready"
    }

def replace_clip(project_dir, clip_id, replacement_video_path, original_filename=""):
    """
    Replaces a specific clip with a new user-uploaded video.
    Normalizes/re-encodes the replacement to standard compatible MP4.
    """
    project_json_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(project_json_path):
        raise FileNotFoundError("Project metadata not found.")
        
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    target_clip = None
    for clip in project_data["clips"]:
        if clip["clip_id"] == clip_id:
            target_clip = clip
            break
            
    if not target_clip:
        raise ValueError(f"Clip {clip_id} not found in project.")
        
    rep_info = get_video_info(replacement_video_path)
    
    rep_filename = f"{clip_id}_replaced.mp4"
    rep_path = os.path.join(project_dir, rep_filename)
    rep_thumb_filename = f"{clip_id}_replaced_thumb.jpg"
    rep_thumb_path = os.path.join(project_dir, rep_thumb_filename)
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", replacement_video_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        rep_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    extract_thumbnail(rep_path, rep_thumb_path, timestamp=min(0.5, rep_info["duration"] / 2.0))
    
    target_clip["is_replaced"] = True
    target_clip["filename"] = rep_filename
    target_clip["thumb_filename"] = rep_thumb_filename
    target_clip["duration"] = rep_info["duration"]
    target_clip["duration_formatted"] = rep_info["duration_formatted"]
    target_clip["replacement_original_name"] = original_filename
    target_clip["filesize"] = os.path.getsize(rep_path)
    target_clip["status"] = "ready"
    
    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)
        
    return project_data

def merge_project_clips(project_dir, output_merged_path):
    """
    Merges all active clips (including any replaced clips) in sequential order.
    """
    project_json_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(project_json_path):
        raise FileNotFoundError("Project metadata not found.")
        
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    clips = project_data.get("clips", [])
    if not clips:
        raise ValueError("No clips to merge.")
        
    concat_txt_path = os.path.join(project_dir, "concat_list.txt")
    with open(concat_txt_path, "w", encoding="utf-8") as f:
        for clip in clips:
            clip_full_path = os.path.join(project_dir, clip["filename"])
            escaped_path = clip_full_path.replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
            
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        output_merged_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    if os.path.exists(concat_txt_path):
        os.remove(concat_txt_path)
        
    return output_merged_path
