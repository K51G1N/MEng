import os
import json
import argparse
from pathlib import Path
from ultralytics import YOLO

def extract_metadata_from_path(path_string: str) -> tuple:
    p = Path(path_string)
    frame_number_string = p.stem
    camera_name = p.parent.name
    set_name = p.parent.parent.name
    return set_name, camera_name, frame_number_string

import cv2
import threading
from queue import Queue
import concurrent.futures

def get_bboxes_from_yolo(yolo_detector, batch_inputs):
    """Run the yolo26x bounding box detector on a batch of images and extract bounding boxes."""
    results = yolo_detector(batch_inputs, verbose=False)
    batch_bboxes = []
    
    for r in results:
        if len(r.boxes) > 0:
            box = r.boxes.xyxy[0].cpu().numpy().tolist()
            batch_bboxes.append([box]) 
        else:
            batch_bboxes.append([])
            
    return batch_bboxes

def read_single_image(path_str):
    return cv2.imread(path_str)

def prefetch_images(paths, batch_size, queue, cpu_cores):
    """Background thread to read and decode JPEGs into memory across 8 CPU cores so the GPU never waits."""
    # Use 8 threads to decode JPEGs in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_cores) as executor:
        for i in range(0, len(paths), batch_size):
            batch_paths = [str(p) for p in paths[i:i+batch_size]]
            
            # Map the read function across the 8-core thread pool
            batch_images = list(executor.map(read_single_image, batch_paths))
            
            # Block if the queue is full (keeps memory usage strictly capped)
            queue.put((batch_paths, batch_images))
    queue.put(None)

def load_existing_progress(json_save_path):
    if json_save_path.exists():
        print(f"Loading existing progress from {json_save_path}...")
        with open(json_save_path, 'r') as file:
            return json.load(file)
    return {}

def filter_unprocessed_images(jpg_files, keypoints_registry):
    unprocessed_files = []
    for p in jpg_files:
        set_name, camera_name, current_frame = extract_metadata_from_path(str(p))
        if current_frame in keypoints_registry and \
           set_name in keypoints_registry[current_frame] and \
           camera_name in keypoints_registry[current_frame][set_name]:
            continue
        unprocessed_files.append(p)
    return unprocessed_files

# ... Skipping run_mmpose_inference and run_yolo_inference unchanged ...

