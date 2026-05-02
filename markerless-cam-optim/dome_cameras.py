import bpy
import math
from dataclasses import dataclass
from typing import List

# ==========================================
# Domain Models (Orthogonal Data Structures)
# ==========================================

@dataclass(frozen=True)
class CameraHardware:
    """Immutable data structure representing physical camera sensor characteristics."""
    sensor_width_mm: float
    sensor_height_mm: float
    focal_length_mm: float

    @property
    def fov_v_rad(self) -> float:
        return 2 * math.atan(self.sensor_height_mm / (2 * self.focal_length_mm))

    @property
    def fov_h_rad(self) -> float:
        return 2 * math.atan(self.sensor_width_mm / (2 * self.focal_length_mm))

@dataclass(frozen=True)
class ActionVolume:
    """Defines the absolute 3D cylindrical space required for the exercise suite."""
    radius_m: float
    height_m: float

@dataclass(frozen=True)
class CameraRingConfig:
    """Configuration for a single horizontal ring of cameras."""
    height_m: float
    pitch_deg: float
    camera_count: int


# ==========================================
# Procedural Generation Logic
# ==========================================

def generate_formulaic_dome(
    total_cameras: int,
    num_rings: int,
    min_height_m: float = 0.1,
    max_height_m: float = 3.5,
    start_pitch_deg: float = 25.0,
    end_pitch_deg: float = -30.0
) -> List[CameraRingConfig]:
    """
    Procedurally generates camera rings, distributing the total camera count 
    proportionally based on a cosine curve to simulate dome circumference.
    """
    configs = []
    
    # Linearly interpolate heights and pitches
    heights = [min_height_m + i * (max_height_m - min_height_m) / (num_rings - 1) for i in range(num_rings)]
    pitches = [start_pitch_deg + i * (end_pitch_deg - start_pitch_deg) / (num_rings - 1) for i in range(num_rings)]
    
    # Calculate proportional weights
    weights = []
    for h in heights:
        norm_h = (h - min_height_m) / (max_height_m - min_height_m)
        weight = math.cos(norm_h * (math.pi / 2.0))
        weights.append(weight)
        
    total_weight = sum(weights)
    
    # Allocate cameras
    allocated_cameras = 0
    for i in range(num_rings):
        if i == num_rings - 1:
            count = total_cameras - allocated_cameras
        else:
            count = max(1, int(round((weights[i] / total_weight) * total_cameras)))
            
        allocated_cameras += count
        configs.append(CameraRingConfig(height_m=heights[i], pitch_deg=pitches[i], camera_count=count))
        
    return configs


# ==========================================
# Core Mathematical Validation
# ==========================================

def is_distance_valid(
    distance_m: float, 
    height_m: float, 
    pitch_deg: float, 
    hardware: CameraHardware, 
    volume: ActionVolume
) -> bool:
    """Evaluates if a specific radial distance safely frames the action volume."""
    if distance_m <= volume.radius_m:
        return False

    pitch_rad = math.radians(pitch_deg)
    dist_to_closest_edge = distance_m - volume.radius_m

    # Vertical Frustum Evaluation
    angle_to_top = math.atan2(volume.height_m - height_m, dist_to_closest_edge)
    angle_to_bottom = math.atan2(0.0 - height_m, dist_to_closest_edge)
    
    v_fov_half = hardware.fov_v_rad / 2.0
    cam_top_limit = pitch_rad + v_fov_half
    cam_bottom_limit = pitch_rad - v_fov_half
    
    if angle_to_top > cam_top_limit or angle_to_bottom < cam_bottom_limit:
        return False

    # Horizontal Frustum Evaluation
    angle_to_side = math.asin(volume.radius_m / distance_m)
    
    if angle_to_side > (hardware.fov_h_rad / 2.0):
        return False

    return True

