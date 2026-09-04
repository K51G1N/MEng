import bpy
import os
from mathutils import Vector
import json

def write_ground_truth_data(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open (path, 'w') as file:
        json.dump(data, file, indent=4)
        
# def get_all_bone_locations(armature_evaluated):
#     bone_locations = {}
    
#     for bone in armature_evaluated.pose.bones:
#         world_position = armature_evaluated.matrix_world @ bone.head
#         bone_locations[bone.name] = [
#             round(world_position.x, 5),
#             round(world_position.y, 5),
#             round(world_position.z, 5)
#         ]
#     return bone_locations 
    
def get_all_bone_locations(armature_evaluated):
    bone_locations = {}
    
    for bone in armature_evaluated.pose.bones:
        # FIX: bone.matrix contains the fully evaluated, posed transformation matrix.
        # Multiplying by Vector((0, 0, 0)) extracts the exact posed head position in world space.
        world_position = armature_evaluated.matrix_world @ bone.matrix @ Vector((0, 0, 0))
        
        bone_locations[bone.name] = [
            round(world_position.x, 5),
            round(world_position.y, 5),
            round(world_position.z, 5)
        ]
    return bone_locations

def export_keypoints():

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()

    armatures = [object for object in scene.objects if object.type == 'ARMATURE']
            
    for armature in armatures:
        frames = range(scene.frame_start, scene.frame_end +1)
        current_dir = os.path.dirname(bpy.data.filepath)
        ground_truth_filename = armature.name + "_ground_truth.json"
        path = os.path.join(current_dir, ground_truth_filename)
        ground_truth_data = {}
        for frame in frames:
            scene.frame_set(frame)
            armature_evaluated = armature.evaluated_get(depsgraph)
            
            ground_truth_data[str(frame)] = get_all_bone_locations(armature_evaluated)
        write_ground_truth_data(path, ground_truth_data)
        
        
def main():
    export_keypoints()
    
        
#    write_keypoints()    
    
if __name__ == '__main__':
    main()  