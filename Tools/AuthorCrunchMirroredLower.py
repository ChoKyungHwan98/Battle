"""v6: mirror Crunch's own first lower-body movement, keep the left punch.

The foot and knee trajectories come from the approved clip, not a generated
lift arc. Native MirrorPose reference-axis corrections preserve mechanical
bone orientations. Originals and v5 stay intact; only MotionLab is connected.
"""
import json
import math
from pathlib import Path
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util
import AuthorCrunchSingleBeat as previous

ROOT = common.ROOT
SOURCE = previous.BASE
BASE = ROOT + '/AS_Crunch_MirroredLower_Base'
RIG = ROOT + '/CR_Crunch_MirroredLower'
SEQ = ROOT + '/LS_Crunch_MirroredLower_LeftSwing'
BAKED = ROOT + '/AS_Crunch_MirroredLower_LeftSwing'
MONTAGE = ROOT + '/AM_Crunch_MirroredLower_LeftSwing'
PLAN = None
FPS = 60


def mirror_vector(v):
    return unreal.Vector(-v.x,v.y,v.z)


def mirror_quat(q):
    return unreal.Quat(x=q.x,y=-q.y,z=-q.z,w=q.w)


def donor_name(name):
    if name.endswith('_r'):return name[:-2]+'_l'
    if name.endswith('_l'):return name[:-2]+'_r'
    return name


def mirror_local(pose,name):
    """UE 5.8 AnimationRuntime.cpp MirrorTransform, mirrored across X."""
    donor = donor_name(name)
    refs,parents = PLAN['refs'],PLAN['parents']
    sp,tp = refs[parents[donor]].rotation,refs[parents[name]].rotation
    sb,tb = refs[donor].rotation,refs[name].rotation
    t = common.copy_transform(pose[donor])
    t.translation = tp.unrotate_vector(mirror_vector(sp.rotate_vector(t.translation)))
    t.rotation = tp.inversed().multiply(mirror_quat(sp.multiply(t.rotation)))\
        .multiply(mirror_quat(sb).inversed()).multiply(tb)
    return t


def lower_weight(t):
    return common.between(t,.02,.28)*(1.-common.between(t,1.10,1.65))


def component_pose(local):
    out = {}
    for name in PLAN['names']:
        parent = PLAN['parents'][name]
        out[name] = local[name].multiply(out[parent]) if parent in out else local[name]
    return out


def lower_pose(t):
    source = common.poses(SOURCE,t)
    desired = {n:common.copy_transform(p) for n,p in source.items()}
    for name in PLAN['lower_names']:
        desired[name] = util.blend(source[name],mirror_local(source,name),lower_weight(t))
    original_global = component_pose(source)
    new_global = component_pose(desired)
    # Counter the mirrored hips at the waist. The original punch's global
    # rotations and its shape relative to the pelvis remain unchanged.
    spine = common.copy_transform(original_global['spine_01'])
    spine.translation += new_global['pelvis'].translation-original_global['pelvis'].translation
    desired['spine_01'] = spine.make_relative(new_global['pelvis'])
    return desired


def mirror_global(source,donor,target):
    t = common.copy_transform(source[donor])
    t.translation = mirror_vector(t.translation)
    refs = PLAN['refs']
    t.rotation = mirror_quat(t.rotation).multiply(mirror_quat(refs[donor].rotation).inversed())\
        .multiply(refs[target].rotation)
    return t


def right_goal(t,source,root_delta):
    # Match the existing rear-right start stance, then release only that
    # offset as the original left-foot lift/plant unfolds.
    goal = mirror_global(source,'foot_l','foot_r')
    goal.translation += root_delta + PLAN['right_start_offset']*(1.-common.between(t,.02,.28))
    correction = PLAN['right_start_rotation'].slerp_quat(
        unreal.Quat(x=0.,y=0.,z=0.,w=1.),common.between(t,.02,.28))
    goal.rotation = correction.multiply(goal.rotation)
    original = common.copy_transform(source['foot_r']);original.translation += root_delta
    return util.blend(goal,original,common.between(t,1.10,1.65))


