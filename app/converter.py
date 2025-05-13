from pathlib import Path
import subprocess, uuid, shutil, os, tempfile
# import sys # No longer using sys.executable directly here

MODELS = Path(__file__).parent.parent / "models"
OUTPUT = Path(__file__).parent.parent / "outputs"

# Logic for finding rvc_script_path and PYTHON_EXECUTABLE moved into convert function,
# using the passed venv_python_executable path.

OUTPUT.mkdir(parents=True, exist_ok=True) # Ensure outputs directory exists

def list_artists():
    if not MODELS.exists():
        return []
    return [d.name for d in MODELS.iterdir() if d.is_dir()]

# Added venv_python_executable parameter
def convert(song_path: Path, artist: str, venv_python_executable: Path) -> Path:
    job_id = uuid.uuid4().hex
    out_dir = OUTPUT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / "out.wav"

    model_dir = MODELS / artist
    try:
        ckpt = next(model_dir.glob("*.pth"))
    except StopIteration:
        raise FileNotFoundError(f"No .pth model file found in {model_dir}")
        
    index_files = list(model_dir.glob("*.index"))
    index = index_files[0] if index_files else None
    
    # Construct path to rvc_infer.py within the venv Scripts directory
    rvc_script_name = "rvc_infer.py"
    # venv_python_executable is like C:\path\to\rvc-webapp\.venv\Scripts\python.exe
    # So, its parent is .venv\Scripts
    venv_scripts_dir = venv_python_executable.parent 
    rvc_script_full_path = venv_scripts_dir / rvc_script_name

    if not venv_python_executable.is_file():
        raise FileNotFoundError(f"Provided venv Python executable not found: {venv_python_executable}")

    if not rvc_script_full_path.is_file():
        raise FileNotFoundError(f"RVC script '{rvc_script_name}' not found in venv Scripts dir: {venv_scripts_dir}. Expected at {rvc_script_full_path}")

    cmd = [
        str(venv_python_executable), str(rvc_script_full_path),
        "--input", str(song_path),
        "--output", str(out_wav),
        "--model", str(ckpt),
        "--pitch", "rmvpe",
    ]
    if index:
        cmd += ["--index", str(index)]

    print(f"Executing RVC command: {' '.join(cmd)}")
    try:
        process = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("RVC STDOUT:", process.stdout)
        print("RVC STDERR:", process.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error during RVC conversion: {e}")
        print("RVC STDOUT:", e.stdout)
        print("RVC STDERR:", e.stderr)
        raise RuntimeError(f"RVC conversion failed: {e.stderr}") from e
    except FileNotFoundError as e: 
        print(f"Error: Problem finding or executing RVC script '{rvc_script_full_path}' with interpreter '{venv_python_executable}'. {e}")
        raise RuntimeError(f"RVC script or venv Python interpreter issue. Error: {e}") from e

    return out_wav 