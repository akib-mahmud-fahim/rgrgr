import os
import subprocess
import json
import imageio_ffmpeg
import video_processor

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_env")
os.makedirs(TEST_DIR, exist_ok=True)

def generate_test_video(path, duration_seconds=135):
    """Generates a test MP4 video with countdown and test tone."""
    print(f"Generating {duration_seconds}s test video at {path}...")
    cmd = [
        FFMPEG,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=size=640x360:rate=25",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_seconds}",
        "-t", str(duration_seconds),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("Test video generated successfully.")

def run_tests():
    sample_video = os.path.join(TEST_DIR, "sample_135s.mp4")
    generate_test_video(sample_video, 135) # 2 min 15 sec
    
    # 1. Test probe
    info = video_processor.get_video_info(sample_video)
    print(f"Probed Info: duration={info['duration']}s ({info['duration_formatted']}), res={info['resolution']}")
    assert abs(info["duration"] - 135) < 1.0, f"Expected ~135s, got {info['duration']}"
    
    # 2. Test slicing
    project_output = os.path.join(TEST_DIR, "project_test")
    os.makedirs(project_output, exist_ok=True)
    
    slice_res = video_processor.slice_video(
        input_video=sample_video,
        output_dir=project_output,
        segment_length=60.0
    )
    
    clips = slice_res["clips"]
    print(f"Generated {len(clips)} clips:")
    for c in clips:
        print(f" - {c['title']}: {c['start_formatted']} -> {c['end_formatted']} ({c['duration_formatted']}) [Remainder: {c['is_remainder']}]")
        assert os.path.exists(os.path.join(project_output, c["filename"])), f"Missing {c['filename']}"
        assert os.path.exists(os.path.join(project_output, c["thumb_filename"])), f"Missing thumb {c['thumb_filename']}"
        
    assert len(clips) == 3, f"Expected 3 clips (60s, 60s, 15s), got {len(clips)}"
    assert clips[0]["duration"] == 60.0
    assert clips[1]["duration"] == 60.0
    assert abs(clips[2]["duration"] - 15.0) < 1.0
    assert clips[2]["is_remainder"] == True
    
    # Save project.json
    project_json = {
        "project_id": "test_proj",
        "segment_length": 60.0,
        "original_info": info,
        "clips": clips
    }
    with open(os.path.join(project_output, "project.json"), "w", encoding="utf-8") as f:
        json.dump(project_json, f, indent=2)
        
    # 3. Test Clip Replacement (Replace Clip 2 with a new 20s video)
    replacement_video = os.path.join(TEST_DIR, "replacement_20s.mp4")
    generate_test_video(replacement_video, 20)
    
    print("Testing clip replacement on clip_002...")
    updated_project = video_processor.replace_clip(
        project_dir=project_output,
        clip_id="clip_002",
        replacement_video_path=replacement_video,
        original_filename="new_replacement.mp4"
    )
    
    clip2 = next(c for c in updated_project["clips"] if c["clip_id"] == "clip_002")
    assert clip2["is_replaced"] == True
    assert abs(clip2["duration"] - 20.0) < 1.0
    print(f"Clip 2 successfully replaced: New duration = {clip2['duration_formatted']}")
    
    # 4. Test Merging
    merged_output = os.path.join(project_output, "merged_final.mp4")
    video_processor.merge_project_clips(project_output, merged_output)
    assert os.path.exists(merged_output)
    merged_info = video_processor.get_video_info(merged_output)
    print(f"Merged Video created successfully! Total Duration: {merged_info['duration_formatted']} (60s + 20s + 15s = ~95s)")
    
    print("\n[SUCCESS] ALL WORKFLOW AND REPLACEMENT TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
