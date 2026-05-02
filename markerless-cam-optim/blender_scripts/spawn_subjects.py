import json
import bpy
import os
import sys
import argparse

# import place_cameras_fin as place_cameras


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def apply_custom_texture(target_mesh, skin_texture_path, clothing_texture_path):
    # Ensure the object has a material slot and a material
    if not target_mesh.data.materials:
        new_mat = bpy.data.materials.new(name="Custom_Material")
        target_mesh.data.materials.append(new_mat)
    
    mat = target_mesh.active_material
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # 1. Create Core Shader Nodes
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (600, 0)
    
    bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf_node.location = (300, 0)
    # Adjust Specular for more realistic skin/cloth blend
    bsdf_node.inputs['Specular IOR Level'].default_value = 0.2 

    # 2. Create the Mix Node (The "Clother")
    # In Blender 3.4+, MixRGB is replaced by ShaderNodeMix
    mix_node = nodes.new(type='ShaderNodeMix')
    mix_node.data_type = 'RGBA'
    mix_node.blend_type = 'MIX'
    mix_node.location = (0, 0)

    # 3. Setup Skin Texture
    if skin_texture_path and os.path.exists(skin_texture_path):
        skin_tex = nodes.new(type='ShaderNodeTexImage')
        skin_tex.image = bpy.data.images.load(skin_texture_path)
        skin_tex.location = (-300, 100)
        skin_tex.label = "Skin Texture"
        links.new(skin_tex.outputs['Color'], mix_node.inputs['A'])
    else:
        print(f"Warning: Skin path missing or invalid: {skin_texture_path}")

    # 4. Setup Clothing Texture
    if clothing_texture_path and os.path.exists(clothing_texture_path):
        cloth_tex = nodes.new(type='ShaderNodeTexImage')
        cloth_tex.image = bpy.data.images.load(clothing_texture_path)
        # Force alpha to be recognized
        cloth_tex.image.alpha_mode = 'STRAIGHT' 
        cloth_tex.location = (-300, -200)
        cloth_tex.label = "Clothing Texture"
        
        # Link Color to B and Alpha to the Factor
        links.new(cloth_tex.outputs['Color'], mix_node.inputs['B'])
        links.new(cloth_tex.outputs['Alpha'], mix_node.inputs['Factor'])
    else:
        print(f"Warning: Clothing path missing or invalid: {clothing_texture_path}")

    # 5. Finalize Connections
    links.new(mix_node.outputs['Result'], bsdf_node.inputs['Base Color'])
    links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
    
    print(f"Textures applied to {target_mesh.name}")

def animate_model(parameters, target_armature):
    """Loads animation and transfers it to the SMPL-X armature."""
    anim_path = parameters.get('animation_path', '')
    if not anim_path or not os.path.exists(anim_path):
        print(f"Animation file not found: {anim_path}")
        return

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.smplx_add_animation(filepath=anim_path)

    anim_source_mesh = bpy.context.active_object
    if not anim_source_mesh:
        return
        
    anim_source_armature = anim_source_mesh.parent

    # Link animation source to target
    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    anim_source_armature.select_set(True)
    bpy.context.view_layer.objects.active = anim_source_armature
    bpy.ops.object.make_links_data(type='ANIMATION')

    # Cleanup temporary source
    bpy.ops.object.select_all(action='DESELECT')
    anim_source_armature.select_set(True)
    for child in anim_source_armature.children:
        child.select_set(True)
    bpy.ops.object.delete()

def create_model(parameters, save_path=None):
    # ... (rest of the setup code)
    # 1. Enable Add-on
    addon_name = "smplx_blender_addon"
    if addon_name not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon_name)

    # 2. Access the Tool Property Group
    # This is the secret sauce for background mode
    wm = bpy.context.window_manager
    tool = wm.smplx_tool 

    # Set properties on the tool directly
    tool.smplx_gender = parameters.get('sex', 'Female').lower() # Must be 'MALE' or 'FEMALE'
    tool.smplx_height = parameters.get('height', 170) / 100    # cm to meters
    tool.smplx_weight = float(parameters.get('weight', 70))
    
    # These flags are often required for the height/weight to actually apply
    tool.smplx_height_fit = True
    tool.smplx_weight_fit = True

    # 3. Trigger Spawn (Now without keyword arguments)
    try:
        bpy.ops.scene.smplx_add_gender()
        print(f"Created model for subject: {parameters.get('subject')}")
    except Exception as e:
        print(f"Failed to spawn SMPL-X: {e}")
        return

    # 4. Get References
    target_mesh = bpy.context.active_object
    if not target_mesh:
        print("Error: No mesh created.")
        return
        
    target_armature = target_mesh.parent

    # 5. Apply Measurements to Shape
    bpy.ops.object.select_all(action='DESELECT')
    target_mesh.select_set(True)
    bpy.context.view_layer.objects.active = target_mesh
    bpy.ops.object.smplx_measurements_to_shape()
    
    target_armature.name = f"{parameters.get('subject', 'S0')}_Armature"

    # 6. Apply Texture and Animation
    apply_custom_texture(target_mesh, parameters.get('texture_path', ''), parameters.get('clothing_path', ''))
    animate_model(parameters, target_armature)

    # 7. Snap to Ground
    try:
        bpy.ops.object.smplx_snap_ground_plane()
    except:
        pass

    # --- SAVING LOGIC ---
    if save_path:
        final_save_path = save_path
    else:
        anim_file = parameters.get('animation_path', 'output.blend')
        base_name = os.path.splitext(os.path.basename(anim_file))[0]
        # Fallback default
        final_save_path = os.path.join(r"C:\Users\20716400\Documents\BlenderProjects", f"{base_name}_front.blend")
    
    print(f"Saving file to: {final_save_path}")
    bpy.ops.wm.save_as_mainfile(filepath=final_save_path)


def main():
    # 1. Parse the arguments passed after '--'
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        print("Error: No arguments passed from Master script.")
        return
        
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject_json', type=str, required=True)
    parser.add_argument('--save_path', type=str, help='Path to save the generated .blend file')
    args = parser.parse_args(argv)

    # 2. Use the dynamically passed JSON path]
    print("********")
    print(args.subject_json)
    json_path = args.subject_json
    print(f"Loading subject parameters from: {json_path}")
    print("********")
    subjects = load_json(json_path)

    if subjects:
        print(f"Loaded {len(subjects)} subjects. Processing first...")
        create_model(subjects[0], save_path=args.save_path)
    else:
        print("JSON is empty or failed to load.")

if __name__ == "__main__":
    main()