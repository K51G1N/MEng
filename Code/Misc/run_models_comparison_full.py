import json
import numpy as np
import os
import torch
import time
import sys
from gpu_optimised import GPUCameraFEPSO

print("Loading Global Data...")

def load_cameras(cam_dir):
    proj_matrices = np.zeros((100, 3, 4))
    cam_centers = np.zeros((100, 3))
    for k in range(100):
        cam_idx = k + 1
        with open(os.path.join(cam_dir, f'set_1_camera_{cam_idx}_matrices.json'), 'r') as f:
            data = json.load(f)
            proj_matrices[k] = np.array(data['projection'])
            ext = np.array(data['extrinsic'])
            R = ext[:, :3]
            t = ext[:, 3]
            cam_centers[k] = -R.T @ t
    return cam_centers, proj_matrices

cams_xyz, proj_matrices = load_cameras(r"D:\six_render\epoch_1\render_output\set 1")

models = {
    'HRNet': r"D:\six_render\epoch_1\render_output\epoch_1_keypoints_hrnet.json",
    'ViTPose': r"D:\six_render\epoch_1\render_output\epoch_1_keypoints_vitpose.json",
    'Yolo26m': r"D:\six_render\epoch_1\render_output\epoch_1_keypoints_yolo.json"
}

subjects = [
    "S0_female_158cm_55kg_set 1",
    "S1_female_175cm_67kg_set 1",
    "S2_female_193cm_82kg_set 1",
    "S3_male_158cm_55kg_set 1",
    "S4_male_175cm_67kg_set 1",
    "S5_male_193cm_82kg_set 1"
]

YOLO_TO_SMPLX = {
    1: 'left_eye', 2: 'right_eye', 5: 'left_shoulder', 6: 'right_shoulder',
    7: 'left_elbow', 8: 'right_elbow', 9: 'left_wrist', 10: 'right_wrist',
    11: 'left_hip', 12: 'right_hip', 13: 'left_knee', 14: 'right_knee',
    15: 'left_ankle', 16: 'right_ankle'
}
COCO_INDICES = list(YOLO_TO_SMPLX.keys())
SMPL_NAMES = list(YOLO_TO_SMPLX.values())
JOINTS = len(COCO_INDICES)
N_CAMS = 100

def get_limb_visibility(confs, subset_0idx):
    # confs shape: (F, J, N_CAMS)
    # subset_0idx: list of camera indices
    
    # Slice the confs tensor to only the cameras in the subset
    confs_sub = confs[:, :, subset_0idx] # (F, J, K)
    
    # A joint is visible in a camera if conf >= 0.20
    is_visible = (confs_sub >= 0.20) # (F, J, K)
    
    # A joint can be triangulated if it's visible in >= 2 cameras
    cams_seen = is_visible.sum(axis=2) # (F, J)
    can_triangulate = (cams_seen >= 2) # (F, J)
    
    # Count how many frames each joint was successfully triangulated
    frames_successful = can_triangulate.sum(axis=0) # (J,)
    
    # Average raw confidence across the selected subset
    avg_conf_per_joint = confs_sub.mean(axis=(0, 2)) # (J,)
    
    # Average max confidence (how well the *best* camera saw it)
    max_conf_per_joint = confs_sub.max(axis=2).mean(axis=0) # (J,)
    
    total_frames = confs.shape[0]
    
    visibility_dict = {}
    for j_idx, name in enumerate(SMPL_NAMES):
        success = int(frames_successful[j_idx])
        visibility_dict[name] = {
            'successful_frames': success,
            'total_frames': total_frames,
            'success_rate_pct': round((success / total_frames) * 100, 2),
            'avg_raw_confidence': round(float(avg_conf_per_joint[j_idx]), 4),
            'avg_max_confidence': round(float(max_conf_per_joint[j_idx]), 4)
        }
        
    # Also get total triangulation failures
    total_failures = int((~can_triangulate).sum())
    visibility_dict['TOTAL_FAILURES'] = total_failures
    
    return visibility_dict

