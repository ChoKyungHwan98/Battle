"""MotionLab v3: Crunch original animation plus a sparse layered correction.

Run inside Unreal through MCP, with PIE stopped. Original Crunch animations,
the v2 authoring scene and Arena action definitions are never overwritten.
The base is a duplicate: original local poses, retiming and explicit seam blends.
Only root travel, a small pelvis compression, foot goals and stable knee poles
are keyed on the additive rig. Original pelvis rotation remains untouched.
"""
import json
import math
from pathlib import Path
import unreal
import vibeue
import CrunchControlRigAuthoring as common

ROOT = common.ROOT
SOURCE = common.SOURCE
RECOVERY = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_01_Recovery'
IDLE = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Idle_Combat'
BASE = ROOT + '/AS_Crunch_LeftSwing_OriginalBase'
RIG = ROOT + '/CR_Crunch_OriginalStep'
SEQ = ROOT + '/LS_Crunch_LeftSwing_OriginalStep'
BAKED = ROOT + '/AS_Crunch_LeftSwing_OriginalStep'
MONTAGE = ROOT + '/AM_Crunch_LeftSwing_OriginalStep'
CARD = '/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant'
FPS, LAST = 60, 132  # even endpoint for the project's 30fps compression target
WORLD_TRAVEL, SCALE = 205., 1.3
LAND, HIT_START, HIT_END = .56, .61, .81
PLAN = None


def blend(a, b, weight):
    result = unreal.Transform()
    result.translation = a.translation + (b.translation - a.translation) * weight
    result.rotation = a.rotation.slerp_quat(b.rotation, weight)
    result.scale3d = a.scale3d + (b.scale3d - a.scale3d) * weight
    return result


def base_pose(t, cache):
    """Keep local bone geometry untouched through the actual original punch."""
    idle = cache[(IDLE, 0.)]
    if t < .16:
        original = cache[(SOURCE, 0.)]
        w = common.between(t, 0., .16)
        return {n: blend(idle[n], original[n], w) for n in idle}
    source_time = .18 * common.between(t, .16, LAND) if t < LAND else .18 + (t - LAND) / 1.5
    if t <= .96:
        return common.poses(SOURCE, source_time)
    if t < 1.08:
        a = cache[(SOURCE, .18 + (.96 - LAND) / 1.5)]
        b = cache[(RECOVERY, 0.)]
        w = common.between(t, .96, 1.08)
        return {n: blend(a[n], b[n], w) for n in a}
    recovery = common.poses(RECOVERY, min(1.4666667, (t - 1.08) * 1.6))
    w = common.between(t, 1.76, LAST / FPS)
    return {n: blend(recovery[n], idle[n], w) for n in recovery}


def duplicate(source, destination):
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        return unreal.EditorAssetLibrary.load_asset(destination)
    obj = unreal.EditorAssetLibrary.duplicate_asset(source, destination)
    assert obj, destination
    print('CREATED duplicate', source, '->', destination)
    return obj


