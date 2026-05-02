# Markerless Camera Optimization Tool

A professional CLI utility for automating Blender scene generation, camera array placement, high-performance rendering, and YOLO-based human pose inference.

## 🚀 Features

- **Automated Scene Generation**: Spawn SMPL-X human models with specific physical parameters and animations using `spawn_subjects.py`.
- **Dynamic Camera Setup**: Programmatically place and configure camera arrays using `setup_rig.py`.
- **High-Performance Rendering**: Headless Blender rendering with explicit OptiX/CUDA GPU acceleration via `batch_render.py`.
- **AI Inference**: Integrated YOLOv8-pose estimation to extract 2D keypoints from rendered frames.
- **Video Stitching**: Automated FFMPEG-based stitching for both raw renders and AI results.

---

## 🛠️ Installation

1. **Clone the repository**:
   ```powershell
   git clone <your-repo-url>
   cd markerless-cam-optim
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -e .
   ```

3. **GPU Support (Recommended)**:
   Ensure you have a CUDA-enabled PyTorch installation for maximum performance:
   ```powershell
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```

---

## ⚙️ Configuration

Create a `.env` file in the project root to define your local paths:

```ini
BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe
PROJECT_ROOT=C:\Path\To\markerless-cam-optim
```

---

## 📖 Usage

The tool is accessible via the `optimize-cameras` command.

### 1. Full Pipeline (End-to-End)
Runs generation, setup, rendering, inference, and video stitching in one sequence.
```powershell
optimize-cameras full_pipeline --subject_config some_info.json --camera_config camera_info.json -o my_experiment
```

### 2. Individual Commands

- **Generate Scene**: 
  `optimize-cameras generate --config subject_info.json --output scene.blend`
- **Setup Cameras**: 
  `optimize-cameras setup_cameras --blend scene.blend --config camera_info.json`
- **Render Frames**: 
  `optimize-cameras render --blend scene.blend --output renders/ --limit 100`
- **Run Inference**: 
  `optimize-cameras inference --input renders/`
- **Stitch Videos**: 
  `optimize-cameras stitch_videos --dir my_experiment/`

*Note: Use the `--continue` (or `-c`) flag on individual commands to automatically trigger the remaining steps in the pipeline.*

---

## 📁 Output Structure

```
my_experiment/
├── scene.blend         # Generated Blender scene
├── renders/            # Raw PNG frames (C0, C1, etc.)
├── inference/          # AI Results (C0_inference, etc.)
│   ├── C0_inference/
│   │   ├── F0001.png   # Annotated frame
│   │   └── C0.json     # 2D Keypoint data
│   └── ...
└── videos/             # Final MP4 results
    ├── C0_raw.mp4
    └── C0_inference.mp4
```

---

## ⚖️ License
Internal Project - All Rights Reserved.
