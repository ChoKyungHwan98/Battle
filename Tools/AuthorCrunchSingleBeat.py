"""v5: approved standing punch tempo, one right step on the same beat.

No v3/v4 retimed base, added preparation, or extra left-foot trajectory.
Copy the approved montage's exact source timing into an editable base, layer
right-foot placement and weight transfer, bake, and keep the original FX/hit
times. Source animations/montage and older comparison versions are preserved.
"""
import math
import json
from pathlib import Path
import unreal
import vibeue
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util

ROOT = common.ROOT
BASE = ROOT + '/AS_Crunch_ApprovedPunch_Base'
SEQ = ROOT + '/LS_Crunch_RightStep_SingleBeat'
BAKED = ROOT + '/AS_Crunch_RightStep_SingleBeat'
MONTAGE = ROOT + '/AM_Crunch_RightStep_SingleBeat'
SOURCE_CARD = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Left'
LAB_CARD = util.CARD
FPS = 60
LIFT_START, LAND = .08, .40
RETURN_START, RETURN_END = 1.25, 1.75
PLAN = None


def base_pose(time):
    segments = PLAN['segments']
    pose = None
    for segment in segments:
        if time < segment.start_time + segment.duration:
            local_time = segment.anim_start_pos + max(0.,time-segment.start_time) * segment.play_rate
            pose = common.poses(segment.anim_sequence_path,local_time)
            break
    if pose is None:
        last = segments[-1]
        pose = common.poses(last.anim_sequence_path,last.anim_end_pos)
    # The approved windup changes root yaw from -12.8 to zero. Root-motion
    # extraction locks it to the first frame, which visibly changes the punch
    # when capsule rotation is disabled. Carry that rotation into every direct
    # root child, preserving component-space poses, and extract translation only.
    old_root = pose['root']
    canonical_root = common.copy_transform(old_root)
    canonical_root.rotation = unreal.Quat(x=0.,y=0.,z=0.,w=1.)
    for name in PLAN['root_children']:
        pose[name] = pose[name].multiply(old_root).make_relative(canonical_root)
    pose['root'] = canonical_root
    return pose


