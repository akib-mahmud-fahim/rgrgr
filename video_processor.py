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
    Extracts video duration, resolution, width, height, and metadata using FFmpeg.
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
    
    # Parse duration
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if not duration_match:
        raise ValueError("Could not parse video duration from FFmpeg output.")
    
    hours, minutes, seconds = duration_match.groups()
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    
    # Parse resolution: 1920x1080
    res_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", stderr)
    if res_match:
        width = int(res_match.group(1))
        height = int(res_match.group(2))
        resolution = f"{width}x{height}"
    else:
        width = 1280
        height = 720
        resolution = "1280x720"
    
    return {
        "duration": total_seconds,
        "duration_formatted": format_seconds(total_seconds),
        "resolution": resolution,
        "width": width,
        "height": height,
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
        "-pix_fmt", "yuv420p",
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

def slice_video(input_video, output_dir, segment_length=60.0, progress_callback=None):
    """Slices video sequentially and returns summary metadata."""
    os.makedirs(output_dir, exist_ok=True)
    info = get_video_info(input_video)
    segments = calculate_segments(info["duration"], segment_length)
    clips = []
    for i, seg in enumerate(segments):
        clip_data = slice_single_clip(input_video, output_dir, seg)
        clips.append(clip_data)
        if progress_callback:
            progress_callback(i + 1, len(segments), f"Cut clip {i + 1} of {len(segments)}")
    return {
        "original_info": info,
        "segment_length": segment_length,
        "total_clips": len(clips),
        "clips": clips
    }

def replace_clip(project_dir, clip_id, replacement_video_path, original_filename=""):
    """
    Replaces a specific clip with a new user-uploaded video (of any duration).
    Normalizes/re-encodes the replacement to standard compatible MP4 and updates thumbnail.
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
    orig_info = project_data.get("original_info", {})
    orig_w = orig_info.get("width", 1280)
    orig_h = orig_info.get("height", 720)
    
    # Ensure even dimensions for h264 encoder
    if orig_w % 2 != 0: orig_w += 1
    if orig_h % 2 != 0: orig_h += 1
    
    # Generate unique timestamped filename so browser caching never serves old video
    ts = int(time.time())
    rep_filename = f"{clip_id}_replaced_{ts}.mp4"
    rep_path = os.path.join(project_dir, rep_filename)
    rep_thumb_filename = f"{clip_id}_replaced_{ts}_thumb.jpg"
    rep_thumb_path = os.path.join(project_dir, rep_thumb_filename)
    
    # Scale replacement to match project aspect ratio/resolution with padding
    scale_filter = f"scale={orig_w}:{orig_h}:force_original_aspect_ratio=decrease,pad={orig_w}:{orig_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", replacement_video_path,
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        rep_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    # Generate fresh thumbnail
    extract_thumbnail(rep_path, rep_thumb_path, timestamp=min(0.5, rep_info["duration"] / 2.0))
    
    # Clean up old replaced files if any existed
    if target_clip.get("is_replaced") and target_clip.get("filename"):
        old_file = os.path.join(project_dir, target_clip["filename"])
        if os.path.exists(old_file) and old_file != rep_path:
            try: os.remove(old_file)
            except Exception: pass
            
    if target_clip.get("is_replaced") and target_clip.get("thumb_filename"):
        old_thumb = os.path.join(project_dir, target_clip["thumb_filename"])
        if os.path.exists(old_thumb) and old_thumb != rep_thumb_path:
            try: os.remove(old_thumb)
            except Exception: pass
            
    # Update target clip data
    target_clip["is_replaced"] = True
    target_clip["filename"] = rep_filename
    target_clip["thumb_filename"] = rep_thumb_filename
    target_clip["duration"] = rep_info["duration"]
    target_clip["duration_formatted"] = rep_info["duration_formatted"]
    target_clip["replacement_original_name"] = original_filename
    target_clip["filesize"] = os.path.getsize(rep_path)
    target_clip["status"] = "ready"
    
    # Save updated project.json
    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)
        
    return project_data

def merge_project_clips(project_dir, output_merged_path):
    """
    Merges all active clips (including any replaced clips of varying durations) in sequential order.
    """
    project_json_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(project_json_path):
        raise FileNotFoundError("Project metadata not found.")
        
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    clips = project_data.get("clips", [])
    ready_clips = [c for c in clips if c.get("status") == "ready"]
    if not ready_clips:
        raise ValueError("No ready clips to merge.")
        
    concat_txt_path = os.path.join(project_dir, f"concat_list_{int(time.time())}.txt")
    with open(concat_txt_path, "w", encoding="utf-8") as f:
        for clip in ready_clips:
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
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        output_merged_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    if os.path.exists(concat_txt_path):
        try: os.remove(concat_txt_path)
        except Exception: pass
        
    return output_merged_path
