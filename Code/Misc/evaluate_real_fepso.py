import json
import numpy as np
import os
from optimisation_algorithm import CameraNetworkFEPSO
from optimised_fepso import VectorizedCameraFEPSO
# 1. Map COCO joints to SMPL
JOINT_MAP = {
    5: "left_shoulder",
    6: "right_shoulder",
    7: "left_elbow",
    8: "right_elbow",
    9: "left_wrist",
    10: "right_wrist",
    11: "left_hip",
    12: "right_hip",
    13: "left_knee",
    14: "right_knee",
    15: "left_ankle",
    16: "right_ankle"
}
COCO_INDICES = list(JOINT_MAP.keys())
SMPL_NAMES = list(JOINT_MAP.values())
JOINTS = len(COCO_INDICES)
N_CAMS = 100

def load_data(gt_path, seq_name, cam_centers, proj_matrices, inf_data):
    # Load GT
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
        
    frames_inf = list(inf_data.keys())
    frames_inf.sort(key=int)
    frames_gt = list(gt_data.keys())
    valid_frames = [f for f in frames_inf if f in frames_gt and seq_name in inf_data[f]]
    valid_frames.sort(key=int)
    
    # Load ALL frames
    FRAMES = len(valid_frames)
    if FRAMES == 0:
        return None, None, None
    
    gt_3d = np.zeros((FRAMES, JOINTS, 3))
    coords_2d = np.zeros((FRAMES, JOINTS, N_CAMS, 2))
    confs_2d = np.zeros((FRAMES, JOINTS, N_CAMS))
    
    for f_idx, f_key in enumerate(valid_frames):
        # GT
        for j_idx, smpl_name in enumerate(SMPL_NAMES):
            if smpl_name in gt_data[f_key]:
                gt_3d[f_idx, j_idx] = gt_data[f_key][smpl_name]
            
        # Inference
        seq_inf = inf_data[f_key][seq_name]
        for k in range(N_CAMS):
            cam_key = f"set_1_camera_{k+1}"
            cam_inf = seq_inf.get(cam_key)
            if cam_inf:
                for j_idx, coco_idx in enumerate(COCO_INDICES):
                    if str(coco_idx) in cam_inf:
                        u, v, c = cam_inf[str(coco_idx)]
                        coords_2d[f_idx, j_idx, k] = [u, v]
                        confs_2d[f_idx, j_idx, k] = c
    
    return gt_3d, coords_2d, confs_2d

def load_cameras_and_inference():
    proj_matrices = np.zeros((N_CAMS, 3, 4))
    cam_centers = np.zeros((N_CAMS, 3))
    
    cam_dir = r"D:\six_render\epoch_1\render_output\set 1"
    for k in range(N_CAMS):
        cam_idx = k + 1
        with open(os.path.join(cam_dir, f"set_1_camera_{cam_idx}_matrices.json"), "r") as f:
            data = json.load(f)
            proj_matrices[k] = np.array(data["projection"])
            ext = np.array(data["extrinsic"])
            R = ext[:, :3]
            t = ext[:, 3]
            cam_centers[k] = -R.T @ t
            
    with open(r"D:\six_render\epoch_1\render_output\epoch_1_keypoints_dataset.json", "r") as f:
        inf_data = json.load(f)
        
    return cam_centers, proj_matrices, inf_data

if __name__ == "__main__":

    
    print("Loading global camera and inference data...")
    cams_xyz, proj_matrices, inf_data = load_cameras_and_inference()
    
    subjects = [
        (r"D:\six_render\S0_female_158cm_55kg_ground_truth.json", "S0_female_158cm_55kg_set 1"),
        (r"D:\six_render\S1_female_175cm_67kg_ground_truth.json", "S1_female_175cm_67kg_set 1"),
        (r"D:\six_render\S2_female_193cm_82kg_ground_truth.json", "S2_female_193cm_82kg_set 1"),
        (r"D:\six_render\S3_male_158cm_55kg_ground_truth.json", "S3_male_158cm_55kg_set 1"),
        (r"D:\six_render\S4_male_175cm_67kg_ground_truth.json", "S4_male_175cm_67kg_set 1"),
        (r"D:\six_render\S5_male_193cm_82kg_ground_truth.json", "S5_male_193cm_82kg_set 1")
    ]
    
    K_SELECT = 3
    
    all_gt, all_coords, all_confs = [], [], []
    
    for gt_path, seq_name in subjects:
        print(f"Loading Subject: {seq_name}...")
        gt_3d, coords_2d, confs_2d = load_data(gt_path, seq_name, cams_xyz, proj_matrices, inf_data)
        if gt_3d is not None:
            all_gt.append(gt_3d)
            all_coords.append(coords_2d)
            all_confs.append(confs_2d)
            
    # Concatenate all sequences into one massive dataset
    global_gt = np.concatenate(all_gt, axis=0)
    global_coords = np.concatenate(all_coords, axis=0)
    global_confs = np.concatenate(all_confs, axis=0)
    
    print(f"\n==========================================================")
    print(f"Evaluating Global General Case")
    print(f"==========================================================")
    print(f"Loaded {global_gt.shape[0]} total frames across {len(subjects)} subjects.")
    
    optimizer = VectorizedCameraFEPSO(
        camera_centers=cams_xyz,
        camera_projections=proj_matrices,
        ground_truth_3d=global_gt,
        yolo_2d_coords=global_coords,
        yolo_confidences=global_confs,
        K=K_SELECT,
        n_particles=50,
        max_iter=15
    )
    
    best_cameras, best_score, score_history = optimizer.optimize()
    
    evaluator = CameraNetworkFEPSO(
        camera_centers=cams_xyz,
        camera_projections=proj_matrices,
        ground_truth_3d=global_gt,
        yolo_2d_coords=global_coords,
        yolo_confidences=global_confs,
        K=K_SELECT,
        precompute_static=True
    )
    pure_mpjpe, pck, valid_ratio = evaluator.evaluate_final(best_cameras, pck_threshold=50.0)
    
    print(f"\n--- Global Optimization Complete ---")
    print(f"Optimal Active Camera Subset (K={K_SELECT}): {[int(c)+1 for c in sorted(list(best_cameras))]}")
    print(f"Final Global Best Fitness (with penalties): {best_score*1000:.4f} mm")
    print(f"Global Pure MPJPE (valid joints only): {pure_mpjpe*1000:.4f} mm")
    print(f"Global PCK@50mm: {pck:.2f}% (Valid triangulable joints: {valid_ratio:.2f}%)")