"""Keys 1 and 2 for mid range (out to 510cm): two running steps into the original attack.

A single step cannot carry the body far enough: the planted leg runs out of length at ~90cm of travel (key 1
stopped at 450cm, key 2 at 385cm). Here both feet move forward by the full travel, once each:

    right foot steps (rear -> front)  ->  left foot steps and lands exactly where the ORIGINAL clip puts it

Both original clips already finish their windup by putting the left foot down (key 1: a short left step with the
left swing, key 2: the knee-raise stomp). So the left step IS the clip's own step, only longer, and from its
landing on the lower body is the original clip moved forward by TRAVEL: same strike stance, same recovery, no
authored recovery steps. The upper body is the approved clip throughout.

The pelvis height is solved, not hand-keyed: the clip stands taller than a stride allows, so the pelvis sinks
just enough to keep both legs inside their length (smoothed), and returns to the clip before the strike.
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
RIG = v6.RIG
ACTIONS = '/Game/BossArena/Boss/AI/Actions/'
FPS = 60
CONFIG = {
    1: dict(source=previous.BASE, src_card=ACTIONS+'DA_Attack_Left', lab_card=ACTIONS+'DA_Lab_Left_RightFootPlant',
        stem='LeftSwingRunIn', display='두 걸음 진입 + 왼손 · 510cm (1번 중거리)',
        travel=136., r=(.02,.17), l=(.17,.385), r_height=14., l_height=16., body=(.02,.31), shift=(.03,.30), stop=300.,
        min_distance=345.),
    2: dict(source=ROOT+'/AS_Crunch_RightCross_Approved_Base', src_card=ACTIONS+'DA_Attack_Right',
        lab_card=ACTIONS+'DA_Lab_Right_RightFootStep',
        stem='RightCrossRunIn', display='두 걸음 진입 + 오른손 · 510cm (2번 중거리)',
        travel=165., heading=15., r=(.02,.16), l=(.165,.36), r_height=14., l_height=30., body=(.02,.35), shift=(.03,.33), stop=280.,
        min_distance=331.),
}
K5 = 1./1.15       # the chain plays the key-1 clip at 1.15x, so the jab's step times scale by this
CONFIG[5] = dict(source=ROOT+'/AS_Crunch_JabJabHook_Approved_Base', src_card=ACTIONS+'DA_Attack_Combo',
    lab_card=ACTIONS+'DA_Lab_Combo_FootStep',
    stem='JabJabHookRunIn', display='두 걸음 진입 잽 + 전진 잽·훅 · 510cm (5번 중거리)',
    travel=136., r=(.02*K5,.17*K5), l=(.17*K5,.385*K5), r_height=14., l_height=16., body=(.02*K5,.31*K5),
    shift=(.03*K5,.30*K5), min_distance=0., stop=300.,
    # Later hits: the clip's own steps made longer. Each foot gains its share only while the clip has it in the air.
    # 2nd hit: the same swing as key 2, so it gets key 2's mid-range entry as is (two strides, 165cm), started
    # from the idle stance the jab's recovery ends in. Hook: its own entry step made longer, plus its switch step.
    # In game the travel of each burst is scaled down to what the distance needs (BossCombatIntentComponent).
    stages=[dict(kind='run', amount=165., stop=280., root=(1.60,2.04), r=(1.62,1.84), l=(1.85,2.14), r_height=14., l_height=30.),
            # The hook steps in on its own windup: the clip's entry step made longer (the right foot also has to
            # pass the left one, 63cm of that stride), then its switch step under the swing. A shuffle step under
            # the 2nd hit's follow-through was tried and rejected by the designer: the boss walked after hit 2 and
            # then the hook itself went in without stepping.
            dict(amount=120., stop=210., root=(2.86,3.24), r=(2.85,3.05), l=(2.92,3.20)),
            dict(amount=45., root=(3.30,3.44), r=(3.33,3.43), l=(3.31,3.47))])
# Key 3 (uppercut): the clip strikes 0.15s in, too soon for two strides, so a lead-in is authored in front of it
# (PREFIX seconds from the idle pose into the clip's first pose) and the boss ducks under while it runs in.
CONFIG[3] = dict(source=ROOT+'/AS_Crunch_UppercutLead_Base',
    clip='/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_03', prefix=.55,
    src_card=ACTIONS+'DA_Attack_Uppercut', lab_card=ACTIONS+'DA_Lab_Uppercut_RunIn',
    stem='UppercutRunIn', display='더킹하며 두 걸음 진입 + 어퍼컷 · 550cm (3번 중거리)',
    # Measured: the uppercut lands with the boss at 283cm and misses at 309cm, so 550cm needs ~280cm of game travel.
    travel=228., r=(.03,.34), l=(.35,.70), r_height=12., l_height=14., body=(.03,.65), shift=(.03,.60),
    min_distance=324., max_distance=550., stop=255., telegraph=.15,
    # The legs stay on IK to the end: handing them back to the clip mid-recovery swung the knees (a clunk at the end).
    ik_hold=True,
    # The clip ends in its own stance, not the idle one. With the whole body on this animation the legs snapped to
    # idle when the montage blended out (the designer's clunk after the move), so a settle back to idle is authored.
    tail=.45, tail_lift=7.,
    duck=dict(depth=26., lean=24., window=(.04,.73)))
# Far half of mid range (about 500..600cm): the same attacks with a longer run-in, as separate assets. The approved
# mid-range versions above stay as they are: stretching them would make the feet slide more at the nearer distances,
# because the game scales the travel down to what the distance needs.
def far(key,stem,card,display,**changes):
    out = dict(CONFIG[key]);out.update(stem=stem,lab_card=ACTIONS+card,display=display,max_distance=600.,**changes)
    return out
CONFIG[11] = far(1,'LeftSwingRunInFar','DA_Lab_Left_RunInFar','도약 진입 + 왼손 · 600cm (1번 중거리 먼 쪽)',travel=211.,min_distance=500.)
# Key 2's clip plants the right foot far forward; 227cm only fits if the left foot leaves before the right one lands
# (a short flight, .12..19): a bounding stride instead of a walking one.
CONFIG[12] = far(2,'RightCrossRunInFar','DA_Lab_Right_RunInFar','도약 진입 + 오른손 · 600cm (2번 중거리 먼 쪽)',travel=227.,
    r=(.02,.19),l=(.12,.36),body=(.02,.30),shift=(.03,.28),min_distance=510.)
CONFIG[13] = far(3,'UppercutRunInFar','DA_Lab_Uppercut_RunInFar','더킹하며 진입 + 어퍼컷 · 600cm (3번 중거리 먼 쪽)',travel=241.,min_distance=545.)
CONFIG[15] = far(5,'JabJabHookRunInFar','DA_Lab_Combo_RunInFar','도약 진입 잽 + 전진 잽·훅 · 600cm (5번 중거리 먼 쪽)',travel=222.,min_distance=490.)
PLANS = {}
CFG = None
PLAN = None
PLANTED_RADIUS = .975      # the idle stance itself reads .971
FLIGHT_RADIUS = .985
SPINE = ['pelvis','spine_01','spine_02','spine_03']


def use(key,**overrides):
    global CFG,PLAN
    CFG = CONFIG[key]
    CFG.update(overrides)
    CFG.update({'key':key,'base':ROOT+'/AS_Crunch_'+CFG['stem']+'_Base','seq':ROOT+'/LS_Crunch_'+CFG['stem'],
        'baked':ROOT+'/AS_Crunch_'+CFG['stem'],'montage':ROOT+'/AM_Crunch_'+CFG['stem']})
    PLAN = PLANS.get(key)
    return CFG


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


def wrap(degrees):
    return (degrees+180.)%360.-180.


def hip_yaw(pose):
    v = pose['thigh_l'].translation-pose['thigh_r'].translation
    return math.degrees(math.atan2(v.y,v.x))


def frame_of(t):
    return round(t*FPS)


def along(amount):
    """Travel vector in component space. Key 2 is played with the boss turned 15 degrees off the target (the
    game aims the diagonal swing that way), so its travel is turned back to run straight at the target."""
    h = math.radians(CFG.get('heading',0.))
    return unreal.Vector(-math.sin(h)*amount,math.cos(h)*amount,0.)


def extra(kind,t):
    """Travel added after the first hit: kind is 'root', 'l' or 'r'."""
    return sum(s['amount']*common.between(t,*s[kind]) for s in CFG.get('stages',[]))


def lift_at(side,t):
    """Foot lift for stages that step a foot the clip keeps on the floor."""
    z = 0.
    for s in CFG.get('stages',[]):
        a,b = s[side]
        if s.get('lift') and a<t<b:z += s['lift']*math.sin(math.pi*(t-a)/(b-a))**1.3
    return z


def total_travel():
    return CFG['travel']+sum(s['amount'] for s in CFG.get('stages',[]))


def in_stage(t,margin=0.):
    for s in CFG.get('stages',[]):
        times = [v for k in ('root','l','r') for v in s[k]]
        if min(times)-margin<=t<=max(times)+margin:return True
    return False


def run_at(t):
    """The later-hit stage that replaces the clip's footwork with two strides, if t is inside it."""
    for i,s in enumerate(CFG.get('stages',[])):
        if s.get('kind')=='run' and s['r'][0]<=t<=s['l'][1]:return i,s
    return None,None