def parse_model_data(json_path):
    with open(json_path, "r") as f:
        inf_data = json.load(f)
        
    all_gt = []
    all_coords = []
    all_confs = []
    
    for subject in subjects:
        # NOTE: HRNet ground truths use smplhf naming for eyes!
        with open(rf"D:\six_render\{subject.split('_set')[0]}_ground_truth.json", "r") as f:
            gt_data = json.load(f)
            
        frames = list(inf_data.keys())
        frames.sort(key=int)
        
        valid_keys = []
        for f_key in frames:
            if f_key in gt_data and subject in inf_data[f_key]:
                valid_keys.append(f_key)
                
        if not valid_keys: continue
        
        gt_3d = np.zeros((len(valid_keys), JOINTS, 3))
        coords = np.zeros((len(valid_keys), JOINTS, N_CAMS, 2))
        confs = np.zeros((len(valid_keys), JOINTS, N_CAMS))
        
        for f_idx, f_key in enumerate(valid_keys):
            for j_idx, smpl_name in enumerate(SMPL_NAMES):
                # Map standard names to ground truth names
                gt_name = smpl_name
                if smpl_name == 'left_eye': gt_name = 'left_eye_smplhf'
                if smpl_name == 'right_eye': gt_name = 'right_eye_smplhf'
                
                if gt_name in gt_data[f_key]: 
                    gt_3d[f_idx, j_idx] = gt_data[f_key][gt_name]
                    
            seq = inf_data[f_key][subject]
            for k in range(N_CAMS):
                cam_key = f"set_1_camera_{k+1}"
                if cam_key in seq:
                    for j_idx, coco_idx in enumerate(COCO_INDICES):
                        if str(coco_idx) in seq[cam_key]:
                            u, v, c = seq[cam_key][str(coco_idx)]
                            coords[f_idx, j_idx, k] = [u, v]
                            confs[f_idx, j_idx, k] = min(max(c, 0.0), 1.0)
                            
        all_gt.append(gt_3d)
        all_coords.append(coords)
        all_confs.append(confs)
        
    gt = np.concatenate(all_gt, axis=0)
    coords = np.concatenate(all_coords, axis=0)
    confs = np.concatenate(all_confs, axis=0)
    return gt, coords, confs

results = {}

def save_progress():
    with open(r"D:\six_render\models_comparison_full_results.json", "w") as f:
        json.dump(results, f, indent=4)

for model_name, path in models.items():
    print(f"\n==============================================")
    print(f"Loading data for {model_name}...")
    gt, coords, confs = parse_model_data(path)
    
    results[model_name] = {}
    
    for K in range(2, 11):
        # Adaptive MCR: 1000 loops for small K, 50 loops for massive K (redundant search space)
        if K <= 6:
            current_mcr = 1000
        else:
            current_mcr = 50
            
        print(f"\n--- Running {model_name} | K={K} (MCR={current_mcr}) ---")
        opt = GPUCameraFEPSO(
            camera_centers=cams_xyz,
            camera_projections=proj_matrices,
            ground_truth_3d=gt,
            yolo_2d_coords=coords,
            yolo_confidences=confs,
            K=K,
            n_particles=30,
            max_iter=30,
            cache_dir=f'./cache_full_{model_name.lower()}'
        )
        
        best_fit = float('inf')
        best_subset = None
        mcr_winners = []
        
        t0 = time.time()
        for m in range(current_mcr):
            # Suppress internal prints
            with open(os.devnull, 'w') as devnull:
                old_stdout = sys.stdout
                sys.stdout = devnull
                try:
                    pos, fit, _ = opt.optimize()
                finally:
                    sys.stdout = old_stdout
                    
            if fit < best_fit:
                best_fit = fit
                best_subset = pos.copy()
                
            # Save the winning set of THIS specific MCR loop
            loop_cams = tuple(sorted([int(x) + 1 for x in pos]))
            mcr_winners.append({
                "loop": m + 1,
                "subset": loop_cams,
                "fitness": float(fit)
            })
                
            # Print occasionally to avoid spamming log
            if (m+1) % 50 == 0 or (m+1) == current_mcr:
                print(f"[{model_name} K={K}] MCR Loop {m+1}/{current_mcr} | Best Fit So Far: {best_fit:.4f}")
                
        t1 = time.time()
        
        cams = tuple(sorted([int(x) + 1 for x in best_subset]))
        cams_0idx = [int(x) for x in best_subset]
        
        # Evaluate to get raw error
        _, best_mpjpe, best_sdpe, _ = opt._batch_evaluate_subset(cams_0idx)
        best_mpjpe = float(best_mpjpe)
        best_sdpe = float(best_sdpe)
        
        # Compute exact limb visibility and triangulation failures
        limb_vis = get_limb_visibility(confs, cams_0idx)
        
        print(f"[{model_name} K={K}] Best Subset: {cams}")
        print(f"[{model_name} K={K}] MPJPE: {best_mpjpe*1000:.1f} mm | SDPE: {best_sdpe*1000:.1f} mm | Fitness: {best_fit:.4f}")
        print(f"[{model_name} K={K}] Total Triangulation Failures: {limb_vis['TOTAL_FAILURES']}")
        print(f"[{model_name} K={K}] Optimization took {t1-t0:.1f}s")
        
        results[model_name][K] = {
            'subset': cams,
            'fitness': float(best_fit),
            'mpjpe_mm': float(best_mpjpe * 1000),
            'sdpe_mm': float(best_sdpe * 1000),
            'limb_visibility': limb_vis,
            'mcr_winners': mcr_winners
        }
        
        # AUTO-SAVE AFTER EVERY K TO PROTECT AGAINST POWER FAILURES
        save_progress()
        print(f"-> Auto-saved progress for K={K}!")

print("\nALL MODELS FINISHED! Results fully saved to models_comparison_full_results.json!")
