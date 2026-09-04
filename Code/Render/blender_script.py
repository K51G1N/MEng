"""
This file handles all the camera placement, camera setup, matrices, scene settings, rendering and saving of the frames.
This is executed via the main file that handles the script
"""

import bpy
import math
import json
import sys
import os 
from mathutils import Euler
from mathutils import Matrix
from pathlib import Path
def get_sensor_size(sensor_fit, sensor_x, sensor_y):
    if sensor_fit == "VERTICAL":
        return sensor_y
    return sensor_x

def get_sensor_fit(sensor_fit, size_x, size_y):
    if sensor_fit == 'AUTO':
        if size_x >= size_y:
            return 'HORIZONTAL'
        else:
            return 'VERTICAL'
    return sensor_fit

def get_calibration_matrix_K_from_blender(camera_data):
    if camera_data.type != "PERSP":
        raise ValueError('Non-perspective cameras not supported')
    scene = bpy.context.scene
    focal_length_in_mm = camera_data.lens
    scale = scene.render.resolution_percentage / 100
    resolution_x_in_px = scale * scene.render.resolution_x
    resolution_y_in_px = scale * scene.render.resolution_y        
    sensor_size_in_mm = get_sensor_size(camera_data.sensor_fit, camera_data.sensor_width, camera_data.sensor_height)
    sensor_fit = get_sensor_fit(camera_data.sensor_fit, scene.render.pixel_aspect_x * resolution_x_in_px, scene.render.pixel_aspect_y * resolution_y_in_px)
    
    pixel_aspect_ratio = scene.render.pixel_aspect_y / scene.render.pixel_aspect_x
    if sensor_fit == 'HORIZONTAL':
        view_fac_in_px = resolution_x_in_px
    else:
        view_fac_in_px = pixel_aspect_ratio *resolution_y_in_px
    
    pixel_size_mm_per_px = sensor_size_in_mm / focal_length_in_mm / view_fac_in_px
    s_u = 1 / pixel_size_mm_per_px # fx
    s_v = 1 / pixel_size_mm_per_px / pixel_aspect_ratio #fy
    
    #Parameters of intrinsic calibration matrix K
    u_0 = resolution_x_in_px / 2 - camera_data.shift_x * view_fac_in_px #cx
    v_0 = resolution_y_in_px / 2 + camera_data.shift_y * view_fac_in_px / pixel_aspect_ratio #cy
    skew = 0
    
    K = Matrix(
        ((s_u, skew, u_0),
         (0, s_v, v_0),
         (0, 0, 1)))
    return K
def get_3x4_RT_matrix_from_blender(camera):
    R_blender_camera_to_cv = Matrix(
        ((1,0,0),
         (0,-1,0),
         (0,0,-1)))
    location, rotation = camera.matrix_world.decompose()[0:2] 
    R_world_to_blender_camera = rotation.to_matrix().transposed()
    
    T_world_to_blender_camera= -1*R_world_to_blender_camera @ location
    R_world_to_cv = R_blender_camera_to_cv @ R_world_to_blender_camera
    T_world_to_cv = R_blender_camera_to_cv @ T_world_to_blender_camera
    
    RT = Matrix((
        R_world_to_cv[0][:] + (T_world_to_cv[0],),
        R_world_to_cv[1][:] + (T_world_to_cv[1],),
        R_world_to_cv[2][:] + (T_world_to_cv[2],)
    ))
    return RT

def get_args():
    if "--" not in sys.argv:
        return []

    separator_index = sys.argv.index("--")
    return sys.argv[separator_index +1 :]

def read_json(path):
    with open(path, 'r') as file:
        data = json.load(file)
    return data

def scene_setup():
    pass

def matrix_to_list(matrix):
    return [list(row) for row in matrix]
    
