"""v4 animation-only correction: retain right step, left foot joins left punch.

Work on a duplicate of v3's editable sequence. Do not retime the base punch,
change the right-foot control, tune attack ranges or alter combat notifies.
Root's existing second weight transfer follows the rescheduled left step;
its endpoint stays unchanged. Knee poles follow the body without extra steps.
"""
import json
import math
from pathlib import Path
import unreal
import vibeue
import AuthorCrunchOriginalStep as v3
import CrunchControlRigAuthoring as common

SEQ = common.ROOT + '/LS_Crunch_LeftStep_WithPunch'
BAKED = common.ROOT + '/AS_Crunch_LeftStep_WithPunch'
MONTAGE = common.ROOT + '/AM_Crunch_LeftStep_WithPunch'
LEFT_START, LEFT_LAND = .56, .78
PLAN = None


def right_channel_values(seq):
    binding = list(seq.get_bindings())[0]
    section = binding.find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0]
    return {str(c.get_name()).rsplit('_',1)[0]:[k.get_value() for k in c.get_keys()]
        for c in section.get_all_channels() if str(c.get_name()).startswith('foot_r_ik.')}


def body_at(t):
    # Preserve preparation and the first transfer; only align the second
    # transfer with the foot. No new travel-distance parameter is introduced.
    preload = 8. * common.between(t,.06,.13) * (1. - common.between(t,.20,.30))
    first = 60. * common.between(t,.02,.50)
    second = (v3.WORLD_TRAVEL / v3.SCALE - 60.) * common.between(t,LEFT_START,LEFT_LAND)
    return preload + first + second


def left_goal(t):
    foot = common.copy_transform(PLAN['idle']['foot_l'])
    phase = common.between(t,LEFT_START,LEFT_LAND)
    foot.translation += unreal.Vector(0.,v3.WORLD_TRAVEL / v3.SCALE * phase,
        12. * math.sin(math.pi * phase))
    return foot


def prepare():
    global PLAN
    common.require_editor()
    seq = v3.duplicate(v3.SEQ,SEQ)
    # A duplicate carries the old bake destination. Retarget its own link
    # before export so Epic's link replacement cannot unlink the v3 output.
    for data in seq.get_editor_property('asset_user_data'):
        if isinstance(data,unreal.LevelSequenceAnimSequenceLink):
            items = list(data.get_editor_property('anim_sequence_links'))
            for item in items:item.set_editor_property('path_to_anim_sequence',
                unreal.SoftObjectPath(BAKED+'.'+BAKED.rsplit('/',1)[1]))
            data.set_editor_property('anim_sequence_links',items)
    binding = list(seq.get_bindings())[0]
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    proxy = next(p for p in unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
        if p.control_rig.get_class() == unreal.EditorAssetLibrary.load_asset(v3.RIG).generated_class())
    rig = proxy.control_rig
    assert unreal.ControlRigSequencerLibrary.is_layered_control_rig(rig)
    idle = common.poses(v3.IDLE,0.,True)
    rig_asset = unreal.EditorAssetLibrary.load_asset(v3.RIG)
    poles = {s:rig_asset.hierarchy.get_global_transform(common.control_key('knee_'+s+'_pole'),True)
        for s in ['l','r']}
    frames = [unreal.FrameNumber(f) for f in range(0,v3.LAST+1,2)]
    right_keys = list(unreal.ControlRigSequencerLibrary.get_local_control_rig_euler_transforms(
        seq,rig,'foot_r_ik',frames))
    PLAN = {'sequence':seq,'binding':binding,'rig':rig,'idle':idle,'poles':poles,
        'right_keys':right_keys,'frames':[]}
    print('PREPARED duplicate',SEQ,'existing right foot and punch retained')


