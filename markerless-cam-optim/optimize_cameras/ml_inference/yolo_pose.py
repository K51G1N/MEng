import cv2
import time
import numpy as np
from ultralytics import YOLO
from OneEuroFilter import OneEuroFilter

class Human:
    """
    Manages the state and filtering for a single person detected in the frame.
    """
    def __init__(self, track_id):
        self.id = track_id
        # Create a list of 17 dictionaries (one per COCO keypoint).
        # Each dictionary contains an independent X and Y filter.
        # freq=30: Should match your processing/camera FPS.
        # min_cutoff: Lower values decrease jitter but increase lag.
        # beta: Higher values decrease lag during fast movement.
        self.filters = [
            {
                'x': OneEuroFilter(freq=30, mincutoff=1.0, beta=0.01, dcutoff=1.0),
                'y': OneEuroFilter(freq=30, mincutoff=1.0, beta=0.01, dcutoff=1.0)
            } 
            for _ in range(17)
        ]

    def apply_filter(self, keypoints_2d, confidences):
        """
        Updates filter states with new raw coordinates and returns cleaned values.
        """
        filtered_coords = []
        
        for i, (coords, conf) in enumerate(zip(keypoints_2d, confidences)):
            x, y = coords
            
            # Only update the filter if the point is actually detected.
            # Updating with (0,0) or low-confidence noise would ruin the filter state.
            if conf > 0.1 and not (x == 0 and y == 0): 
                clean_x = self.filters[i]['x'](x)
                clean_y = self.filters[i]['y'](y)
                filtered_coords.append([clean_x, clean_y])
            else:
                # If invisible, keep the raw coords (likely 0,0) without updating filter memory.
                filtered_coords.append([x, y])
                
        return np.array(filtered_coords)

def run_pose_estimation():
    # Initialize YOLO model on the GPU
    model = YOLO('yolov8n-pose.pt')
    model.to('cuda')

    # Initialize webcam capture
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # Dictionary to store Human instances using their unique Track IDs as keys
    active_humans = {}

    print("Tracking active... Press 'q' to exit.")

    while True:
        start_loop_time = time.time()
        success, frame = cap.read()
        if not success:
            break

        # model.track() is used instead of model() to maintain ID persistence.
        # persist=True ensures IDs remain consistent across frames.
        results = model.track(frame, persist=True, device=0, stream=True, conf=0.5)

        # Clone the frame for drawing the filtered visualization
        annotated_frame = frame.copy()

        for r in results:
            # Skip logic if no boxes/IDs are found in the current frame
            if r.boxes is None or r.boxes.id is None:
                # Plot raw detection if tracking isn't locked yet
                annotated_frame = r.plot()
                continue

            # Extract IDs, 2D coordinates, and confidence scores
            track_ids = r.boxes.id.int().cpu().tolist()
            keypoints_data = r.keypoints.xy.cpu().numpy()  # (N_people, 17, 2)
            confidences = r.keypoints.conf.cpu().numpy()    # (N_people, 17)

            for i, track_id in enumerate(track_ids):
                # Instantiate a new Human container if this ID is seen for the first time
                if track_id not in active_humans:
                    active_humans[track_id] = Human(track_id)
                
                # Pass raw detection data into the Human's filters
                raw_kp = keypoints_data[i]
                conf = confidences[i]
                clean_kp = active_humans[track_id].apply_filter(raw_kp, conf)

                # Visualization: Draw filtered circles and index labels
                for j, (x, y) in enumerate(clean_kp):
                    if conf[j] > 0.5:  # Only draw high-confidence joints
                        cv2.circle(annotated_frame, (int(x), int(y)), 4, (0, 255, 0), -1)
                        cv2.putText(annotated_frame, str(j), (int(x), int(y)-5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Calculate and display current performance
        fps = 1 / (time.time() - start_loop_time)
        cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Filtered YOLO Pose Tracking", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Clean up resources
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_pose_estimation()