def strides():
    """(right step, left step) time pairs of every two-stride entry."""
    return [(CFG['r'],CFG['l'])]+[(s['r'],s['l']) for s in CFG.get('stages',[]) if s.get('kind')=='run']


def root_at(t):
    return CFG['travel']*common.between(t,*CFG['body'])+extra('root',t)


def shift_at(t):
    """The clip starts leaned back from the idle pose; start on idle and hand over to the clip before the left foot lands."""
    return PLAN['pelvis_shift']*(1.-common.between(t,*CFG['shift']))


def duck_at(t):
    """0..1: how far the boss is ducked under (bob and weave) while it runs in."""
    d = CFG.get('duck')
    if not d:return 0.
    a,b = d['window']
    return common.between(t,a,a+.16)*(1.-common.between(t,b-.16,b))


def prepare_lead(key):
    """Source for a clip that needs a lead-in: PREFIX seconds easing from the idle pose into the clip's first
    pose, then the clip unchanged."""
    common.require_editor()
    use(key)
    P = CFG['prefix']
    clip = unreal.EditorAssetLibrary.load_asset(CFG['clip'])
    length = clip.get_play_length()
    TAIL = CFG.get('tail',0.)
    last = math.ceil((P+length+TAIL)*FPS/2)*2
    rig_asset = unreal.EditorAssetLibrary.load_asset(RIG)
    rig_asset.recompile_vm()
    children = [str(k.name) for k in rig_asset.hierarchy.get_bones()
        if str(rig_asset.hierarchy.get_first_parent(k).name)=='root']
    def canonical(pose):
        """Root at the origin with no rotation; its children keep their component-space pose."""
        old = pose['root']
        root = common.copy_transform(old)
        root.rotation = unreal.Quat(x=0.,y=0.,z=0.,w=1.)
        root.translation = unreal.Vector(0.,0.,0.)
        for name in children:pose[name] = pose[name].multiply(old).make_relative(root)
        pose['root'] = root
        return pose
    idle = canonical(common.poses(IDLE,0.))
    first = canonical(common.poses(CFG['clip'],0.))
    # The first version eased to a standstill on the clip's first pose and then the clip started at full speed:
    # a stop-and-go the designer felt as a clunk. Now the clip's first JOIN seconds are stretched over the whole
    # lead-in with a time curve whose speed reaches 1 exactly where the unchanged clip takes over.
    JOIN = .10
    ending = canonical(common.poses(CFG['clip'],length))
    def pose(t):
        if TAIL and t>P+length:
            w = common.between(t,P+length,P+length+TAIL)
            return {n:util.blend(ending[n],idle[n],w) for n in ending}
        if t>=P+JOIN:return canonical(common.poses(CFG['clip'],min(t-P,length)))
        clip_time = JOIN*(t/(P+JOIN))**((P+JOIN)/JOIN)
        moving = canonical(common.poses(CFG['clip'],clip_time))
        w = common.between(t,.04,P*.85)
        return {n:util.blend(idle[n],moving[n],w) for n in moving}
    base = util.duplicate(CFG['clip'],CFG['source'])
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    base.set_editor_property('enable_root_motion',False)
    base.set_editor_property('force_root_lock',False)
    samples = [pose(f/FPS) for f in range(last+1)]
    controller = base.get_editor_property('controller')
    controller.open_bracket('Lead-in from idle, then the clip',False)
    try:
        controller.set_frame_rate(unreal.FrameRate(FPS,1),False)
        controller.set_number_of_frames(unreal.FrameNumber(last),False)
        for name in base.get_editor_property('data_model_interface').get_bone_track_names():
            keys = [p[str(name)] for p in samples]
            assert controller.set_bone_track_keys(name,[p.translation for p in keys],
                [p.rotation for p in keys],[p.scale3d for p in keys],False),name
    finally:controller.close_bracket(False)
    common.save(base)
    print('PREPARED lead-in source',CFG['source'],'prefix',P,'endpoint',last)


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
    total = 0.
    for (r0,r1),_ in strides():
        d = r1-r0
        total += curve(t,[(r0,0.),(r0+.30*d,26.),(r0+.78*d,-8.),(r1,0.)])     # toes trail, then heel leads into the landing
    return total


