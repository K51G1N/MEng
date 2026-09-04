import os
import time
import pickle
import numpy as np
import torch

class GPUCameraFEPSO:
    """
    Massively Vectorized, GPU-Accelerated Fuzzy Evolutionary Particle Swarm Optimization (FEPSO)
    for Fixed-Cardinality Camera Subset Selection in Markerless Motion Capture.

    Incorporates:
    - Triangulability cone restricted to [40, 140] degrees with calibrated Fuzzy Gaussian geometry.
    - Pure graded spatial penalties: 1000 mm (0 views), 500 mm (1 view or non-triangulable).
    - Unclamped raw Euclidean MPJPE for triangulable points.
    - Co-visibility gated SimE Goodness via Product T-norm and indicator noise gate.
    - Explicit double summation over frames (F) and joints (J).
    - SDPE consistency regularizer with calibrated alpha = 0.10.
    - Static 3D unit ray precomputation with disk persistence (.pt).
    - In-memory and disk-backed evaluation lookup table (.pkl).
    """

    def __init__(
        self,
        camera_centers: np.ndarray,       # (N, 3) 3D nodal coordinates in world space
        camera_projections: np.ndarray,   # (N, 3, 4) Projection matrices P_k
        ground_truth_3d: np.ndarray,      # (F, J, 3) Reference ground-truth coordinates x*_{f,j}
        yolo_2d_coords: np.ndarray,       # (F, J, N, 2) 2D pixel coordinates (u, v)
        yolo_confidences: np.ndarray,     # (F, J, N) YOLO detection confidences c in [0, 1]
        K: int = 8,                       # Target active camera subset size
        n_particles: int = 25,            # Swarm population size
        max_iter: int = 50,               # Maximum iterations
        theta_min_deg: float = 40.0,      # Optical triangulability lower bound
        theta_max_deg: float = 140.0,     # Optical triangulability upper bound
        sigma_theta_deg: float = 16.5,    # Gaussian spread calibrated for [40, 140] deg cone
        conf_thresh: float = 0.20,        # tau_conf: 2D detection noise gate threshold
        lambda_w: float = 5.0,            # Exponential wDLT decay rate
        c0_w: float = 0.5,                # Exponential wDLT confidence offset
        b_start: float = -0.15,           # FEPSO cooling bias start (high exploration)
        b_end: float = 0.15,              # FEPSO cooling bias end (high exploitation)
        v_max: int = 2,                   # Maximum link swaps allowed per iteration
        alpha_sdpe: float = 0.10,         # Calibrated SDPE consistency regularization weight
        cache_dir: str = "./cache_fepso", # Path to save precomputed tensors and banks
        device: str = None
    ):
        # Auto-detect CUDA GPU acceleration, falling back to multi-threaded CPU
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        print(f"[GPU-FEPSO] Initialized on device: {self.device}")

        self.F, self.J, self.N_cams, _ = yolo_2d_coords.shape
        self.B = self.F * self.J          # Flattened batch dimension (all joint-frames)
        self.K = K
        self.n_particles = n_particles
        self.max_iter = max_iter

        self.theta_min_deg = theta_min_deg
        self.theta_max_deg = theta_max_deg
        self.sigma_theta_rad = np.radians(sigma_theta_deg)
        self.conf_thresh = conf_thresh
        self.lambda_w = lambda_w
        self.c0_w = c0_w
        self.b_start = b_start
        self.b_end = b_end
        self.v_max = v_max
        self.alpha_sdpe = alpha_sdpe
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        # Move base arrays to device as contiguous batch tensors
        self.C = torch.tensor(camera_centers, dtype=torch.float32, device=self.device)          # (N, 3)
        self.P = torch.tensor(camera_projections, dtype=torch.float32, device=self.device)      # (N, 3, 4)
        self.X_gt = torch.tensor(ground_truth_3d, dtype=torch.float32, device=self.device).reshape(self.B, 3)
        self.coords_2d = torch.tensor(yolo_2d_coords, dtype=torch.float32, device=self.device).reshape(self.B, self.N_cams, 2)
        self.confs_2d = torch.tensor(yolo_confidences, dtype=torch.float32, device=self.device).reshape(self.B, self.N_cams)

        # 1. Precalculate or Load Static 3D Ray Vectors: (B, N, 3)
        self.V_static = self._init_static_rays()

        # 2. Load or Initialize Persistent Evaluation Bank (Lookup Table)
        self.bank_path = os.path.join(self.cache_dir, f"evaluation_bank_K{self.K}.pkl")
        self.eval_bank: dict[frozenset, tuple[float, float, float, np.ndarray]] = self._load_evaluation_bank()

    def _init_static_rays(self) -> torch.Tensor:
        """
        Loads precomputed static 3D unit ray vectors from disk, or computes
        and saves them. Shape: (B, N_cams, 3).
        """
        tensor_path = os.path.join(self.cache_dir, f"static_rays_F{self.F}_J{self.J}_N{self.N_cams}.pt")
        if os.path.exists(tensor_path):
            print(f"[GPU-FEPSO] Loading cached static 3D rays from {tensor_path}")
            return torch.load(tensor_path, map_location=self.device)

        print("[GPU-FEPSO] Precomputing static 3D ray tensor...")
        t0 = time.time()
        # Broadcast difference: (1, N, 3) - (B, 1, 3) -> (B, N, 3)
        diff = self.C.unsqueeze(0) - self.X_gt.unsqueeze(1)
        norms = torch.norm(diff, dim=-1, keepdim=True).clamp(min=1e-9)
        V_static = diff / norms

        torch.save(V_static, tensor_path)
        size_mb = (V_static.element_size() * V_static.nelement()) / (1024 ** 2)
        print(f"[GPU-FEPSO] Saved static rays ({size_mb:.2f} MB) in {time.time() - t0:.2f}s")
        return V_static

    def _load_evaluation_bank(self) -> dict:
        """Loads cached subset evaluations from disk to avoid redundant evaluations."""
        if os.path.exists(self.bank_path):
            try:
                with open(self.bank_path, "rb") as f:
                    bank = pickle.load(f)
                print(f"[GPU-FEPSO] Loaded evaluation bank with {len(bank)} cached configurations.")
                return bank
            except Exception as e:
                print(f"[GPU-FEPSO] Warning: Could not read cache ({e}). Initializing empty bank.")
        return {}

    def save_evaluation_bank(self):
        """Persists the evaluation lookup table to disk."""
        with open(self.bank_path, "wb") as f:
            pickle.dump(self.eval_bank, f)
        print(f"[GPU-FEPSO] Persisted {len(self.eval_bank)} cached configurations to {self.bank_path}")

    def _batch_evaluate_subset(self, cam_list: list[int]) -> tuple[float, float, float, np.ndarray]:
        """
        Full vectorized GPU evaluation across all F frames and J joints:
        - 3D Convergence Angles restricted to [40, 140] deg.
        - Co-visibility gated SimE Goodness via Product T-norm and indicator noise gate over (F, J).
        - Graded Spatial Penalty Step Function (1000 mm for 0 views, 500 mm for 1 view or ill-conditioned).
        - Batched Normal Matrix (A^T A) Eigendecomposition for triangulable points.
        - Pure, un-clamped raw Euclidean MPJPE for triangulable points.
        - Consistency regularizer: MPJPE + alpha_sdpe * SDPE.
        """
        cams_idx = torch.tensor(cam_list, dtype=torch.long, device=self.device)

        # Slice subset data: (B, K, ...)
        coords_sub = self.coords_2d[:, cams_idx, :]  # (B, K, 2)
        confs_sub = self.confs_2d[:, cams_idx]       # (B, K)
        V_sub = self.V_static[:, cams_idx, :]        # (B, K, 3)
        P_sub = self.P[cams_idx]                     # (K, 3, 4)

        # -------------------------------------------------------------
        # 1. Vectorized Convergence Angles & Fuzzy Gaussian Geometry
        # -------------------------------------------------------------
        pairwise_dots = torch.bmm(V_sub, V_sub.transpose(1, 2)).clamp(-1.0, 1.0)
        angles = torch.acos(pairwise_dots)  # Radians

        # Strictly restrict triangulability to [40, 140] degrees
        deg = torch.rad2deg(angles)
        valid_angle_mask = (deg >= self.theta_min_deg) & (deg <= self.theta_max_deg)

        mu_geom = torch.where(
            valid_angle_mask,
            torch.exp(-((angles - (np.pi / 2.0)) ** 2) / (2.0 * (self.sigma_theta_rad ** 2))),
            torch.zeros_like(angles)
        )
        mu_geom.diagonal(dim1=-2, dim2=-1).fill_(0.0)  # Ignore self-pairs

        # -------------------------------------------------------------
        # 2. SimE Camera Goodness: g_k(X) with Co-Visibility Gating
        # -------------------------------------------------------------
        vis_mask = (confs_sub >= self.conf_thresh).float()   # (B, K)

        # Partner quality: c_{k'} * I(c_{k'} >= tau_conf), shape (B, 1, K)
        partner_quality = (confs_sub * vis_mask).unsqueeze(1)

        # Pairwise product T-norm Q matrix across all (k, k'): (B, K, K)
        pair_triangulation_quality = mu_geom * partner_quality

        # Best visible, triangulable partner for camera k: (B, K)
        best_partner_quality, _ = pair_triangulation_quality.max(dim=-1)

        # Reshape to (F, J, K) to honor the biomechanical frame-joint double summation
        g_tensor = (confs_sub * best_partner_quality).reshape(self.F, self.J, self.K)
        goodness_np = g_tensor.mean(dim=(0, 1)).detach().cpu().numpy()  # (K,)

        # -------------------------------------------------------------
        # 3. Visibility & Graded Spatial Penalty Step Function
        # -------------------------------------------------------------
        n_vis = vis_mask.sum(dim=-1)  # (B,) Number of visible cameras above tau_conf

        # Check if at least one visible camera pair meets the [40, 140] deg criterion
        pair_detected = (vis_mask.unsqueeze(-1) * vis_mask.unsqueeze(-2)) > 0
        triangulable_pairs = (mu_geom > 0.0) & pair_detected
        has_triangulable_pair = triangulable_pairs.any(dim=-1).any(dim=-1)  # (B,)

        # Graded Penalties:
        # Case 1: 1000 mm for 0 cameras (complete blind spot)
        errors = torch.full((self.B,), 1000.0, dtype=torch.float32, device=self.device)

        # Case 2: 500 mm for exactly 1 camera OR (>=2 cameras with no valid [40, 140] deg pair)
        untriangulable_mask = (n_vis == 1) | ((n_vis >= 2) & (~has_triangulable_pair))
        errors = torch.where(untriangulable_mask, 500.0, errors)

        # -------------------------------------------------------------
        # 4. Batched wDLT Normal Matrix Eigendecomposition
        # Case 3: Triangulable keypoints (>=2 cameras AND valid angle)
        # -------------------------------------------------------------
        solve_mask = (n_vis >= 2) & has_triangulable_pair

        if solve_mask.any():
            coords_sl = coords_sub[solve_mask]  # (B_solve, K, 2)
            confs_sl = confs_sub[solve_mask]    # (B_solve, K)
            vis_sl = vis_mask[solve_mask]        # (B_solve, K)

            # Adaptive exponential uncertainty weights (zero out non-detected views)
            w = torch.exp(self.lambda_w * (confs_sl - self.c0_w)) * vis_sl  # (B_solve, K)

            u = coords_sl[:, :, 0:1]  # (B_solve, K, 1)
            v = coords_sl[:, :, 1:2]  # (B_solve, K, 1)

            p1 = P_sub[:, 0, :].unsqueeze(0)  # (1, K, 4)
            p2 = P_sub[:, 1, :].unsqueeze(0)  # (1, K, 4)
            p3 = P_sub[:, 2, :].unsqueeze(0)  # (1, K, 4)

            # Two projection rows per camera
            row1 = w.unsqueeze(-1) * (u * p3 - p1)  # (B_solve, K, 4)
            row2 = w.unsqueeze(-1) * (v * p3 - p2)  # (B_solve, K, 4)
            A = torch.cat([row1, row2], dim=1)      # (B_solve, 2*K, 4)

            # Form normal equations: A^T A (B_solve, 4, 4)
            ATA = torch.bmm(A.transpose(1, 2), A)

            # Normalize ATA by its max absolute value per batch item to prevent cusolver float32 overflow
            max_vals = torch.amax(torch.abs(ATA), dim=(1, 2), keepdim=True).clamp(min=1e-9)
            ATA_norm = ATA / max_vals

            # cuSOLVER has a hard limit on batchSize (fails > ~32k). We chunk it to avoid CUSOLVER_STATUS_INVALID_VALUE
            chunk_size = 25000
            eigvecs_list = []
            for i in range(0, ATA_norm.size(0), chunk_size):
                _, evecs = torch.linalg.eigh(ATA_norm[i:i+chunk_size])
                eigvecs_list.append(evecs)
            
            eigvecs = torch.cat(eigvecs_list, dim=0)
            X_homo = eigvecs[:, :, 0]  # Eigenvector for smallest eigenvalue: (B_solve, 4)

            # Convert to 3D Euclidean coordinates
            w_coord = X_homo[:, 3:4]
            valid_w = torch.abs(w_coord) > 1e-7

            x_pred = X_homo[:, :3] / torch.where(valid_w, w_coord, torch.ones_like(w_coord))
            gt_sl = self.X_gt[solve_mask]

            # Pure raw Euclidean reconstruction error in mm (no clamp)
            raw_dists = torch.norm(x_pred - gt_sl, dim=-1)

            # Fallback for numerical matrix singularities only
            dists = torch.where(valid_w.squeeze(-1), raw_dists, torch.tensor(1500.0, device=self.device))

            errors[solve_mask] = dists

        # -------------------------------------------------------------
        # 5. Global Fitness Evaluation (MPJPE + alpha * SDPE)
        # -------------------------------------------------------------
        mpjpe = errors.mean().item()
        sdpe = errors.std().item()
        fitness = mpjpe + self.alpha_sdpe * sdpe

        return fitness, mpjpe, sdpe, goodness_np

    def evaluate(self, camera_set: set[int]) -> tuple[float, float, float, dict[int, float]]:
        """Queries the persistent lookup table bank before triggering GPU computation."""
        key = frozenset(camera_set)
        cam_list = sorted(list(camera_set))

        # Check bank cache
        if key in self.eval_bank:
            fit, mpjpe, sdpe, g_np = self.eval_bank[key]
            goodness_dict = {cam: float(g_np[idx]) for idx, cam in enumerate(cam_list)}
            return fit, mpjpe, sdpe, goodness_dict

        # Evaluate on GPU
        fit, mpjpe, sdpe, g_np = self._batch_evaluate_subset(cam_list)
        # Update bank
        self.eval_bank[key] = (fit, mpjpe, sdpe, g_np)
        goodness_dict = {cam: float(g_np[idx]) for idx, cam in enumerate(cam_list)}

        return fit, mpjpe, sdpe, goodness_dict

    def optimize(self, verbose: bool = True) -> tuple[set[int], float, list[float]]:
        """
        Runs the FEPSO optimization loop using discrete set operations,
        Simulated Evolution selection with dynamic cooling bias, and GPU evaluation.
        """
        all_cams = list(range(self.N_cams))

        # 1. Swarm Initialization
        particles: list[set[int]] = []
        pbest_positions: list[set[int]] = []
        pbest_fitness: list[float] = []

        if verbose:
            print(f"[GPU-FEPSO] Initializing {self.n_particles} particles (K={self.K})...")
        t0 = time.time()

        for _ in range(self.n_particles):
            p = set(np.random.choice(all_cams, size=self.K, replace=False))
            particles.append(p)
            fit, _, _, _ = self.evaluate(p)
            pbest_positions.append(set(p))
            pbest_fitness.append(fit)

        gbest_idx = int(np.argmin(pbest_fitness))
        gbest_position = set(pbest_positions[gbest_idx])
        gbest_fitness = pbest_fitness[gbest_idx]

        if verbose:
            print(f"Iter 00: Initial Global Best = {gbest_fitness:.2f} mm (Elapsed: {time.time() - t0:.2f}s)")
        history = [gbest_fitness]

        no_improvement_counter = 0
        best_recorded_fitness = gbest_fitness

        # 2. Main Optimization Loop
        for t in range(1, self.max_iter + 1):
            t_iter = time.time()
            # Linear cooling bias schedule B(t)
            B_t = self.b_start + (self.b_end - self.b_start) * (t / self.max_iter)

            for i in range(self.n_particles):
                current_set = particles[i]

                # A. FEPSO SimE Selection Step
                _, _, _, goodness = self.evaluate(current_set)
                marked_for_removal = set()

                for k, g_k in goodness.items():
                    u = np.random.uniform(0.0, 1.0)
                    if u <= (1.0 - g_k - B_t):  # Selection condition
                        marked_for_removal.add(k)

                # Velocity clamp V_max: drop lowest goodness cameras first
                if len(marked_for_removal) > self.v_max:
                    sorted_removals = sorted(list(marked_for_removal), key=lambda c: goodness[c])
                    marked_for_removal = set(sorted_removals[:self.v_max])

                # B. Discrete Swarm Velocity & Position Update
                pbest_diff = pbest_positions[i] - current_set
                gbest_diff = gbest_position - current_set
                candidate_pool = list(pbest_diff | gbest_diff)

                if len(candidate_pool) < len(marked_for_removal):
                    available = list(set(all_cams) - current_set - set(candidate_pool))
                    needed = len(marked_for_removal) - len(candidate_pool)
                    candidate_pool.extend(list(np.random.choice(available, size=needed, replace=False)))

                replacements = list(np.random.permutation(candidate_pool))[:len(marked_for_removal)]

                # Apply link swaps preserving cardinality K
                new_position = set(current_set)
                for out_c, in_c in zip(list(marked_for_removal), replacements):
                    new_position.remove(out_c)
                    new_position.add(in_c)

                particles[i] = new_position

                # C. Evaluate & Update Memories
                fit, _, _, _ = self.evaluate(new_position)

                if fit < pbest_fitness[i]:
                    pbest_fitness[i] = fit
                    pbest_positions[i] = set(new_position)
                    if fit < gbest_fitness:
                        gbest_fitness = fit
                        gbest_position = set(new_position)

            history.append(gbest_fitness)
            if t % 5 == 0 or t == self.max_iter:
                dt = time.time() - t_iter
                if verbose:
                    print(f"Iter {t:02d}/{self.max_iter} [B(t)={B_t:+.2f}]: GBest = {gbest_fitness:.2f} mm ({dt:.3f}s/iter)")

        # Persist updated evaluation bank
        if verbose:
            print(f"[GPU-FEPSO] Saving {len(self.eval_bank)} cached configurations...")
        self.save_evaluation_bank()
        return gbest_position, gbest_fitness, history


