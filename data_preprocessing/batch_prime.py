"""
SUMediPose Labeling: SOMA Batch Priming

This script automates the process of labeling C3D marker points using the SOMA "SuperSet" model.
It is a mandatory pre-processing step before solving for body shape/motion, ensuring
that marker IDs are conformed and consistent.
"""

from omegaconf import OmegaConf
import os
import os.path as osp
import shutil
from soma.tools.run_soma_multiple import run_soma_on_multiple_settings

# ==========================================
# 1. PATH CONFIGURATION
# ==========================================
def resolve_mocap_subject(path):
    """
    OmegaConf resolver to automatically extract the subject name (e.g., 'S1')
    from the directory structure of the input file.

    Args:
        path (str): The file path to the C3D file.

    Returns:
        str: The name of the subject folder (e.g., 'S1').
    """
    # Get the parent folder name
    return os.path.basename(os.path.dirname(path))

def prime(constructed_c3d_path, primed_c3d_path, soma_support_dir, base_directory):
    """
    Orchestrates the SOMA labeling process:
    - Sets up SOMA resolvers and environment paths.
    - Executes SOMA 'SuperSet' labeling on the converted C3D files.
    - Collects labeled results from SOMA's evaluation folders.
    - Copies subject-level 'settings.json' (gender) for down-stream tasks.

    Args:
        constructed_c3d_path (str): Path to the converted, unlabeled C3D files.
        primed_c3d_path (str): Path where the SOMA-labeled C3D files will be saved.
        soma_support_dir (str): Path to the SOMA support base directory.
        base_directory (str): The base directory for relative path resolution.

    Returns:
        None
    """
    if not OmegaConf.has_resolver("resolve_mocap_subject"):
        OmegaConf.register_new_resolver("resolve_mocap_subject", resolve_mocap_subject, replace=True)
        print("✅ Custom resolver 'resolve_mocap_subject' registered successfully.")

    # The root of your SOMA installation (where 'support_files' is located)
    soma_work_base_dir = soma_support_dir

    # The folder explicitly containing the support data (models, etc.)
    support_base_dir = soma_work_base_dir 

    # TARGET DATA SETUP
    mocap_base_dir = base_directory
    # Ensure target_dataset_name is relative to mocap_base_dir for SOMA's internal categorization
    target_dataset_name = osp.relpath(constructed_c3d_path, mocap_base_dir)
    c3d_prime_output_path = primed_c3d_path

    # Ensure output base directory exists
    if not osp.exists(c3d_prime_output_path):
        os.makedirs(c3d_prime_output_path, exist_ok=True)
        print(f"📁 Created directory: {c3d_prime_output_path}")

    # ==========================================
    # 2. RUN SOMA (LABEL PRIMING)
    # ==========================================
    # Runs the actual SuperSet labeling. This uses a pre-trained model to map
    # the generic marker names (from Vicon) to the standardized SOMA marker IDs.
    print(f"🚀 Starting SOMA processing for dataset: {target_dataset_name}...")
    run_soma_on_multiple_settings(
        # Use the pre-trained "SuperSet" labeler model
        soma_expr_ids=['V48_02_SuperSet'], 
        
        # Use the specific training ID associated with SuperSet
        soma_data_ids=['OC_05_G_03_real_000_synt_100'],
        
        # Point to your dataset folder name
        soma_mocap_target_ds_names=[target_dataset_name],
        
        soma_cfg={
            'soma.batch_size': 256,
            'dirs.support_base_dir': support_base_dir,
            
            # Override output paths to go to the prime directory
            'dirs.work_dir': c3d_prime_output_path,
            'dirs.mocap_out_fname': osp.join(c3d_prime_output_path, '${mocap.subject_name}', '${mocap.basename}.pkl'),
            'dirs.log_fname': osp.join(c3d_prime_output_path, '${mocap.subject_name}', '${mocap.basename}.log'),

            # IMPORTANT: Match this to your C3D file units. 
            'mocap.unit': 'mm', 

            'save_c3d': True,               # Save the labeled output
            'keep_nan_points': True,        # Keep missing markers as NaNs
            'remove_zero_trajectories': True
        },
        
        parallel_cfg={
            'max_num_jobs': 10000, # Large number to process everything
            'randomly_run_jobs': False,
        },
        
        run_tasks=['soma'],
        
        mocap_base_dir=mocap_base_dir,
        soma_work_base_dir=soma_work_base_dir,
        mocap_ext='.c3d'
    )

    # ==========================================
    # 3. COLLECT RESULTS
    # ==========================================
    # SOMA saves .c3d files deep in its evaluation folder (training_experiments/.../evaluations/...). 
    # To make the data easy for the solver to find, we traverse and pull these .c3d files
    # back into a subject-organized folder structure (S1, S2, etc.).
    soma_expr_id = 'V48_02_SuperSet'
    soma_data_id = 'OC_05_G_03_real_000_synt_100'
    soma_eval_dir = osp.join(c3d_prime_output_path, 'training_experiments', soma_expr_id, soma_data_id, 
                             'evaluations', 'soma_labeled_mocap_tracklet', target_dataset_name)
    
    if osp.exists(soma_eval_dir):
        print(f"📦 Collecting SOMA results from {soma_eval_dir}...")
        for root, dirs, files in os.walk(soma_eval_dir):
            for file in files:
                if file.endswith('.c3d'):
                    rel_dir = osp.relpath(root, soma_eval_dir)
                    dest_dir = osp.join(c3d_prime_output_path, rel_dir)
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(osp.join(root, file), osp.join(dest_dir, file))
        print("✅ Results collected successfully.")

    # ==========================================
    # 4. COPY SETTINGS.JSON
    # ==========================================
    # The solver (MoSh++) needs to know the gender of each subject.
    # We copy 'settings.json' into the prime folders so the solver can find it.
    print("📂 Copying settings.json to output directories...")
    s_folders = [d for d in os.listdir(osp.join(mocap_base_dir, target_dataset_name)) if d.startswith('S')]

    for s_folder in s_folders:
        src_dir = osp.join(mocap_base_dir, target_dataset_name, s_folder)
        dst_dir = osp.join(c3d_prime_output_path, s_folder)
        
        # Path for settings.json in source and destination
        src_settings_path = osp.join(src_dir, 'settings.json')
        dst_settings_path = osp.join(dst_dir, 'settings.json')
        
        # Ensure destination directory exists (it should have been created by SOMA, but just in case)
        if not osp.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        if osp.exists(src_settings_path):
            shutil.copy2(src_settings_path, dst_settings_path)
            # print(f"✅ Copied {s_folder}/settings.json")
        else:
            print(f"⚠️ Warning: {s_folder}/settings.json not found.")

    print("✨ All done!")
