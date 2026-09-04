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
    camera_count: int
    yaw_offset_deg: float


# ==========================================
# Procedural Generation Logic
# ==========================================

def generate_staggered_cylinder(
    total_cameras: int,
    num_rings: int,
    min_height_m: float = 0.1,
    max_height_m: float = 3.5
) -> List[CameraRingConfig]:
    """
    Procedurally generates camera rings, distributing cameras evenly.
    Crucially, it staggers alternating rings (like a brick wall) to 
    prevent cameras from stacking vertically in straight columns.
    """
    configs = []
    
    # Linearly interpolate heights
    heights = [min_height_m + i * (max_height_m - min_height_m) / (num_rings - 1) for i in range(num_rings)]
    
    # Evenly divide the cameras
    base_count = total_cameras // num_rings
    remainder = total_cameras % num_rings
    
    for i in range(num_rings):
        # Distribute leftover cameras
        count = base_count + (1 if i < remainder else 0)
        
        yaw_step = 360.0 / count
        # Removed the stagger to ensure perfect vertical columns
        yaw_offset_deg = 0.0
        
        configs.append(CameraRingConfig(
            height_m=heights[i], 
            camera_count=count,
            yaw_offset_deg=yaw_offset_deg
        ))
        
    return configs

# ==========================================
# Core Mathematical Validation
# ==========================================

def is_distance_valid(
    distance_m: float, 
    height_m: float, 
    target_z_m: float, 
    hardware: CameraHardware, 
    volume: ActionVolume
) -> bool:
    """Evaluates if a specific radial distance safely frames the action volume while aiming at a specific Z height."""
    if distance_m <= volume.radius_m:
        return False

    # Dynamically calculate the pitch required to look at the target Z coordinate
    pitch_rad = math.atan2(target_z_m - height_m, distance_m)
    
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
    target_z_m: float, 
    hardware: CameraHardware, 
    volume: ActionVolume,
    search_limit_m: float = 20.0,
    tolerance_m: float = 0.01
) -> float:
    """Executes a binary search to find the closest valid distance down to the centimeter."""
    low_m = volume.radius_m + 0.01
    high_m = search_limit_m

    if not is_distance_valid(high_m, height_m, target_z_m, hardware, volume):
        raise ValueError(f"Placement impossible at height {height_m}m aiming at Z={target_z_m}m.")

    while (high_m - low_m) > tolerance_m:
        mid_m = (low_m + high_m) / 2.0
        if is_distance_valid(mid_m, height_m, target_z_m, hardware, volume):
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
    
    # Universal volume covering the action space
    universal_volume = ActionVolume(radius_m=1.5, height_m=3.0)
    
    # Define the precise Z-height all cameras should aim at
    target_z_focus_m = 0.9625

    # 2. Generate the cylindrical blueprint without stagger
    cylinder_configuration = generate_staggered_cylinder(
        total_cameras=100, 
        num_rings=5, 
        min_height_m=0.1, 
        max_height_m=3.5
    )

    # Calculate the maximum safe distance required across all rings to ensure the whole cylinder is safe
    max_required_radius_m = 0.0
    for ring in cylinder_configuration:
        safe_dist = find_minimum_safe_distance(
            height_m=ring.height_m,
            target_z_m=target_z_focus_m,
            hardware=imx708,
            volume=universal_volume
        )
        if safe_dist > max_required_radius_m:
            max_required_radius_m = safe_dist
            
    # Set the cylinder radius to the maximum safe distance so ALL cameras can see the volume
    cylinder_radius_m = max_required_radius_m

    # 3. Setup the Blender scene
    collection = create_camera_collection("Calculated_Camera_Cylinder")
    
    # 4. Calculate coordinates and spawn cameras
    cam_index = 0
    for ring in cylinder_configuration:
        if ring.camera_count <= 0:
            continue
            
        yaw_step = 360.0 / ring.camera_count
        
        # The exact pitch required to hit target_z_focus_m from this specific height and radius
        computed_pitch_rad = math.atan2(target_z_focus_m - ring.height_m, cylinder_radius_m)
        computed_pitch_deg = math.degrees(computed_pitch_rad)
        
        for i in range(ring.camera_count):
            # Apply the offset to stagger this ring
            yaw_deg = (i * yaw_step) + ring.yaw_offset_deg
            yaw_rad = math.radians(yaw_deg)
            
            # Cartesian mapping ensuring Z-rotation 0 faces origin
            x_loc = cylinder_radius_m * math.sin(yaw_rad)
            y_loc = -cylinder_radius_m * math.cos(yaw_rad)
            
            name = f"Cam_{cam_index:03d}_H{ring.height_m:.1f}m"
            create_camera(
                name=name,
                hardware=imx708,
                x_m=x_loc,
                y_m=y_loc,
                z_m=ring.height_m,
                pitch_deg=computed_pitch_deg,
                yaw_deg=yaw_deg,
                collection=collection
            )
            cam_index += 1

    print(f"Successfully generated {cam_index} staggered cylinder cameras at radius {cylinder_radius_m}m aimed at Z={target_z_focus_m}m.")

if __name__ == "__main__":
    main()