def find_minimum_safe_distance(
    height_m: float, 
    pitch_deg: float, 
    hardware: CameraHardware, 
    volume: ActionVolume,
    search_limit_m: float = 20.0,
    tolerance_m: float = 0.01
) -> float:
    """Executes a binary search to find the closest valid distance down to the centimeter."""
    low_m = volume.radius_m + 0.01
    high_m = search_limit_m

    if not is_distance_valid(high_m, height_m, pitch_deg, hardware, volume):
        raise ValueError(f"Placement impossible at height {height_m}m with pitch {pitch_deg}°.")

    while (high_m - low_m) > tolerance_m:
        mid_m = (low_m + high_m) / 2.0
        if is_distance_valid(mid_m, height_m, pitch_deg, hardware, volume):
            high_m = mid_m 
        else:
            low_m = mid_m   

    return high_m


# ==========================================
# Blender Scene Management
# ==========================================

def create_camera(
    name: str, 
    hardware: CameraHardware, 
    x_m: float, 
    y_m: float, 
    z_m: float, 
    pitch_deg: float, 
    yaw_deg: float,
    collection: bpy.types.Collection
):
    """Spawns and configures a Blender camera object with exact hardware specifications."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = 'PERSP'
    cam_data.lens_unit = 'MILLIMETERS'
    cam_data.lens = hardware.focal_length_mm
    cam_data.sensor_width = hardware.sensor_width_mm
    cam_data.sensor_height = hardware.sensor_height_mm
    cam_data.sensor_fit = 'HORIZONTAL' 

    cam_obj = bpy.data.objects.new(name, cam_data)
    collection.objects.link(cam_obj)

    cam_obj.location = (x_m, y_m, z_m)

    rot_x = math.radians(90.0 + pitch_deg)
    rot_y = 0.0
    rot_z = math.radians(yaw_deg)
    cam_obj.rotation_euler = (rot_x, rot_y, rot_z)

def create_camera_collection(collection_name: str) -> bpy.types.Collection:
    """Creates a fresh collection, purging the old one to keep the outliner clean."""
    if collection_name in bpy.data.collections:
        col = bpy.data.collections[collection_name]
        for obj in col.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        col = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(col)
    return col


# ==========================================
# Main Execution Controller
# ==========================================

def main():
    # 1. Initialize static properties
    imx708 = CameraHardware(
        sensor_width_mm=3.6288, 
        sensor_height_mm=6.4512, 
        focal_length_mm=4.74
    )
    
    # Universal volume covering Star Jumps, Lunges, and Pushups
    universal_volume = ActionVolume(radius_m=1.16, height_m=2.53)

    # 2. Generate the dome blueprint formulaically
    # Adjust total_cameras and num_rings here to change the density
    dome_configuration = generate_formulaic_dome(
        total_cameras=1, 
        num_rings=1, 
        min_height_m=0.1, 
        max_height_m=3.5, 
        start_pitch_deg=25.0, 
        end_pitch_deg=-30.0
    )

    # 3. Setup the Blender scene
    collection = create_camera_collection("Calculated_Camera_Shell")
    
    # 4. Calculate distances and spawn cameras
    cam_index = 0
    for ring in dome_configuration:
        try:
            min_dist = find_minimum_safe_distance(
                height_m=ring.height_m,
                pitch_deg=ring.pitch_deg,
                hardware=imx708,
                volume=universal_volume
            )
            
            yaw_step = 360.0 / ring.camera_count
            
            for i in range(ring.camera_count):
                yaw_deg = i * yaw_step
                yaw_rad = math.radians(yaw_deg)
                
                # Cartesian mapping ensuring Z-rotation 0 faces origin
                x_loc = min_dist * math.sin(yaw_rad)
                y_loc = -min_dist * math.cos(yaw_rad)
                
                name = f"Cam_{cam_index:03d}_H{ring.height_m:.1f}m"
                create_camera(
                    name=name,
                    hardware=imx708,
                    x_m=x_loc,
                    y_m=y_loc,
                    z_m=ring.height_m,
                    pitch_deg=ring.pitch_deg,
                    yaw_deg=yaw_deg,
                    collection=collection
                )
                cam_index += 1
                
        except ValueError as e:
            print(f"Skipped ring at {ring.height_m}m: {e}")

    print(f"Successfully generated {cam_index} mathematically validated cameras.")

if __name__ == "__main__":
    main()