def prepare():
    global PLAN
    common.require_editor()
    cache = {(p, t): common.poses(p, t) for p, t in
        [(IDLE, 0.), (SOURCE, 0.), (SOURCE, .18 + (.96 - LAND) / 1.5), (RECOVERY, 0.)]}
    original = unreal.EditorAssetLibrary.load_asset(SOURCE)
    base = duplicate(SOURCE, BASE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(base)
    base.modify()
    base.set_editor_property('enable_root_motion', False)
    base.set_editor_property('force_root_lock', False)
    samples = [base_pose(f / FPS, cache) for f in range(LAST + 1)]
    model = base.get_editor_property('data_model_interface')
    controller = base.get_editor_property('controller')
    names = list(model.get_bone_track_names())
    controller.open_bracket('Crunch original pose retiming and entry/recovery seams', False)
    try:
        controller.set_frame_rate(unreal.FrameRate(FPS, 1), False)
        controller.set_number_of_frames(unreal.FrameNumber(LAST), False)
        for name in names:
            keys = [s[str(name)] for s in samples]
            assert controller.set_bone_track_keys(name, [t.translation for t in keys],
                [t.rotation for t in keys], [t.scale3d for t in keys], False), str(name)
    finally:
        controller.close_bracket(False)
    common.save(base)
    rig_asset = duplicate(common.RIG, RIG)
    # A duplicated RigVM asset needs an explicit compile before its new
    # generated class is used by Sequencer; otherwise the base can export alone.
    rig_asset.recompile_vm()
    common.save(rig_asset)
    seq, binding = common.create_scene(SEQ, LAST)
    animation_section = common.animation_track(binding, base, LAST)
    params = animation_section.get_editor_property('params')
    # Allow Sequencer's layered rig anim instance to evaluate the correction.
    params.force_custom_mode = False
    animation_section.set_editor_property('params',params)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    track = unreal.ControlRigSequencerLibrary.find_or_create_control_rig_track(
        world, seq, rig_asset.generated_class(), binding)
    rigs = unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
    rig = next(p.control_rig for p in rigs if p.control_rig.get_class() == rig_asset.generated_class())
    if not unreal.ControlRigSequencerLibrary.is_layered_control_rig(rig):
        assert unreal.ControlRigSequencerLibrary.set_control_rig_layered_mode(track, True)
    sections = list(track.get_sections())
    assert len(sections) == 1
    section = sections[0]
    section.set_range(0, LAST + 1)
    assert not any(c.get_keys() for c in section.get_all_channels()), 'Do not erase existing authoring keys'
    # Unkeyed transform controls remain additive identity: original poses run
    # through Backwards Solve, with no pelvis/spine/arm overrides at all.
    idle_global = common.poses(IDLE, 0., True)
    poles = {s: rig_asset.hierarchy.get_global_transform(common.control_key('knee_' + s + '_pole'), True)
        for s in ['l', 'r']}
    PLAN = {'sequence': seq, 'binding': binding, 'rig': rig, 'track': track,
        'section': section, 'samples': samples, 'idle': idle_global, 'poles': poles,
        'frames': [], 'cache': cache}
    common.save(seq)
    print('PREPARED original duplicate + native layered rig', len(names), 'base tracks')
    return 1


def travel_at(t):
    # Retain the original hip advance instead of adding a full root advance to
    # it. Carry the remaining travel with the single trailing-foot step.
    preload = 8. * common.between(t,.06,.13) * (1. - common.between(t,.20,.30))
    return preload + 60. * common.between(t, .02, .50) + (WORLD_TRAVEL / SCALE - 60.) * common.between(t, .80, 1.30)


def compression_at(t):
    return 10. * common.between(t,.50,.63) * (1. - common.between(t,.75,.96))


def foot_goal(t, side):
    initial = PLAN['idle']['foot_' + side]
    foot = common.copy_transform(initial)
    phase = common.between(t, .18, LAND) if side == 'r' else common.between(t, .86, 1.30)
    lift = 18. if side == 'r' else 8.
    foot.translation = initial.translation + unreal.Vector(
        0., WORLD_TRAVEL / SCALE * phase, lift * math.sin(math.pi * phase))
    return foot


def knee_goal(t, side, original_global, root_delta, foot):
    """Use a stable bend hemisphere; avoid automatic 180-degree pole flips."""
    idle = PLAN['idle']
    hip0, knee0, ankle0 = [idle[n + '_' + side].translation for n in ['thigh', 'calf', 'foot']]
    axis0 = common.unit_vector(ankle0 - hip0)
    bend0 = common.unit_vector(knee0 - hip0 - axis0 * (knee0 - hip0).dot(axis0))
    hip = original_global['thigh_' + side].translation + root_delta
    axis = common.unit_vector(foot.translation - hip)
    bend = common.unit_vector(bend0 - axis * bend0.dot(axis))
    pole = unreal.Transform()
    pole.translation = hip + (foot.translation - hip) * .5 + bend * 90.
    return pole


def key_step():
    assert PLAN
    common.require_editor()
    seq, rig = PLAN['sequence'], PLAN['rig']
    controls = {n: [] for n in ['root_fk', 'pelvis_fk', 'foot_l_ik', 'foot_r_ik', 'knee_l_pole', 'knee_r_pole']}
    frames = [unreal.FrameNumber(f) for f in range(0, LAST + 1, 2)]
    for f in range(0, LAST + 1, 2):
        t = f / FPS
        global_pose = common.poses(BASE, t, True)
        root_delta = unreal.Vector(0., travel_at(t), 0.)
        desired_root = common.copy_transform(global_pose['root'])
        desired_root.translation += root_delta
        values = {'root_fk': desired_root.make_relative(global_pose['root'])}
        # Local translation only: keep the source's hip turn and all torso keys.
        original_local = common.poses(BASE,t)
        pelvis = common.copy_transform(original_local['pelvis'])
        compression = global_pose['root'].rotation.unrotate_vector(unreal.Vector(0.,0.,-compression_at(t)))
        pelvis.translation += compression
        values['pelvis_fk'] = pelvis.make_relative(original_local['pelvis'])
        for side in ['l', 'r']:
            foot = foot_goal(t, side)
            values['foot_' + side + '_ik'] = foot.make_relative(global_pose['foot_' + side])
            pole = knee_goal(t, side, global_pose, root_delta, foot)
            values['knee_' + side + '_pole'] = pole.make_relative(PLAN['poles'][side])
        PLAN['frames'].append((f, values))
    # Reuse the tested Euler-unwrapping setter, with an isolated PLAN.
    previous = common.PLAN
    try:
        common.PLAN = PLAN
        common.write_control_keys(list(controls))
    finally:
        common.PLAN = previous
    for side in ['l', 'r']:
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(seq, rig,
            'leg_' + side + '_ik_weight', frames, [1. - common.between(f.value / FPS, 1.80, 2.20) for f in frames])
    for label, frame in [('원본 준비', 0), ('오른발 내딛기', 11), ('오른발 착지', 34),
            ('왼손 판정 시작', 37), ('왼손 판정 종료', 49), ('왼발 따라오기', 52), ('대기 연결', 132)]:
        if label not in {m.label for m in seq.get_marked_frames()}:
            seq.add_marked_frame(unreal.MovieSceneMarkedFrame(frame_number=unreal.FrameNumber(frame), label=label))
    counts = {str(c.get_name()):len(c.get_keys()) for c in PLAN['section'].get_all_channels() if c.get_keys()}
    assert counts and not any('spine' in n or 'hand' in n for n in counts)
    common.save(seq)
    print('KEYED sparse layer', len(counts), 'channels; source hip rotation retained, spine/arms have zero keys')
    return counts


def bake():
    assert PLAN
    common.require_editor()
    result = common.bake(PLAN['sequence'], PLAN['binding'], BAKED, LAST)
    result.set_editor_property('enable_root_motion', False)  # sample raw geometry before enabling extraction
    return result


def validate():
    """Geometry checks are technical evidence, not artistic quality approval."""
    common.require_editor()
    result = unreal.EditorAssetLibrary.load_asset(BAKED)
    original_flag = result.get_editor_property('enable_root_motion')
    result.set_editor_property('enable_root_motion', False)
    max_foot, max_preserved, max_length = 0., 0., 0.
    lengths = {}
    reference = unreal.EditorAssetLibrary.load_asset(RIG).hierarchy
    for side in ['l','r']:
        pp = {n:reference.get_global_transform(common.bone_key(n),True)
            for n in ['thigh_'+side,'calf_'+side,'foot_'+side]}
        lengths[side] = ((pp['thigh_' + side].translation - pp['calf_' + side].translation).length(),
            (pp['calf_' + side].translation - pp['foot_' + side].translation).length())
    try:
        for f in range(0, LAST + 1, 2):
            t = f / FPS
            local, global_pose = common.poses(BAKED, t), common.poses(BAKED, t, True)
            original = common.poses(BASE, t)
            for n in ['pelvis', 'spine_01', 'spine_02', 'spine_03', 'upperarm_l', 'lowerarm_l', 'hand_l', 'hand_r']:
                q = local[n].rotation.multiply(original[n].rotation.inversed())
                max_preserved = max(max_preserved, math.degrees(2 * math.acos(min(1., abs(q.w)))))
            for side in ['l','r']:
                if t <= 1.80:
                    max_foot = max(max_foot, (global_pose['foot_' + side].translation - foot_goal(t, side).translation).length())
                actual = [(global_pose[a + '_' + side].translation - global_pose[b + '_' + side].translation).length()
                    for a,b in [('thigh','calf'),('calf','foot')]]
                if t < 1.80:
                    max_length = max(max_length, *(abs(a-b) for a,b in zip(actual,lengths[side])))
        start, end = common.poses(BAKED, 0., True), common.poses(BAKED, LAST / FPS, True)
        idle_end = common.poses(IDLE, 0.)
        local_end = common.poses(BAKED, LAST / FPS)
        end_position = max((local_end[n].translation - idle_end[n].translation).length()
            for n in ['pelvis','foot_l','foot_r','spine_01','hand_l'])
        report = {'original_upper_body_max_rotation_error_degrees':max_preserved,
            'foot_goal_max_error_cm':max_foot,'bone_length_max_error_cm':max_length,
            'end_idle_local_position_error_cm':end_position,
            'raw_root_travel_animation_cm':(end['root'].translation-start['root'].translation).length(),
            'pelvis_compression_max_animation_cm':10.,
            'quality_approved':False,'reach_550_verified':False,'arena_integrated':False}
        print('VALIDATION',json.dumps(report))
        assert max_preserved < 1., report
        assert max_foot < 1., report
        assert max_length < .1, report
        assert end_position < .2, report
        PLAN['report'] = report
    finally:
        result.set_editor_property('enable_root_motion', original_flag)
    result.set_editor_property('enable_root_motion', True)
    result.set_editor_property('force_root_lock', False)
    result.set_editor_property('root_motion_root_lock', unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    common.save(result)
    return report


def integrate():
    common.require_editor()
    assert PLAN and 'report' in PLAN
    ams = unreal.AnimMontageService
    if not unreal.EditorAssetLibrary.does_asset_exist(MONTAGE):
        assert ams.create_montage_from_animation(BAKED, ROOT, MONTAGE.rsplit('/',1)[1])
        print('CREATED',MONTAGE)
        assert ams.set_slot_name(MONTAGE,0,'UpperBody')
    montage = unreal.EditorAssetLibrary.load_asset(MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    if not ams.list_notifies(MONTAGE):
        unreal.AnimationLibrary.add_animation_notify_track(montage,'ContactFX',unreal.LinearColor(1.,.4,.1,1.))
        base = unreal.EditorAssetLibrary.load_asset('/Game/BossArena/Boss/AI/Actions/DA_Attack_Left')
        source_montage = base.get_editor_property('Montage')
        source_fx = next(o for o in unreal.ObjectIterator(unreal.AnimNotifyState)
            if o.get_outer() == source_montage and 'ScaledParticle' in o.get_name())
        fx = unreal.AnimationLibrary.add_animation_notify_state_event(montage,'ContactFX',.38,.843333,source_fx.get_class())
        for p in ['FXScale','MatchSocket','MatchTemplate']:
            fx.set_editor_property(p,source_fx.get_editor_property(p))
        notify_class = unreal.EditorAssetLibrary.load_asset('/Game/BossArena/Boss/Animations/Notifies/ANS_PhysicalStrike_0').generated_class()
        assert unreal.AnimationLibrary.add_animation_notify_state_event(montage,'ContactFX',HIT_START,HIT_END-HIT_START,notify_class)
    assert ams.set_blend_in(MONTAGE,.10,'Cubic')
    assert ams.set_blend_out(MONTAGE,.18,'Cubic')
    assert ams.set_enable_root_motion_translation(MONTAGE,True)
    assert ams.set_enable_root_motion_rotation(MONTAGE,False)
    common.save(montage)
    card = unreal.EditorAssetLibrary.load_asset(CARD)
    previous = {'montage':card.get_editor_property('Montage').get_path_name(),
        'display':str(card.get_editor_property('DisplayName')),
        'impact_times':list(card.get_editor_property('ImpactTimes')),
        'window_ends':list(card.get_editor_property('HitWindowEnds')),
        'total_seconds':card.get_editor_property('TotalSeconds')}
    rate = card.get_editor_property('PlayRate')
    telegraph = card.get_editor_property('TelegraphSeconds')
    card.modify()
    card.set_editor_property('Montage',montage)
    card.set_editor_property('DisplayName','오른발 디딤 → 왼손 · 원본 보존 v3')
    card.set_editor_property('ImpactTimes',[telegraph + HIT_START / rate])
    card.set_editor_property('HitWindowEnds',[HIT_END])
    card.set_editor_property('TotalSeconds',LAST / FPS / rate + telegraph + .05)
    card.set_editor_property('MaxDistance',550.)
    common.save(card)
    report = {**PLAN['report'],'previous_card':previous,'source':SOURCE,'base':BASE,
        'rig':RIG,'sequence':SEQ,'baked':BAKED,'montage':MONTAGE,
        'source_policy':'Crunch original only; sparse root, pelvis compression, foot/pole corrections',
        'hit_window_montage_seconds':[HIT_START,HIT_END]}
    path = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/crunch_original_step_v3.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODIFIED',CARD,'MotionLab L mode 3 / key 1', 'REPORT',str(path))
    return report
