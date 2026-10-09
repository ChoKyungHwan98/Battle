"""v7: rear right foot steps through on the punch's own beat.

v6 moved the right foot during the windup and mirrored the pelvis, which
twisted the waist ~130 degrees under the preserved punch. Here the windup stays
planted, the foot flies only while the original punch explodes (0.22-0.385s),
the hips keep a reduced share of their original swing, and both recovery foot
moves are lifted steps rather than ground slides. Originals and v5/v6 stay
intact; only MotionLab is connected.
"""
import json
import math
from pathlib import Path
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util
import AuthorCrunchSingleBeat as previous
import AuthorCrunchMirroredLower as v6

ROOT = common.ROOT
SOURCE = previous.BASE
RIG = v6.RIG
BASE = ROOT + '/AS_Crunch_StepThrough_Base'
SEQ = ROOT + '/LS_Crunch_StepThrough_LeftSwing'
BAKED = ROOT + '/AS_Crunch_StepThrough_LeftSwing'
MONTAGE = ROOT + '/AM_Crunch_StepThrough_LeftSwing'
DISPLAY = '오른발 디딤 + 왼손 · 한 박자 v7'
FPS = 60
PLAN = None

TRAVEL = 55.                       # same body travel as v5/v6; range is not tuned here
PEEL_START, TOE_OFF, LAND = .12, .22, .385
LAND_X, LAND_AHEAD, LAND_TOE_YAW = -52., 82., 105.   # ahead of the planted left foot; toe 15 degrees out
HIP_SCALE = .47                    # share of the original hip swing kept under the punch
RETURN_OFF, RETURN_HOME = 1.20, 1.62
LEFT_ADJUST = (1.80, 1.98)
SPINE_SHARE = [('pelvis',1.),('spine_01',2./3.),('spine_02',1./3.),('spine_03',0.)]


def curve(t,keys):
    if t<=keys[0][0]:return keys[0][1]
    for (t0,v0),(t1,v1) in zip(keys,keys[1:]):
        if t<=t1:return v0+(v1-v0)*common.between(t,t0,t1)
    return keys[-1][1]


def axis_angle(axis,degrees):
    half = math.radians(degrees)*.5
    s = math.sin(half)
    return unreal.Quat(x=axis.x*s,y=axis.y*s,z=axis.z*s,w=math.cos(half))


def yaw_quat(degrees):
    return axis_angle(unreal.Vector(0.,0.,1.),degrees)


def wrap(degrees):
    return (degrees+180.)%360.-180.


def hip_yaw(pose):
    v = pose['thigh_l'].translation-pose['thigh_r'].translation
    return math.degrees(math.atan2(v.y,v.x))


def root_at(t):
    return TRAVEL*common.between(t,.20,.39)*(1.-common.between(t,1.25,1.75))


def compression_at(t):
    # The planted front leg is already straight in the approved windup, so the
    # coil sits slightly deeper; the lunge then lands lower than the standing
    # stomp and absorbs the landing.
    return 4.*common.between(t,.02,.12)*(1.-common.between(t,.20,.30))\
        +15.*common.between(t,.30,.40)*(1.-common.between(t,.42,.62))


def hip_weight(t):
    return 1.-common.between(t,1.15,1.60)


def toe_yaw(foot,ball_local):
    toe = ball_local.multiply(foot).translation-foot.translation
    return math.degrees(math.atan2(toe.y,toe.x))


def pitch_about_ball(foot,ball_local,degrees):
    """Raise the heel around the ball joint so the toes keep their floor contact."""
    if abs(degrees)<1e-4:return common.copy_transform(foot)
    ball = ball_local.multiply(foot).translation
    toe = ball-foot.translation;toe.z=0.
    q = axis_angle(common.unit_vector(toe).cross(unreal.Vector(0.,0.,1.)),degrees*PLAN['pitch_sign'])
    out = common.copy_transform(foot)
    out.rotation = q.multiply(foot.rotation)
    out.translation = ball+q.rotate_vector(foot.translation-ball)
    return out


def right_pitch(t):
    return curve(t,[(PEEL_START,0.),(TOE_OFF,20.),(.28,32.),(.36,5.),(LAND,0.),
        (1.12,0.),(RETURN_OFF+.02,12.),(1.45,10.),(RETURN_HOME,0.)])


def left_pitch(t):
    return curve(t,[(.28,0.),(.40,PLAN['left_heel']),(1.15,PLAN['left_heel']),(1.40,0.)])


def toe_counter(side,t):
    # Toes stay on the floor while the heel peels; in the air they follow the foot.
    if side=='l':return 1.
    return curve(t,[(TOE_OFF,1.),(.27,0.),(1.12,0.),(1.14,1.),(RETURN_OFF,1.),(RETURN_OFF+.06,0.)])


