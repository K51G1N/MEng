# SUMediPose Data Pipeline User Guide

This guide explains the end-to-end process of converting raw [SUMediPose](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/GRRROM) keypoint data into Blender-compatible SMPL-X animations.

---

## 1. Pipeline Overview

The pipeline consists of four main stages designed to move from raw Vicon keypoint JSONs to standardized animation files:

1.  **Ingestion:** `convert_json_to_c3d.py`
    - Converts raw JSON to C3D.
    - Applies a +90 degree X-rotation and X-mirroring to align the coordinate system with SMPL-X.
2.  **Labeling (Priming):** `batch_prime.py`
    - Uses SOMA's "SuperSet" model to conform marker labels to a standardized layout.
3.  **Solving:** `batch_solve_multi.py`
    - High-performance parallel solver using MoSh++ to extract body shape and motion from markers.
4.  **Rectification:** `batch_convert_npz_rectified.py`
    - Converts results to `.npz`.
    - **Crucial:** Truncates betas from 400 to 100 to ensure compatibility with Blender's SMPL-X add-on.

---

## 2. Configuration (`processing_paths.json`)

To run the pipeline on your local machine, you must populate `processing_paths.json`. This allows the code to run without modification regardless of your folder structure.

| Key | Description |
| :--- | :--- |
| `base_directory` | The root folder for your project files. |
| `sumedi_json_wcs_path` | Path to the raw SUMediPose `WCS` directory. |
| `mosh_c3d_template` | Path to a valid C3D file used as a metadata template. |
| `constructed_c3d_path` | Output directory for the initial C3D conversion. |
| `primed_c3d_path` | Output directory for the SOMA-labeled C3D files. |
| `soma_support_base` | The root folder of your SOMA installation. |
| `output_root_dir` | Where the final solver results (.pkl) will be stored. |
| `npz_animations_path` | The final destination for Blender-ready .npz files. |

---

## 3. Detailed Process Flow

### Step 1: Ingestion
Run via `main.py` or `convert_json_to_c3d.py`.
- **Input:** Raw JSON folders (S1, S2, etc.).
- **Operation:** Reads XYZ keypoints, applies the rotation matrix to "stand the character up," and saves as C3D.
- **Output:** Subject folders containing unlabeled `.c3d` files and `settings.json`.

### Step 2: Labeling (Priming)
Run via `main.py` or `batch_prime.py`.
- **Input:** Unlabeled C3D files.
- **Operation:** SOMA maps Vicon labels to standardized IDs. This is required because raw labels often drift or are inconsistent.
- **Output:** Labeled `.c3d` files collected into a clean subject-based directory.

### Step 3: Solving (MoSh++)
Run via `main.py` or `batch_solve_multi.py`.
- **Input:** Labeled C3D files + `settings.json` (for gender).
- **Operation:** Uses 16 cores (4 subjects x 4 cores) to solve for SMPL-X parameters.
- **Output:** Stage II `.pkl` files containing `trans`, `fullpose`, and `betas`.

### Step 4: Rectification
Run via `main.py` or `batch_convert_npz_rectified.py`.
- **Input:** Stage II `.pkl` files.
- **Operation:** Extracts parameters and truncates the 400 SMPL-X betas down to the first 100.
- **Why?** Blender's SMPL-X implementation only supports 100 shape keys. Providing 400 will cause import errors.
- **Output:** Blender-ready `.npz` files.

---

## 4. Environment Setup

### System Requirements
- Ubuntu 20.04 (Recommended)
- NVIDIA GPU (RTX 3090+ requires CUDA 11.0+)
- Python 3.7 (Conda environment named `soma`)

### Key Dependencies
1.  **SOMA & MoSh++:** Clone from [nghorbani/soma](https://github.com/nghorbani/soma) and [nghorbani/moshpp](https://github.com/nghorbani/moshpp).
2.  **SMPL-X Models:** Download the "Locked Head" models from the SMPL-X website.
3.  **VPoser:** Required for the solver's pose prior.
4.  **ezc3d:** For reading/writing C3D files.

For a full step-by-step installation log, refer to the `READ_ME.md` file.

---

## 5. Usage

To run the entire pipeline from start to finish:

1.  Activate your environment: `conda activate soma`
2.  Update `processing_paths.json` with your local paths.
3.  Execute the orchestrator: `python main.py`

You can also run individual stages by executing the corresponding `batch_*.py` scripts directly.
