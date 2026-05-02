"""
SUMediPose Ingestion Module: JSON to C3D Conversion

This module serves as the first stage of the data processing pipeline. It is responsible 
for taking raw 3D keypoint data (extracted from the SUMediPose dataset in JSON format) 
and converting it into the industry-standard C3D format.

Why C3D?
The SOMA labeler and MoSh++ solver are built to work with C3D files, which store 3D 
point data alongside rich metadata (marker labels, frame rates, etc.).

Key Transformations:
The most critical part of this script is the coordinate system alignment. Raw 
SUMediPose data uses a Vicon World Coordinate System (WCS) that is rotated 
relative to the expected SMPL-X/SOMA space. This script 'rectifies' that 
alignment so the markers appear correctly oriented for the solver.
"""

import json
import numpy as np
import ezc3d
import os
import glob
import shutil

# ==========================================
#        CONFIGURATION (FALLBACKS)
# ==========================================
# These defaults are used if the script is run without a processing_paths.json
ROOT_FOLDER = "SUMediPose_WCS"
OUTPUT_ROOT_FOLDER = "SUMediPose_WCS_c3d"
TEMPLATE_FILE = "/home/keagan/Documents/meng/soma/test_data/MoSh_results/c3d/50002/jumping_jacks.c3d"

def apply_x_rotation_plus_90(points_data):
    """
    Aligns SUMediPose Vicon markers with the SMPL-X/SOMA coordinate system.
    
    The Problem:
    In the raw SUMediPose JSONs, the characters appear to be lying on face 
    or oriented incorrectly relative to the 'Ground' expected by SOMA.
    
    The Solution:
    We apply a +90 degree rotation around the X-axis and mirror the X-axis. 
    This 'stands the character up' and ensures Left/Right orientation is correct.
    
    Mathematical Mapping:
      - The new X is the negative of the old X (Mirroring).
      - The new Y (Forward) is the negative of the old Z (Up).
      - The new Z (Up) is the old Y (Forward).
    
    Args:
        points_data (np.ndarray): A 4xNxT array where 4 represents (X, Y, Z, Residual), 
                                  N is the number of markers, and T is the number of frames.
    
    Returns:
        np.ndarray: The transformed coordinate data.
    """
    rotated_data = points_data.copy()
    
    # Extract original channels for clear mapping
    old_x = points_data[0, :, :]
    old_y = points_data[1, :, :]
    old_z = points_data[2, :, :]
    
    # Apply the mapping logic defined above
    rotated_data[0, :, :] = -old_x     # Mirror X
    rotated_data[1, :, :] = -old_z     # Map Y to -Z
    rotated_data[2, :, :] = old_y      # Map Z to Y
            
    return rotated_data

def convert_json_to_c3d(json_file, template_path, output_path):
    """
    Converts a single SUMediPose JSON file into a structured C3D file.
    
    The process involves:
    1. Parsing the JSON to extract marker labels and XYZ coordinates.
    2. Loading a 'Template' C3D to inherit the standard C3D parameter structure.
    3. Cleaning the template and injecting new metadata (labels, frame counts).
    4. Structuring the point data into the 4xNxT format required by ezc3d.
    5. Applying the +90 degree X-rotation/mirroring.
    6. Writing the final file to disk.
    
    Args:
        json_file (str): Path to input JSON.
        template_path (str): Path to template C3D.
        output_path (str): Path for output C3D.

    Returns:
        None
    """
    print(f"Processing {json_file}")
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"❌ Read Error {os.path.basename(json_file)}: {e}")
        return

    if not json_data: return

    # 1. Extract Metadata from JSON
    # We assume the first frame contains the 'point_ids' (marker labels)
    try:
        marker_labels = json_data[0].get('point_ids', [])
    except (KeyError, IndexError) as e:
        print(f"❌ Error processing {os.path.basename(json_file)}. Incorrect format: {e}")
        return
    n_markers = len(marker_labels)
    n_frames = len(json_data)

    # 2. Load and Prepare the C3D Template
    # ezc3d works best when modifying an existing header structure rather than 
    # building one from scratch.
    c3d = ezc3d.c3d(template_path)
    
    # Remove 'meta_points' if they exist in the template to avoid conflicts
    if 'meta_points' in c3d['data']:
        del c3d['data']['meta_points']

    # 3. Inject New Metadata
    # We update the 'POINT' parameters to match our specific JSON data.
    c3d['parameters']['POINT']['LABELS']['value'] = marker_labels
    c3d['parameters']['POINT']['USED']['value'] = [n_markers]
    c3d['parameters']['POINT']['FRAMES']['value'] = [n_frames]
    c3d['parameters']['ANALOG']['USED']['value'] = [0] # We don't use analog data (EMG, etc.)
    c3d['data']['analogs'] = np.zeros((1, 0, n_frames))

    # 4. Process Point Data
    # C3D stores points as (X, Y, Z, Residual). 
    # Residual 0.0 means the point is valid; -1.0 usually indicates a missing marker.
    points_data = np.zeros((4, n_markers, n_frames))

    for i, frame in enumerate(json_data):
        xyz = frame.get('xyz', [])
        
        # Data Cleaning: Ensure we have exactly n_markers for every frame
        if len(xyz) != n_markers:
            if len(xyz) < n_markers:
                # Pad missing markers with NaNs
                xyz.extend([[np.nan, np.nan, np.nan]] * (n_markers - len(xyz)))
            else:
                # Trim extra markers if they exceed the header count
                xyz = xyz[:n_markers]
        
        coords = np.array(xyz).T # Transpose to get 3xN
        
        # Mask valid vs invalid (NaN) points
        valid_mask = ~np.isnan(coords).any(axis=0)
        points_data[0:3, valid_mask, i] = coords[:, valid_mask]
        points_data[3, valid_mask, i] = 0.0      # Valid marker
        points_data[3, ~valid_mask, i] = -1.0    # Missing marker (Residual -1)

    # 5. Coordinate Alignment
    # Apply the X+90 rotation to fix the character's orientation.
    points_data = apply_x_rotation_plus_90(points_data)

    # 6. Finalize and Save
    c3d['data']['points'] = points_data
    c3d['header']['points']['first_frame'] = 0
    c3d['header']['points']['last_frame'] = n_frames - 1 
    
    c3d.write(output_path)
    print(f"✅ Saved: {os.path.basename(output_path)}")

