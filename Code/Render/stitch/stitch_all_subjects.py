import numpy as np
import os
import json

def process_all_subjects(json_path, viewer_fps=30):
    with open(json_path, 'r') as f:
        tracking_dictionary = json.load(f)
        
    for subject, actions in tracking_dictionary.items():
        print(f"--- Processing {subject} ---")
        
        out_dict = {}
        trans_list = []
        poses_list = []
        
        first_file = True
        original_fps = 200.0
        
        # Sort actions to ensure consistent ordering A3 -> A9
        for action_name in sorted(actions.keys()):
            reps = actions[action_name]["reps"]
            sources = actions[action_name]["source"]
            
            for i in range(len(reps)):
                start_v, end_v = reps[i]
                
                # e.g., "S3A3D3 Rep 2" -> "S3A3D3" -> "S3A3D3.npz"
                base_filename = sources[i].split()[0] + ".npz"
                filepath = os.path.join(subject, base_filename)
                
                if not os.path.exists(filepath):
                    print(f"Warning: '{filepath}' not found. Skipping...")
                    continue
                
                data = np.load(filepath, allow_pickle=True)
                
                if first_file:
                    original_fps = data.get('mocap_frame_rate', 200.0)
                    for key in ['gender', 'surface_model_type', 'mocap_frame_rate', 'betas', 'num_betas']:
                        if key in data:
                            out_dict[key] = data[key]
                    first_file = False
                    
                scale_factor = original_fps / viewer_fps
                start = int(round(start_v * scale_factor))
                end = int(round(end_v * scale_factor))
                
                if 'trans' in data:
                    trans_list.append(data['trans'][start:end])
                if 'poses' in data:
                    poses_list.append(data['poses'][start:end])
                    
        if not trans_list and not poses_list:
            print(f"Error: No data to stitch for {subject}.")
            continue
            
        if trans_list:
            out_dict['trans'] = np.concatenate(trans_list, axis=0)
        if poses_list:
            out_dict['poses'] = np.concatenate(poses_list, axis=0)
            
        total_frames = out_dict.get('poses', out_dict.get('trans', [])).shape[0]
            
        if total_frames > 0 and 'mocap_frame_rate' in out_dict:
            out_dict['mocap_time_length'] = total_frames / float(out_dict['mocap_frame_rate'])
            
        output_file = f"{subject}_stitched_all.npz"
        print(f"Saving {subject} (Total frames: {total_frames} at {original_fps}fps) to {output_file}...\n")
        np.savez(output_file, **out_dict)

if __name__ == "__main__":
    json_file = "tracking_dictionary.json"
    process_all_subjects(json_file, viewer_fps=30)
