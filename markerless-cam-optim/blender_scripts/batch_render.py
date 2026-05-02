import bpy
import os
import json
import sys

def setup_gpu():
    """Ensures that the GPU is enabled for rendering."""
    print("Setting up GPU acceleration...")
    scene = bpy.context.scene
    prefs = bpy.context.preferences
    
    # Try to access cycles preferences to enable GPU devices
    try:
        cprefs = prefs.addons['cycles'].preferences
        # Attempt to use OptiX (best for RTX cards), fallback to CUDA
        for compute_device_type in ('OPTIX', 'CUDA'):
            try:
                cprefs.compute_device_type = compute_device_type
                print(f"Set compute device type to {compute_device_type}")
                break
            except TypeError:
                pass

        # Refresh devices
        cprefs.get_devices()
        
        # Enable all GPU devices
        for device in cprefs.devices:
            if device.type in ('OPTIX', 'CUDA'):
                device.use = True
                print(f"Enabled device: {device.name}")
    except KeyError:
        print("Cycles addon not found, skipping detailed GPU device selection.")

    # Set scene to use GPU if possible
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

def render_flat_directory(output_directory, frame_limit=None, eevee_settings_path=None):
    scene = bpy.context.scene
    
    # 1. THE FIX: Kill Multiview to stop the 3x duplication
    scene.render.use_multiview = False
    
    # 2. Fast GPU Setup
    setup_gpu()
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    
    # 3. Apply Eevee optimizations
    if eevee_settings_path:
        apply_eevee_settings(eevee_settings_path)
    else:
        # Default fallback optimizations
        if hasattr(scene, 'eevee'):
            scene.eevee.taa_render_samples = 16
        
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        
    # Collect and sort cameras to ensure consistent C0, C1, C2 indexing
    cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
    cameras.sort(key=lambda x: x.name)
    
    if not cameras:
        print("No cameras found.")
        return

    # Determine frame range
    start_frame = scene.frame_start
    end_frame = scene.frame_end
    if frame_limit:
        end_frame = min(start_frame + int(frame_limit) - 1, scene.frame_end)
        print(f"Limiting render to first {frame_limit} frames ({start_frame} to {end_frame})")

    # Main Render Loop
    for frame in range(start_frame, end_frame + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        
        for index, cam in enumerate(cameras):
            # Explicitly set the camera
            scene.camera = cam
            
            # Create camera-specific subdirectory
            cam_dir = os.path.join(output_directory, f"C{index}")
            if not os.path.exists(cam_dir):
                os.makedirs(cam_dir)
            
            # Format: F0001.png inside C0/ folder
            filename = f"F{frame:04d}.png"
            scene.render.filepath = os.path.join(cam_dir, filename)
            
            # Render the single frame
            bpy.ops.render.render(write_still=True)
            print(f"Saved: C{index}/{filename}")

def main():
    # Default paths
    output_path = r"C:\Users\20716400\Documents\BlenderProjects\Renders"
    frame_limit = None
    eevee_settings = None
    
    # Check for arguments passed from orchestrator.py
    # Expected: blender -b scene.blend -P script.py -- output_dir frame_limit eevee_settings_json
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
        if len(argv) >= 1:
            output_path = argv[0]
        if len(argv) >= 2 and argv[1] != "None":
            frame_limit = argv[1]
        if len(argv) >= 3 and argv[2] != "None":
            eevee_settings = argv[2]
            
    render_flat_directory(output_path, frame_limit=frame_limit, eevee_settings_path=eevee_settings)

if __name__ == "__main__":
    main()