def path_processing(sumedi_json_folder_path, mosh_c3d_template, constructed_c3d_path):
    """
    Scans the dataset directory and processes every subject found.
    
    This function handles the folder hierarchy:
    - Iterates through subject folders (e.g., S1, S2...).
    - Creates corresponding output folders in the target directory.
    - Finds all JSON files and converts them.
    - Copies 'settings.json' (which contains subject-specific gender) for later use.
    
    Args:
        sumedi_json_folder_path (str): Path to raw JSON data.
        mosh_c3d_template (str): Path to the C3D template.
        constructed_c3d_path (str): Root path for the converted C3D results.

    Returns:
        None
    """
    if not os.path.exists(constructed_c3d_path):
        os.makedirs(constructed_c3d_path)

    # Find all top-level subject directories
    subject_folders = [f.path for f in os.scandir(sumedi_json_folder_path) if f.is_dir()]

    for subject_folder in subject_folders:
        subject_name = os.path.basename(subject_folder)
        output_subject_folder = os.path.join(constructed_c3d_path, subject_name)
        
        if not os.path.exists(output_subject_folder):
            os.makedirs(output_subject_folder)
            
        # Case-insensitive glob for JSON files
        json_files = glob.glob(os.path.join(subject_folder, "*.[jJ][sS][oO][nN]"))
        print(f"--- STARTING BATCH CONVERSION FOR {subject_name}: {len(json_files)} FILES ---")

        for f in json_files:
            name = os.path.splitext(os.path.basename(f))[0]
            out = os.path.join(output_subject_folder, name + ".c3d")
            convert_json_to_c3d(f, mosh_c3d_template, out)
            
        # Carry forward the settings.json file. This is vital because Stage 3 (Solving) 
        # needs to know the subject's gender to initialize the SMPL-X model correctly.
        settings_file = os.path.join(subject_folder, 'settings.json')
        if os.path.exists(settings_file):
            shutil.copy(settings_file, output_subject_folder)
            print(f"✅ Copied settings.json for {subject_name}")

if __name__ == "__main__":
    # Standard entry point logic. It attempts to load paths from processing_paths.json
    # but provides fallbacks to ensure the script is robust.
    try:
        with open("processing_paths.json", 'r') as f:
            paths = json.load(f)
        
        # Absolute path resolution from the JSON config
        sumedi_json_folder_path = os.path.abspath(paths['sumedi_json_wcs_path'])
        mosh_c3d_template = os.path.abspath(paths['mosh_c3d_template'])
        base_directory = os.path.abspath(paths['base_directory'])
        constructed_c3d_path = paths['constructed_c3d_path']
        
        if not os.path.isabs(constructed_c3d_path):
            constructed_c3d_path = os.path.join(base_directory, constructed_c3d_path)
        constructed_c3d_path = os.path.abspath(constructed_c3d_path)

        path_processing(sumedi_json_folder_path, mosh_c3d_template, constructed_c3d_path)
    except Exception as e:
        print(f"⚠️ Falling back to defaults as configuration failed: {e}")
        if not os.path.exists(OUTPUT_ROOT_FOLDER):
            os.makedirs(OUTPUT_ROOT_FOLDER)
        path_processing(ROOT_FOLDER, TEMPLATE_FILE, OUTPUT_ROOT_FOLDER)

    print("--- INGESTION COMPLETE ---")
