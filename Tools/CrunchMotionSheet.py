"""Dump component-space bone positions so a motion can be reviewed as a stick-figure sheet.

Editor side: dump(animation_path, json_path). Renderer: Tools/RenderMotionSheet.py
(plain Python + Pillow, outside the editor).
"""
import json
import unreal

BONES = ['root','pelvis','spine_01','spine_02','spine_03','neck_01','head']
for _side in 'lr':
    BONES += [n+'_'+_side for n in ['clavicle','upperarm','lowerarm','hand','thigh','calf','foot','ball']]


def dump(animation, out_path, fps=60, step=1):
    sequence = unreal.EditorAssetLibrary.load_asset(animation)
    last = round(sequence.get_play_length()*fps)
    frames = []
    for f in range(0,last+1,step):
        pose = {str(p.bone_name):p.transform for p in
            unreal.AnimSequenceService.get_pose_at_time(animation,f/fps,True)}
        row = {'t':f/fps}
        for name in BONES:
            v = pose[name].translation
            row[name] = [v.x,v.y,v.z]
        # Toe direction: the ball bone gives the foot's facing on the floor.
        frames.append(row)
    with open(out_path,'w',encoding='utf-8') as handle:
        json.dump({'animation':animation,'frames':frames},handle)
    print('DUMPED',animation,len(frames),'frames ->',out_path)
