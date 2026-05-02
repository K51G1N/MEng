import cv2
import torch
from ultralytics import YOLO

def process_single_video(input_path, output_path, model, compute_device):
    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        print(f"Error: Could not open video at {input_path}")
        return

    # Keep original dimensions for the saved video
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

    print(f"Processing {input_path}...")
    print("Press 'q' to stop early.")

    # --- THE WINDOW FIX ---
    # Create a window that allows resizing, then force it to a reasonable viewing size.
    # This prevents the window from overflowing your screen, but keeps the saved video full-res.
    window_name = "YOLOv8 Pose with Bounding Boxes"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720) 

    while True:
        success, frame = cap.read()
        if not success:
            break

        results = model(frame, verbose=False, device=compute_device)

        # --- THE BOUNDING BOX FIX ---
        # Calling .plot() with no arguments defaults to showing EVERYTHING: 
        # the skeleton, the bounding boxes, the class label, and the confidence score.
        annotated_frame = results[0].plot()

        # Write the full-resolution frame to the file
        out.write(annotated_frame)
        
        # Display it in our scaled-down window
        cv2.imshow(window_name, annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Video interrupted by user.")
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"Done! Saved to {output_path}")


if __name__ == "__main__":
    # Ensure CUDA is still doing the heavy lifting
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"SUCCESS: CUDA detected! Using GPU: {gpu_name}")
        target_device = 0 
    else:
        print("WARNING: CUDA is NOT available! Falling back to CPU.")
        target_device = 'cpu'

    print("Loading YOLO model...")
    pose_model = YOLO('yolov8n-pose.pt')

    # Target just the C0 video
    input_video = r"C:\Users\20716400\Documents\BlenderProjects\Renders_six\C0_output.mp4"
    
    # Saving it with a slightly different name so you don't overwrite your skeleton-only version
    output_video = r"C:\Users\20716400\Documents\BlenderProjects\Renders_six\C0_infered_boxes.mp4"
    
    process_single_video(input_video, output_video, pose_model, target_device)