def run_both_mmpose_inference(total_files, jpg_files, render_output, cpu_cores, device):
    try:
        from mmpose.apis import MMPoseInferencer
    except ImportError:
        print("MMPose is not installed! Please run this in the mmpose_gpu conda environment.")
        return

    det_model = YOLO(r"C:\Users\20716400\Documents\MEng\good\yolo26x-pose.pt")
    det_model.to(device)
    
    print("Downloading and initializing HRNet and ViTPose simultaneously...")
    hrnet_inferencer = MMPoseInferencer(\"td-hm_hrnet-w32_8xb64-210e_coco-256x192\", device=device)
    vitpose_inferencer = MMPoseInferencer(\"td-hm_ViTPose-base-simple_8xb64-210e_coco-256x192\", device=device)

    hrnet_save_path = render_output / "epoch_1_keypoints_hrnet.json"
    vitpose_save_path = render_output / "epoch_1_keypoints_vitpose.json"
    bboxes_save_path = render_output / "epoch_1_bboxes.json"
    
    hrnet_registry = load_existing_progress(hrnet_save_path)
    vitpose_registry = load_existing_progress(vitpose_save_path)
    bboxes_registry = load_existing_progress(bboxes_save_path)
    
    unprocessed_files = filter_unprocessed_images(jpg_files, hrnet_registry)
    total_unprocessed = len(unprocessed_files)
    print(f"Found {total_files} total images. {total_unprocessed} remaining to process for both models.")
    
    if total_unprocessed == 0:
        print("All images processed!")
        return

    batch_size = 64
    
    # Start the asynchronous prefetching background thread
    print("Starting asynchronous JPEG decoding dataloader...")
    image_queue = Queue(maxsize=3)
    fetch_thread = threading.Thread(target=prefetch_images, args=(unprocessed_files, batch_size, image_queue, cpu_cores))
    fetch_thread.start()
    
    for i in range(0, total_unprocessed, batch_size):
        # Fetch decoded arrays from RAM instantly (0 disk latency)
        item = image_queue.get()
        if item is None:
            break
        batch_paths, batch_images = item
        
        # 1. Run YOLO bounding boxes ONLY ONCE
        batch_bboxes = get_bboxes_from_yolo(det_model, batch_images)
        
        # 2. Run HRNet
        hrnet_generator = hrnet_inferencer(batch_images, bboxes=batch_bboxes, batch_size=batch_size, show=False)
        # 3. Run ViTPose
        vitpose_generator = vitpose_inferencer(batch_images, bboxes=batch_bboxes, batch_size=batch_size, show=False)
        
        for path_string, bboxes, hrnet_res, vitpose_res in zip(batch_paths, batch_bboxes, hrnet_generator, vitpose_generator):
            set_name, camera_name, current_frame = extract_metadata_from_path(path_string)
            
            # Extract HRNet keypoints
            hr_frame_keypoints = {}
            if 'predictions' in hrnet_res and len(hrnet_res['predictions'][0]) > 0:
                kpts = hrnet_res['predictions'][0][0]['keypoints']
                scores = hrnet_res['predictions'][0][0]['keypoint_scores']
                for index, (kpt, score) in enumerate(zip(kpts, scores)):
                    hr_frame_keypoints[index] = [kpt[0], kpt[1], score]

            # Extract ViTPose keypoints
            vit_frame_keypoints = {}
            if 'predictions' in vitpose_res and len(vitpose_res['predictions'][0]) > 0:
                kpts = vitpose_res['predictions'][0][0]['keypoints']
                scores = vitpose_res['predictions'][0][0]['keypoint_scores']
                for index, (kpt, score) in enumerate(zip(kpts, scores)):
                    vit_frame_keypoints[index] = [kpt[0], kpt[1], score]

            if current_frame not in hrnet_registry:
                hrnet_registry[current_frame] = {}
            if current_frame not in vitpose_registry:
                vitpose_registry[current_frame] = {}
            if current_frame not in bboxes_registry:
                bboxes_registry[current_frame] = {}
                
            if set_name not in hrnet_registry[current_frame]:
                hrnet_registry[current_frame][set_name] = {}
            if set_name not in vitpose_registry[current_frame]:
                vitpose_registry[current_frame][set_name] = {}
            if set_name not in bboxes_registry[current_frame]:
                bboxes_registry[current_frame][set_name] = {}
                
            hrnet_registry[current_frame][set_name][camera_name] = hr_frame_keypoints
            vitpose_registry[current_frame][set_name][camera_name] = vit_frame_keypoints
            
            # Save the YOLO26x bounding box for permanent storage
            bboxes_registry[current_frame][set_name][camera_name] = bboxes[0] if len(bboxes) > 0 else []
            
        print(f"Processed {min(i+batch_size, total_unprocessed)} / {total_unprocessed} remaining images using both models.")

        if (i // batch_size) % 50 == 0:
            with open(hrnet_save_path, 'w') as file:
                json.dump(hrnet_registry, file, indent=4)
            with open(vitpose_save_path, 'w') as file:
                json.dump(vitpose_registry, file, indent=4)
            with open(bboxes_save_path, 'w') as file:
                json.dump(bboxes_registry, file, indent=4)

    # Clean up the background thread
    fetch_thread.join()

    with open(hrnet_save_path, 'w') as file:
        json.dump(hrnet_registry, file, indent=4)
    with open(vitpose_save_path, 'w') as file:
        json.dump(vitpose_registry, file, indent=4)
    with open(bboxes_save_path, 'w') as file:
        json.dump(bboxes_registry, file, indent=4)
    print("Saved final results for both models and bounding boxes.")

def main():
    parser = argparse.ArgumentParser(description="Multi-model batch inference script")
    parser.add_argument("--model", type=str, choices=["hrnet", "vitpose", "yolo", "both"], required=True, 
                        help="Choose which model to run: hrnet, vitpose, yolo, or both")
    parser.add_argument("--yolo-weights", type=str, default="yolo26m-pose.pt", 
                        help="Path to the yolo weights (only used if --model yolo)")
    parser.add_argument("--cpu-cores", type=int, default=os.cpu_count() or 8, 
                        help="Number of CPU cores for background JPEG decoding (default: all available)")
    import torch
    default_device = "cuda:0" if torch.cuda.is_available() else "cpu"
    parser.add_argument("--device", type=str, default=default_device,
                        help=f"Device to run inference on (default: {default_device})")
    
    args = parser.parse_args()

    render_output = Path(r"d:\six_render\epoch_1\render_output")
    jpg_files = list(render_output.rglob("*.jpg"))
    total_files = len(jpg_files)
    
    if args.model in ['hrnet', 'vitpose']:
        run_mmpose_inference(args.model, total_files, jpg_files, render_output)
    elif args.model == 'both':
        run_both_mmpose_inference(total_files, jpg_files, render_output, args.cpu_cores, args.device)
    elif args.model == 'yolo':
        run_yolo_inference(args.yolo_weights, total_files, jpg_files, render_output)

if __name__ == "__main__":
    main()