def key_left_step():
    common.require_editor()
    assert PLAN
    previous = v3.PLAN
    v3.PLAN = PLAN
    try:
        for f in range(0,v3.LAST+1,2):
            t = f / v3.FPS
            original = common.poses(v3.BASE,t,True)
            root_delta = unreal.Vector(0.,body_at(t),0.)
            root = common.copy_transform(original['root'])
            root.translation += root_delta
            foot = left_goal(t)
            values = {'root_fk':root.make_relative(original['root']),
                'foot_l_ik':foot.make_relative(original['foot_l'])}
            for side in ['l','r']:
                goal = foot if side=='l' else v3.foot_goal(t,side)
                pole = v3.knee_goal(t,side,original,root_delta,goal)
                values['knee_'+side+'_pole'] = pole.make_relative(PLAN['poles'][side])
            PLAN['frames'].append((f,values))
    finally:
        v3.PLAN = previous
    previous = common.PLAN
    try:
        common.PLAN = PLAN
        common.write_control_keys(['root_fk','foot_l_ik','knee_l_pole','knee_r_pole'])
    finally:
        common.PLAN = previous
    # Replace only the obsolete marker describing the old recovery follow-up.
    seq = PLAN['sequence']
    for i in reversed(range(len(seq.get_marked_frames()))):
        if seq.get_marked_frames()[i].label == '왼발 따라오기':seq.delete_marked_frame(i)
    existing = {m.label for m in seq.get_marked_frames()}
    for label,frame in [('왼발 + 왼손 시작',34),('왼발 착지',47)]:
        if label not in existing:seq.add_marked_frame(unreal.MovieSceneMarkedFrame(
            frame_number=unreal.FrameNumber(frame),label=label))
    common.save(seq)
    frames = [unreal.FrameNumber(f) for f in range(0,v3.LAST+1,2)]
    right_after = list(unreal.ControlRigSequencerLibrary.get_local_control_rig_euler_transforms(
        seq,PLAN['rig'],'foot_r_ik',frames))
    assert right_channel_values(seq)==right_channel_values(unreal.EditorAssetLibrary.load_asset(v3.SEQ)), 'Right-foot keys changed'
    print('KEYED left step during existing punch; right-foot keys unchanged')


def bake_and_validate():
    common.require_editor()
    # Duplicate v3's output as well, preserving asset-level settings and curves.
    output = v3.duplicate(v3.BAKED,BAKED)
    for data in output.get_editor_property('asset_user_data'):
        if isinstance(data,unreal.AnimSequenceLevelSequenceLink):
            data.set_editor_property('path_to_level_sequence',
                unreal.SoftObjectPath(SEQ+'.'+SEQ.rsplit('/',1)[1]))
    result = common.bake(PLAN['sequence'],PLAN['binding'],BAKED,v3.LAST)
    right_error,left_error,rotation_error = 0.,0.,0.
    previous = v3.PLAN
    v3.PLAN = PLAN
    try:
        for f in range(0,109,2):
            t = f / v3.FPS
            pose = common.poses(BAKED,t,True)
            right_error = max(right_error,(pose['foot_r'].translation-v3.foot_goal(t,'r').translation).length())
            left_error = max(left_error,(pose['foot_l'].translation-left_goal(t).translation).length())
            a,b = common.poses(BAKED,t),common.poses(v3.BASE,t)
            for n in ['pelvis','spine_01','hand_l','hand_r']:
                q = a[n].rotation.multiply(b[n].rotation.inversed())
                rotation_error = max(rotation_error,math.degrees(2*math.acos(min(1.,abs(q.w)))))
    finally:
        v3.PLAN = previous
    report = {'right_foot_max_goal_error_cm':right_error,'left_foot_max_goal_error_cm':left_error,
        'preserved_rotation_max_error_degrees':rotation_error,'right_keys_unchanged':True,
        'left_step_animation_seconds':[LEFT_START,LEFT_LAND],
        'range_tuned':False,'damage_tuned':False,'notifies_retimed':False,'quality_approved':False}
    print('POSE_CHECK',json.dumps(report))
    assert right_error<1. and left_error<1. and rotation_error<1.,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    common.save(result)
    PLAN['report'] = report
    return report


def integrate():
    common.require_editor()
    assert PLAN and 'report' in PLAN
    montage = v3.duplicate(v3.MONTAGE,MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    assert len(tracks)==1
    anim_track = tracks[0].get_editor_property('anim_track')
    segments = list(anim_track.get_editor_property('anim_segments'))
    assert len(segments)==1
    segments[0].set_editor_property('anim_reference',unreal.EditorAssetLibrary.load_asset(BAKED))
    anim_track.set_editor_property('anim_segments',segments)
    tracks[0].set_editor_property('anim_track',anim_track)
    montage.modify()
    montage.set_editor_property('slot_anim_tracks',tracks)
    common.save(montage)
    card = unreal.EditorAssetLibrary.load_asset(v3.CARD)
    before = {n:str(card.get_editor_property(n)) for n in
        ['MinDistance','MaxDistance','PlayRate','ImpactTimes','HitWindowEnds','TotalSeconds']}
    card.modify()
    card.set_editor_property('Montage',montage)
    card.set_editor_property('DisplayName','오른발 → 왼발 + 왼손 · 모션 연결 v4')
    common.save(card)
    assert before=={n:str(card.get_editor_property(n)) for n in before}
    after = unreal.AnimMontageService.list_anim_segments(MONTAGE,0)
    assert len(after)==1 and after[0].anim_sequence_path.rsplit('.',1)[0]==BAKED
    report = {**PLAN['report'],'sequence':SEQ,'animation':BAKED,'montage':MONTAGE,
        'unchanged_combat_fields':before}
    path = Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_left_step_v4.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED lab comparison card only; combat fields unchanged',str(path))
    return report
