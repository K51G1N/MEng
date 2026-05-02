import bpy
import os
import json
import sys

def setup_gpu():
    """Ensures that the GPU is enabled for rendering."""
    print("Setting up GPU acceleration...")
    scene = bpy.context.scene
    prefs = bpy.context.preferences
    
    try:
        cprefs = prefs.addons['cycles'].preferences
        for compute_device_type in ('OPTIX', 'CUDA'):
            try:
                cprefs.compute_device_type = compute_device_type
                print(f"Set compute device type to {compute_device_type}")
                break
            except TypeError:
                pass

        cprefs.get_devices()
        for device in cprefs.devices:
            if device.type in ('OPTIX', 'CUDA'):
                device.use = True
                print(f"Enabled device: {device.name}")
    except KeyError:
        print("Cycles addon not found, skipping detailed GPU device selection.")

    if hasattr(scene, 'cycles'):
        scene.cycles.device = 'GPU'
    
    print("GPU setup complete.")

def apply_eevee_settings(settings_path):
    """Loads Eevee settings from a JSON file and applies them to the current scene."""
    if not settings_path or not os.path.exists(settings_path):
        print(f"Eevee settings file not found: {settings_path}")
        return

    print(f"Applying Eevee settings from {settings_path}...")
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        scene = bpy.context.scene
        if not hasattr(scene, 'eevee'):
            print("Scene does not have Eevee settings (check render engine).")
            return

        eevee = scene.eevee
        for key, value in settings.items():
            if hasattr(eevee, key):
                setattr(eevee, key, value)
                print(f"  Set {key} = {value}")
            else:
                print(f"  Warning: Eevee does not have property '{key}'")
    except Exception as e:
        print(f"Error applying Eevee settings: {e}")

def render_speed(output_directory, frame_limit=None, eevee_settings_path=None, camera_indices=None, tiles=(1, 1)):
    """
    Highly optimized render loop.
    - camera_indices: List of integers [0, 2, 4] to render only specific cameras (for parallelization).
    - tiles: (x, y) tuple for render-border tiling.
    """
    scene = bpy.context.scene
    
    # 1. Kill Multiview
    scene.render.use_multiview = False
    
    # 2. Fast GPU Setup & Engine
    setup_gpu()
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    
    # 3. Apply Eevee optimizations
    if eevee_settings_path:
        apply_eevee_settings(eevee_settings_path)
    
    # Global performance overrides
    if hasattr(scene, 'eevee'):
        scene.eevee.use_shadows = True # Speed up by keeping it True but low quality usually better
        
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        
    # Collect and sort cameras
    all_cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
    all_cameras.sort(key=lambda x: x.name)
    
    # Filter cameras if indices provided
    if camera_indices is not None:
        cameras_to_render = []
        for idx in camera_indices:
            if 0 <= idx < len(all_cameras):
                cameras_to_render.append((idx, all_cameras[idx]))
        print(f"Rendering camera subset: {[c[0] for c in cameras_to_render]}")
    else:
        cameras_to_render = list(enumerate(all_cameras))
    
    if not cameras_to_render:
        print("No cameras to render.")
        return

    # Determine frame range
    start_frame = scene.frame_start
    end_frame = scene.frame_end
    if frame_limit:
        end_frame = min(start_frame + int(frame_limit) - 1, scene.frame_end)

    # Render Border Tiling Setup
    tiles_x, tiles_y = tiles
    use_tiling = tiles_x > 1 or tiles_y > 1
    scene.render.use_border = use_tiling
    scene.render.use_crop_to_border = False # Usually want full size images even if tiled (or True if stitching later)

    # Main Render Loop
    for frame in range(start_frame, end_frame + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        
        for index, cam in cameras_to_render:
            scene.camera = cam
            cam_dir = os.path.join(output_directory, f"C{index}")
            if not os.path.exists(cam_dir):
                os.makedirs(cam_dir)
            
            filename = f"F{frame:04d}.png"
            scene.render.filepath = os.path.join(cam_dir, filename)
            
            if not use_tiling:
                bpy.ops.render.render(write_still=True)
            else:
                # Tiling logic (Note: This saves multiple files per frame if not careful)
                # For simplicity in this script, we just render the tiles 
                # but overwrite the same file or use a suffix
                for tx in range(tiles_x):
                    for ty in range(tiles_y):
                        scene.render.border_min_x = tx / tiles_x
                        scene.render.border_max_x = (tx + 1) / tiles_x
                        scene.render.border_min_y = ty / tiles_y
                        scene.render.border_max_y = (ty + 1) / tiles_y
                        
                        # If tiling, we might want to save chunks
                        if use_tiling:
                            scene.render.filepath = os.path.join(cam_dir, f"F{frame:04d}_t{tx}_{ty}.png")
                        
                        bpy.ops.render.render(write_still=True)
            
            print(f"Saved: C{index}/{filename} (Frame {frame})")

def main():
    output_path = r"C:\Users\20716400\Documents\BlenderProjects\Renders"
    frame_limit = None
    eevee_settings = None
    camera_indices = None
    tiles = (1, 1)
    
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
        if len(argv) >= 1:
            output_path = argv[0]
        if len(argv) >= 2 and argv[1] != "None":
            frame_limit = int(argv[1])
        if len(argv) >= 3 and argv[2] != "None":
            eevee_settings = argv[2]
        if len(argv) >= 4 and argv[3] != "None":
            # Expecting comma separated indices: "0,1,2"
            camera_indices = [int(i) for i in argv[3].split(",")]
        if len(argv) >= 5 and argv[4] != "None":
            # Expecting "2x2"
            tx, ty = [int(i) for i in argv[4].split("x")]
            tiles = (tx, ty)
            
    render_speed(output_path, frame_limit, eevee_settings, camera_indices, tiles)

if __name__ == "__main__":
    main()
