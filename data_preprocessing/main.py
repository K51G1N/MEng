"""
SUMediPose Data Pipeline Orchestrator

This script serves as the central entry point for the SUMediPose animation data pipeline.
It coordinates the flow of data through four distinct stages:
1. Ingestion: Converts raw SUMediPose JSON to C3D format.
2. Labeling (Priming): Uses SOMA to conform marker IDs.
3. Solving: Uses MoSh++ to solve for body shape and motion.
4. Rectification: Converts results to Blender-compatible NPZ files.

The pipeline is configured via 'processing_paths.json', allowing for flexible
path management without modifying the core logic.
"""

import json
import os
import convert_json_to_c3d
import batch_prime
import batch_solve_multi
import batch_convert_npz_rectified

def run_pipeline():
    """
    Orchestrates the end-to-end data processing pipeline.
    
    This function performs the following steps:
    - Loads configuration from 'processing_paths.json'.
    - Resolves relative paths against the provided 'base_directory'.
    - Executes the four stages of the pipeline sequentially (Ingestion, Labeling, Solving, Rectification).

    Args:
        None

    Returns:
        None
    """
    # --- STAGE 0: Configuration and Path Resolution ---
    try:
        with open("processing_paths.json", 'r') as f:
            paths = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ Error loading processing_paths.json: {e}")
        print("Please ensure the file exists and contains valid JSON.")
        return

    # Extract core paths from configuration
    sumedi_json_folder_path = os.path.abspath(paths['sumedi_json_wcs_path'])
    mosh_c3d_template = os.path.abspath(paths['mosh_c3d_template'])
    base_directory = os.path.abspath(paths['base_directory'])
    
    # Path Utility: Resolve relative paths against the base_directory
    def resolve_path(key, default=None):
        val = paths.get(key, default)
        if val and not os.path.isabs(val):
            return os.path.abspath(os.path.join(base_directory, val))
        return os.path.abspath(val) if val else None

    # Resolve necessary directory paths
    constructed_c3d_path = resolve_path('constructed_c3d_path')
    primed_c3d_path = resolve_path('primed_c3d_path')
    soma_base = os.path.abspath(paths['soma_support_base'])
    npz_animations_path = os.path.abspath(paths['npz_animations_path'])
    output_root_dir = os.path.abspath(paths.get('output_root_dir', '/media/keagan/Crucial/sumedi_results'))
    markerset_yaml = paths.get('markerset_yaml', 'superset')

    print(f"Data Ingestion complete. Paths loaded successfully.")
    print(f"Base Directory: {base_directory}")
    
    # --- STAGE 1: Ingestion (JSON to C3D) ---
    # Converts raw Vicon JSON keypoints into the industry-standard C3D format.
    print("Starting JSON to C3D conversion...")
    convert_json_to_c3d.path_processing(sumedi_json_folder_path, mosh_c3d_template, constructed_c3d_path)
    
    # --- STAGE 2: Labeling (SOMA Priming) ---
    # Runs the SOMA 'SuperSet' labeler to ensure marker IDs are consistent for the solver.
    print("JSON to C3D conversion complete. Starting batch priming...")
    batch_prime.prime(constructed_c3d_path, primed_c3d_path, soma_base, base_directory)
    
    # --- STAGE 3: Solving (MoSh++) ---
    # Uses MoSh++ to solve for SMPL-X body parameters (shape and pose) from markers.
    # Note: SOMA expects the 'support_files' subdirectory within the soma_base.
    print("SOMA label_priming complete. Starting batch solving...")
    soma_support_files = os.path.join(soma_base, 'support_files')
    batch_solve_multi.multi_solve(primed_c3d_path, output_root_dir, soma_support_files, markerset_yaml)
    
    # --- STAGE 4: Rectification (PKL to NPZ) ---
    # Converts solver results (.pkl) into Blender-compatible AMASS-style .npz files.
    # We pass the solve_root (where .pkl files were saved) to the converter.
    print("Batch solving complete. Starting animation processing...")
    solve_root = os.path.join(output_root_dir, os.path.basename(primed_c3d_path))
    batch_convert_npz_rectified.batch_convert_rectified(npz_animations_path, solve_root, primed_c3d_path)
    
    print("Pipeline complete! All steps executed successfully.")

if __name__ == "__main__":
    run_pipeline()
