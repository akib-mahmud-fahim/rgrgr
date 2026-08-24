import os
import uuid
import json
import zipfile
import threading
import shutil
import time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import video_processor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="AutoClip Pro - Video Slicer & Dubbing Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global task state tracking
tasks_progress = {}

def process_video_background(project_id: str, input_video_path: str, segment_length: float, original_filename: str, project_name: str):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    
    try:
        # Step 1: Probe video info immediately
        info = video_processor.get_video_info(input_video_path)
        segments = video_processor.calculate_segments(info["duration"], segment_length)
        total_segments = len(segments)
        
        # Initialize placeholder clips list
        initial_clips = []
        for seg in segments:
            initial_clips.append({
                "clip_id": seg["clip_id"],
                "index": seg["index"],
                "title": f"Clip {seg['index']:02d}",
                "filename": f"{seg['clip_id']}.mp4",
                "thumb_filename": f"{seg['clip_id']}_thumb.jpg",
                "start": seg["start"],
                "end": seg["end"],
                "duration": seg["duration"],
                "start_formatted": seg["start_formatted"],
                "end_formatted": seg["end_formatted"],
                "duration_formatted": seg["duration_formatted"],
                "is_remainder": seg["is_remainder"],
                "is_replaced": False,
                "replaced_filename": None,
                "original_filename": f"{seg['clip_id']}.mp4",
                "filesize": 0,
                "status": "pending"  # pending | processing | ready
            })
            
        project_data = {
            "project_id": project_id,
            "project_name": project_name or f"Project #{project_id}",
            "original_filename": original_filename,
            "segment_length": segment_length,
            "total_clips": total_segments,
            "original_info": info,
            "clips": initial_clips,
            "created_at": time.time(),
            "status": "processing",  # processing | ready
            "ready_clips_count": 0,
            "current_processing_index": 1
        }
        
        json_path = os.path.join(project_dir, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2)
            
        tasks_progress[project_id] = {
            "status": "processing",
            "percent": 5,
            "message": f"Planned {total_segments} clips. Slicing Clip 1...",
            "current": 0,
            "total": total_segments,
            "project": project_data
        }
        
        # Step 2: Slice each clip progressively & update project.json in real time!
        for i, seg in enumerate(segments):
            project_data["current_processing_index"] = i + 1
            project_data["clips"][i]["status"] = "processing"
            
            # Save processing state
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=2)
                
            tasks_progress[project_id]["message"] = f"Slicing Clip {i + 1} of {total_segments}..."
            tasks_progress[project_id]["current"] = i
            tasks_progress[project_id]["percent"] = int(10 + (i / total_segments) * 85)
            
            # Perform slicing for this single clip
            ready_clip = video_processor.slice_single_clip(input_video_path, project_dir, seg)
            
            # Replace placeholder with ready clip
            project_data["clips"][i] = ready_clip
            project_data["ready_clips_count"] = i + 1
            
            # Save instantly so frontend and download endpoints can immediately access it!
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=2)
                
            tasks_progress[project_id]["project"] = project_data
            tasks_progress[project_id]["current"] = i + 1
            tasks_progress[project_id]["percent"] = int(10 + ((i + 1) / total_segments) * 85)
            tasks_progress[project_id]["message"] = f"Clip {i + 1} of {total_segments} is ready!"
            
        # All clips finished
        project_data["status"] = "ready"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2)
            
        tasks_progress[project_id] = {
            "status": "completed",
            "percent": 100,
            "message": f"All {total_segments} clips sliced and ready for dubbing!",
            "project": project_data
        }
        
    except Exception as e:
        tasks_progress[project_id] = {
            "status": "error",
            "percent": 0,
            "message": f"Processing failed: {str(e)}"
        }

