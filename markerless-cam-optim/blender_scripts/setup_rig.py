import bpy
import json
import math
import os
import sys
from mathutils import Euler

def load_json(path):
    """Reads the camera configuration file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def setup_multiview_globals():
    """Configures the scene for Multiview rendering."""
    scene = bpy.context.scene
    render = scene.render
    
    # 1. Enable Multiview
    render.use_multiview = True
    render.views_format = 'MULTIVIEW'
    
    # 2. Clear default 'left' and 'right' views to keep the UI clean
    for view_name in ["left", "right"]:
        if view_name in render.views:
            render.views[view_name].use = False

def cleanup_existing_cameras():
    """
    Removes existing objects starting with 'Camera' to prevent 
    naming collisions like 'Camera.001'.
    """
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA' or obj.name.startswith("Camera"):
            # We delete the object and its data to keep the file light
            cam_data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if cam_data:
                bpy.data.cameras.remove(cam_data)

def add_camera_to_multiview(cam_obj, index):
    """
    Links a camera object to a specific Render View via a numeric suffix.
    """
    render_views = bpy.context.scene.render.views
    
    # Define naming strings
    view_name = str(index)      # The name in the 'Views' list
    suffix = f"_{index}"        # The suffix Blender looks for (e.g., _0, _1)
    
    # Create the Render View entry if it doesn't exist
    if view_name not in render_views:
        new_view = render_views.new(name=view_name)
    else:
        new_view = render_views[view_name]
    
    # Set the suffix so Blender knows: "To render View '0', use object 'Camera_0'"
    new_view.file_suffix = suffix
    new_view.use = True

    # Rename the object to match the suffix logic
    cam_obj.name = f"Camera{suffix}"

def ensure_camera_object(name):
    """Creates a new camera object and links it to the scene."""
    cam_data = bpy.data.cameras.new(name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam_obj)
    return cam_obj, cam_data

def set_camera_properties(cam_obj, cam_data, cfg):
    """Applies location, rotation, and hardware settings from JSON."""
    # Set World Position
    loc = cfg.get('location')
    if loc: 
        cam_obj.location = tuple(float(x) for x in loc)

    # Set Euler Rotation (Degrees to Radians)
    rot_deg = cfg.get('rotation_degrees')
    if rot_deg:
        rot_rad = [math.radians(float(a)) for a in rot_deg]
        cam_obj.rotation_euler = Euler(rot_rad, 'XYZ')

    # Apply Physical Camera parameters
    params = cfg.get('parameters', {})
    hw = params.get('hardware', {})
    if hw:
        cam_data.lens = float(hw.get('focal_length_mm', 4.74))
        cam_data.sensor_width = float(hw.get('sensor_width_mm', 6.4512))
        cam_data.sensor_height = float(hw.get('sensor_height_mm', 3.6288))

    # Apply Render Resolution (Global Scene Setting)
    intrinsics = params.get('intrinsics', {})
    res = intrinsics.get('resolution')
    if res:
        bpy.context.scene.render.resolution_x = int(res[0])
        bpy.context.scene.render.resolution_y = int(res[1])

def process_config(config):
    """Main loop to process the JSON list and build the rig."""
    # Start with a clean slate
    cleanup_existing_cameras()
    setup_multiview_globals()

    for entry in config:
        for key, item in entry.items():
            # 'key' is the index (0, 1, 2) from your JSON dictionary
            name = item.get('camera_name')
            if not name: 
                continue

            # 1. Create the camera
            cam_obj, cam_data = ensure_camera_object(name)
            
            # 2. Apply properties
            set_camera_properties(cam_obj, cam_data, item)
            
            # 3. Register in Multiview (Renames to Camera_0, Camera_1, etc.)
            add_camera_to_multiview(cam_obj, key)
            
            # 4. Set Camera_0 as the Scene's Master Camera
            if key == "0":
                bpy.context.scene.camera = cam_obj

def main(path=None):
    """Entry point for the script."""
    # Update this path to your local environment
    default_path = r"C:\Users\20716400\Documents\BlenderProjects\camera_info.json"
    
    # Handle Command Line Arguments (for background rendering)
    argv = sys.argv
    if "--" in argv:
        idx = argv.index("--")
        args = argv[idx+1:]
        cfg_path = args[0] if len(args) >= 1 else default_path
    else:
        cfg_path = path if path else default_path

    if not os.path.exists(cfg_path):
        print(f"Error: File not found {cfg_path}")
        return

    # Execute
    config = load_json(cfg_path)
    process_config(config)
    
    # Save the file to persist changes
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    
    print("Multiview setup complete: Cameras named Camera_0, Camera_1, etc.")
    print(f"File saved: {bpy.data.filepath}")

if __name__ == "__main__":
    main()