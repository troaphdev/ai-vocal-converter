from fastapi import FastAPI, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import torch # Added for PyTorch settings

# Useful touch from the guide: GPU OOM on 6 GB
# These settings might help performance and memory on compatible GPUs.
# Ensure your PyTorch version and hardware support these.
try:
    torch.set_float32_matmul_precision('high') # or 'medium'
    torch.backends.cuda.matmul.allow_tf32 = True
    print("Applied PyTorch matmul precision settings.")
except Exception as e:
    print(f"Could not apply PyTorch matmul precision settings: {e}")

# Assuming converter.py is in the same directory (app/)
from .converter import list_artists, convert 

app = FastAPI()

# --- Directory Setup ---
BASE_DIR = Path(__file__).resolve().parent.parent # This should be rvc-webapp directory
VENV_PYTHON_EXECUTABLE = BASE_DIR / ".venv" / "Scripts" / "python.exe" # Path for Windows
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
MODELS_DIR = BASE_DIR / "models" # For checking if it exists initially
OUTPUT_DIR = BASE_DIR / "outputs" # For consistency with converter.py

# Create necessary directories if they don't exist
UPLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True) # Ensure models dir exists for user to populate
OUTPUT_DIR.mkdir(exist_ok=True) # Ensure outputs dir exists as converter.py also creates subdirs here

# --- Job Management ---
# Using a simple dictionary for job management as per the guide.
# For production, a more robust system (Redis, Celery, RQ) is recommended.
jobs: dict[str, dict] = {} # Stores job_id: {"status": str, "result_path": Path | None, "error": str | None}


# --- Helper Functions ---
async def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        await upload_file.close()

# --- API Endpoints ---
@app.get("/artists")
def get_artists():
    """Lists available artist models."""
    available_artists = list_artists()
    if not available_artists and not list(MODELS_DIR.iterdir()): # Check if models folder is truly empty or just no subdirs
        print(f"No artist subdirectories found in {MODELS_DIR}. Please ensure models are organized in subfolders like '{MODELS_DIR}/ArtistName/'")
    elif not available_artists:
        print(f"No valid artist model directories found by list_artists() in {MODELS_DIR}. Check converter.py logic and model structure.")
    return available_artists

@app.post("/convert")
async def post_convert(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    artist: str = Form(...)
):
    """Accepts a song file and artist name, starts async conversion, returns job_id."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    
    # Secure filename (though Path handling is generally safer)
    # from werkzeug.utils import secure_filename
    # safe_filename = secure_filename(file.filename)
    # Using a UUID or a combination for the temp file to avoid collisions
    import uuid
    temp_filename = f"{uuid.uuid4().hex}_{file.filename}"
    tmp_song_path = UPLOADS_DIR / temp_filename

    await save_upload_file(file, tmp_song_path)

    # Simplified job ID from the guide, consider making it more unique if high traffic
    job_id = f"{artist}_{file.filename.replace(' ', '_')}_{len(jobs)}"
    jobs[job_id] = {"status": "processing", "result_path": None, "error": None}

    def conversion_task(song_path: Path, selected_artist: str, current_job_id: str):
        try:
            print(f"Starting conversion for job: {current_job_id}, artist: {selected_artist}, file: {song_path.name}")
            result_path = convert(song_path, selected_artist, VENV_PYTHON_EXECUTABLE)
            jobs[current_job_id]["status"] = "completed"
            jobs[current_job_id]["result_path"] = result_path
            print(f"Conversion completed for job: {current_job_id}. Output: {result_path}")
        except Exception as e:
            print(f"Error during conversion task for job {current_job_id}: {e}")
            jobs[current_job_id]["status"] = "failed"
            jobs[current_job_id]["error"] = str(e)
        finally:
            # Clean up the temporary uploaded file
            if song_path.exists():
                try:
                    song_path.unlink()
                    print(f"Cleaned up temporary file: {song_path}")
                except OSError as e_unlink:
                    print(f"Error cleaning up temporary file {song_path}: {e_unlink}")

    background_tasks.add_task(conversion_task, tmp_song_path, artist, job_id)
    return {"job_id": job_id}

@app.get("/result/{job_id}")
def get_result(job_id: str):
    """Checks job status. If completed, streams/downloads the WAV file."""
    job_info = jobs.get(job_id)

    if not job_info:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    if job_info["status"] == "processing":
        return {"status": "processing"}
    elif job_info["status"] == "failed":
        return {"status": "failed", "error": job_info["error"]}
    elif job_info["status"] == "completed" and job_info["result_path"]:
        result_path: Path = job_info["result_path"]
        if result_path.exists():
            return FileResponse(result_path, media_type="audio/wav", filename="converted.wav")
        else:
            # This case should ideally not happen if job completed successfully
            print(f"Error: Result file {result_path} not found for completed job {job_id}.")
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = "Result file missing after conversion."
            return {"status": "failed", "error": "Result file missing after conversion."}
    else:
        # Should not happen with current states
        raise HTTPException(status_code=500, detail="Inconsistent job state.")

# Mount static files last, as it can catch all other routes if not careful.
# The guide suggests mounting at "/" to serve index.html as the default page.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

# --- To run this app (from rvc-webapp directory): ---
# Ensure you have an RVC environment activated if needed.
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 