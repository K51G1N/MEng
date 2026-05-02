import argparse
import sys
from pathlib import Path
from . import orchestrator
from . import config

def ensure_exists(path, message):
    p = Path(path)
    if not p.exists():
        print(f"Error: {message} not found: {path}")
        sys.exit(1)
    return p

def main():
    parser = argparse.ArgumentParser(description="Markerless Camera Optimization CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    #Shared parser to hold common arguments
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--continue", "-c", dest="continue_pipeline", action="store_true", help="Continue to stitching")
    shared_parser.add_argument("--limit", type=int, help="Limit rendering to first N frames")
    shared_parser.add_argument("--run_name", type=str, required=False, help="Optional name for this run, used in output directories otherwise experiment_run used as default")
    shared_parser.add_argument("--eevee_settings", type=str, help="Path to Eevee settings JSON")
    shared_parser.add_argument("--speed", action="store_true", help="Use high-speed rendering optimizations and parallel workers")
    shared_parser.add_argument("--workers", type=int, default=0, help="Number of parallel Blender workers (0 for auto, requires --speed)")
    shared_parser.add_argument("--tiles", type=str, default="1x1", help="Render tiling (e.g. 2x2) (requires --speed)")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a Blender scene with SMPL-X models")
    gen_parser.add_argument("--config", type=str, required=True, help="Path to the subject info JSON")
    gen_parser.add_argument("--output", type=str, default="generated_scene.blend", help="Path to save the .blend file")
    gen_parser.add_argument("--scene", type=str, help="Path to the base .blend scene")
    
    # Camera setup command
    camera_parser = subparsers.add_parser("setup_cameras", parents=[shared_parser], help="Place cameras in an existing .blend file")
    camera_parser.add_argument("--blend", type=str, required=True, help="Path to the .blend file")
    camera_parser.add_argument("--config", type=str, required=True, help="Path to the camera config JSON")

    # Render command
    render_parser = subparsers.add_parser("render", parents=[shared_parser], help="Render a .blend scene from all cameras")
    render_parser.add_argument("--blend", type=str, required=True, help="Path to the .blend file to render")
    render_parser.add_argument("--output", type=str, help="Directory to save renders")
    # Inference command
    infer_parser = subparsers.add_parser("inference", parents=[shared_parser], help="Perform human pose estimation on rendered images")
    infer_parser.add_argument("--input", type=str, required=True, help="Directory containing images to process")
    infer_parser.add_argument("--output", type=str, help="Directory to save results")
    # Stitch videos command
    stitch_parser = subparsers.add_parser("stitch_videos", parents=[shared_parser], help="Stitch frames into MP4 videos using FFMPEG")
    stitch_parser.add_argument("--dir", type=str, required=True, help="Root directory containing renders and inference folders")
    stitch_parser.add_argument("--output", "-o", type=str, default="videos", help="Subdirectory name for videos")

    # Full Pipeline command
    full_parser = subparsers.add_parser("full_pipeline", parents=[shared_parser], help="Run entire pipeline: generate > setup_cameras > render > inference > stitch")
    full_parser.add_argument("--subject_config", type=str, required=True, help="Path to subject info JSON")
    full_parser.add_argument("--camera_config", type=str, required=True, help="Path to camera info JSON")
    full_parser.add_argument("--output", "-o", type=str, required=True, help="Root directory for all outputs")
    full_parser.add_argument("--scene", type=str, help="Path to base .blend file")

    args = parser.parse_args()

    if args.command == "generate":
        config_path = config.resolve_config(args.config)
        scene = config.resolve_config(args.scene) if args.scene else config.BASE_SCENE
        
        success = orchestrator.run_blender_generation(config_path, Path(args.output), scene)
        
        if not success:
            sys.exit(1)
        print(f"[SUCCESS] Generated scene saved to: {success}")

    elif args.command == "setup_cameras":
        blend_path = ensure_exists(args.blend, "Blender file")
        config_path = config.resolve_config(args.config)
        
        if not orchestrator.run_camera_setup(blend_path, config_path): sys.exit(1)

        if args.continue_pipeline:
            root = blend_path.parent
            render_dir = root / "renders"
            if args.speed:
                eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS_SPEED
                orchestrator.run_blender_render_speed(blend_path, render_dir, frame_limit=args.limit, eevee_settings=eevee_settings, workers=args.workers, tiles=args.tiles)
            else:
                eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS
                orchestrator.run_blender_render(blend_path, render_dir, frame_limit=args.limit, eevee_settings=eevee_settings)
            
            orchestrator.run_human_inference(render_dir)
            orchestrator.run_stitch_videos(root)

    elif args.command == "render":
        blend_path = Path(args.blend)
        blend_path = ensure_exists(blend_path, "Blender file")
        output_dir = Path(args.output) if args.output else config.RENDER_OUTPUT
        
        if args.speed:
            eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS_SPEED
            success = orchestrator.run_blender_render_speed(blend_path, output_dir, frame_limit=args.limit, eevee_settings=eevee_settings, workers=args.workers, tiles=args.tiles)
        else:
            eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS
            success = orchestrator.run_blender_render(blend_path, output_dir, frame_limit=args.limit, eevee_settings=eevee_settings)
        
        if not success: sys.exit(1)
        
        if args.continue_pipeline:
            actual_render_dir = output_dir if output_dir else config.RENDER_OUTPUT
            root_dir = actual_render_dir.parent
            print("\n--- CONTINUING TO INFERENCE ---")
            inference_dir = root_dir / "inference"
            if orchestrator.run_human_inference(actual_render_dir, inference_dir):
                print("\n--- CONTINUING TO STITCHING ---")
                orchestrator.run_stitch_videos(root_dir)

    elif args.command == "inference":
        input_dir = ensure_exists(args.input, "Input directory")
        output_dir = Path(args.output) if args.output else input_dir.parent / "inference"

        if not orchestrator.run_human_inference(input_dir, output_dir): sys.exit(1)
            
        if args.continue_pipeline:

            # Determine root directory for stitching
            # If input_dir is 'renders', then parent is root
            root_dir = input_dir.parent
            print("\n--- CONTINUING TO STITCHING ---")
            orchestrator.run_stitch_videos(root_dir)

    elif args.command == "stitch_videos":
        root_dir = ensure_exists(args.dir, "Root directory for stitching")
        orchestrator.run_stitch_videos(root_dir, args.output)

    elif args.command == "full_pipeline":
        root_output = Path(args.output)
        root_output.mkdir(parents=True, exist_ok=True)
        
        subject_config = config.resolve_config(args.subject_config)
        camera_config = config.resolve_config(args.camera_config)
        scene = config.resolve_config(args.scene) if args.scene else config.BASE_SCENE
        eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS

        blend = orchestrator.run_blender_generation(subject_config, root_output / "generated_scene.blend", scene)

        if not blend: sys.exit(1)

        if not orchestrator.run_camera_setup(blend, camera_config): sys.exit(1)

        render_dir = root_output / "renders"

        if args.speed:
            eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS_SPEED
            if not orchestrator.run_blender_render_speed(blend, render_dir, frame_limit=args.limit, eevee_settings=eevee_settings, workers=args.workers, tiles=args.tiles): sys.exit(1)
        else:
            eevee_settings = config.resolve_config(args.eevee_settings) if args.eevee_settings else config.DEFAULT_EEVEE_SETTINGS
            if not orchestrator.run_blender_render(blend, render_dir, frame_limit=args.limit, eevee_settings=eevee_settings): sys.exit(1)

        
        if not orchestrator.run_human_inference(render_dir, root_output / "inference"): sys.exit(1)

        orchestrator.run_stitch_videos(root_output)
    
        print(f"\n[SUCCESS] Full pipeline completed. Results in: {root_output}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