def left_pitch(t):
    return sum(curve(t,[(l0-.07,0.),(l0,20.),(l0+.08,0.)]) for _,(l0,_) in strides())   # heel peels before the foot leaves


def toe_counter(side,t):
    if side=='r':return 0. if any(r0<t<r1 for (r0,r1),_ in strides()) else 1.
    return min(1.-common.between(t,l0,l0+.04)*(1.-common.between(t,l1,l1+.04)) for _,(l0,l1) in strides())


def stride(a,b,p,height):
    s = .12*p+.88*common.smooth(p)
    out = util.blend(a,b,s)
    out.translation.z += height*math.sin(math.pi*p)**1.3
    return out


def flat_feet(t,source):
    """Foot goals before heel pitch, in component space with the root travel included."""
    T = along(CFG['travel'])
    initial = PLAN['initial']
    r0,r1 = CFG['r'];l0,l1 = CFG['l']
    # Right foot: planted, one step to where the clip's right foot stands at the strike (+ travel), then the clip.
    if t<=r0:right = common.copy_transform(initial['foot_r'])
    elif t<r1:right = stride(initial['foot_r'],PLAN['land_r'],(t-r0)/(r1-r0),CFG['r_height'])
    elif t<=l1:right = common.copy_transform(PLAN['land_r'])
    else:
        right = common.copy_transform(source['foot_r']);right.translation += T+along(extra('r',t))
        right.translation.z += lift_at('r',t)
    # Left foot: planted while the right foot steps, then one step that ends as the clip's own left-foot landing.
    shift = shift_at(t);shift.z = 0.
    clip = common.copy_transform(source['foot_l'])
    clip.translation += shift+along(root_at(t) if t<l1 else CFG['travel']+extra('l',t))
    if t<=l0:left = common.copy_transform(initial['foot_l'])
    elif t<l1:
        left = stride(initial['foot_l'],PLAN['land_l'],(t-l0)/(l1-l0),CFG['l_height'])
        left.rotation = initial['foot_l'].rotation.slerp_quat(clip.rotation,common.between(t,l0,l0+.10))
        left = util.blend(left,clip,common.between(t,l1-.07,l1))
    else:
        left = clip;left.translation.z += lift_at('l',t)
        if CFG.get('tail'):       # the left foot steps (not slides) back to the idle stance
            start = PLAN['last_frame']/FPS-CFG['tail']
            if start<t<start+CFG['tail']*.8:
                left.translation.z += CFG['tail_lift']*math.sin(math.pi*(t-start)/(CFG['tail']*.8))**1.3
    i,run = run_at(t)
    if run:
        # A later hit entered with two strides: both feet start where they stand and land where the clip has them
        # when its own left foot comes down, moved forward by everything travelled so far.
        plan = PLAN['runs'][i]
        (a0,a1),(b0,b1) = run['r'],run['l']
        if t<a1:right = stride(plan['start_r'],plan['land_r'],(t-a0)/(a1-a0),run['r_height'])
        else:right = common.copy_transform(plan['land_r'])
        if t<=b0:left = common.copy_transform(plan['start_l'])
        else:
            target = common.copy_transform(source['foot_l']);target.translation += along(plan['before']+run['amount'])
            left = stride(plan['start_l'],plan['land_l'],(t-b0)/(b1-b0),run['l_height'])
            left.rotation = plan['start_l'].rotation.slerp_quat(target.rotation,common.between(t,b0,b0+.10))
            left = util.blend(left,target,common.between(t,b1-.07,b1))
    return {'l':left,'r':right}


