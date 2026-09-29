"""Restore imported Kubold forward displacement in the four Quinn attack clips.

Only local root Y keys change. Pose keys, root rotation/scale, sequence length,
playback rate, notifies, montage joins and shared retargeter are preserved.
"""
import hashlib
import json
import os
import unreal

SUFFIXES = ['Sword_Attack_R', 'Sword_Attack_RL', 'Sword_Attack_RLL', 'Sword_Attack_RLLR']
SOURCE = '/Game/ThirdParty/Kubold/SwordShieldAnimsetPro/Animations/Part2/SwordShieldAnimsetPro_part2_'
TARGET = '/Game/BossArena/Player/Animation/SwordShield/Sequences/Q_SwordShieldAnimsetPro_part2_'
plans = []
objects = ()


def fingerprint(poses):
    # Local transforms of every non-root bone; world transforms necessarily move.
    values = [(str(p.bone_name), p.transform.export_text()) for p in poses if str(p.bone_name) != 'root']
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def prepare():
    global plans, objects
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    # Fixed eight-asset scope; no bulk discovery/load loop.
    objects = (unreal.load_asset(TARGET+SUFFIXES[0]), unreal.load_asset(TARGET+SUFFIXES[1]),
               unreal.load_asset(TARGET+SUFFIXES[2]), unreal.load_asset(TARGET+SUFFIXES[3]),
               unreal.load_asset(SOURCE+SUFFIXES[0]), unreal.load_asset(SOURCE+SUFFIXES[1]),
               unreal.load_asset(SOURCE+SUFFIXES[2]), unreal.load_asset(SOURCE+SUFFIXES[3]))
    assert all(objects)
    plans = []
    for i, suffix in enumerate(SUFFIXES):
        asset = objects[i]
        model = asset.get_editor_property('data_model_interface')
        rate = model.get_frame_rate()
        count = model.get_number_of_keys()
        assert abs(asset.get_play_length()-objects[i+4].get_play_length()) < .001
        keys, source_y, hashes = [], [], []
        for f in range(count):
            time = f*rate.denominator/rate.numerator
            poses = unreal.AnimSequenceService.get_pose_at_time(TARGET+suffix, time, False)
            root = next(p.transform for p in poses if str(p.bone_name) == 'root')
            src = next(p.transform for p in unreal.AnimSequenceService.get_pose_at_time(SOURCE+suffix, time, False)
                       if str(p.bone_name) == 'Root')
            keys.append({'position': root.translation.to_tuple(), 'rotation': root.rotation.to_tuple(),
                         'scale': root.scale3d.to_tuple()})
            source_y.append(src.translation.y)
            hashes.append(fingerprint(poses))
        origin = keys[0]['position'][1]
        restored = [[k['position'][0], origin+y-source_y[0], k['position'][2]]
                    for k,y in zip(keys,source_y)]
        plan = {'suffix': suffix, 'fps': rate.numerator/rate.denominator, 'count': count,
                'keys': keys, 'positions': restored, 'nonroot_hashes': hashes,
                'original_forward_cm': source_y[-1]-source_y[0],
                'before_forward_cm': keys[-1]['position'][1]-origin}
        plans.append(plan)
        print('PREVIEW:', suffix, 'forward cm', round(plan['before_forward_cm'],3),
              '->',round(plan['original_forward_cm'],3),'keys',count)
    out = os.path.join(unreal.Paths.project_saved_dir(),'VibeUE','sword-forward-before.json')
    if not os.path.exists(out):
        with open(out,'w',encoding='utf-8') as f:
            json.dump(plans,f,indent=2)
    return True


def apply():
    assert len(plans) == 4
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    editor = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    results = []
    for asset, plan in zip(objects[:4], plans):
        editor.close_all_editors_for_asset(asset)
        controller = asset.get_editor_property('controller')
        controller.open_bracket('Restore original Kubold forward displacement')
        try:
            assert controller.set_bone_track_keys('root',
                [unreal.Vector(*p) for p in plan['positions']],
                [unreal.Quat(*k['rotation']) for k in plan['keys']],
                [unreal.Vector(*k['scale']) for k in plan['keys']])
        finally:
            controller.close_bracket()
        print('MODIFIED:', TARGET+plan['suffix'], 'root Y keys only')
        for f in range(plan['count']):
            poses = unreal.AnimSequenceService.get_pose_at_time(TARGET+plan['suffix'],f/plan['fps'],False)
            assert fingerprint(poses) == plan['nonroot_hashes'][f], 'Non-root pose changed'
            root = next(p.transform for p in poses if str(p.bone_name) == 'root')
            assert abs(root.translation.y-plan['positions'][f][1]) < .02
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset)
        result = {'path':TARGET+plan['suffix'],'before_forward_cm':plan['before_forward_cm'],
                  'restored_forward_cm':plan['original_forward_cm'],'keys':plan['count'],
                  'nonroot_pose_keys_unchanged':True}
        results.append(result)
        print('VERIFIED:', result)
    with open(os.path.join(unreal.Paths.project_saved_dir(),'VibeUE','sword-forward-restored.json'),'w',encoding='utf-8') as f:
        json.dump(results,f,indent=2)
    return True