def flat_feet(t,source):
    """Foot goals before heel pitch, in the travelled component space."""
    delta = unreal.Vector(0.,root_at(t),0.)
    initial,landing = PLAN['initial'],PLAN['landing']
    home_l = common.copy_transform(source['foot_l']);home_l.translation+=delta
    home_r = common.copy_transform(source['foot_r']);home_r.translation+=delta
    # Left: planted support, then one small lifted adjust to the original end stance.
    phase = common.between(t,*LEFT_ADJUST)
    left = util.blend(initial['foot_l'],home_l,phase)
    left.translation.z += 5.*math.sin(math.pi*phase)
    # Right: planted through the windup, one flight on the punch, lifted return.
    if t<=TOE_OFF:
        right = common.copy_transform(initial['foot_r'])
    elif t<LAND:
        p = (t-TOE_OFF)/(LAND-TOE_OFF)
        s = .5*p+.5*common.smooth(p)
        right = util.blend(initial['foot_r'],landing,s)
        right.translation.z += 18.*math.sin(math.pi*p)**.9
    elif t<=RETURN_OFF:
        right = common.copy_transform(landing)
    else:
        q = common.between(t,RETURN_OFF,RETURN_HOME)
        right = util.blend(landing,PLAN['home_r'],q)
        right.rotation = landing.rotation.slerp_quat(source['foot_r'].rotation,q)
        right.translation.z += 12.*math.sin(math.pi*q)
        right = util.blend(right,home_r,common.between(t,1.50,1.76))
    return {'l':left,'r':right}


def foot_goals(t,source):
    flat = flat_feet(t,source)
    local = common.poses(SOURCE,t)
    return {'l':pitch_about_ball(flat['l'],local['ball_l'],left_pitch(t)),
        'r':pitch_about_ball(flat['r'],local['ball_r'],right_pitch(t))},flat


def base_pose(t):
    """Approved punch with a reduced hip swing; the twist is spread over the spine."""
    local = common.poses(SOURCE,t)
    source = common.poses(SOURCE,t,True)
    swing = wrap(hip_yaw(source)-PLAN['hip0'])
    delta = (HIP_SCALE-1.)*swing*hip_weight(t)
    out = {n:common.copy_transform(p) for n,p in local.items()}
    parent = source['root']
    for name,share in SPINE_SHARE:
        g = common.copy_transform(source[name])
        g.rotation = yaw_quat(delta*share).multiply(g.rotation)
        if name=='pelvis':g.translation.z -= compression_at(t)
        else:g.translation = local[name].multiply(parent).translation
        out[name] = g.make_relative(parent)
        parent = g
    goals,flat = foot_goals(t,source)
    for side in 'lr':
        ball = local['ball_'+side]
        level = ball.multiply(flat[side]).make_relative(goals[side])
        level.translation = ball.translation
        out['ball_'+side] = util.blend(ball,level,toe_counter(side,t))
    return out


def knee_pole(side,hip,foot,toe_turn):
    pp = PLAN['initial']
    hip0,knee0,ankle0 = [pp[n+'_'+side].translation for n in ['thigh','calf','foot']]
    axis0 = common.unit_vector(ankle0-hip0)
    bend0 = yaw_quat(toe_turn).rotate_vector(knee0-hip0-axis0*(knee0-hip0).dot(axis0))
    axis = common.unit_vector(foot.translation-hip)
    bend = bend0-axis*bend0.dot(axis)
    assert bend.length()>.01,'Degenerate knee pole'
    pole = unreal.Transform()
    pole.translation = hip+(foot.translation-hip)*.5+common.unit_vector(bend)*90.
    return pole


def frame_goals(t):
    source = common.poses(SOURCE,t,True)
    base = common.poses(BASE,t,True)
    delta = unreal.Vector(0.,root_at(t),0.)
    goals,_ = foot_goals(t,source)
    ball = common.poses(SOURCE,t)['ball_r']
    turn = {'l':0.,'r':wrap(toe_yaw(flat_feet(t,source)['r'],ball)-PLAN['toe0'])}
    poles = {s:knee_pole(s,base['thigh_'+s].translation+delta,goals[s],turn[s]) for s in 'lr'}
    return base,delta,goals,poles