def airborne(side,t):
    a,b = CFG[side]
    return a<t<b or any(s[side][0]<t<s[side][1] for s in CFG.get('stages',[]))


def authored(t):
    """True where the legs are placed by this script rather than being the clip's own."""
    return t<CFG['l'][1] or in_stage(t)


def foot_goals(t,source,local):
    flat = flat_feet(t,source)
    goals = {'l':pitch_about_ball(flat['l'],local['ball_l'],left_pitch(t)),
        'r':pitch_about_ball(flat['r'],local['ball_r'],right_pitch(t))}
    if 'drop' in PLAN:
        # A foot in the air must still be inside the leg's reach of the hip it hangs from.
        f = min(frame_of(t),PLAN['last_frame'])
        for s in 'lr':
            if not airborne(s,t):continue
            hip = PLAN['hips'][f][s]
            dz = hip.z-PLAN['drop'][f]-goals[s].translation.z
            limit = math.sqrt(max(1.,(PLAN['leg'][s]*FLIGHT_RADIUS)**2-dz*dz))
            dx,dy = goals[s].translation.x-hip.x,goals[s].translation.y-hip.y
            h = math.hypot(dx,dy)
            if h>limit:
                move = unreal.Vector(dx*(limit/h-1.),dy*(limit/h-1.),0.)
                goals[s].translation += move;flat[s].translation += move
                PLAN['clamped'][s] = max(PLAN['clamped'][s],h-limit)
    return goals,flat


def base_pose(t):
    """The approved clip standing on the idle pose at the start, with the solved pelvis height."""
    local = common.poses(CFG['source'],t)
    source = common.poses(CFG['source'],t,True)
    out = {n:common.copy_transform(p) for n,p in local.items()}
    parent = source['root']
    duck = duck_at(t)
    lean = axis_angle(unreal.Vector(-1.,0.,0.),CFG['duck']['lean']*duck) if duck else None
    for name in SPINE:
        g = common.copy_transform(source[name])
        if lean and name!='pelvis':g.rotation = lean.multiply(g.rotation)     # torso bows forward over the hips
        if name=='pelvis':
            if duck:g.translation.z -= CFG['duck']['depth']*duck
            # The clip's pelvis stands more upright than the idle one; start from the idle tilt (the spine keeps
            # its own global rotation, so the upper body is untouched).
            g.rotation = PLAN['idle_rot'].slerp_quat(g.rotation,common.between(t,.03,.20))
            g.translation += shift_at(t)
            # The clip stands taller than the idle pose on feet together; a stride cannot follow that, so the
            # pelvis stays at the idle height until the clip itself comes down for the strike.
            cap = 1.-common.between(t,CFG['l'][1]-.08,CFG['l'][1])
            for (r0,_),(_,l1) in strides()[1:]:
                cap = max(cap,common.between(t,r0-.04,r0+.08)*(1.-common.between(t,l1-.08,l1)))
            g.translation.z -= max(0.,g.translation.z-PLAN['z_cap'])*cap
            if 'drop' in PLAN:g.translation.z -= PLAN['drop'][min(frame_of(t),PLAN['last_frame'])]
        else:g.translation = local[name].multiply(parent).translation
        out[name] = g.make_relative(parent)
        parent = g
    goals,flat = foot_goals(t,source,local)
    for side in 'lr':
        ball = local['ball_'+side]
        level = ball.multiply(flat[side]).make_relative(goals[side])
        level.translation = ball.translation
        out['ball_'+side] = util.blend(ball,level,toe_counter(side,t))
    return out


def hips_of(pose,t):
    pelvis = pose['pelvis'].multiply(pose['root'])
    delta = along(root_at(t))
    return {s:pose['thigh_'+s].multiply(pelvis).translation+delta for s in 'lr'}