def prepare():
    global PLAN
    common.require_editor()
    card = unreal.EditorAssetLibrary.load_asset(SOURCE_CARD)
    montage = card.get_editor_property('Montage')
    segments = list(unreal.AnimMontageService.list_anim_segments(montage.get_path_name(),0))
    assert len(segments)==2
    duration = sum(s.duration for s in segments)
    last_frame = math.ceil(duration*FPS/2)*2
    rig_asset = unreal.EditorAssetLibrary.load_asset(util.RIG)
    rig_asset.recompile_vm()
    children = [str(k.name) for k in rig_asset.hierarchy.get_bones()
        if str(rig_asset.hierarchy.get_first_parent(k).name)=='root']
    PLAN = {'segments':segments,'source_montage':montage,'duration':duration,'last_frame':last_frame,
        'root_children':children}
    # Duplicate only the approved windup, which is not a Sequencer-linked output.
    base = util.duplicate(segments[0].anim_sequence_path,BASE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    base.set_editor_property('enable_root_motion',False)
    base.set_editor_property('force_root_lock',False)
    samples = [base_pose(f/FPS) for f in range(last_frame+1)]
    names = list(base.get_editor_property('data_model_interface').get_bone_track_names())
    controller = base.get_editor_property('controller')
    controller.open_bracket('Preserve approved standing punch timing',False)
    try:
        controller.set_frame_rate(unreal.FrameRate(FPS,1),False)
        controller.set_number_of_frames(unreal.FrameNumber(last_frame),False)
        for name in names:
            keys = [p[str(name)] for p in samples]
            assert controller.set_bone_track_keys(name,[p.translation for p in keys],
                [p.rotation for p in keys],[p.scale3d for p in keys],False)
    finally:
        controller.close_bracket(False)
    common.save(base)
    seq,binding = common.create_scene(SEQ,last_frame)
    section = common.animation_track(binding,base,last_frame)
    params = section.get_editor_property('params');params.force_custom_mode=False
    section.set_editor_property('params',params)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    # Recompile before instantiation even for a reused rig. A deferred compile
    # of the loaded asset can otherwise rebuild the section and discard keys.
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    track = unreal.ControlRigSequencerLibrary.find_or_create_control_rig_track(
        world,seq,rig_asset.generated_class(),binding)
    rig = next(p.control_rig for p in unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
        if p.control_rig.get_class()==rig_asset.generated_class())
    if not unreal.ControlRigSequencerLibrary.is_layered_control_rig(rig):
        assert unreal.ControlRigSequencerLibrary.set_control_rig_layered_mode(track,True)
    track.get_sections()[0].set_range(0,last_frame+1)
    initial = common.poses(BASE,0.,True)
    contact = common.poses(BASE,.41,True)
    landing = common.copy_transform(contact['foot_r'])
    # Author a leading-foot stance from the original footprint, not a hit-range goal.
    landing.translation.y = contact['foot_l'].translation.y + 16.
    landing.translation.z = initial['foot_r'].translation.z
    poles = {s:rig_asset.hierarchy.get_global_transform(common.control_key('knee_'+s+'_pole'),True)
        for s in ['l','r']}
    PLAN.update({'sequence':seq,'binding':binding,'rig':rig,'initial':initial,
        'landing':landing,'poles':poles,'frames':[]})
    common.save(seq)
    print('PREPARED approved timing without prefix',duration,'seconds; endpoint',last_frame)


def root_at(t):
    # One coherent loading gesture, then withdraw during the original recovery.
    return 55. * common.between(t,LIFT_START,LAND) * (1.-common.between(t,RETURN_START,RETURN_END))


def compression_at(t):
    return 6. * common.between(t,.28,.39) * (1.-common.between(t,.55,.85))


def right_goal(t,source):
    if t < LIFT_START:return common.copy_transform(source['foot_r'])
    if t < LAND:
        phase = common.between(t,LIFT_START,LAND)
        initial = common.poses(BASE,LIFT_START,True)['foot_r']
        foot = util.blend(initial,PLAN['landing'],phase)
        foot.translation.z += 18. * math.sin(math.pi*phase)
        return foot
    if t < RETURN_START:return common.copy_transform(PLAN['landing'])
    # Only the same right foot returns; no separately authored left step.
    phase = common.between(t,RETURN_START,RETURN_END)
    foot = util.blend(PLAN['landing'],source['foot_r'],phase)
    foot.translation.z += 9. * math.sin(math.pi*phase)
    return foot


def knee_goal(side,source,hip_delta,foot):
    pp = PLAN['initial']
    hip0,knee0,ankle0 = [pp[n+'_'+side].translation for n in ['thigh','calf','foot']]
    axis0 = common.unit_vector(ankle0-hip0)
    bend0 = common.unit_vector(knee0-hip0-axis0*(knee0-hip0).dot(axis0))
    hip = source['thigh_'+side].translation + hip_delta
    axis = common.unit_vector(foot.translation-hip)
    bend = common.unit_vector(bend0-axis*bend0.dot(axis))
    pole = unreal.Transform();pole.translation=hip+(foot.translation-hip)*.5+bend*90.
    return pole


def key_step():
    common.require_editor()
    assert PLAN
    frames = [unreal.FrameNumber(f) for f in range(0,PLAN['last_frame']+1,2)]
    for f in range(0,PLAN['last_frame']+1,2):
        t = f/FPS
        source = common.poses(BASE,t,True)
        local = common.poses(BASE,t)
        delta = unreal.Vector(0.,root_at(t),0.)
        root = common.copy_transform(source['root']);root.translation += delta
        pelvis = common.copy_transform(local['pelvis'])
        pelvis.translation += source['root'].rotation.unrotate_vector(unreal.Vector(0.,0.,-compression_at(t)))
        values = {'root_fk':root.make_relative(source['root']),
            'pelvis_fk':pelvis.make_relative(local['pelvis'])}
        for side in ['l','r']:
            # Left follows the approved original footprint exactly; the new root
            # is compensated so it cannot carry the supporting foot into a slide.
            foot = common.copy_transform(source['foot_l']) if side=='l' else right_goal(t,source)
            values['foot_'+side+'_ik'] = foot.make_relative(source['foot_'+side])
            pole = knee_goal(side,source,delta+unreal.Vector(0.,0.,-compression_at(t)),foot)
            values['knee_'+side+'_pole'] = pole.make_relative(PLAN['poles'][side])
        PLAN['frames'].append((f,values))
    previous = common.PLAN
    try:
        common.PLAN = PLAN
        common.write_control_keys(list(PLAN['frames'][0][1]))
    finally:
        common.PLAN = previous
    for side in ['l','r']:
        weights = [common.between(f.value/FPS,.0,.06)*(1.-common.between(f.value/FPS,1.75,1.95)) for f in frames]
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(PLAN['sequence'],PLAN['rig'],
            'leg_'+side+'_ik_weight',frames,weights)
    seq = PLAN['sequence']
    for label,frame in [('기존 준비',0),('오른발 들기',5),('오른발 착지 + 왼손 타격',24),
        ('기존 판정 시작',21),('기존 회복',73),('오른발 회수',75)]:
        if label not in {m.label for m in seq.get_marked_frames()}:
            seq.add_marked_frame(unreal.MovieSceneMarkedFrame(frame_number=unreal.FrameNumber(frame),label=label))
    common.save(seq)
    channels = PLAN['binding'].find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0].get_all_channels()
    assert any(str(c.get_name()).startswith('root_fk.Location.Y') and len(c.get_keys())==len(frames)
        for c in channels),'Root keys were not stored'
    print('KEYED one right step, original left footprint, no added upper-body timing')


