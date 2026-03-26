"""
SUMediPose Solving: Multi-Subject MoSh++ Solver

This script runs the MoSh++ solver to extract SMPL-X body shape and motion 
parameters from labeled C3D markers. It is parallelized to process 
multiple subjects simultaneously for maximum efficiency.
"""

import os
import os.path as osp
from glob import glob
from loguru import logger
import json
from concurrent.futures import ProcessPoolExecutor
from soma.amass.mosh_manual import mosh_manual
from functools import partial

# ==========================================
#               USER SETTINGS
# ==========================================

# PARALLELISM SETTINGS
# To avoid overloading the CPU, we solve 4 subjects at once, 
# each utilizing 4 cores for internal operations.
MAX_SUBJECTS_AT_ONCE = 4  
CORES_PER_SUBJECT = 4     

# ==========================================
#               WORKER FUNCTION
# ==========================================
def solve_subject(subject_id, mocap_base_dir, output_root_dir, soma_support_dir, markerset_yaml):
    """
    Worker function to solve all actions for a single subject.
    
    This function:
    1. Identifies all .c3d files for the subject.
    2. Checks which files have already been solved to avoid redundant work.
    3. Reads the subject's gender from 'settings.json'.
    4. Executes the MoSh++ solver.

    Args:
        subject_id (str): The ID of the subject (e.g., 'S1').
        mocap_base_dir (str): Base directory containing labeled C3D files.
        output_root_dir (str): Root directory for solver results.
        soma_support_dir (str): Directory containing SOMA support files.
        markerset_yaml (str): Marker layout to use for MoSh++.

    Returns:
        str: Status message indicating success or skip reason.
    """
    subject_dir = osp.join(mocap_base_dir, subject_id)
    mocap_fnames = sorted(glob(osp.join(subject_dir, "*.c3d")))
    dataset_name = os.path.basename(mocap_base_dir)
    if not mocap_fnames:
        return f"Skipped {subject_id}: No data."

    # Filter for files that haven't been solved yet
    to_solve = []
    for f in mocap_fnames:
        rel_path = osp.relpath(f, osp.dirname(mocap_base_dir))
        base_name = osp.splitext(rel_path)[0]
        out_pkl = osp.join(output_root_dir, base_name + "_stageii.pkl")
        if not osp.exists(out_pkl):
            to_solve.append(f)

    if not to_solve:
        return f"Skipped {subject_id}: Already complete."

    # Initialize gender - default to neutral if settings.json is missing
    gender = 'neutral'
    settings_path = osp.join(subject_dir, 'settings.json')
    if osp.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                gender = json.load(f).get('gender', 'neutral')
        except: pass

    logger.info(f"🧵 Starting Subject {subject_id} ({len(to_solve)} actions) | Gender: {gender}")
    current_dataset_name = osp.basename(mocap_base_dir)
    try:
        mosh_manual(
            to_solve, 
            mosh_cfg={
                'mocap.dataset_name': current_dataset_name,
                'moshpp.verbosity': 1, 
                'moshpp.fall_back_gender': gender,
                'moshpp.marker_layout': markerset_yaml,
                'moshpp.stagei_frame_picker.least_avail_markers': 0.80, 
                'moshpp.stagei_frame_picker.num_frames': 12, 
                'moshpp.stagei_frame_picker.stagei_mocap_fnames': mocap_fnames,
                'moshpp.mocap.multi_subject': False, 
                'dirs.work_base_dir': output_root_dir,
                'dirs.support_base_dir': soma_support_dir,
                # Explicitly set the output filename to match our existence check structure
                'dirs.mosh_out_fname': osp.join(output_root_dir, '${mocap.dataset_name}', '${mocap.subject_name}', '${mocap.basename}_stageii.pkl'),
                'dirs.mocap_base_dir': osp.dirname(mocap_base_dir),
            },
            render_cfg={
                'dirs.work_base_dir': output_root_dir,
                'dirs.temp_base_dir': osp.join(output_root_dir, 'tmp', subject_id), 
                'dirs.support_base_dir': soma_support_dir,
            },
            parallel_cfg={
                'pool_size': CORES_PER_SUBJECT,
                'max_num_jobs': 1000, 
            },
            run_tasks=['mosh'], 
            fast_dev_run=False,
        )
        return f"✅ Subject {subject_id} Finished."
    except Exception as e:
        return f"❌ Subject {subject_id} Failed: {e}"

# ==========================================
#               MAIN EXECUTION
# ==========================================

def multi_solve(mocap_base_dir, output_root_dir, soma_support_dir, markerset_yaml):
    """
    Main entry point for multi-subject solving.
    Uses ProcessPoolExecutor to manage the subject-level parallelism.

    Args:
        mocap_base_dir (str): Path to the folder containing labeled subject C3D files.
        output_root_dir (str): Root directory where solve results will be stored.
        soma_support_dir (str): Path to SOMA's support_files directory.
        markerset_yaml (str): Marker layout to use for MoSh++.

    Returns:
        None
    """
    if not osp.exists(output_root_dir):
        os.makedirs(output_root_dir, exist_ok=True)

    # Find all subject folders (starting with 'S')
    subject_folders = sorted([d for d in os.listdir(mocap_base_dir) if d.startswith('S') and osp.isdir(osp.join(mocap_base_dir, d))])
    
    # Filter out completed subjects to avoid pool overhead
    remaining_subjects = []
    for subject in subject_folders:
        subject_dir = osp.join(mocap_base_dir, subject)
        mocap_fnames = glob(osp.join(subject_dir, "*.c3d"))
        needs_work = False
        for f in mocap_fnames:
            rel_path = osp.relpath(f, osp.dirname(mocap_base_dir))
            out_pkl = osp.join(output_root_dir, osp.splitext(rel_path)[0] + "_stageii.pkl")
            if not osp.exists(out_pkl):
                needs_work = True
                break
        if needs_work:
            remaining_subjects.append(subject)

    if not remaining_subjects:
        print("No subjects need processing.")
        return

    print(f"🚀 Launching Multi-Subject Solve for {len(remaining_subjects)} subjects.")
    print(f"🔥 Parallelism: {MAX_SUBJECTS_AT_ONCE} subjects x {CORES_PER_SUBJECT} cores = 16 cores active.")

    # Create a partial function to bundle static arguments
    # We do NOT pass subject_id here so it can be passed as a positional argument by executor.map
    solve_func = partial(solve_subject,
                         mocap_base_dir=mocap_base_dir, 
                         output_root_dir=output_root_dir, 
                         soma_support_dir=soma_support_dir,
                         markerset_yaml=markerset_yaml)
    # Distribute subjects across the process pool
    with ProcessPoolExecutor(max_workers=MAX_SUBJECTS_AT_ONCE) as executor:
        results = list(executor.map(solve_func, remaining_subjects))

    for res in results:
        print(res)


if __name__ == "__main__":
    mocap_base_dir = "/home/keagan/Documents/meng/SUMediPose_WCS_c3d_prime"
    output_root_dir = '/media/keagan/Crucial/sumedi_results'
    soma_support_dir = os.path.expanduser('~/Documents/meng/soma/support_base/support_files')
    markerset_yaml = 'superset'
    multi_solve(mocap_base_dir, output_root_dir, soma_support_dir, markerset_yaml)