def solve_drop():
    """Pelvis sink that keeps planted legs inside PLANTED_RADIUS, smoothed so the body does not bob."""
    last = PLAN['last_frame']
    raw,hips,trouble = [],[],[]
    solve_until = CFG['l'][1]            # from the left landing on, the lower body is the clip itself
    for f in range(last+1):
        t = f/FPS
        pose = base_pose(t)
        hip = hips_of(pose,t);hips.append(hip)
        need = 0.
        if t<=solve_until or in_stage(t):
            goals,_ = foot_goals(t,common.poses(CFG['source'],t,True),common.poses(CFG['source'],t))
            for s in 'lr':
                if airborne(s,t):continue
                if t>solve_until and not run_at(t)[1] and abs(extra(s,t)-extra('root',t))<.5:continue    # the clip's own leg
                off = hip[s]-goals[s].translation
                radius = PLAN['leg'][s]*PLANTED_RADIUS
                h2 = off.x*off.x+off.y*off.y
                if h2>=radius*radius:
                    trouble.append((round(t,3),s,round(math.sqrt(h2),1)));continue
                need = max(need,off.z-math.sqrt(radius*radius-h2))
        raw.append(need)
    assert not trouble,('planted foot out of horizontal reach',trouble[:8])
    w = 8
    envelope = [max(raw[max(0,i-w):i+w+1]) for i in range(len(raw))]
    def box(values,half):
        return [sum(values[max(0,i-half):i+half+1])/len(values[max(0,i-half):i+half+1]) for i in range(len(values))]
    pad = [0.]*16                         # the sink starts from nothing, so the first frame stays the idle pose
    drop = box(box(pad+envelope,4),4)[16:]
    drop = [d*common.smooth(i/5.) for i,d in enumerate(drop)]
    assert all(d>=r-.3 for d,r in zip(drop,raw)),'smoothed sink fell below the requirement'
    PLAN['hips'] = hips;PLAN['drop'] = drop;PLAN['raw_drop'] = raw
    return max(drop)


def knee_pole(side,hip,foot):
    pp = PLAN['initial']
    hip0,knee0,ankle0 = [pp[n+'_'+side].translation for n in ['thigh','calf','foot']]
    axis0 = common.unit_vector(ankle0-hip0)
    bend0 = knee0-hip0-axis0*(knee0-hip0).dot(axis0)
    axis = common.unit_vector(foot.translation-hip)
    bend = bend0-axis*bend0.dot(axis)
    assert bend.length()>.01,'Degenerate knee pole'
    pole = unreal.Transform()
    pole.translation = hip+(foot.translation-hip)*.5+common.unit_vector(bend)*90.
    return pole


def frame_goals(t):
    source = common.poses(CFG['source'],t,True)
    base = common.poses(CFG['base'],t,True)
    delta = along(root_at(t))
    goals,_ = foot_goals(t,source,common.poses(CFG['source'],t))
    poles = {s:knee_pole(s,base['thigh_'+s].translation+delta,goals[s]) for s in 'lr'}
    return base,delta,goals,poles


def leg_reach():
    """Hip-to-ankle distance against leg length while the legs are authored (to the left landing)."""
    worst = {'max_extension':0.}
    for f in range(PLAN['last_frame']+1):
        t = f/FPS
        if not authored(t):continue      # elsewhere it is the clip's own leg
        base,delta,goals,_ = frame_goals(t)
        for s in 'lr':
            if t>=CFG['l'][1] and not run_at(t)[1] and abs(extra(s,t)-extra('root',t))<.5:continue
            ratio = (goals[s].translation-base['thigh_'+s].translation-delta).length()/PLAN['leg'][s]
            if ratio>worst['max_extension']:worst = {'max_extension':ratio,'side':s,'time':t}
    return worst


def build_plan(key,**overrides):
    """Everything prepare() decides before it writes assets: stance, landings, pelvis sink. Returns the max sink."""
    global PLAN
    use(key,**overrides)
    initial = common.poses(IDLE,0.,True)          # the combat idle stance, not the clip's first frame
    ball0 = common.poses(IDLE,0.)['ball_r']
    clip0 = common.poses(CFG['source'],0.,True)
    source = unreal.EditorAssetLibrary.load_asset(CFG['source'])
    last = round(source.get_play_length()*FPS)
    last += last%2
    PLAN = PLANS[key] = {'initial':initial,'pelvis_shift':initial['pelvis'].translation-clip0['pelvis'].translation,
        'idle_rot':initial['pelvis'].rotation,'z_cap':initial['pelvis'].translation.z,'pitch_sign':1.,'last_frame':last,'frames':[],'clamped':{'l':0.,'r':0.},
        'leg':{s:(initial['thigh_'+s].translation-initial['calf_'+s].translation).length()
            +(initial['calf_'+s].translation-initial['foot_'+s].translation).length() for s in 'lr'}}
    if pitch_about_ball(initial['foot_r'],ball0,10.).translation.z<initial['foot_r'].translation.z:
        PLAN['pitch_sign'] = -1.
    landed = common.poses(CFG['source'],CFG['l'][1],True)
    T = along(CFG['travel'])
    for s in 'lr':
        foot = common.copy_transform(landed['foot_'+s]);foot.translation += T
        PLAN['land_'+s] = foot
    PLAN['runs'] = {}
    before = CFG['travel']
    for i,s in enumerate(CFG.get('stages',[])):
        if s.get('kind')=='run':
            start,end = [common.poses(CFG['source'],t,True) for t in (s['r'][0],s['l'][1])]
            plan = {'before':before}
            for side in 'lr':
                a = common.copy_transform(start['foot_'+side]);a.translation += along(before)
                b = common.copy_transform(end['foot_'+side]);b.translation += along(before+s['amount'])
                plan['start_'+side] = a;plan['land_'+side] = b
            PLAN['runs'][i] = plan
        before += s['amount']
    return solve_drop()