# ==========================================
# Example Driver & Synthetic Verification
# ==========================================
if __name__ == "__main__":
    np.random.seed(42)
    torch.manual_seed(42)

    # 1. Define synthetic fishbowl parameters
    N_CAMS = 30       # Total calibrated cameras in fishbowl pool
    FRAMES = 15       # Motion sequence frame count
    JOINTS = 14       # Human skeletal keypoints (COCO format)
    K_SELECT = 6      # Active cameras to select

    print("Generating synthetic fishbowl camera network...")
    # Circular array at radius 3.0m, height 1.5m
    azimuths = np.linspace(0, 2 * np.pi, N_CAMS, endpoint=False)
    cams_xyz = np.stack([3.0 * np.cos(azimuths), 3.0 * np.sin(azimuths), np.full(N_CAMS, 1.5)], axis=1)

    proj_matrices = np.zeros((N_CAMS, 3, 4))
    for k in range(N_CAMS):
        proj_matrices[k, :3, :3] = np.eye(3)
        proj_matrices[k, :3, 3] = -cams_xyz[k]

    # Synthetic reference 3D ground truth (squat sequence)
    gt_3d = np.zeros((FRAMES, JOINTS, 3))
    for f in range(FRAMES):
        for j in range(JOINTS):
            gt_3d[f, j] = np.array([0.05 * f, 0.02 * j, 1.0 - 0.08 * (f % 6)])

    # Synthetic 2D detections and confidences
    coords_2d = np.zeros((FRAMES, JOINTS, N_CAMS, 2))
    confs_2d = np.random.uniform(0.20, 0.95, size=(FRAMES, JOINTS, N_CAMS))

    for f in range(FRAMES):
        for j in range(JOINTS):
            for k in range(N_CAMS):
                pt_h = np.append(gt_3d[f, j], 1.0)
                uv_h = proj_matrices[k] @ pt_h
                noise = np.random.normal(0, 0.02 * (1.0 - confs_2d[f, j, k]), size=2)
                coords_2d[f, j, k] = uv_h[:2] / uv_h[2] + noise

    # 2. Instantiate and Run Optimizer
    optimizer = GPUCameraFEPSO(
        camera_centers=cams_xyz,
        camera_projections=proj_matrices,
        ground_truth_3d=gt_3d,
        yolo_2d_coords=coords_2d,
        yolo_confidences=confs_2d,
        K=K_SELECT,
        n_particles=100,
        max_iter=100,
        theta_min_deg=40.0,
        theta_max_deg=140.0,
        conf_thresh=0.20,
        alpha_sdpe=0.10,
        cache_dir="./cache_fepso"
    )

    best_subset, best_fitness, history = optimizer.optimize()

    print("\n--- Optimization Complete ---")
    print(f"Optimal Active Camera Subset (K={K_SELECT}): {sorted(list(best_subset))}")
    print(f"Final Global Best Fitness: {best_fitness:.4f} mm")