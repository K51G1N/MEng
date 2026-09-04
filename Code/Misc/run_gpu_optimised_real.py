import json
import numpy as np
import os
from gpu_optimised import GPUCameraFEPSO

# 1. Map 14 COCO joints (including eyes) to SMPL-X
YOLO_TO_SMPLX = {
    1: "left_eye_smplhf",
    2: "right_eye_smplhf",
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

COCO_INDICES = list(YOLO_TO_SMPLX.keys())
SMPL_NAMES = list(YOLO_TO_SMPLX.values())
JOINTS = len(COCO_INDICES)
N_CAMS = 100

def load_data(gt_path, seq_name, cam_centers, proj_matrices, inf_data):
    # Load GT
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
        
    frames_inf = list(inf_data.keys())
    frames_inf.sort(key=int)
    frames_gt = list(gt_data.keys())
    
    # We match inference frames with GT frames
    valid_frames = [f for f in frames_inf if f in frames_gt and seq_name in inf_data[f]]
    valid_frames.sort(key=int)
    
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
                        # Clip confidences to [0, 1] to prevent overflow (some are anomalously huge)
                        if c > 1.0:
                            c = 1.0
                        elif c < 0.0:
                            c = 0.0
                        coords_2d[f_idx, j_idx, k] = [u, v]
                        confs_2d[f_idx, j_idx, k] = c
                        
    return gt_3d, coords_2d, confs_2d

import argparse

def load_cameras_and_inference(cam_dir, keypoints_json):
    proj_matrices = np.zeros((N_CAMS, 3, 4))
    cam_centers = np.zeros((N_CAMS, 3))
    
    for k in range(N_CAMS):
        cam_idx = k + 1
        with open(os.path.join(cam_dir, f"set_1_camera_{cam_idx}_matrices.json"), "r") as f:
            data = json.load(f)
            proj_matrices[k] = np.array(data["projection"])
            ext = np.array(data["extrinsic"])
            R = ext[:, :3]
            t = ext[:, 3]
            cam_centers[k] = -R.T @ t
            
    with open(keypoints_json, "r") as f:
        inf_data = json.load(f)
        
    return cam_centers, proj_matrices, inf_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU Optimised Real")
    parser.add_argument("--data_dir", type=str, default=r"D:\six_render", help="Base directory for data")
    parser.add_argument("--cam_dir", type=str, default=r"D:\six_render\epoch_1\render_output\set 1", help="Directory containing camera matrices")
    parser.add_argument("--keypoints_json", type=str, default=r"D:\six_render\epoch_1\render_output\epoch_1_keypoints_dataset.json", help="Path to keypoints dataset JSON")
    args = parser.parse_args()

    print("Loading global camera and inference data...")
    cams_xyz, proj_matrices, inf_data = load_cameras_and_inference(args.cam_dir, args.keypoints_json)
    
    subjects = [
        (os.path.join(args.data_dir, "S0_female_158cm_55kg_ground_truth.json"), "S0_female_158cm_55kg_set 1"),
        (os.path.join(args.data_dir, "S1_female_175cm_67kg_ground_truth.json"), "S1_female_175cm_67kg_set 1"),
        (os.path.join(args.data_dir, "S2_female_193cm_82kg_ground_truth.json"), "S2_female_193cm_82kg_set 1"),
        (os.path.join(args.data_dir, "S3_male_158cm_55kg_ground_truth.json"), "S3_male_158cm_55kg_set 1"),
        (os.path.join(args.data_dir, "S4_male_175cm_67kg_ground_truth.json"), "S4_male_175cm_67kg_set 1"),
        (os.path.join(args.data_dir, "S5_male_193cm_82kg_ground_truth.json"), "S5_male_193cm_82kg_set 1")
    ]
    
    # You can change K_SELECT to explore different subset sizes (e.g. 6 or 8)
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
    
    K_SELECT = 3
    import time
    from collections import Counter
    
    print(f"\n==========================================================")
    print(f"Evaluating K={K_SELECT} with 1 loop (2000 Iterations Unit Test)")
    print(f"==========================================================")
    
    optimizer = GPUCameraFEPSO(
        camera_centers=cams_xyz,
        camera_projections=proj_matrices,
        ground_truth_3d=global_gt,
        yolo_2d_coords=global_coords,
        yolo_confidences=global_confs,
        K=K_SELECT,
        n_particles=100,
        max_iter=2000,
        conf_thresh=0.20,
        alpha_sdpe=0.10,
        cache_dir=f"./cache_fepso_real_k{K_SELECT}"
    )
    
    start_time = time.time()
    results = []
    fitnesses = []
    
    print(f"\n--- Starting optimization run ---")
    for i in range(1):
        best_cameras, best_score, score_history = optimizer.optimize(verbose=False)
        subset_tuple = tuple(sorted([int(c)+1 for c in best_cameras]))
        results.append(subset_tuple)
        fitnesses.append(best_score)
        
        if (i + 1) % 100 == 0:
            print(f"Completed {i+1}/1000 runs...")
            
    total_time = time.time() - start_time
    
    print(f"\n==========================================================")
    print(f"1000 Runs Optimization Complete in {total_time:.2f} seconds.")
    
    avg_fitness = np.mean(fitnesses)
    best_overall_score = np.min(fitnesses)
    worst_overall = np.max(fitnesses)
    
    print(f"\nFitness Statistics over 1000 runs:")
    print(f"Average Fitness: {avg_fitness:.4f}")
    print(f"Best Fitness:    {best_overall_score:.4f}")
    print(f"Worst Fitness:   {worst_overall:.4f}")
    
    counter = Counter(results)
    print(f"\nMost Frequent Subsets (Top 5):")
    for subset, count in counter.most_common(5):
        print(f"Subset {subset}: {count} times ({(count/1000)*100:.1f}%)")
        
    best_subset_1_indexed = counter.most_common(1)[0][0]
    best_subset_0_indexed = [c - 1 for c in best_subset_1_indexed]
    
    print(f"\n==========================================================")
    print(f"Joint Contribution Analysis for Best Subset: {best_subset_1_indexed}")
    print(f"==========================================================")
    
    for idx_in_subset, cam_idx in enumerate(best_subset_0_indexed):
        print(f"\nCamera {cam_idx + 1} Contribution Profile:")
        cam_confs = global_confs[:, :, cam_idx]
        
        for j_idx, joint_name in enumerate(SMPL_NAMES):
            joint_conf = cam_confs[:, j_idx]
            avg_conf = np.mean(joint_conf)
            visibility_pct = np.mean(joint_conf >= 0.20) * 100
            
            bar_len = int(avg_conf * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print(f"  {joint_name.rjust(16)}: |{bar}| {avg_conf:.3f} avg conf ({visibility_pct:5.1f}% visible)")