def prepare(left_heel=16.):
    global PLAN
    common.require_editor()
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    rig.recompile_vm()
    initial = common.poses(SOURCE,0.,True)
    ball0 = common.poses(SOURCE,0.)['ball_r']
    source = unreal.EditorAssetLibrary.load_asset(SOURCE)
    last = round(source.get_play_length()*FPS)
    last += last%2
    PLAN = {'initial':initial,'hip0':hip_yaw(initial),'toe0':toe_yaw(initial['foot_r'],ball0),
        'left_heel':left_heel,'pitch_sign':1.,'last_frame':last,'frames':[]}
    if pitch_about_ball(initial['foot_r'],ball0,10.).translation.z<initial['foot_r'].translation.z:
        PLAN['pitch_sign'] = -1.
    landing = common.copy_transform(initial['foot_r'])
    landing.rotation = yaw_quat(wrap(LAND_TOE_YAW-PLAN['toe0'])).multiply(landing.rotation)
    landing.translation = unreal.Vector(LAND_X,initial['foot_l'].translation.y+LAND_AHEAD,
        initial['foot_r'].translation.z)
    home = common.copy_transform(common.poses(SOURCE,RETURN_HOME,True)['foot_r'])
    home.translation.z = initial['foot_r'].translation.z
    PLAN.update({'landing':landing,'home_r':home})
    base = util.duplicate(SOURCE,BASE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    samples = [base_pose(f/FPS) for f in range(last+1)]
    c = base.get_editor_property('controller')
    c.open_bracket('Reduce hip swing under the preserved punch',False)
    try:
        for track_name in base.get_editor_property('data_model_interface').get_bone_track_names():
            name = str(track_name)
            poses = [p[name] for p in samples]
            assert c.set_bone_track_keys(name,[p.translation for p in poses],
                [p.rotation for p in poses],[p.scale3d for p in poses],False),name
    finally:c.close_bracket(False)
    common.save(base)
    reach = leg_reach()
    print('REACH',json.dumps(reach))
    # The approved start pose itself holds the front leg at 0.99-1.01.
    assert reach['max_extension']<1.,reach
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
    PLAN.update({'sequence':seq,'binding':binding,'rig':instance,
        'poles':{s:rig.hierarchy.get_global_transform(common.control_key('knee_'+s+'_pole'),True) for s in 'lr'}})
    common.save(seq)
    print('PREPARED v7 endpoint',last,'landing',landing.translation,'toe0',PLAN['toe0'])


def leg_reach():
    """Hip-to-ankle distance against leg length; a full stretch pops the knee."""
    pp = PLAN['initial']
    length = {s:(pp['thigh_'+s].translation-pp['calf_'+s].translation).length()
        +(pp['calf_'+s].translation-pp['foot_'+s].translation).length() for s in 'lr'}
    worst = {'max_extension':0.}
    for f in range(PLAN['last_frame']+1):
        t = f/FPS
        base,delta,goals,_ = frame_goals(t)
        for s in 'lr':
            ratio = (goals[s].translation-base['thigh_'+s].translation-delta).length()/length[s]
            if ratio>worst['max_extension']:worst = {'max_extension':ratio,'side':s,'time':t}
    return worst


def key_step():
    common.require_editor()
    PLAN['frames'] = []
    for f in range(PLAN['last_frame']+1):
        base,delta,goals,poles = frame_goals(f/FPS)
        root = common.copy_transform(base['root']);root.translation+=delta
        values = {'root_fk':root.make_relative(base['root'])}
        for s in 'lr':
            values['foot_'+s+'_ik'] = goals[s].make_relative(base['foot_'+s])
            values['knee_'+s+'_pole'] = poles[s].make_relative(PLAN['poles'][s])
        PLAN['frames'].append((f,values))
    before = common.PLAN
    try:
        common.PLAN=PLAN;common.write_control_keys(list(PLAN['frames'][0][1]))
    finally:common.PLAN=before
    frames = [unreal.FrameNumber(f) for f,_ in PLAN['frames']]
    weights = [common.between(f.value/FPS,0.,.06)*(1.-common.between(f.value/FPS,2.00,2.10)) for f in frames]
    for s in 'lr':
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(PLAN['sequence'],PLAN['rig'],
            'leg_'+s+'_ik_weight',frames,weights)
    for label,t in [('기존 준비 · 양발 고정',0.),('오른발 뒤꿈치 들기',PEEL_START),('오른발 이지',TOE_OFF),
            ('오른발 착지 · 왼손 타격',LAND),('오른발 회수',RETURN_OFF),('왼발 자세 정리',LEFT_ADJUST[0])]:
        if label not in {m.label for m in PLAN['sequence'].get_marked_frames()}:
            PLAN['sequence'].add_marked_frame(unreal.MovieSceneMarkedFrame(
                frame_number=unreal.FrameNumber(round(t*FPS)),label=label))
    common.save(PLAN['sequence'])
    channels = PLAN['binding'].find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0].get_all_channels()
    for control in ['root_fk','foot_l_ik','foot_r_ik','knee_l_pole','knee_r_pole']:
        assert any(str(c.get_name()).startswith(control+'.Location.') and len(c.get_keys())==len(frames) for c in channels),control
    print('KEYED planted windup, single right flight, lifted recovery steps')


