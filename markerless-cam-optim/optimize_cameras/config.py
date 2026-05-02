import os 
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Always base the ROOT_DIR on the location of this file (config.py is in optimize_cameras/)
ROOT_DIR = Path(__file__).resolve().parent.parent

# External dependencies: BLENDER_EXE should be in .env if not default
BLENDER_EXE = Path(os.getenv("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"))

# Default render output (Relative to ROOT_DIR)
RENDER_OUTPUT = ROOT_DIR / "renders"

# Internal assets relative to ROOT_DIR
BLENDER_SCRIPTS_DIR = ROOT_DIR / "blender_scripts"
TEMPLATES_DIR = ROOT_DIR / "templates"

# Default target files
SPAWN_SCRIPT = BLENDER_SCRIPTS_DIR / "spawn_subjects.py"
CAMERA_SCRIPT = BLENDER_SCRIPTS_DIR / "setup_rig.py"
RENDER_SCRIPT = BLENDER_SCRIPTS_DIR / "batch_render.py"
RENDER_SCRIPT_SPEED = BLENDER_SCRIPTS_DIR / "batch_render_speed.py"
BASE_SCENE = TEMPLATES_DIR / "large_room.blend"

DEFAULT_EEVEE_SETTINGS = TEMPLATES_DIR / "eevee_fast_settings.json"
DEFAULT_EEVEE_SETTINGS_SPEED = TEMPLATES_DIR / "eevee_fastest_settings.json"

def resolve_config(path_str):
    """Smarter path resolver: checks current dir, then templates/."""
    if not path_str:
        return None
        
    p = Path(path_str)
    # If it's absolute, return it
    if p.is_absolute() and p.exists():
        return p.resolve()

    # If it's relative to current working directory
    if p.exists():
        return p.resolve()

    # Check templates/ relative to ROOT_DIR
    p_template = TEMPLATES_DIR / path_str
    if p_template.exists():
        return p_template.resolve()

    # Final fallback: resolve relative to ROOT_DIR
    return (ROOT_DIR / path_str).resolve()
