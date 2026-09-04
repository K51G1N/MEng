import subprocess
import threading
from subprocess import Popen
import os
import json
from ultralytics import YOLO
import cv2 as cv
from glob import glob
import numpy as np
from scipy import linalg
from pathlib import Path

def calculate_mpjpe(epoch_3d_data, ground_truth_data, mapping):
    mpjpe_scores = []
    mpjpe_frame = []
    number_of_keypoints = 17-3
    number_of_frames = len(epoch_3d_data)
    
    set_counts = {}
    set_errors = {}
    for frame_id, frame_data in epoch_3d_data.items():
        for set_name, keypoints in frame_data.items():
            if set_name not in set_errors:
                set_errors[set_name] = 0.0
                set_counts[set_name] = 0
            kp_error = None
            for keypoint_id, infered_kp in keypoints.items():
                gt_kp_name = mapping.get(str(keypoint_id))
                
                if not gt_kp_name or gt_kp_name not in ground_truth_data.get(frame_id, {}):
                    continue
                
                infered_kp_pos = np.array(infered_kp)
                gt_pos = np.array(ground_truth_data[frame_id][gt_kp_name])
                
                dist = np.linalg.norm(infered_kp_pos - gt_pos)
                set_errors[set_name] += dist
                set_counts[set_name] += 1
                
    mpjpe_scores = {}
    for set_name in set_errors:
        if set_counts[set_name] > 0:
            mpjpe_scores[set_name] = set_errors[set_name] / set_counts[set_name]
        else:
            mpjpe_scores[set_name] = 9999999
    
    return mpjpe_scores
    
                    
    
def keypoint_mapping(model) -> dict:
    YOLO_map = {
    "0": None, 
    "1": "left_eye_smplhf",
    "2": "right_eye_smplhf",
    "3": None,
    "4": None,
    "5": "left_shoulder",
    "6": "right_shoulder",
    "7": "left_elbow",
    "8": "right_elbow",
    "9": "left_wrist",
    "10":"right_wrist",
    "11":"left_hip",
    "12":"right_hip",
    "13":"left_knee",
    "14":"right_knee",
    "15": "left_ankle",
    "16": "right_ankle",
    }
    return YOLO_map
        
    
    return mapping
def get_projection_matrices(epoch_render_dir, completed_set_name) -> dict:
    set_directory = epoch_render_dir / completed_set_name 
    projection_matrices = {}
    for file_path in set_directory.glob("*.json"):
        with open(file_path, 'r') as file:
            matrix_data = json.load(file)
            file_name = file_path.name
            
            camera_name = file_name.replace("_matrices.json", "")
            projection_matrices[camera_name] = matrix_data['projection']
    return projection_matrices

def DLT(set_data, completed_set_name, epoch_render_dir) -> list:
    projection_matrices = get_projection_matrices(epoch_render_dir, completed_set_name)
    number_of_keypoints = 0
    print(f"RENDER DIR: {epoch_render_dir}")
    for camera_name in set_data:
        number_of_keypoints = len(set_data[camera_name]) #We know this number to be 17 because of the Yolo 0,...,16        
    wcs_keypoints = {}            
    for keypoint in range(0, number_of_keypoints):
        corresponding_keypoints = []
        A = []
        for index, camera_name in enumerate(set_data):
            a_single_keypoint = set_data[camera_name].get(keypoint) or set_data[camera_name].get(str(keypoint))
            if a_single_keypoint:
                u = a_single_keypoint[0]
                v = a_single_keypoint[1]
                respective_projection_matrix = np.array(projection_matrices[camera_name])
                
                row_1 = u * respective_projection_matrix[2,:] - respective_projection_matrix[0,:]
                row_2 = v * respective_projection_matrix[2,:] - respective_projection_matrix[1,:]
                A.append(row_1)
                A.append(row_2)
        A = np.array(A)
        
        if A.ndim < 2:
            print(f"CRASH AVERTED: Missing data in Set: {completed_set_name}, Keypoint: {keypoint}")
            wcs_keypoints[keypoint] = None
            continue 
        
        U, S, Vh = linalg.svd(A, full_matrices = False) #Vh is the hermitian and also known as V transpose
        points_4D_homogenous =  Vh[-1, :]
        
        cartesian_3D_point = points_4D_homogenous[:3] / points_4D_homogenous[3]
        wcs_keypoints[keypoint] = cartesian_3D_point.tolist()
    return wcs_keypoints    

    

def extract_metadata_from_path(path_string: str) -> tuple:
    # Example: /path/to/project/Epoch_1/render_output/set 1/set_1_camera_1/532.png
    p = Path(path_string)
    frame_number_string = p.stem
    camera_name = p.parent.name
    set_name = p.parent.parent.name
    
    return set_name, camera_name, frame_number_string

def get_inference_path(path_string: str) -> str:
    p = Path(path_string)
    
    inference_directory = p.parent.with_name(f"{p.parent.name}_inference")
    
    return str(inference_directory / p.name)
    
