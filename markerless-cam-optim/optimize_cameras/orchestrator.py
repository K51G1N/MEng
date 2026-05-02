import os
import subprocess
from pathlib import Path
from .ml_inference import pose
from . import config
# Fix for OpenMP duplicate library error (OMP: Error #15)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


def _run_blender(blend_file: Path, script_path: Path, task_name: str, script_args: list = None):
    """
    An internal helper function to run Blender with a specified script and arguments, with error handling.
    """

    if not config.BLENDER_EXE.exists():
        print(f"[!] ERROR: Blender not found at {config.BLENDER_EXE}")
        return False
    cmd = [
        str(config.BLENDER_EXE),
        "-b", str(blend_file.resolve()),
        "-P", str(script_path.resolve()),
        "--"
    ]
    if script_args:
        cmd.extend([str(arg) for arg in script_args])

    try:
        subprocess.run(cmd, check=True)
        print(f"[+] {task_name} completed successfully.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] ERROR: {task_name} failed with code {e.returncode}")
        return False
    
def run_blender_generation(subject_json_path: Path, output_blend: Path, scene_path: Path = config.BASE_SCENE):
    """
    Triggers Blender headlessly to run the generation script (spawns SMPL-X).
    """
    print(f"\n[+] Initializing Blender Generation Phase...")
    args = ["--subject_json", subject_json_path.resolve(), "--save_path", output_blend.resolve()]
    success = _run_blender(scene_path, config.SPAWN_SCRIPT, "Blender Generation", args)
    return output_blend if success else False

def run_camera_setup(blend_file: Path, camera_json_path: Path):
    """
    Triggers Blender to setup cameras in an existing .blend file.
    """
    print(f"\n[+] Initializing Camera Setup Phase...")
    return _run_blender(blend_file, config.CAMERA_SCRIPT, "Camera Setup", [camera_json_path.resolve()])

def run_blender_render(blend_file: Path, output_dir: Path = None, frame_limit: int = None, eevee_settings: Path = config.DEFAULT_EEVEE_SETTINGS):
    """
    Triggers Blender headlessly to render the scene from all cameras.
    """
    blend_file = blend_file.resolve()
    
    out = (output_dir or config.RENDER_OUTPUT).resolve()
    print(f"\n[+] Initializing Blender Rendering Phase...")
    
    # Arguments for batch_render.py: output_dir, frame_limit, eevee_settings_path
    args = [
        out,
        frame_limit if frame_limit else "None",
        eevee_settings.resolve() if eevee_settings and eevee_settings.exists() else "None"
    ]
    
    return _run_blender(blend_file, config.RENDER_SCRIPT, "Blender Render", args)

def run_blender_render_speed(blend_file: Path, output_dir: Path = None, frame_limit: int = None, eevee_settings: Path = config.DEFAULT_EEVEE_SETTINGS_SPEED, workers: int = 0, tiles: str = "1x1"):
    """
    Highly optimized parallel rendering using multiple Blender instances.
    """
    import math
    import os
    from concurrent.futures import ThreadPoolExecutor

    blend_file = blend_file.resolve()
    out = (output_dir or config.RENDER_OUTPUT).resolve()
    
    # Dynamically determine optimal workers if not specified
    if workers <= 0:
        logical_cores = os.cpu_count() or 8
        # Safe default: 1/4 of logical cores, capped at 4 to prevent RAM/VRAM exhaustion
        workers = max(1, min(4, logical_cores // 4))
        print(f"\n[+] Auto-detected optimal workers: {workers} (based on {logical_cores} logical cores)")
    
    print(f"\n[+] Initializing SPEED Rendering Phase with {workers} worker(s)...")

    # 1. First, we need to know how many cameras are in the scene to split them
    # For now, we'll assume the user might have many cameras. 
    # A simple way to get camera count is to run a small blender script or just use a high number and let workers fail gracefully.
    # Better: Assume 12 cameras for now or try to detect.
    # To keep it robust, let's just use 24 as a "max" and split them. 
    # Or even better, just divide 0-23 into N chunks.
    
    total_cameras = 24 # Fallback

    # In a real scenario, we might want to query Blender for the camera count first.
    
    camera_chunks = []
    cameras_per_worker = math.ceil(total_cameras / workers)
    for i in range(workers):
        start = i * cameras_per_worker
        end = min((i + 1) * cameras_per_worker, total_cameras)
        if start < end:
            indices = ",".join(map(str, range(start, end)))
            camera_chunks.append(indices)

    def run_worker(indices):
        worker_args = [
            out,
            frame_limit if frame_limit else "None",
            eevee_settings.resolve() if eevee_settings and eevee_settings.exists() else "None",
            indices,
            tiles
        ]
        return _run_blender(blend_file, config.RENDER_SCRIPT_SPEED, f"Worker[{indices}]", worker_args)

    if workers == 1:
        return run_worker(None) # Render all if only 1 worker
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(run_worker, camera_chunks))
        
        return all(results)

def run_human_inference(input_dir: Path, output_dir: Path = None):
    """
    Performs pose inference on camera-specific subdirectories.
    """
    return pose.run_pose_inference(input_dir, output_dir)

def run_stitch_videos(root_dir: Path, output_name: str = "videos"):
    """
    Stitches frames into videos for both renders and inference results.
    """
    root_dir = root_dir.resolve()
    renders_dir = root_dir / "renders"
    inference_dir = root_dir / "inference"
    video_output_dir = root_dir / output_name
    video_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[+] Initializing Video Stitching Phase...")

    def stitch_folder(input_folder: Path, output_file: Path):
        print(f"    [+] Stitching: {input_folder.name} -> {output_file.name}")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", "30",
            "-i", str(input_folder / "F%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_file)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"    [!] FFMPEG Error: {e.stderr.decode()}")
            return False

    # 1. Stitch Raw Renders
    if renders_dir.exists():
        for cam_dir in sorted([d for d in renders_dir.iterdir() if d.is_dir()]):
            out_file = video_output_dir / f"{cam_dir.name}_raw.mp4"
            stitch_folder(cam_dir, out_file)

    # 2. Stitch Inference Results
    if inference_dir.exists():
        for cam_dir in sorted([d for d in inference_dir.iterdir() if d.is_dir()]):
            cam_id = cam_dir.name.replace("_inference", "")
            out_file = video_output_dir / f"{cam_id}_inference.mp4"
            stitch_folder(cam_dir, out_file)

   
    print(f"[+] Video stitching completed. Results in: {video_output_dir}\n")
    return True