def knee_pole(side,source,base,delta,foot,t):
    hip = base['thigh_'+side].translation+delta
    if side=='r':
        knee = mirror_vector(source['calf_l'].translation)+delta\
            +PLAN['right_knee_offset']*(1.-common.between(t,.02,.28))
        knee += (base['calf_r'].translation+delta-knee)*common.between(t,1.10,1.65)
    else:
        knee = base['calf_l'].translation+delta
    axis = common.unit_vector(foot.translation-hip)
    bend = knee-hip-axis*(knee-hip).dot(axis)
    assert bend.length()>.01,'Degenerate knee pole'
    pole = unreal.Transform()
    pole.translation = hip+(foot.translation-hip)*.5+common.unit_vector(bend)*90.
    return pole


def prepare():
    global PLAN
    common.require_editor()
    rig = util.duplicate(util.RIG,RIG)
    # UE duplication can copy graph links without rebuilding each pin's
    # transient link cache. Reload this saved, generated rig before compiling;
    # never add a second copy of an existing edge to repair that cache.
    if any(link.get_source_pin() not in link.get_target_pin().get_linked_source_pins()
            for graph in rig.get_all_models() for link in graph.get_links()):
        common.save(rig)
        reloaded,error = unreal.EditorLoadingAndSavingUtils.reload_packages(
            [rig.get_outermost()],unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
        assert reloaded and not str(error),str(error)
        rig = unreal.EditorAssetLibrary.load_asset(RIG)
    for graph in rig.get_all_models():
        edges=[(link.get_source_pin().get_pin_path(),link.get_target_pin().get_pin_path())
            for link in graph.get_links()]
        assert len(edges)==len(set(edges)),graph.get_name()
        assert all(link.get_source_pin() in link.get_target_pin().get_linked_source_pins()
            for link in graph.get_links()),graph.get_name()
    rig.recompile_vm();common.save(rig)
    keys = list(rig.hierarchy.get_bones())
    names = [str(k.name) for k in keys]
    PLAN = {'names':names,
        'parents':{str(k.name):str(rig.hierarchy.get_first_parent(k).name) for k in keys},
        'refs':{str(k.name):rig.hierarchy.get_global_transform(k,True) for k in keys},
        'lower_names':[n for n in names if n=='pelvis' or n.startswith(('hip_','thigh_','calf_','foot_','ball_'))]}
    source = unreal.EditorAssetLibrary.load_asset(SOURCE)
    last = round(source.get_play_length()*FPS)
    last += last%2
    base = util.duplicate(SOURCE,BASE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    samples = [lower_pose(f/FPS) for f in range(last+1)]
    c = base.get_editor_property('controller')
    c.open_bracket('Mirror original Crunch lower body and preserve punch',False)
    try:
        for track_name in base.get_editor_property('data_model_interface').get_bone_track_names():
            name = str(track_name)
            poses = [p[name] for p in samples]
            assert c.set_bone_track_keys(name,[p.translation for p in poses],
                [p.rotation for p in poses],[p.scale3d for p in poses],False),name
    finally:c.close_bracket(False)
    common.save(base)
    seq,binding = common.create_scene(SEQ,last)
    section = common.animation_track(binding,base,last)
    params = section.get_editor_property('params');params.force_custom_mode=False
    section.set_editor_property('params',params)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    track = unreal.ControlRigSequencerLibrary.find_or_create_control_rig_track(
        world,seq,rig.generated_class(),binding)
    instance = next(p.control_rig for p in unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
        if p.control_rig.get_class()==rig.generated_class())
    if not unreal.ControlRigSequencerLibrary.is_layered_control_rig(instance):
        assert unreal.ControlRigSequencerLibrary.set_control_rig_layered_mode(track,True)
    track.get_sections()[0].set_range(0,last+1)
    initial = common.poses(SOURCE,0.,True)
    mirrored_initial = mirror_global(initial,'foot_l','foot_r')
    PLAN.update({'sequence':seq,'binding':binding,'rig':instance,'last_frame':last,
        'initial':initial,'frames':[],
        'right_start_offset':initial['foot_r'].translation-mirrored_initial.translation,
        'right_start_rotation':initial['foot_r'].rotation.multiply(mirrored_initial.rotation.inversed()),
        'right_knee_offset':initial['calf_r'].translation-mirror_vector(initial['calf_l'].translation),
        'poles':{s:rig.hierarchy.get_global_transform(common.control_key('knee_'+s+'_pole'),True) for s in ['l','r']}})
    common.save(seq)
    print('PREPARED v6 lower bones',PLAN['lower_names'],'endpoint',last)


def key_step():
    common.require_editor()
    for f in range(0,PLAN['last_frame']+1,2):
        t=f/FPS
        source = common.poses(SOURCE,t,True)
        base = common.poses(BASE,t,True)
        delta = unreal.Vector(0.,previous.root_at(t),0.)
        root = common.copy_transform(base['root']);root.translation+=delta
        right = right_goal(t,source,delta)
        left = util.blend(PLAN['initial']['foot_l'],source['foot_l'],common.between(t,1.25,1.90))
        values = {'root_fk':root.make_relative(base['root'])}
        for side,foot in [('l',left),('r',right)]:
            values['foot_'+side+'_ik'] = foot.make_relative(base['foot_'+side])
            pole = knee_pole(side,source,base,delta,foot,t)
            values['knee_'+side+'_pole'] = pole.make_relative(PLAN['poles'][side])
        PLAN['frames'].append((f,values))
    before = common.PLAN
    try:
        common.PLAN=PLAN;common.write_control_keys(list(PLAN['frames'][0][1]))
    finally:common.PLAN=before
    frames=[unreal.FrameNumber(f) for f,_ in PLAN['frames']]
    weights=[common.between(f.value/FPS,0.,.06)*(1.-common.between(f.value/FPS,1.75,1.95)) for f in frames]
    for side in ['l','r']:
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(PLAN['sequence'],PLAN['rig'],
            'leg_'+side+'_ik_weight',frames,weights)
    for label,frame in [('기존 준비 자세',0),('원본 하체 반전',17),('오른발 착지 · 기존 왼손',24),('기존 회복 연결',100)]:
        if label not in {m.label for m in PLAN['sequence'].get_marked_frames()}:
            PLAN['sequence'].add_marked_frame(unreal.MovieSceneMarkedFrame(frame_number=unreal.FrameNumber(frame),label=label))
    common.save(PLAN['sequence'])
    channels=PLAN['binding'].find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0].get_all_channels()
    for control in ['root_fk','foot_l_ik','foot_r_ik','knee_l_pole','knee_r_pole']:
        assert any(str(c.get_name()).startswith(control+'.Location.') and len(c.get_keys())==len(frames) for c in channels),control
    print('KEYED mirrored source foot/knee, planted left support, preserved root travel')


def bake_validate():
    common.require_editor()
    result=common.bake(PLAN['sequence'],PLAN['binding'],BAKED,PLAN['last_frame'])
    foot_error,rotation_error,start_error,end_error=0.,0.,0.,0.
    for f in range(0,PLAN['last_frame']+1,2):
        t=f/FPS;actual=common.poses(BAKED,t,True);source=common.poses(SOURCE,t,True)
        delta=unreal.Vector(0.,previous.root_at(t),0.)
        if .06<=t<=1.75:
            goals={'foot_r':right_goal(t,source,delta),
                'foot_l':util.blend(PLAN['initial']['foot_l'],source['foot_l'],common.between(t,1.25,1.90))}
            foot_error=max(foot_error,max((actual[n].translation-goal.translation).length() for n,goal in goals.items()))
        for n in ['spine_01','spine_02','upperarm_l','lowerarm_l','hand_l','hand_r']:
            q=actual[n].rotation.multiply(source[n].rotation.inversed())
            rotation_error=max(rotation_error,math.degrees(2*math.acos(min(1.,abs(q.w)))))
        if f==0:start_error=max((actual[n].translation-source[n].translation).length() for n in ['pelvis','foot_l','foot_r','hand_l'])
        if f==PLAN['last_frame']:end_error=max((actual[n].translation-source[n].translation).length() for n in ['pelvis','foot_l','foot_r','hand_l'])
    report={'source':SOURCE,'mirrored_lower_bones':PLAN['lower_names'],
        'foot_goal_error_cm':foot_error,'upper_global_rotation_error_degrees':rotation_error,
        'start_pose_error_cm':start_error,'end_pose_error_cm':end_error,
        'generated_lift_arc':False,'new_left_step':False,'quality_approved':False,'range_tuned':False}
    print('VALIDATION',json.dumps(report,ensure_ascii=False))
    assert foot_error<2. and rotation_error<1. and start_error<.1 and end_error<.1,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    previous.mark_full_body(result);common.save(result)
    PLAN['report']=report
    return report


def integrate():
    common.require_editor()
    assert 'report' in PLAN
    card=unreal.EditorAssetLibrary.load_asset(previous.SOURCE_CARD)
    source=card.get_editor_property('Montage')
    montage=util.duplicate(source.get_path_name(),MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks=list(montage.get_editor_property('slot_anim_tracks'))
    track=tracks[0].get_editor_property('anim_track')
    segment=list(track.get_editor_property('anim_segments'))[0]
    duration=source.get_play_length()
    segment.set_editor_property('anim_reference',unreal.EditorAssetLibrary.load_asset(BAKED))
    segment.set_editor_property('anim_end_time',duration)
    segment.set_editor_property('anim_play_rate',1.)
    segment.set_editor_property('cached_play_length',duration)
    track.set_editor_property('anim_segments',[segment]);tracks[0].set_editor_property('anim_track',track)
    montage.modify();montage.set_editor_property('slot_anim_tracks',tracks)
    unreal.AnimationLibrary.remove_animation_notify_events_by_name(montage,'ANS_BossAttackStep')
    assert unreal.AnimMontageService.set_enable_root_motion_translation(MONTAGE,True)
    assert unreal.AnimMontageService.set_enable_root_motion_rotation(MONTAGE,False)
    common.save(montage)
    expected=[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(source.get_path_name()) if n.notify_name!='ANS_BossAttackStep']
    assert expected==[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(MONTAGE)]
    lab=unreal.EditorAssetLibrary.load_asset(previous.LAB_CARD)
    before={'montage':lab.get_editor_property('Montage').get_path_name(),'display':str(lab.get_editor_property('DisplayName'))}
    lab.modify();lab.set_editor_property('Montage',montage)
    lab.set_editor_property('DisplayName','원본 하체 반전 + 왼손 · v6')
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        lab.set_editor_property(name,card.get_editor_property(name))
    common.save(lab)
    report={**PLAN['report'],'previous_card':before,'sequence':SEQ,'animation':BAKED,'montage':MONTAGE,'notifies':expected}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_mirrored_lower_v6.json'
    if before['montage'].split('.')[0]==MONTAGE:
        recorded=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        rollback=recorded.get('previous_card',{})
        if rollback.get('montage','').split('.')[0]==MONTAGE or not rollback:
            rollback={'montage':previous.MONTAGE+'.'+previous.MONTAGE.rsplit('/',1)[1],
                'display':'오른발 디딤 + 왼손 · 원래 템포 v5'}
        report['previous_card']=rollback
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED MotionLab card:',str(path))
    return report
