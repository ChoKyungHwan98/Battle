"""Key 2 (right hand) for mid range: the original knee-raise and stomp, carried forward by a hop of the support foot.

The original clip is a pitcher-like move: stand on the right foot, raise the left knee, stomp the left foot
down and smash with the right hand. The first step version (AuthorCrunchRightCrossStep) kept that upper body
but planted the left foot and stepped the RIGHT foot through, so the torso wound up for a stomp while the legs
did something else (both legs gathered under the body with the arm overhead) - it read as awkward.

Here the legs do what the clip does. The clip is placed on the combat idle stance (its own first frame has the
feet together and the left foot already lifted, which snapped ~92cm from idle), the left foot follows the clip's
own raise and stomp, and the forward travel comes from the support (right) foot hopping forward once with the
body while the knee is up (a crow hop). The stance after the stomp is nearly the idle stance, so recovery needs
only a small left-foot adjust instead of two large steps.
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
IDLE = util.IDLE
SRC_CARD = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Right'
LAB_CARD = '/Game/BossArena/Boss/AI/Actions/DA_Lab_Right_RightFootStep'
SOURCE = ROOT + '/AS_Crunch_RightCross_Approved_Base'
RIG = v6.RIG
BASE = ROOT + '/AS_Crunch_RightCrossHop_Base'
SEQ = ROOT + '/LS_Crunch_RightCrossHop'
BAKED = ROOT + '/AS_Crunch_RightCrossHop'
MONTAGE = ROOT + '/AM_Crunch_RightCrossHop'
DISPLAY = '왼발 들어 찍기 + 버팀발 홉 · 오른손 (2번 v2)'
REFERENCE_ANIMATION = ROOT + '/AS_Crunch_StepThroughAdvance_LeftSwing'   # key 1 (v9), for comparison only
FPS = 60
PLAN = None
SRC = None

TRAVEL = 55.                       # same body travel as key 1; range is not tuned here
HOP_OFF, HOP_LAND = .07, .26       # support foot leaves and lands while the left knee is up
HOP_HEIGHT = 9.
HOP_EXTRA = 0.                     # extra hop distance that brings the support foot further under the body
STOMP = .40                        # the clip's left foot is down from here (hit window opens at .333)
BODY_START, BODY_END = .06, .30    # the body travels with the hop and has arrived before the stomp
HIP_SCALE = 1.                     # the clip's own hip swing
LEFT_ADJUST = (1.50, 1.85)         # small lifted adjust from the stomp stance to the idle stance
RIGHT_ADJUST = (1.20, 1.45)        # only used when HOP_EXTRA is not zero
IK_FADE = (2.18, 2.29)             # leg IK hands over to the idle pose at the end of the clip
CAP_PELVIS_Z = False
SPINE_SHARE = [('pelvis',1.),('spine_01',2./3.),('spine_02',1./3.),('spine_03',0.)]


def curve(t,keys):
    """Monotone cubic through the keys: no velocity kinks, no overshoot, eased at both ends."""
    if t<=keys[0][0]:return keys[0][1]
    if t>=keys[-1][0]:return keys[-1][1]
    ts,vs = [k[0] for k in keys],[k[1] for k in keys]
    h = [b-a for a,b in zip(ts,ts[1:])]
    d = [(vs[i+1]-vs[i])/h[i] for i in range(len(h))]
    m = [0.]+[0. if d[i-1]*d[i]<=0. else 2.*d[i-1]*d[i]/(d[i-1]+d[i]) for i in range(1,len(d))]+[0.]
    for i in range(len(h)):
        if t<=ts[i+1]:
            s = (t-ts[i])/h[i]
            return (2*s**3-3*s**2+1)*vs[i]+(s**3-2*s**2+s)*h[i]*m[i]\
                +(-2*s**3+3*s**2)*vs[i+1]+(s**3-s**2)*h[i]*m[i+1]
    return vs[-1]


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
    return TRAVEL*common.between(t,BODY_START,BODY_END)


def compression_at(t):
    # The clip's stomp stretches the support leg 2.6% past its length on this stance; sinking 6cm into the
    # stomp absorbs it. Released slowly so the body does not bob.
    return 6.*common.between(t,.30,.40)*(1.-common.between(t,.55,.95))


def shift_at(t):
    """Where the clip sits relative to its own space, so it stands on the idle stance.

    Start: the pelvis is the idle pelvis. Stomp: the clip's support foot coincides with ours. Recovery: back to
    zero, because the clip's last frame is the idle pose itself.
    """
    a = common.between(t,.05,STOMP-.02)
    back = common.between(t,1.25,1.75)
    return PLAN['pelvis_shift']*(1.-a)+PLAN['stomp_shift']*(a*(1.-back))


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


def toe_counter(side,t):
    return 1.      # no authored heel pitch here: the toes keep the clip's own bend


def feet(t,source):
    """Foot goals in component space with the root travel included."""
    delta = unreal.Vector(0.,root_at(t),0.)
    initial = PLAN['initial']
    # Support (right) foot: planted, one low hop forward with the body, planted again.
    right = common.copy_transform(initial['foot_r'])
    if t>HOP_OFF:
        p = min(1.,(t-HOP_OFF)/(HOP_LAND-HOP_OFF))
        right.translation.y += (TRAVEL+HOP_EXTRA)*common.smooth(p)
        right.translation.z += HOP_HEIGHT*math.sin(math.pi*p)**1.3
    if HOP_EXTRA:
        q = common.between(t,*RIGHT_ADJUST)
        right.translation.y -= HOP_EXTRA*q
        right.translation.z += 4.*math.sin(math.pi*q)
    # Striding (left) foot: the clip's own knee raise and stomp, then world-planted where it landed.
    shift = shift_at(t);shift.z = 0.
    clip = common.copy_transform(source['foot_l']);clip.translation += shift+delta
    if t<=STOMP:
        start = common.copy_transform(initial['foot_l']);start.translation += delta
        left = util.blend(start,clip,common.between(t,0.,.10))
    else:
        phase = common.between(t,*LEFT_ADJUST)
        home = common.copy_transform(source['foot_l']);home.translation += delta
        left = util.blend(PLAN['stomp_l'],home,phase)
        left.translation.z += 4.*math.sin(math.pi*phase)
    return {'l':left,'r':right}


def foot_goals(t,source):
    goals = feet(t,source)
    return goals,goals


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
        if name=='pelvis':
            # The clip's pelvis stands more upright than the idle one, which lengthens the planted leg;
            # start from the idle tilt and hand over to the clip by the strike (spine keeps its global rotation).
            g.rotation = PLAN['idle_rot'].slerp_quat(g.rotation,common.between(t,.03,.20))
        g.rotation = yaw_quat(delta*share).multiply(g.rotation)
        if name=='pelvis':
            g.translation += shift_at(t)
            # The clip stands tall (to 124cm) on feet together; on the idle stance the legs cannot follow,
            # so the pelvis is held at the idle height until the clip itself drops below it (~.33s).
            g.translation.z -= max(0.,g.translation.z-PLAN['z_cap'])
            g.translation.z -= compression_at(t)
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
    poles = {s:knee_pole(s,base['thigh_'+s].translation+delta,goals[s],0.) for s in 'lr'}
    return base,delta,goals,poles


def source_pose(time):
    """Pose of the original key-2 montage (windup + 1.6x recovery) at montage time, root rotation carried into its children."""
    pose = None
    for segment in SRC['segments']:
        if time < segment.start_time + segment.duration:
            local_time = segment.anim_start_pos + max(0.,time-segment.start_time) * segment.play_rate
            pose = common.poses(segment.anim_sequence_path,local_time)
            break
    if pose is None:
        last = SRC['segments'][-1]
        pose = common.poses(last.anim_sequence_path,last.anim_end_pos)
    old_root = pose['root']
    canonical_root = common.copy_transform(old_root)
    canonical_root.rotation = unreal.Quat(x=0.,y=0.,z=0.,w=1.)
    # The clip's own root drift (key 2 drifts sideways) must not reach the montage's root motion, which only
    # carries the authored forward travel. Children keep their component-space pose; only their parent frame changes.
    canonical_root.translation = unreal.Vector(0.,0.,0.)
    for name in SRC['root_children']:
        pose[name] = pose[name].multiply(old_root).make_relative(canonical_root)
    pose['root'] = canonical_root
    return pose


def prepare_source():
    """Bake the original key-2 montage into one AnimSequence (the in-place punch as it plays today)."""
    global SRC
    common.require_editor()
    card = unreal.EditorAssetLibrary.load_asset(SRC_CARD)
    montage = card.get_editor_property('Montage')
    segments = list(unreal.AnimMontageService.list_anim_segments(montage.get_path_name(),0))
    assert len(segments)==2
    duration = sum(s.duration for s in segments)
    last = math.ceil(duration*FPS/2)*2          # even endpoint for the project's 30fps compression target
    rig_asset = unreal.EditorAssetLibrary.load_asset(RIG)
    rig_asset.recompile_vm()
    children = [str(k.name) for k in rig_asset.hierarchy.get_bones()
        if str(rig_asset.hierarchy.get_first_parent(k).name)=='root']
    SRC = {'segments':segments,'root_children':children}
    base = util.duplicate(segments[0].anim_sequence_path,SOURCE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    base.set_editor_property('enable_root_motion',False)
    base.set_editor_property('force_root_lock',False)
    samples = [source_pose(f/FPS) for f in range(last+1)]
    controller = base.get_editor_property('controller')
    controller.open_bracket('Bake the original key-2 punch and recovery',False)
    try:
        controller.set_frame_rate(unreal.FrameRate(FPS,1),False)
        controller.set_number_of_frames(unreal.FrameNumber(last),False)
        for name in base.get_editor_property('data_model_interface').get_bone_track_names():
            keys = [p[str(name)] for p in samples]
            assert controller.set_bone_track_keys(name,[p.translation for p in keys],
                [p.rotation for p in keys],[p.scale3d for p in keys],False),name
    finally:controller.close_bracket(False)
    common.save(base)
    print('PREPARED source',SOURCE,'montage',round(duration,3),'s; endpoint',last)


def prepare(left_heel=16.):
    global PLAN
    common.require_editor()
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    rig.recompile_vm()
    assert unreal.EditorAssetLibrary.does_asset_exist(SOURCE),'run prepare_source() first'
    initial = common.poses(IDLE,0.,True)          # the combat idle stance, not the clip's first frame
    ball0 = common.poses(IDLE,0.)['ball_r']
    clip0 = common.poses(SOURCE,0.,True)
    source = unreal.EditorAssetLibrary.load_asset(SOURCE)
    last = round(source.get_play_length()*FPS)
    last += last%2
    stomp = common.poses(SOURCE,STOMP,True)
    # At the stomp the clip's support foot must be where ours is after the hop (minus the body travel).
    ours = initial['foot_r'].translation+unreal.Vector(0.,HOP_EXTRA,0.)
    stomp_shift = ours-stomp['foot_r'].translation;stomp_shift.z = 0.
    PLAN = {'initial':initial,'hip0':hip_yaw(clip0),'toe0':toe_yaw(initial['foot_r'],ball0),
        'pelvis_shift':initial['pelvis'].translation-clip0['pelvis'].translation,
        'stomp_shift':stomp_shift,
        'z_cap':initial['pelvis'].translation.z if CAP_PELVIS_Z else 1e9,
        'idle_rot':initial['pelvis'].rotation,
        'left_heel':left_heel,'pitch_sign':1.,'last_frame':last,'frames':[]}
    landed = common.copy_transform(stomp['foot_l'])
    landed.translation += stomp_shift+unreal.Vector(0.,TRAVEL,0.)
    PLAN['stomp_l'] = landed
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
    print('PREPARED key-2 hop endpoint',last,'stomp at',landed.translation,'stomp_shift',stomp_shift)


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
    weights = [1.-common.between(f.value/FPS,*IK_FADE) for f in frames]   # on from frame 0: the start stance is already the idle one
    for s in 'lr':
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(PLAN['sequence'],PLAN['rig'],
            'leg_'+s+'_ik_weight',frames,weights)
    for label,t in [('대기 자세에서 시작',0.),('버팀발(오른발) 홉 시작',HOP_OFF),('버팀발 착지',HOP_LAND),
            ('왼발 찍기 · 오른손 타격',STOMP),('왼발 자세 정리',LEFT_ADJUST[0])]:
        if label not in {m.label for m in PLAN['sequence'].get_marked_frames()}:
            PLAN['sequence'].add_marked_frame(unreal.MovieSceneMarkedFrame(
                frame_number=unreal.FrameNumber(round(t*FPS)),label=label))
    common.save(PLAN['sequence'])
    channels = PLAN['binding'].find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0].get_all_channels()
    for control in ['root_fk','foot_l_ik','foot_r_ik','knee_l_pole','knee_r_pole']:
        assert any(str(c.get_name()).startswith(control+'.Location.') and len(c.get_keys())==len(frames) for c in channels),control
    print('KEYED knee raise and stomp from the clip, support-foot hop, small left adjust')


def angle_between(a,b):
    q = a.multiply(b.inversed())
    return math.degrees(2*math.acos(min(1.,abs(q.w))))


def smoothness(path):
    """Clunk metrics, identical for v7 and v8 (timing-independent, so pass either animation).

    foot_accel / foot_decel: peak speed-up and slow-down of the right foot in the flight
    (frame to frame, m/s^2): the take-off snap and the landing slap. The flight must cover
    ~180cm in ~0.2s, so these are bounded by the windup limit (a foot that starts earlier reads
    as walking into the punch); v7 measured 304 / 275. stop_accel: peak pelvis acceleration
    after the strike begins. settle_speed: peak left-foot speed in recovery.
    """
    last = round(unreal.EditorAssetLibrary.load_asset(path).get_play_length()*FPS)
    rows = [common.poses(path,f/FPS,True) for f in range(last+1)]
    pos = lambda f,n:rows[f][n].translation
    speed = lambda n,a,b:(pos(b,n)-pos(a,n)).length()*FPS/(b-a)
    ahead = [pos(f,'foot_r').y for f in range(round(.6*FPS))]
    f_land = next(f for f,y in enumerate(ahead) if y>=max(ahead)-1.)
    v = [speed('foot_r',f-1,f+1) for f in range(1,round(.6*FPS))]
    a = [(v[i+1]-v[i])*FPS/100. for i in range(len(v)-1)]
    accel = lambda n,f:(pos(f+2,n)-pos(f,n)*2.+pos(f-2,n)).length()*FPS*FPS/4./100.
    return {'foot_accel_m_s2':round(max(a)),'foot_decel_m_s2':round(-min(a)),
        'landing_seconds':round(f_land/FPS,3),'net_forward_cm':round(pos(last,'root').y-pos(0,'root').y,1),
        'stop_accel_m_s2':round(max(accel('pelvis',f) for f in range(round(.34*FPS),round(.55*FPS)))),
        'settle_speed_cm_s':round(max(speed('foot_l',f,f+2) for f in range(round(1.5*FPS),last-2)))}


def fix_last_key(path,last):
    """The Sequencer export writes the very last key from the animation's end boundary (upper body off by up to
    74 degrees), while every earlier key is exact. The clip is static there, so repeat the previous key."""
    anim = unreal.EditorAssetLibrary.load_asset(path)
    poses = [common.poses(path,f/FPS) for f in range(last)]
    poses.append(poses[-1])
    controller = anim.get_editor_property('controller')
    controller.open_bracket('Repeat the previous key at the final frame',False)
    try:
        for name in anim.get_editor_property('data_model_interface').get_bone_track_names():
            keys = [p[str(name)] for p in poses]
            assert controller.set_bone_track_keys(name,[k.translation for k in keys],
                [k.rotation for k in keys],[k.scale3d for k in keys],False),name
    finally:controller.close_bracket(False)
    common.save(anim)
    print('FIXED final key of',path)


TWIST_CAP = 75.   # shoulder line vs hip line; the approved key-2 clip alone reads 68.8


def bake_validate():
    common.require_editor()
    result = common.bake(PLAN['sequence'],PLAN['binding'],BAKED,PLAN['last_frame'])
    fix_last_key(BAKED,PLAN['last_frame'])
    end = PLAN['last_frame']/FPS
    foot_error,upper_error,twist,planted_r,planted_l = 0.,0.,0.,0.,0.
    ref = {'r0':common.poses(IDLE,0.,True)['ball_r'].translation,
        'r1':common.poses(BAKED,HOP_LAND+.03,True)['ball_r'].translation,
        'l':common.poses(BAKED,STOMP+.03,True)['ball_l'].translation}
    for f in range(PLAN['last_frame']+1):
        t = f/FPS
        actual = common.poses(BAKED,t,True);source = common.poses(SOURCE,t,True)
        if t<=end-.16:
            goals,_ = foot_goals(t,source)
            foot_error = max(foot_error,max((actual['foot_'+s].translation-goals[s].translation).length() for s in 'lr'))
        for n in ['spine_03','head','upperarm_l','lowerarm_l','hand_l','hand_r']:
            upper_error = max(upper_error,angle_between(actual[n].rotation,source[n].rotation))
        shoulders = actual['upperarm_l'].translation-actual['upperarm_r'].translation
        twist = max(twist,abs(wrap(math.degrees(math.atan2(shoulders.y,shoulders.x))-hip_yaw(actual))))
        # Support foot: still before the hop and after it; striding foot: still from the stomp to its adjust.
        if t<=HOP_OFF:planted_r = max(planted_r,(actual['ball_r'].translation-ref['r0']).length())
        if HOP_LAND+.03<=t<=(RIGHT_ADJUST[0] if HOP_EXTRA else end-.16):
            planted_r = max(planted_r,(actual['ball_r'].translation-ref['r1']).length())
        if STOMP+.03<=t<=LEFT_ADJUST[0]:planted_l = max(planted_l,(actual['ball_l'].translation-ref['l']).length())
    first,final = [common.poses(BAKED,t,True) for t in [0.,end]]
    source_end = common.poses(SOURCE,end,True)
    idle = common.poses(IDLE,0.,True)
    shift = unreal.Vector(0.,TRAVEL,0.)
    start_error = max((first[n].translation-idle[n].translation).length() for n in ['pelvis','foot_l','foot_r'])
    end_error = max((final[n].translation-source_end[n].translation-shift).length() for n in ['pelvis','foot_l','foot_r','hand_r'])
    root_end = final['root'].translation.y-first['root'].translation.y
    report = {'source':SOURCE,'foot_goal_error_cm':foot_error,'upper_global_rotation_error_degrees':upper_error,
        'max_shoulder_to_hip_twist_degrees':twist,'support_foot_drift_cm':planted_r,'stomp_foot_drift_cm':planted_l,
        'start_pose_error_cm':start_error,'end_pose_error_cm':end_error,'net_forward_cm':root_end,
        'hop_seconds':[HOP_OFF,HOP_LAND],'stomp_seconds':STOMP,'leg_reach':leg_reach(),
        'left_adjust_cm':(PLAN['stomp_l'].translation-(source_end['foot_l'].translation+shift)).length(),
        'quality_approved':False,'range_tuned':False}
    print('VALIDATION',json.dumps(report,ensure_ascii=False))
    assert foot_error<2. and upper_error<1. and start_error<.1 and end_error<.1,report
    assert planted_r<2. and planted_l<2. and twist<TWIST_CAP and abs(root_end-TRAVEL)<1.,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    previous.mark_full_body(result);common.save(result)
    PLAN['report'] = report
    return report


def integrate():
    common.require_editor()
    # bake() leaves the Sequencer open; its spawnable Crunch at the origin would be copied into PIE, on top of the player.
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    assert 'report' in PLAN
    card = unreal.EditorAssetLibrary.load_asset(SRC_CARD)
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
    lab = util.duplicate(SRC_CARD,LAB_CARD)       # the lab card is the original card with its own montage and range
    before = {'montage':lab.get_editor_property('Montage').get_path_name(),'display':str(lab.get_editor_property('DisplayName'))}
    lab.modify();lab.set_editor_property('Montage',montage)
    lab.set_editor_property('DisplayName',DISPLAY)
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        lab.set_editor_property(name,card.get_editor_property(name))
    lab.set_editor_property('MinDistance',312.)   # stationary reach measured by the designer
    lab.set_editor_property('MaxDistance',385.)   # measured: hits at 385cm, misses at 400cm
    common.save(lab)
    report = {**PLAN['report'],'previous_card':before,'sequence':SEQ,'animation':BAKED,'montage':MONTAGE,'notifies':expected}
    path = Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_right_cross_hop.json'
    if before['montage'].split('.')[0]==MONTAGE and path.exists():
        report['previous_card'] = json.loads(path.read_text(encoding='utf-8')).get('previous_card',before)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED MotionLab card:',str(path))
    return report
