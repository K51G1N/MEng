import cv2
import torch
from ultralytics import YOLO
from pathlib import Path

def process_video(input_path_str, output_path_str, model, compute_device):
    cap = cv2.VideoCapture(input_path_str)

    if not cap.isOpened():
        print(f"Error: Could not open video at {input_path_str}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path_str, fourcc, fps, (frame_width, frame_height))

    print(f"Processing {Path(input_path_str).name}... Press 'q' to skip to the next video.")

    while True:
        success, frame = cap.read()
        if not success:
            break

        # Explicitly tell YOLO to use the device we verified (GPU 0)
        results = model(frame, verbose=False, device=compute_device)

        # Draw ONLY the keypoints and skeleton lines, NO bounding boxes
        annotated_frame = results[0].plot(boxes=False)

        out.write(annotated_frame)
        
        # Display the video while processing
        cv2.imshow("YOLOv8 Pose Processing", annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Video interrupted by user. Moving to next...")
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"Saved to {output_path_str}\n")


if __name__ == "__main__":
    # --- HARDWARE CHECK ---
    # Verify that PyTorch can actually see your RTX 3090
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"SUCCESS: CUDA detected! Using GPU: {gpu_name}")
        # '0' tells YOLO to use the first CUDA GPU it finds
        target_device = 0 
    else:
        print("\nWARNING: CUDA is NOT available! PyTorch cannot see your GPU.")
        print("Falling back to CPU. Processing will be very slow.")
        print("You likely need to reinstall PyTorch with CUDA support.\n")
        target_device = 'cpu'

    print("Loading YOLO model...")
    pose_model = YOLO('yolov26n-pose.pt')

    # Base directory for the 6 renders
    base_dir = r"C:\Users\20716400\Documents\BlenderProjects\Renders_six"
    
    # Generates paths for C0_output.mp4 through C5_output.mp4
    video_paths = [Path(base_dir) / f"C{i}_output.mp4" for i in range(6)]

    for input_path in video_paths:
        if not input_path.exists():
            print(f"File not found, skipping: {input_path}")
            continue
            
        # Replace '_output' with '_infered'
        output_name = input_path.name.replace("_output", "_infered")
        output_path = input_path.parent / output_name
        
        # Pass the verified target_device into the function
        process_video(str(input_path), str(output_path), pose_model, target_device)
        
    print("All inference complete!")