def bake_validate():
    common.require_editor()
    result = common.bake(PLAN['sequence'],PLAN['binding'],BAKED,PLAN['last_frame'])
    left_error,right_error,upper_error,end_error = 0.,0.,0.,0.
    for f in range(0,PLAN['last_frame']+1,2):
        t=f/FPS
        source=common.poses(BASE,t,True);actual=common.poses(BAKED,t,True)
        if .06 <= t <= 1.75:
            left_error=max(left_error,(actual['foot_l'].translation-source['foot_l'].translation).length())
            right_error=max(right_error,(actual['foot_r'].translation-right_goal(t,source).translation).length())
        a,b=common.poses(BAKED,t),common.poses(BASE,t)
        for n in ['pelvis','spine_01','spine_02','upperarm_l','lowerarm_l','hand_l','hand_r']:
            q=a[n].rotation.multiply(b[n].rotation.inversed())
            upper_error=max(upper_error,math.degrees(2*math.acos(min(1.,abs(q.w)))))
        if f==PLAN['last_frame']:
            end_error=max((actual[n].translation-source[n].translation).length()
                for n in ['pelvis','foot_l','foot_r','hand_l'])
    report={'original_timing_preserved':True,'left_added_step':False,
        'left_original_footprint_max_error_cm':left_error,'right_goal_max_error_cm':right_error,
        'original_upper_rotation_max_error_degrees':upper_error,'end_pose_max_error_cm':end_error,
        'landing_animation_seconds':LAND,'quality_approved':False,'range_tuned':False}
    print('POSE_CHECK',json.dumps(report))
    landing_pose=common.poses(BAKED,LAND,True)
    landing_source=common.poses(BASE,LAND,True)
    assert abs(landing_pose['root'].translation.y-landing_source['root'].translation.y-root_at(LAND))<.1
    assert left_error<1. and right_error<1. and upper_error<1. and end_error<.1,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    common.save(result)
    PLAN['report']=report
    return report


def integrate():
    common.require_editor()
    assert PLAN and 'report' in PLAN
    source=PLAN['source_montage']
    montage=util.duplicate(source.get_path_name(),MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks=list(montage.get_editor_property('slot_anim_tracks'))
    anim_track=tracks[0].get_editor_property('anim_track')
    segments=list(anim_track.get_editor_property('anim_segments'))
    segment=segments[0]
    segment.set_editor_property('anim_reference',unreal.EditorAssetLibrary.load_asset(BAKED))
    segment.set_editor_property('anim_end_time',PLAN['duration'])
    segment.set_editor_property('anim_play_rate',1.)
    segment.set_editor_property('cached_play_length',PLAN['duration'])
    anim_track.set_editor_property('anim_segments',[segment])
    tracks[0].set_editor_property('anim_track',anim_track)
    montage.modify();montage.set_editor_property('slot_anim_tracks',tracks)
    unreal.AnimationLibrary.remove_animation_notify_events_by_name(montage,'ANS_BossAttackStep')
    assert unreal.AnimMontageService.set_enable_root_motion_translation(MONTAGE,True)
    assert unreal.AnimMontageService.set_enable_root_motion_rotation(MONTAGE,False)
    common.save(montage)
    expected=[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(source.get_path_name())
        if n.notify_name!='ANS_BossAttackStep']
    actual=[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(MONTAGE)]
    assert expected==actual,'Source FX/physical windows changed'
    card=unreal.EditorAssetLibrary.load_asset(LAB_CARD)
    base=unreal.EditorAssetLibrary.load_asset(SOURCE_CARD)
    before={'montage':card.get_editor_property('Montage').get_path_name(),
        'display':str(card.get_editor_property('DisplayName'))}
    card.modify();card.set_editor_property('Montage',montage)
    card.set_editor_property('DisplayName','오른발 디딤 + 왼손 · 원래 템포 v5')
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        card.set_editor_property(name,base.get_editor_property(name))
    common.save(card)
    report={**PLAN['report'],'previous_card':before,'source_montage':source.get_path_name(),
        'sequence':SEQ,'animation':BAKED,'montage':MONTAGE,
        'physical_notify_animation_seconds':expected[-1][1],
        'combat_timing_copied_from':SOURCE_CARD,'new_fx_times':actual}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_single_beat_v5.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED MotionLab card; approved tempo and notifies restored',str(path))
    return report