@app.get("/api/projects")
async def list_projects():
    """Lists all created projects with summary metadata."""
    projects = []
    if not os.path.exists(PROJECTS_DIR):
        return []
        
    for pid in os.listdir(PROJECTS_DIR):
        pdir = os.path.join(PROJECTS_DIR, pid)
        if not os.path.isdir(pdir):
            continue
            
        json_path = os.path.join(pdir, "project.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                    
                clips = pdata.get("clips", [])
                replaced_count = sum(1 for c in clips if c.get("is_replaced"))
                ready_count = sum(1 for c in clips if c.get("status") == "ready")
                
                # Check first ready thumbnail for project cover
                cover_thumb = ""
                for c in clips:
                    if c.get("status") == "ready" and c.get("thumb_filename"):
                        cover_thumb = c["thumb_filename"]
                        break
                
                projects.append({
                    "project_id": pdata["project_id"],
                    "project_name": pdata.get("project_name", f"Project {pid}"),
                    "original_filename": pdata.get("original_filename", "Video"),
                    "total_clips": len(clips),
                    "ready_count": ready_count,
                    "replaced_count": replaced_count,
                    "duration_formatted": pdata.get("original_info", {}).get("duration_formatted", "--:--"),
                    "created_at": pdata.get("created_at", os.path.getctime(json_path)),
                    "cover_thumb": cover_thumb,
                    "status": pdata.get("status", "ready")
                })
            except Exception:
                continue
        elif pid in tasks_progress and tasks_progress[pid]["status"] == "processing":
            projects.append({
                "project_id": pid,
                "project_name": f"Processing ({pid})",
                "original_filename": "Analyzing video...",
                "total_clips": tasks_progress[pid].get("total", 0),
                "ready_count": tasks_progress[pid].get("current", 0),
                "replaced_count": 0,
                "duration_formatted": "--:--",
                "created_at": time.time(),
                "cover_thumb": "",
                "status": "processing",
                "percent": tasks_progress[pid].get("percent", 0)
            })
            
    projects.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return projects

@app.post("/api/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    segment_length: float = Form(60.0)
):
    project_id = str(uuid.uuid4())[:8]
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(project_dir, exist_ok=True)
    
    clean_name = project_name.strip() if project_name and project_name.strip() else os.path.splitext(file.filename)[0]
    
    # Save uploaded original video
    ext = os.path.splitext(file.filename)[1] or ".mp4"
    saved_path = os.path.join(project_dir, f"original{ext}")
    
    with open(saved_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024 * 4):  # 4MB chunks
            buffer.write(chunk)
            
    tasks_progress[project_id] = {
        "status": "queued",
        "percent": 0,
        "message": "Video uploaded, starting background slicing...",
        "current": 0,
        "total": 0
    }
    
    # Start progressive background slicing
    threading.Thread(
        target=process_video_background,
        args=(project_id, saved_path, segment_length, file.filename, clean_name),
        daemon=True
    ).start()
    
    return {"project_id": project_id, "status": "processing", "project_name": clean_name}

@app.get("/api/progress/{project_id}")
async def get_progress(project_id: str):
    if project_id not in tasks_progress:
        json_path = os.path.join(PROJECTS_DIR, project_id, "project.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                project_data = json.load(f)
            return {
                "status": project_data.get("status", "ready"),
                "percent": 100 if project_data.get("status") == "ready" else 50,
                "message": "Ready",
                "project": project_data
            }
        raise HTTPException(status_code=404, detail="Task or project not found")
        
    return tasks_progress[project_id]

@app.get("/api/project/{project_id}")
async def get_project(project_id: str):
    json_path = os.path.join(PROJECTS_DIR, project_id, "project.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.delete("/api/project/{project_id}")
async def delete_project(project_id: str):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir, ignore_errors=True)
    if project_id in tasks_progress:
        del tasks_progress[project_id]
    return {"status": "deleted", "project_id": project_id}

@app.patch("/api/project/{project_id}")
async def rename_project(project_id: str, name: str = Form(...)):
    json_path = os.path.join(PROJECTS_DIR, project_id, "project.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
    project_data["project_name"] = name.strip()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)
    return project_data

@app.get("/api/media/{project_id}/{filename}")
async def get_media(project_id: str, filename: str):
    file_path = os.path.join(PROJECTS_DIR, project_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found or still processing")
        
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)

@app.get("/api/download/clip/{project_id}/{clip_id}")
async def download_clip(project_id: str, clip_id: str):
    json_path = os.path.join(PROJECTS_DIR, project_id, "project.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Project not found")
        
    with open(json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    clip = next((c for c in project_data["clips"] if c["clip_id"] == clip_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
        
    if clip.get("status") != "ready":
        raise HTTPException(status_code=400, detail="This clip is still being processed. Please wait a moment.")
        
    file_path = os.path.join(PROJECTS_DIR, project_id, clip["filename"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Clip file not found")
        
    proj_prefix = project_data.get("project_name", "Video").replace(" ", "_")
    download_filename = f"{proj_prefix}_Clip_{clip['index']:02d}_{clip['start_formatted'].replace(':', '-')}_to_{clip['end_formatted'].replace(':', '-')}.mp4"
    if clip.get("is_replaced"):
        download_filename = f"{proj_prefix}_Clip_{clip['index']:02d}_Dubbed.mp4"
        
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=download_filename,
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
    )

@app.get("/api/download/zip/{project_id}")
async def download_all_zip(project_id: str):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    json_path = os.path.join(project_dir, "project.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Project not found")
        
    with open(json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    proj_title = project_data.get("project_name", f"Project_{project_id}").replace(" ", "_")
    zip_filename = f"{proj_title}_Ready_Clips.zip"
    zip_path = os.path.join(project_dir, zip_filename)
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for clip in project_data.get("clips", []):
            if clip.get("status") == "ready":
                clip_path = os.path.join(project_dir, clip["filename"])
                if os.path.exists(clip_path):
                    arcname = f"Clip_{clip['index']:02d}_{clip['start_formatted'].replace(':', '-')}_to_{clip['end_formatted'].replace(':', '-')}.mp4"
                    if clip.get("is_replaced"):
                        arcname = f"Clip_{clip['index']:02d}_Dubbed.mp4"
                    zipf.write(clip_path, arcname=arcname)
                
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_filename,
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )

@app.post("/api/replace/{project_id}/{clip_id}")
async def replace_clip_endpoint(
    project_id: str,
    clip_id: str,
    file: UploadFile = File(...)
):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
        
    temp_ext = os.path.splitext(file.filename)[1] or ".mp4"
    temp_path = os.path.join(project_dir, f"temp_rep_{clip_id}{temp_ext}")
    
    with open(temp_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024 * 4):
            buffer.write(chunk)
            
    try:
        updated_project = video_processor.replace_clip(
            project_dir=project_dir,
            clip_id=clip_id,
            replacement_video_path=temp_path,
            original_filename=file.filename
        )
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return updated_project
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export-merged/{project_id}")
async def export_merged_video(project_id: str):
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project not found")
        
    merged_filename = f"Final_Dubbed_Video_{project_id}.mp4"
    merged_path = os.path.join(project_dir, merged_filename)
    
    try:
        video_processor.merge_project_clips(project_dir, merged_path)
        return {
            "status": "ready",
            "filename": merged_filename,
            "download_url": f"/api/media/{project_id}/{merged_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AutoClip Studio</h1>"
