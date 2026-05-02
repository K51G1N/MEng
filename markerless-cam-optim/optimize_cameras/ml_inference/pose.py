import json 
import torch
from ultralytics import YOLO
import cv2
from pathlib import Path

def run_pose_inference(input_dir, output_dir, device: str = None):
    input_dir = input_dir.resolve()
    if output_dir is None:
        output_dir = input_dir.parent / "inference"
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[+] Initializing Human Inference Phase...")
    print(f"    Input:  {input_dir}")
    print(f"    Output: {output_dir}")

    # Load Model
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"    Using device: {device}")


    model_name = "yolo26n-pose.pt"
    model_path = Path(__file__).resolve().parent / model_name
    
    model = YOLO(str(model_path) if model_path.exists() else model_name)
    model.to(device)

    # Find Camera Subdirectories (C0, C1, etc.)
    cam_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir() and d.name.startswith('C')])
    
    if not cam_dirs:
        print(f"[!] No camera directories found in {input_dir}")
        return False

    for cam_dir in cam_dirs:
        cam_id = cam_dir.name
        print(f"\n[+] Processing Camera: {cam_id}")
        
        # Setup specific output for this camera
        cam_inference_dir = output_dir / f"{cam_id}_inference"
        cam_inference_dir.mkdir(parents=True, exist_ok=True)
        
        image_files = sorted([f for f in cam_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg"]])
        
        if not image_files:
            print(f"    [!] No images found in {cam_dir}")
            continue

        camera_keypoints = []

        print(f"    [+] Processing {len(image_files)} images...")
        for i, img_path in enumerate(image_files, 1):
            if i % 50 == 0 or i == 1 or i == len(image_files):
                print(f"        [{i}/{len(image_files)}] {img_path.name}")
                
            results = model(str(img_path), verbose=False, device=device)
            
            # Keypoint Extraction
            kps_list = []
            if len(results[0].keypoints.data) > 0:
                kps = results[0].keypoints.data[0].cpu().numpy().tolist()
                kps_list = kps
            else:
                kps_list = [[0, 0, 0]] * 17

            camera_keypoints.append({
                "frame": img_path.stem,
                "keypoints": kps_list
            })

            # Save annotated image
            save_path = cam_inference_dir / img_path.name
            if not save_path.exists():
                annotated_frame = results[0].plot()
                cv2.imwrite(str(save_path), annotated_frame)

        # Save JSON for this camera inside its inference folder
        json_file = cam_inference_dir / f"{cam_id}.json"
        with open(json_file, 'w') as f:
            json.dump(camera_keypoints, f, indent=4)
        print(f"    [SUCCESS] {cam_id}.json saved to {cam_inference_dir}")

    print(f"\n[+] Full inference and data extraction completed.\n")
    return True