def inference(model, input_path) -> list:
    
    if not os.path.exists(input_path):
        print(f"Warning: File not found for inference -> {input_path}")
        return []
    
    # path = "/path/to/project/render_output/set 2/set_2_camera_1/532.png"
    results = model(input_path)
    
    output_path = get_inference_path(input_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    frame_keypoints = {}
    
    for result in results:
        annotated_image = result.plot()
        # cv.imwrite(output_path, annotated_image)
        if result.keypoints is not None and len(result.keypoints) > 0:
            points_list = result.keypoints.data[0].cpu().numpy().tolist()
            for index, keypoint in enumerate(points_list):
                frame_keypoints[index] = keypoint
            
    return frame_keypoints
    
def write_points_to_json_file(json_save_path: str, epoch_points_registery):
    with open(json_save_path, 'w') as file:
        json.dump(epoch_points_registery, file, indent=4)
        
        
def read_json_file(config_file):
    with open(config_file, 'r') as file:
        data = json.load(file)
    return data
        
def launch_blender(blend_file_path, script_path, cameras_path, output_path, blend_save , blender_exe, epoch):
    # blender_exe = r"C:\Program Files\Blender Foundation\Blender 5.1\blender-launcher.exe"

    command = [
        blender_exe,
        "-b",
        blend_file_path,
        "--python",
        script_path,
        "--",
        cameras_path,
        output_path,
        blend_save,
        epoch
    ]

    process = Popen(
        command,
        stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT,
        text = True,
        encoding = "utf-8",
        errors = 'replace'
    )
    
    return process
    
def monitor_process(process, model: YOLO, epoch_render_dir) -> tuple:
    keypoints_registry = {}
    points_3d_registry = {}
    current_frame = None
    
    for line in process.stdout:
        line = line.strip()
        print(f"Blender: {line}")
        
        if "Saved: '" in line:
            try:
                path_string = line.split("Saved: '")[1].rstrip("'")
                set_name, camera_name, current_frame = extract_metadata_from_path(path_string)
        
                keypoints = inference(model, path_string)
                
                if current_frame not in keypoints_registry:
                    keypoints_registry[current_frame] = {}
                if set_name not in keypoints_registry[current_frame]:
                    keypoints_registry[current_frame][set_name] = {}
                
                keypoints_registry[current_frame][set_name][camera_name] = keypoints
                
            except IndexError:
                print(f"failed to parse line: {line}")
            except Exception as e:
                print(f"CRITICAL ERROR during inference for {line}: {e}")
                
        elif "Set done: " in line:
            try:
                completed_data = line.split(",")
                completed_set_name = completed_data[0].split("Set done: ")[1].strip() 
                completed_frame = completed_data[1].split("Frame: ")[1].strip()
            
                if completed_frame in keypoints_registry:
                    set_data = keypoints_registry[completed_frame].get(completed_set_name)
                    
                    if set_data:
                        
                        points_3d = DLT(set_data, completed_set_name, epoch_render_dir)

                        if completed_frame not in points_3d_registry:
                            points_3d_registry[completed_frame] = {}
                        points_3d_registry[completed_frame][completed_set_name] = points_3d
  
                            
            except Exception as e:
                print(f"Critical Error triggering DLT: {e}")        

    return keypoints_registry, points_3d_registry      

def main():
    config_file = "configuration.json"
    paths = read_json_file(config_file)
    
    base_dir = Path(paths["base_dir"])
    
    blend_file_path = base_dir / paths["blend_file_path"]
    script_path = base_dir / paths["script_path"]
    blend_save = base_dir / paths["blend_save"]
    blender_exe = Path(paths["blender_exe"])
    ground_truth = base_dir / paths["ground_truth"]
    base_render_dir = Path(paths["base_dir"])
    base_camera_dir = Path(paths["base_dir"])
    
    yolo_model_path = paths.get("yolo_model", "yolo26x-pose.pt")
    model = YOLO(yolo_model_path)
    mapping = keypoint_mapping("YOLO")
    ground_truth_data = read_json_file(ground_truth)
    for epoch in range(1, 2):
        
        epoch_prefix = f"epoch_{epoch}"
        epoch_render_dir = base_dir / epoch_prefix / "render_output"
        epoch_cameras_path = base_dir / f"{epoch_prefix}_cameras.json"
        
        epoch_render_dir.mkdir(parents=True, exist_ok=True)
        
        process = launch_blender(
            str(blend_file_path),
            str(script_path),
            str(epoch_cameras_path),
            str(epoch_render_dir),
            str(blend_save),
            str(blender_exe),
            str(epoch)
        )
        
        epoch_keypoints_registery, epoch_3d_data = monitor_process(process, model, epoch_render_dir)
        
        json_2D_save_path = epoch_render_dir/ f"{epoch_prefix}_keypoints_dataset.json"
        json_3D_save_path = epoch_render_dir/ f"{epoch_prefix}_3D_points.json"
        
        
        # write_points_to_json_file(json_2D_save_path, epoch_keypoints_registery)
        # write_points_to_json_file(json_3D_save_path, epoch_3d_data)
        
        json_mpjpe_save_path = epoch_render_dir / f"{epoch_prefix}_set_mpjpes.json"
        mpjpe_scores = calculate_mpjpe(epoch_3d_data, ground_truth_data, mapping)
        
        # write_points_to_json_file(json_mpjpe_save_path, mpjpe_scores)
        
        
        print(f"Epoch {epoch} complete. 2D Keypoints saved to: {json_2D_save_path} and 3D Keypoints saved to {json_3D_save_path}")
        
    #DO MPJPE
    # inference()
     #Do make camera suggestions // Differential evolution 
if __name__ == "__main__":
    main()