def feasible(key,**overrides):
    """Dry run: can the legs make this travel in these step windows? Writes nothing."""
    keep = dict(CONFIG[key])
    try:
        sink = build_plan(key,**overrides)
        return {'ok':True,'max_sink':round(sink,1)}
    except AssertionError as e:
        return {'ok':False,'why':str(e)[:300]}
    finally:
        CONFIG[key].clear();CONFIG[key].update(keep);PLANS.pop(key,None)


def prepare(key,**overrides):
    common.require_editor()
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    rig.recompile_vm()
    sink = build_plan(key,**overrides)
    last = PLAN['last_frame']
    base = util.duplicate(CFG['source'],CFG['base'])
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    samples = [base_pose(f/FPS) for f in range(last+1)]
    c = base.get_editor_property('controller')
    c.open_bracket('Stand the approved attack on the idle pose with the solved pelvis height',False)
    try:
        # An existing base keeps its old length when the source got longer (the lead-in was retimed).
        c.set_frame_rate(unreal.FrameRate(FPS,1),False)
        c.set_number_of_frames(unreal.FrameNumber(last),False)
        for track_name in base.get_editor_property('data_model_interface').get_bone_track_names():
            name = str(track_name)
            poses = [p[name] for p in samples]
            assert c.set_bone_track_keys(name,[p.translation for p in poses],
                [p.rotation for p in poses],[p.scale3d for p in poses],False),name
    finally:c.close_bracket(False)
    common.save(base)
    reach = leg_reach()
    print('REACH',json.dumps(reach),'max_sink',round(sink,1),'clamped',PLAN['clamped'])
    assert reach['max_extension']<1.,reach
    seq,binding = common.create_scene(CFG['seq'],last)
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
    print('PREPARED run-in key',key,'endpoint',last,'right lands',PLAN['land_r'].translation,'left lands',PLAN['land_l'].translation)


def ik_weight(t):
    l1 = CFG['l'][1]
    if CFG.get('ik_hold'):return 1.
    w = 1.-common.between(t,l1+.30,l1+.44)        # afterwards the legs are the original clip's own (after the sink has eased out)
    for s in CFG.get('stages',[]):               # ...except around the lengthened steps of the later hits
        times = [v for k in ('root','l','r') for v in s[k]]
        a,b = min(times)-.30,max(times)+.30
        w = max(w,common.between(t,a,a+.08)*(1.-common.between(t,b-.08,b)))
    return w


def key_step(key):
    common.require_editor()
    use(key)
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
    weights = [ik_weight(f.value/FPS) for f in frames]
    assert all(w>.999 or PLAN['drop'][f.value]<.01 for f,w in zip(frames,weights)),'pelvis sinks where the leg IK is off'
    for s in 'lr':
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(PLAN['sequence'],PLAN['rig'],
            'leg_'+s+'_ik_weight',frames,weights)
    for label,t in [('대기 자세에서 시작',0.),('오른발 떼기',CFG['r'][0]),('오른발 착지',CFG['r'][1]),
            ('왼발 떼기',CFG['l'][0]),('왼발 착지 · 타격 (이후 원본 그대로)',CFG['l'][1])]:
        if label not in {m.label for m in PLAN['sequence'].get_marked_frames()}:
            PLAN['sequence'].add_marked_frame(unreal.MovieSceneMarkedFrame(
                frame_number=unreal.FrameNumber(round(t*FPS)),label=label))
    common.save(PLAN['sequence'])
    channels = PLAN['binding'].find_tracks_by_type(unreal.MovieSceneControlRigParameterTrack)[0].get_sections()[0].get_all_channels()
    for control in ['root_fk','foot_l_ik','foot_r_ik','knee_l_pole','knee_r_pole']:
        assert any(str(c.get_name()).startswith(control+'.Location.') and len(c.get_keys())==len(frames) for c in channels),control
    print('KEYED right step, left step into the clip landing')


def angle_between(a,b):
    q = a.multiply(b.inversed())
    return math.degrees(2*math.acos(min(1.,abs(q.w))))


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


def mark_travel_stop(sequence):
    """TravelStop curve: the centre distance each advance should end at, so the hit after it still has room to
    step in. Read by UBossCombatIntentComponent::UpdateTravelScale when a burst of travel begins."""
    curve = unreal.AnimationCurveIdentifier()
    curve.set_curve_identifier('TravelStop',unreal.RawCurveTrackTypes.RCT_FLOAT)
    controller = sequence.get_editor_property('controller')
    if not unreal.AnimationLibrary.does_curve_exist(sequence,'TravelStop',unreal.RawCurveTrackTypes.RCT_FLOAT):
        assert controller.add_curve(curve)
    steps = [(0.,CFG['stop'])]
    for s in CFG.get('stages',[]):
        if 'stop' in s:steps.append((s['root'][0]-.05,s['stop']))
    keys = [unreal.RichCurveKey(time=t,value=v,interp_mode=unreal.RichCurveInterpMode.RCIM_CONSTANT) for t,v in steps]
    assert controller.set_curve_keys(curve,keys)
    print('MODIFIED TravelStop curve:',steps)
    return steps