def angle_between(a,b):
    q = a.multiply(b.inversed())
    return math.degrees(2*math.acos(min(1.,abs(q.w))))


def bake_validate():
    common.require_editor()
    result = common.bake(PLAN['sequence'],PLAN['binding'],BAKED,PLAN['last_frame'])
    foot_error,upper_error,twist,planted_r,planted_l = 0.,0.,0.,0.,0.
    ball0 = {s:common.poses(SOURCE,0.,True)['ball_'+s].translation for s in 'lr'}
    for f in range(PLAN['last_frame']+1):
        t = f/FPS
        actual = common.poses(BAKED,t,True);source = common.poses(SOURCE,t,True)
        if .06<=t<=2.:
            goals,_ = foot_goals(t,source)
            foot_error = max(foot_error,max((actual['foot_'+s].translation-goals[s].translation).length() for s in 'lr'))
        for n in ['spine_03','head','upperarm_l','lowerarm_l','hand_l','hand_r']:
            upper_error = max(upper_error,angle_between(actual[n].rotation,source[n].rotation))
        shoulders = actual['upperarm_l'].translation-actual['upperarm_r'].translation
        twist = max(twist,abs(wrap(math.degrees(math.atan2(shoulders.y,shoulders.x))-hip_yaw(actual))))
        if .06<=t<=TOE_OFF:planted_r = max(planted_r,(actual['ball_r'].translation-ball0['r']).length())
        if .06<=t<=LEFT_ADJUST[0]:planted_l = max(planted_l,(actual['ball_l'].translation-ball0['l']).length())
    first,final = [common.poses(BAKED,t,True) for t in [0.,PLAN['last_frame']/FPS]]
    ends = [common.poses(SOURCE,t,True) for t in [0.,PLAN['last_frame']/FPS]]
    start_error,end_error = [max((a[n].translation-b[n].translation).length() for n in ['pelvis','foot_l','foot_r','hand_l'])
        for a,b in [(first,ends[0]),(final,ends[1])]]
    report = {'source':SOURCE,'foot_goal_error_cm':foot_error,'upper_global_rotation_error_degrees':upper_error,
        'max_shoulder_to_hip_twist_degrees':twist,'right_toe_drift_before_toe_off_cm':planted_r,
        'left_toe_drift_while_supporting_cm':planted_l,'start_pose_error_cm':start_error,'end_pose_error_cm':end_error,
        'toe_off_seconds':TOE_OFF,'landing_seconds':LAND,'leg_reach':leg_reach(),
        'quality_approved':False,'range_tuned':False}
    print('VALIDATION',json.dumps(report,ensure_ascii=False))
    assert foot_error<2. and upper_error<1. and start_error<.1 and end_error<.1,report
    # Shoulder line includes the punching clavicle; the approved clip alone reads 42, v6 read 140.
    assert planted_r<2. and planted_l<2. and twist<70.,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    previous.mark_full_body(result);common.save(result)
    PLAN['report'] = report
    return report


def integrate():
    common.require_editor()
    assert 'report' in PLAN
    card = unreal.EditorAssetLibrary.load_asset(previous.SOURCE_CARD)
    source = card.get_editor_property('Montage')
    montage = util.duplicate(source.get_path_name(),MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    track = tracks[0].get_editor_property('anim_track')
    segment = list(track.get_editor_property('anim_segments'))[0]
    duration = source.get_play_length()
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
    expected = [(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(source.get_path_name()) if n.notify_name!='ANS_BossAttackStep']
    assert expected==[(n.notify_name,n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(MONTAGE)]
    lab = unreal.EditorAssetLibrary.load_asset(previous.LAB_CARD)
    before = {'montage':lab.get_editor_property('Montage').get_path_name(),'display':str(lab.get_editor_property('DisplayName'))}
    lab.modify();lab.set_editor_property('Montage',montage)
    lab.set_editor_property('DisplayName',DISPLAY)
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        lab.set_editor_property(name,card.get_editor_property(name))
    common.save(lab)
    report = {**PLAN['report'],'previous_card':before,'sequence':SEQ,'animation':BAKED,'montage':MONTAGE,'notifies':expected}
    path = Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_step_through_v7.json'
    if before['montage'].split('.')[0]==MONTAGE and path.exists():
        report['previous_card'] = json.loads(path.read_text(encoding='utf-8')).get('previous_card',before)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED MotionLab card:',str(path))
    return report