def save_matrices(render_path):
    camera_sets = {}
    for collection in bpy.data.collections:
        cameras = [object for object in collection.objects if object.type == 'CAMERA']
        if cameras:
            camera_sets[collection.name] = cameras
    print(camera_sets)
    #Resolution
    resolution_x = bpy.context.scene.render.resolution_x
    resolution_y = bpy.context.scene.render.resolution_y    
    bpy.context.view_layer.update()
    for set, cameras in camera_sets.items():
        for camera in cameras:
            intrinsic_matrix_K = get_calibration_matrix_K_from_blender(camera.data)
            extrinsic_matrix_RT = get_3x4_RT_matrix_from_blender(camera)
            projection_matrix_P = intrinsic_matrix_K @ extrinsic_matrix_RT
            
            
            matrices = {
                "projection": matrix_to_list(projection_matrix_P), 
                "intrinsic" : matrix_to_list(intrinsic_matrix_K), 
                "extrinsic": matrix_to_list(extrinsic_matrix_RT)
                }
            matrices_json = json.dumps(matrices, indent=4)
            save_path = render_path + "\\" + set + "\\" + camera.name + "_matrices.json"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as file:
                file.write(matrices_json)
            # print("FULL")
            # print(f"Name:{camera.name} Matrices Projection:  {intrinsic_matrix_K@extrinsic_matrix_RT}, intrinsic: {intrinsic_matrix_K}, extrinsic: {extrinsic_matrix_RT}")
        
            # print(f"camera: {camera.name} from set: {set}, its location is: {list(camera.location)}") #, options: {dir(camera)}, data: {dir(camera.data)}
            # camera_name = camera.name
            # print(f"Name: {camera_name}")
            #Intrinsic
            sensor_width_mm = camera.data.sensor_width
            sensor_height_mm = camera.data.sensor_height
            focal_length_mm = camera.data.lens
            
            fx = (focal_length_mm/sensor_width_mm ) * resolution_x
            fy = (focal_length_mm/sensor_height_mm) * resolution_y
            cx = resolution_x / 2
            cy = resolution_y / 2
            
            m_intrinsic = Matrix([
                [fx, 0, cx,0], 
                [0, fy, cy,0], 
                [0,0,1,0]
                ]) 
            # print(f"intrinsic: {m_intrinsic}")
            #Extrinsics
            camera_location = list(camera.location)
            rotation_euler = list(camera.rotation_euler)
            roation_degrees = [math.degrees(rot) for rot in rotation_euler]
            
            m_extrinsic = camera.matrix_world.inverted()
            # print(f"extrinsic: {m_extrinsic}")
            projection_matrix = m_intrinsic @ m_extrinsic
            
            # print(f"Projection matrix: {projection_matrix}")
            # print("SHORT")
            # print(f"Name:{camera.name} Matrices Projection:  {projection_matrix}, intrinsic: {m_intrinsic}, extrinsic: {m_extrinsic}")
            # print("-------------------")

def camera_place(camera_sets):
    # print(camera_sets)
    for camera_set in camera_sets:
        
        set_collection = bpy.data.collections.get(camera_set)
        if not set_collection:
            print(f"Collection does not exist, creating collection")
            set_collection = bpy.data.collections.new(camera_set)
            bpy.context.scene.collection.children.link(set_collection)
            print(f"created collection: {set_collection.name} ")
        for camera in camera_sets[camera_set]:
            camera_name = camera["name"]
            
            if camera_name in bpy.data.objects:
                print(f"Found {camera_name}, updating camera")
                camera_object = bpy.data.objects[camera_name]
                camera_data = camera_object.data
            else:
                print(f"Camera does not exist creating camera {camera_name}")
                camera_data = bpy.data.cameras.new(camera_name)
                camera_object = bpy.data.objects.new(camera_name, camera_data)
                set_collection.objects.link(camera_object)
                
            # camera_data = bpy.data.cameras.new(camera["name"])
            
            camera_data.lens = camera["parameters"]["hardware"]["focal_length_mm"]
            camera_data.sensor_width  = camera["parameters"]["hardware"]["sensor_width_mm"]
            camera_data.sensor_height =camera["parameters"]["hardware"]["sensor_height_mm"]

            camera_data.sensor_fit = 'HORIZONTAL'
            # camera_object = bpy.data.objects.new(camera["name"], camera_data)
            camera_object.location = camera["location"]
            rot_deg = camera["rotation_degrees"]
            rot_rad = [math.radians(a) for a in rot_deg]
            camera_object.rotation_euler = Euler(rot_rad, "XYZ")
        
            resolution = camera["parameters"]["intrinsics"]["resolution"]
            bpy.context.scene.render.resolution_x = resolution[0]
            bpy.context.scene.render.resolution_y = resolution[1]

def render(camera_sets, render_path):
    scene = bpy.context.scene
    scene.render.use_multiview = False
    scene.render.engine = 'BLENDER_EEVEE'
    start_frame = 185
    end_frame = 186     
    for frame in range(start_frame, end_frame+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for camera_set in camera_sets:
            set_collection = bpy.data.collections.get(camera_set)
            for camera in camera_sets[camera_set]:
                scene.camera = bpy.data.objects.get(camera["name"])
                save_path = render_path+"\\"+set_collection.name+"\\"+str(camera["name"])+"\\"+str(frame)+".png"
                print(f"saving: {save_path}")
                scene.render.filepath = save_path
                bpy.ops.render.render(write_still = True)
            print(f"Set done: {set_collection.name}, Frame: {frame}")


def main():
    blend_save_path = "" # Replaced by args[2] if provided
    args = get_args()
    # print(f"The args: {args}")
    if len(args) >= 4:
        camera_paths = args[0]
        render_path = args[1]
        base_blend_save_path = args[2]
        epoch = args[3]
        # print(f"Loaded cameras {camera_paths} and Loaded render path {blend_save_path}")
    else:
        print(f"Missing args, expected 4 and only got: {len(args)}")
    camera_sets = read_json(camera_paths)
    
    camera_place(camera_sets)
    save_matrices(render_path)
    # print("rendering")
    render(camera_sets, render_path)
    
    original_path = Path(base_blend_save_path)
    epoch_blend_filename = f"{original_path.stem}_{epoch}{original_path.suffix}"
    epoch_blend_save_path = original_path.with_name(epoch_blend_filename)
    
    print(f"saving modified scene to: {epoch_blend_save_path}")
    # epoch_blend_save_path = Path(blend_save_path+f"_{epoch}")
    # output_path = "camera_excellent.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(epoch_blend_save_path))

if __name__ == '__main__':
    main()