def bake_validate(key):
    common.require_editor()
    use(key)
    result = common.bake(PLAN['sequence'],PLAN['binding'],CFG['baked'],PLAN['last_frame'])
    fix_last_key(CFG['baked'],PLAN['last_frame'])
    last = PLAN['last_frame'];end = last/FPS
    r0,r1 = CFG['r'];l0,l1 = CFG['l']
    rows = [common.poses(CFG['baked'],f/FPS,True) for f in range(last+1)]
    foot_error,upper_error,twist,planted_r,planted_l,after = 0.,0.,0.,0.,0.,0.
    T = along(CFG['travel'])
    idle = common.poses(IDLE,0.,True)
    r_ref = rows[frame_of(r1)+2]['ball_r'].translation
    for f in range(last+1):
        t = f/FPS
        actual = rows[f];source = common.poses(CFG['source'],t,True)
        if t<=l1+.05 or in_stage(t):
            goals,_ = foot_goals(t,source,common.poses(CFG['source'],t))
            foot_error = max(foot_error,max((actual['foot_'+s].translation-goals[s].translation).length() for s in 'lr'))
        if t>=l1+.25 and ik_weight(t)<.001:      # the lower body must be the clip itself, moved forward
            moved = along(root_at(t))
            after = max(after,max((actual[n].translation-source[n].translation-moved).length() for n in ['pelvis','foot_l','foot_r','calf_l','calf_r']))
        if not duck_at(t):       # while ducked the torso is bowed on purpose
            for n in ['spine_03','head','upperarm_l','lowerarm_l','hand_l','hand_r']:
                upper_error = max(upper_error,angle_between(actual[n].rotation,source[n].rotation))
        shoulders = actual['upperarm_l'].translation-actual['upperarm_r'].translation
        twist = max(twist,abs(wrap(math.degrees(math.atan2(shoulders.y,shoulders.x))-hip_yaw(actual))))
        if t<=r0:planted_r = max(planted_r,(actual['ball_r'].translation-idle['ball_r'].translation).length())
        if r1+.04<=t<=l1:planted_r = max(planted_r,(actual['ball_r'].translation-r_ref).length())
        if t<=l0-.08:planted_l = max(planted_l,(actual['ball_l'].translation-idle['ball_l'].translation).length())
    speed = lambda n:max((rows[f+1][n].translation-rows[f-1][n].translation).length()*FPS/2. for f in range(1,frame_of(l1)+6))
    accel = lambda n:max((rows[f+2][n].translation-rows[f][n].translation*2.+rows[f-2][n].translation).length()*FPS*FPS/400.
        for f in range(2,frame_of(l1)+12))
    start_error = max((rows[0][n].translation-idle[n].translation).length() for n in ['pelvis','foot_l','foot_r'])
    source_end = common.poses(CFG['source'],end,True)
    end_error = max((rows[last][n].translation-source_end[n].translation-along(total_travel())).length() for n in ['pelvis','foot_l','foot_r','hand_r'])
    root_end = (rows[last]['root'].translation-rows[0]['root'].translation).length()
    report = {'key':key,'source':CFG['source'],'travel_cm':CFG['travel'],'total_travel_cm':total_travel(),'stages':CFG.get('stages',[]),'foot_goal_error_cm':foot_error,
        'upper_global_rotation_error_degrees':upper_error,'max_shoulder_to_hip_twist_degrees':twist,
        'right_foot_drift_cm':planted_r,'left_foot_drift_cm':planted_l,'start_pose_error_cm':start_error,
        'end_pose_error_cm':end_error,'after_landing_vs_clip_cm':after,'net_forward_cm':root_end,
        'right_step_seconds':list(CFG['r']),'left_step_seconds':list(CFG['l']),'leg_reach':leg_reach(),
        'max_pelvis_sink_cm':max(PLAN['drop']),'flight_clamp_cm':PLAN['clamped'],
        'peak_speed_cm_s':{n:round(speed(n)) for n in ['foot_r','foot_l','pelvis']},
        'peak_pelvis_accel_m_s2':round(accel('pelvis')),
        'quality_approved':False}
    print('VALIDATION',json.dumps(report,ensure_ascii=False))
    assert foot_error<2. and upper_error<1. and start_error<.1 and end_error<.1 and after<1.,report
    assert planted_r<2. and planted_l<2. and abs(root_end-total_travel())<1.,report
    result.set_editor_property('enable_root_motion',True)
    result.set_editor_property('force_root_lock',False)
    result.set_editor_property('root_motion_root_lock',unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    previous.mark_full_body(result)
    report['travel_stop_cm'] = mark_travel_stop(result)
    common.save(result)
    PLAN['report'] = report
    return report


def integrate(key,max_distance=None):
    common.require_editor()
    use(key)
    max_distance = max_distance or CFG.get('max_distance',510.)
    # bake() leaves the Sequencer open; its spawnable Crunch at the origin would be copied into PIE, on top of the player.
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    assert 'report' in PLAN
    P = CFG.get('prefix',0.)
    card = unreal.EditorAssetLibrary.load_asset(CFG['src_card'])
    source = card.get_editor_property('Montage')
    montage = util.duplicate(source.get_path_name(),CFG['montage'])
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    track = tracks[0].get_editor_property('anim_track')
    segment = list(track.get_editor_property('anim_segments'))[0]
    duration = source.get_play_length()+P+CFG.get('tail',0.)
    segment.set_editor_property('anim_reference',unreal.EditorAssetLibrary.load_asset(CFG['baked']))
    segment.set_editor_property('anim_end_time',duration)
    segment.set_editor_property('anim_play_rate',1.)
    segment.set_editor_property('cached_play_length',duration)
    track.set_editor_property('anim_segments',[segment]);tracks[0].set_editor_property('anim_track',track)
    montage.modify();montage.set_editor_property('slot_anim_tracks',tracks)
    if P:      # the montage's own length follows the segment only through the service
        common.save(montage)
        assert unreal.AnimMontageService.set_segment_end_position(CFG['montage'],0,0,duration)
    unreal.AnimationLibrary.remove_animation_notify_events_by_name(montage,'ANS_BossAttackStep')
    assert unreal.AnimMontageService.set_enable_root_motion_translation(CFG['montage'],True)
    assert unreal.AnimMontageService.set_enable_root_motion_rotation(CFG['montage'],False)
    expected = [(str(n.notify_name),n.trigger_time+P,n.duration) for n in unreal.AnimMontageService.list_notifies(source.get_path_name()) if n.notify_name!='ANS_BossAttackStep']
    if P:      # every event of the original attack happens PREFIX later
        assert abs(montage.get_play_length()-duration)<.01,montage.get_play_length()
        # Set from the original's times (not relative), so running this again does not shift them twice.
        order = lambda items:sorted(items,key=lambda n:(str(n.notify_name),n.trigger_time))
        originals = order([n for n in unreal.AnimMontageService.list_notifies(source.get_path_name()) if n.notify_name!='ANS_BossAttackStep'])
        for n,o in zip(order(unreal.AnimMontageService.list_notifies(CFG['montage'])),originals):
            assert unreal.AnimMontageService.set_notify_trigger_time(CFG['montage'],n.notify_index,o.trigger_time+P),(str(n.notify_name),o.trigger_time+P)
    common.save(montage)
    actual = [(str(n.notify_name),n.trigger_time,n.duration) for n in unreal.AnimMontageService.list_notifies(CFG['montage'])]
    assert len(actual)==len(expected) and all(a[0]==e[0] and abs(a[1]-e[1])<.002 and abs(a[2]-e[2])<.002
        for a,e in zip(sorted(actual),sorted(expected))),(actual,expected)
    if unreal.EditorAssetLibrary.does_asset_exist(CFG['lab_card']):lab = unreal.EditorAssetLibrary.load_asset(CFG['lab_card'])
    else:lab = util.duplicate(CFG['src_card'],CFG['lab_card'])
    before = {'montage':lab.get_editor_property('Montage').get_path_name(),'display':str(lab.get_editor_property('DisplayName')),
        'min_distance':lab.get_editor_property('MinDistance'),'max_distance':lab.get_editor_property('MaxDistance')}
    lab.modify();lab.set_editor_property('Montage',montage)
    lab.set_editor_property('DisplayName',CFG['display'])
    for name in ['PlayRate','TelegraphSeconds','ImpactTimes','HitWindowEnds','TotalSeconds']:
        lab.set_editor_property(name,card.get_editor_property(name))
    if P:
        # Card times: ImpactTimes and TotalSeconds are real seconds from the telegraph, HitWindowEnds montage seconds.
        rate = card.get_editor_property('PlayRate')
        telegraph = CFG.get('telegraph',card.get_editor_property('TelegraphSeconds'))
        moved = P/rate+telegraph-card.get_editor_property('TelegraphSeconds')
        lab.set_editor_property('TelegraphSeconds',telegraph)
        lab.set_editor_property('ImpactTimes',[v+moved for v in card.get_editor_property('ImpactTimes')])
        lab.set_editor_property('HitWindowEnds',[v+P for v in card.get_editor_property('HitWindowEnds')])
        lab.set_editor_property('TotalSeconds',card.get_editor_property('TotalSeconds')+moved)
    lab.set_editor_property('MinDistance',CFG['min_distance'])
    lab.set_editor_property('MaxDistance',max_distance)
    common.save(lab)
    report = {**PLAN['report'],'previous_card':before,'sequence':CFG['seq'],'animation':CFG['baked'],'montage':CFG['montage'],'notifies':actual}
    path = Path(unreal.Paths.project_saved_dir())/f'VibeUE/Reports/crunch_run_in_key{key}.json'
    if before['montage'].split('.')[0]==CFG['montage'] and path.exists():
        report['previous_card'] = json.loads(path.read_text(encoding='utf-8')).get('previous_card',before)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED MotionLab card:',str(path))
    return report
