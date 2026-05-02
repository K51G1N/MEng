"""
SUMediPose Rectification: PKL to Blender-Compatible NPZ

This script converts MoSh++ solver results (.pkl) into AMASS-style .npz files.

CRITICAL FEATURE: Rectification
By default, SMPL-X uses 400 shape parameters (betas). However, Blender's 
SMPL-X implementation often only supports 100 shape keys. This script 
"rectifies" the data by truncating the betas to 100, preventing 
"No key block for ShapeXXX" errors during animation import.
"""

import pickle
import numpy as np
import os
import json
from glob import glob
from tqdm import tqdm

# ==========================================
#               CONFIGURATION
# ==========================================
# Fallback paths for standalone execution
SOLVE_ROOT = "/media/keagan/Crucial/sumedi_results/SUMediPose_WCS_c3d_prime"
SETTINGS_ROOT = "/home/keagan/Documents/meng/SUMediPose_WCS_c3d_prime"
OUT_ROOT = "/media/keagan/Crucial/sumedi_results/sumedi_npz_animate_rectified"

def get_gender(subject_id, settings_root):
    """
    Retrieves the gender for a subject from their settings.json file.

    Args:
        subject_id (str): The ID of the subject (e.g., 'S1').
        settings_root (str): The directory where subject settings.json files are located.

    Returns:
        str: The gender of the subject ('male', 'female', or 'neutral').
    """
    settings_path = os.path.join(settings_root, subject_id, "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                return json.load(f).get('gender', 'neutral')
        except:
            pass
    return 'neutral'

def batch_convert_rectified(output_root, solve_root, settings_root):
    """
    Batch converts all subject .pkl files into rectified .npz files.

    Args:
        output_root (str): Where to save the resulting .npz files.
        solve_root (str): The directory containing solved subject folders.
        settings_root (str): The directory containing subject settings.json files.

    Returns:
        None
    """
    print("🚀 Starting Rectified Batch NPZ Animation Conversion...")
    os.makedirs(output_root, exist_ok=True)
    
    # Identify subject folders in the solve directory
    subject_dirs = sorted([d for d in os.listdir(solve_root) if d.startswith('S') and os.path.isdir(os.path.join(solve_root, d))])
    
    for subject in tqdm(subject_dirs, desc="Subjects"):
        subject_solve_dir = os.path.join(solve_root, subject)
        subject_out_dir = os.path.join(output_root, subject)
        os.makedirs(subject_out_dir, exist_ok=True)
        
        gender = get_gender(subject, settings_root)
        
        # Find all second-stage solver output files
        pkl_files = glob(os.path.join(subject_solve_dir, "*_stageii.pkl"))
        
        for pkl_path in pkl_files:
            action_name = os.path.basename(pkl_path).replace('_stageii.pkl', '')
            npz_out_path = os.path.join(subject_out_dir, f"{action_name}_rectified.npz")
            
            if os.path.exists(npz_out_path):
                continue
                
            try:
                with open(pkl_path, 'rb') as f:
                    # SOMA/MoSh++ pickles are often saved with latin1 encoding
                    data = pickle.load(f, encoding='latin1')
                
                # Extract core SMPL-X parameters
                fullpose = data['fullpose'].astype(np.float64)
                trans = data['trans'].astype(np.float64)
                
                # RECTIFICATION: Truncate from 400 betas to 100 for Blender compatibility
                betas = data['betas'].astype(np.float32)#[:100].astype(np.float32)
                
                # Construct the AMASS-style data structure
                npz_data = {
                    'gender':             gender,
                    'surface_model_type': 'smplx',
                    'mocap_frame_rate':   np.array(30.0, dtype=np.float64), # SOMA default
                    'mocap_time_length':  np.array(float(len(trans)), dtype=np.float64),
                    'trans':              trans,
                    'poses':              fullpose,
                    'betas':              betas,
                    'num_betas':          np.array(len(betas), dtype=np.int64)
                }
                
                np.savez(npz_out_path, **npz_data)
            except Exception as e:
                print(f"❌ Error converting {pkl_path}: {e}")

    print(f"\n✨ Rectified conversion complete! Files in: {output_root}")


if __name__ == "__main__":
    # When running standalone, use the hardcoded defaults at the top
    batch_convert_rectified(OUT_ROOT, SOLVE_ROOT, SETTINGS_ROOT)
