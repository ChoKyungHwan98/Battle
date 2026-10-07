"""Crunch-only Control Rig / Sequencer authoring. Run inside Unreal via MCP.

Source animation assets are read-only. Editable Level Sequences and baked
outputs live separately under Authoring. Runtime integration is MotionLab only.
"""
import json
import math
from pathlib import Path
import unreal
import vibeue

ROOT = '/Game/BossArena/Boss/Authoring'
MESH = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Meshes/Crunch'
SKELETON = MESH + '_Skeleton'
SOURCE = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_01'
RIG = ROOT + '/CR_Crunch_Attack'
SEQ = ROOT + '/LS_Crunch_RightStep_LeftSwing'
BAKED = ROOT + '/AS_Crunch_RightStep_LeftSwing'
FPS = 60


def require_editor():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning'), 'Stop PIE before authoring'


def asset(path, cls, factory):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        obj = unreal.EditorAssetLibrary.load_asset(path)
        assert isinstance(obj, cls), path
        return obj
    obj = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        path.rsplit('/', 1)[1], path.rsplit('/', 1)[0], cls, factory)
    assert obj, path
    print('CREATED', path)
    return obj


def save(obj):
    assert unreal.EditorAssetLibrary.save_loaded_asset(obj, False)
    print('SAVED', obj.get_path_name())


def create_scene(path, last_frame):
    require_editor()
    seq = asset(path, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.modify()
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_tick_resolution_directly(unreal.FrameRate(24000, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(last_frame + 1)
    bindings = list(seq.get_bindings())
    if not bindings:
        binding = seq.add_spawnable_from_class(unreal.SkeletalMeshActor)
        binding.set_name('Crunch Authoring')
        template = binding.get_object_template()
        template.modify()
        template.skeletal_mesh_component.set_skeletal_mesh_asset(unreal.EditorAssetLibrary.load_asset(MESH))
        template.skeletal_mesh_component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        template.skeletal_mesh_component.set_editor_property('visibility_based_anim_tick_option',
            unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
        template.set_actor_enable_collision(False)
    else:
        assert len(bindings) == 1
        binding = bindings[0]
    return seq, binding


def animation_track(binding, animation, last_frame):
    tracks = list(binding.find_tracks_by_type(unreal.MovieSceneSkeletalAnimationTrack))
    track = tracks[0] if tracks else binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    sections = list(track.get_sections())
    section = sections[0] if sections else track.add_section()
    section.set_range(0, last_frame + 1)
    params = section.get_editor_property('params')
    params.animation = animation
    params.force_custom_mode = True
    params.skip_anim_notifiers = True
    section.set_editor_property('params', params)
    return section


def bake(sequence, binding, destination, last_frame):
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton', unreal.EditorAssetLibrary.load_asset(SKELETON))
    result = asset(destination, unreal.AnimSequence, factory)
    # Root keys must be visible in comparisons, rather than force-locked during sampling.
    result.set_editor_property('force_root_lock', False)
    result.set_editor_property('enable_root_motion', False)
    options = unreal.AnimSeqExportOption()
    options.export_transforms = True
    options.export_morph_targets = False
    options.export_attribute_curves = True
    options.record_in_world_space = False
    options.use_custom_frame_rate = True
    options.custom_frame_rate = unreal.FrameRate(FPS, 1)
    options.custom_display_rate = unreal.FrameRate(FPS, 1)
    options.use_custom_time_range = True
    options.custom_start_frame = unreal.FrameNumber(0)
    options.custom_end_frame = unreal.FrameNumber(last_frame)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    # This native editor library has no generated Python class in 5.8.3.
    # call_method invokes its reflected UFUNCTION, without adding a plugin.
    library_class = unreal.load_class(None, '/Script/ControlRigEditor.ControlRigSequencerEditorLibrary')
    library = unreal.get_default_object(library_class)
    assert library.call_method('ExportAnimSequenceFromSequencer', (result, options, binding, True))
    save(result)
    save(sequence)
    return result


def poses(path, time, global_space=False):
    return {str(p.bone_name): p.transform for p in unreal.AnimSequenceService.get_pose_at_time(path, time, global_space)}


def compare_pose(source, result, times):
    max_pos, max_angle = 0., 0.
    for t in times:
        a, b = poses(source, t, True), poses(result, t, True)
        for bone in a:
            if bone not in b:
                continue
            max_pos = max(max_pos, (a[bone].translation - b[bone].translation).length())
            q = a[bone].rotation.multiply(b[bone].rotation.inversed())
            angle = math.degrees(2 * math.acos(min(1., abs(q.w))))
            max_angle = max(max_angle, angle)
    return {'max_component_position_error_cm': max_pos, 'max_rotation_error_degrees': max_angle}


def fk_roundtrip():
    require_editor()
    source = unreal.EditorAssetLibrary.load_asset(SOURCE)
    last = math.ceil(source.get_play_length() * FPS / 2) * 2
    seq, binding = create_scene(ROOT + '/LS_Crunch_BakeBaseline', last)
    section = animation_track(binding, source, last)
    save(seq)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    options = unreal.AnimSeqExportOption()
    options.export_transforms = True
    options.record_in_world_space = False
    if not unreal.ControlRigSequencerLibrary.get_control_rigs(seq):
        assert unreal.ControlRigSequencerLibrary.bake_to_control_rig(
            world, seq, unreal.FKControlRig.static_class(), options, False, .001, binding)
    save(seq)
    result = bake(seq, binding, ROOT + '/AS_Crunch_BakeBaseline', last)
    report = compare_pose(SOURCE, result.get_path_name(), [.0, .1, .2, .35, .5, .7])
    assert report['max_component_position_error_cm'] < 1., report
    assert report['max_rotation_error_degrees'] < 1., report
    print('VERIFIED FK roundtrip', json.dumps(report))
    return report


def bone_key(name):
    return unreal.RigElementKey(type=unreal.RigElementType.BONE, name=name)


def control_key(name):
    return unreal.RigElementKey(type=unreal.RigElementType.CONTROL, name=name)


def unit_vector(vector):
    return vector / max(vector.length(), .000001)


def euler_value(t):
    return unreal.RigHierarchy.make_control_value_from_euler_transform(
        unreal.EulerTransform(location=t.translation, rotation=t.rotation.rotator(), scale=t.scale3d))


def build_rig():
    """Round-trippable FK controls plus independent foot targets and knee poles.

    FK preserves all Crunch mechanical/twist bones. Optional native Basic IK
    runs afterwards and never stretches a leg. Source import defaults IK to 0.
    """
    require_editor()
    from animation_toolset.toolsets.controlrig import ControlRigTools as CR
    rig = unreal.EditorAssetLibrary.load_asset(RIG) if unreal.EditorAssetLibrary.does_asset_exist(RIG) else CR.create(RIG)
    if not CR.get_all_bones(rig):
        CR.import_bones_from_asset(rig, unreal.EditorAssetLibrary.load_asset(MESH))
    rig.modify()
    rig.set_auto_vm_recompile(False)
    h = rig.hierarchy
    hc = rig.get_hierarchy_controller()
    graph = CR.get_forward_solve_graph(rig)
    ctl = rig.get_controller_by_name(graph.get_name())
    # Remove only the unconnected inspection nodes created by this authoring script.
    for node in list(graph.get_nodes()):
        if node.get_name().startswith('Inspect'):
            assert ctl.remove_node(node, False)
    models = list(rig.get_all_models())
    back = next((g for g in models if any(n.get_node_title() == 'Backwards Solve' for n in g.get_nodes())), None)
    if not back:
        back = CR.add_backward_solve_graph(rig, 'BackwardsSolve')
    bc = rig.get_controller_by_name(back.get_name())

    def node(controller, name, kind, x=0, y=0):
        obj = controller.get_graph().find_node_by_name(name)
        if not obj:
            obj = controller.add_unit_node_from_struct_path('/Script/ControlRig.' + kind,
                'Execute', unreal.Vector2D(x, y), name, False)
        assert obj, name
        return name

    def value(controller, pin, data):
        assert controller.set_pin_default_value(pin, str(data), True, False), pin

    def link(controller, output, input):
        p = controller.get_graph().find_pin(input)
        if output not in [s.get_pin_path() for s in p.get_linked_source_pins()]:
            assert controller.add_link(output, input, False), (output, input)

    def add_transform(name, parent, t, visible):
        if h.contains(control_key(name)):
            return
        settings = unreal.RigControlSettings()
        settings.control_type = unreal.RigControlType.EULER_TRANSFORM
        settings.animation_type = unreal.RigControlAnimationType.ANIMATION_CONTROL
        settings.shape_visible = visible
        settings.shape_name = 'Circle_Thick'
        settings.shape_color = unreal.LinearColor(.1, .8, 1., 1.)
        hc.add_control(name, parent, settings, euler_value(t), False)

    start = node(ctl, 'ForwardSolve', 'RigUnit_BeginExecution', 0, 0) + '.ExecutePin'
    back_nodes = list(back.get_nodes())
    backward_event = next(n for n in back_nodes if n.get_node_title() == 'Backwards Solve')
    back_start = backward_event.get_name() + '.ExecutePin'
    bones = list(h.get_bones())
    for index, key in enumerate(bones):
        name = str(key.name)
        parent = h.get_first_parent(key)
        parent_control = control_key(str(parent.name) + '_fk') if str(parent.name) != 'None' else unreal.RigElementKey()
        add_transform(name + '_fk', parent_control, h.get_local_transform(key, True),
            name in ['root', 'pelvis', 'spine_01', 'spine_02', 'hand_l', 'hand_r'])
        y = index * 150
        get = node(ctl, 'Read_' + name, 'RigUnit_GetTransform', 100, y)
        set = node(ctl, 'Write_' + name, 'RigUnit_SetTransform', 420, y)
        for n, item_type, item_name in [(get, 'Control', name + '_fk'), (set, 'Bone', name)]:
            value(ctl, n + '.Item.Type', item_type)
            value(ctl, n + '.Item.Name', item_name)
            value(ctl, n + '.Space', 'LocalSpace')
        link(ctl, get + '.Transform', set + '.Value')
        link(ctl, start, set + '.ExecutePin')
        start = set + '.ExecutePin'
        read = node(bc, 'ReadBone_' + name, 'RigUnit_GetTransform', 100, y)
        write = node(bc, 'RestoreControl_' + name, 'RigUnit_SetControlTransform', 420, y)
        value(bc, read + '.Item.Type', 'Bone')
        value(bc, read + '.Item.Name', name)
        value(bc, read + '.Space', 'LocalSpace')
        value(bc, write + '.Control', name + '_fk')
        value(bc, write + '.Space', 'LocalSpace')
        link(bc, read + '.Transform', write + '.Transform')
        link(bc, back_start, write + '.ExecutePin')
        back_start = write + '.ExecutePin'

    for side in ['l', 'r']:
        thigh, calf, foot = [bone_key(n + '_' + side) for n in ['thigh', 'calf', 'foot']]
        ankle = h.get_global_transform(foot, True)
        hip = h.get_global_transform(thigh, True)
        knee = h.get_global_transform(calf, True).translation
        pole = unreal.Transform()
        pole.translation = knee + unreal.Vector(0, 100, 0)
        add_transform('foot_' + side + '_ik', unreal.RigElementKey(), ankle, True)
        add_transform('knee_' + side + '_pole', unreal.RigElementKey(), pole, True)
        weight_name = 'leg_' + side + '_ik_weight'
        if not h.contains(control_key(weight_name)):
            settings = unreal.RigControlSettings()
            settings.control_type = unreal.RigControlType.FLOAT
            settings.animation_type = unreal.RigControlAnimationType.ANIMATION_CHANNEL
            hc.add_control(weight_name, unreal.RigElementKey(), settings,
                unreal.RigHierarchy.make_control_value_from_float(0.), False)
        eff = node(ctl, 'FootTarget_' + side, 'RigUnit_GetTransform', 100, len(bones) * 150 + 200)
        pv = node(ctl, 'KneeTarget_' + side, 'RigUnit_GetTransform')
        w = node(ctl, 'LegWeight_' + side, 'RigUnit_GetControlFloat')
        ik = node(ctl, 'LegIK_Left' if side == 'l' else 'LegIK_Right', 'RigUnit_TwoBoneIKSimple')
        for n, ctrl in [(eff, 'foot_' + side + '_ik'), (pv, 'knee_' + side + '_pole')]:
            value(ctl, n + '.Item.Type', 'Control')
            value(ctl, n + '.Item.Name', ctrl)
            value(ctl, n + '.Space', 'GlobalSpace')
        value(ctl, w + '.Control', weight_name)
        for pin, bone in [('BoneA', thigh.name), ('BoneB', calf.name), ('EffectorBone', foot.name)]:
            value(ctl, ik + '.' + pin, bone)
        primary = unit_vector(h.get_local_transform(calf, True).translation)
        secondary = hip.rotation.unrotate_vector(pole.translation - hip.translation)
        secondary = unit_vector(secondary - primary * secondary.dot(primary))
        fmt = lambda v: '(X=%f,Y=%f,Z=%f)' % (v.x, v.y, v.z)
        value(ctl, ik + '.PrimaryAxis', fmt(primary))
        value(ctl, ik + '.SecondaryAxis', fmt(secondary))
        value(ctl, ik + '.PoleVectorKind', 'Location')
        value(ctl, ik + '.bEnableStretch', 'False')
        link(ctl, eff + '.Transform', ik + '.Effector')
        link(ctl, pv + '.Transform.Translation', ik + '.PoleVector')
        link(ctl, w + '.FloatValue', ik + '.Weight')
        link(ctl, start, ik + '.ExecutePin')
        start = ik + '.ExecutePin'
        # Importing a source animation restores the independent foot target too.
        read = node(bc, 'RestoreFootSource_' + side, 'RigUnit_GetTransform')
        write = node(bc, 'RestoreFootControl_' + side, 'RigUnit_SetControlTransform')
        value(bc, read + '.Item.Name', foot.name)
        value(bc, write + '.Control', 'foot_' + side + '_ik')
        link(bc, read + '.Transform', write + '.Transform')
        link(bc, back_start, write + '.ExecutePin')
        back_start = write + '.ExecutePin'
    rig.set_auto_vm_recompile(True)
    rig.recompile_vm()
    save(rig)
    print('MODIFIED', RIG, 'FK controls', len(bones), 'plus two native IK chains and Backwards Solve')
    return rig


def custom_roundtrip():
    require_editor()
    source = unreal.EditorAssetLibrary.load_asset(SOURCE)
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    last = math.ceil(source.get_play_length() * FPS / 2) * 2
    seq, binding = create_scene(ROOT + '/LS_Crunch_RigBaseline', last)
    animation_track(binding, source, last)
    save(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    options = unreal.AnimSeqExportOption()
    options.export_transforms = True
    if not unreal.ControlRigSequencerLibrary.get_control_rigs(seq):
        assert unreal.ControlRigSequencerLibrary.bake_to_control_rig(
            world, seq, rig.generated_class(), options, False, .001, binding)
    save(seq)
    result = bake(seq, binding, ROOT + '/AS_Crunch_RigBaseline', last)
    report = compare_pose(SOURCE, result.get_path_name(), [0, .1, .2, .35, .5, .7])
    assert report['max_component_position_error_cm'] < 1., report
    assert report['max_rotation_error_degrees'] < 1., report
    print('VERIFIED Crunch rig roundtrip', json.dumps(report))
    return report


def smooth(value):
    value = min(1., max(0., value))
    return value * value * (3. - 2. * value)


def between(time, start, end):
    return smooth((time - start) / (end - start))


def copy_transform(value):
    t = unreal.Transform()
    t.translation, t.rotation, t.scale3d = value.translation, value.rotation, value.scale3d
    return t


def attack_foot_target(time, side, initial):
    """One leading right step; only a low trailing-foot adjustment afterwards.

    Hold the resulting stance through recovery. Do not schedule the old two
    recovery lifts just to reconstruct the starting left-leading stance.
    """
    foot = copy_transform(initial)
    if side == 'r':
        step = between(time, .16, .60)
        foot.translation = initial.translation + unreal.Vector(
            0., (155. - initial.translation.y) * step, 26. * math.sin(math.pi * step))
    else:
        follow = between(time, .60, .84)
        foot.translation = initial.translation + unreal.Vector(
            0., 60. * follow, 2. * math.sin(math.pi * follow))
    return foot


def sync_ik_targets():
    """Keep the game's existing LegIK targets aligned with the authored feet."""
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    ctl = rig.get_controller_by_name('RigVMModel')
    graph = ctl.get_graph()
    last = 'LegIK_Right.ExecutePin'
    for side in ['l', 'r']:
        read_name, write_name = 'SolvedFoot_' + side, 'SyncGameFoot_' + side
        read = graph.find_node_by_name(read_name)
        if not read:
            read = ctl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_GetTransform', 'Execute', unreal.Vector2D(), read_name, False)
        write = graph.find_node_by_name(write_name)
        if not write:
            write = ctl.add_unit_node_from_struct_path('/Script/ControlRig.RigUnit_SetTransform', 'Execute', unreal.Vector2D(), write_name, False)
        for pin, value in [(read_name + '.Item.Name', 'foot_' + side), (write_name + '.Item.Name', 'ik_foot_' + side)]:
            assert ctl.set_pin_default_value(pin, value, True, False)
        for output, input in [(read_name + '.Transform', write_name + '.Value'),
                ('LegWeight_' + side + '.FloatValue', write_name + '.Weight'),
                (last, write_name + '.ExecutePin')]:
            p = graph.find_pin(input)
            if output not in [s.get_pin_path() for s in p.get_linked_source_pins()]:
                assert ctl.add_link(output, input, False)
        last = write_name + '.ExecutePin'
    rig.recompile_vm()
    save(rig)
    print('MODIFIED', RIG, 'optional IK targets match solved feet')


PLAN = None


def prepare_attack():
    """Prepare editable control keys, not raw AnimSequence bone tracks.

    The upper body follows Crunch's current left attack. The right step and
    support-foot release are authored independently of running animations.
    Animation-space +Y is Crunch actor-forward because the mesh yaw is -90.
    """
    global PLAN
    require_editor()
    prefix, consumed, attack_end, recovery_rate = .6, .3, 1.2066669464111328, 1.6
    windup = '/Game/BossArena/Boss/Animations/Ability_Combo_01_Slow_Low_Windup'
    recovery = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_01_Recovery'
    clip_a = unreal.EditorAssetLibrary.load_asset(windup)
    clip_b = unreal.EditorAssetLibrary.load_asset(recovery)
    last = math.ceil((prefix + attack_end - consumed + clip_b.get_play_length() / recovery_rate) * FPS / 2) * 2
    seq, binding = create_scene(SEQ, last)
    assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rig_asset = unreal.EditorAssetLibrary.load_asset(RIG)
    track = unreal.ControlRigSequencerLibrary.find_or_create_control_rig_track(world, seq, rig_asset.generated_class(), binding)
    sections = list(track.get_sections())
    section = sections[0]
    section.set_range(0, last + 1)
    proxies = unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
    rig = next(p.control_rig for p in proxies if p.control_rig.get_class() == rig_asset.generated_class())
    # Replace only channels owned by this generated attack, preserving scene/rig objects.
    for channel in section.get_all_channels():
        for key in list(channel.get_keys()):
            channel.remove_key(key)
    skeleton = rig_asset.hierarchy
    names = [str(k.name) for k in skeleton.get_bones()]
    initial = poses(windup, 0)
    feet = poses(windup, 0, True)
    frames = []
    for frame in range(0, last + 1, 2):
        t = frame / FPS
        at = consumed * between(t, 0., prefix) if t < prefix else consumed + t - prefix
        if at <= attack_end:
            local = poses(windup, at)
        else:
            local = poses(recovery, min(clip_b.get_play_length(), (at - attack_end) * recovery_rate))
        # Hold the leg FK posture; native IK supplies their actual articulated poses.
        for name in names:
            if any(name.startswith(p) for p in ['thigh_', 'calf_', 'foot_', 'ball_', 'ik_foot']):
                local[name] = copy_transform(initial[name])
        root = copy_transform(local['root'])
        root.rotation = initial['root'].rotation
        travel = 95 * between(t, .10, .50) + 25 * between(t, .50, .60) + (205 / 1.3 - 120) * between(t, .66, .87)
        root.translation = initial['root'].translation + unreal.Vector(0., travel, 0.)
        local['root'] = root
        # A modest preload / landing compression; no root-height bobbing or leg stretch.
        crouch = 10 * between(t, .04, .16) + 4 * between(t, .46, .60) - 14 * between(t, .85, 1.45)
        pelvis = copy_transform(local['pelvis'])
        # Source punches contain a large pelvis translation. Combining it with
        # the new root step overextends the planted leg, so root owns advance.
        pelvis.translation = initial['pelvis'].translation
        source_pelvis_rotation = pelvis.rotation
        pelvis.rotation = initial['pelvis'].rotation.slerp_quat(source_pelvis_rotation, .2)
        # Redistribute the source's exaggerated hip turn into the torso while
        # preserving its chest orientation. Keep the leg stance anatomically reachable.
        spine = copy_transform(local['spine_01'])
        spine.rotation = pelvis.rotation.inversed().multiply(source_pelvis_rotation.multiply(spine.rotation))
        local['spine_01'] = spine
        pelvis.translation = pelvis.translation + root.rotation.unrotate_vector(unreal.Vector(0., 0., -crouch))
        local['pelvis'] = pelvis
        frame_controls = {name + '_fk': local[name] for name in names}
        for side in ['l', 'r']:
            foot = attack_foot_target(t, side, feet['foot_' + side])
            frame_controls['foot_' + side + '_ik'] = foot
            pole = unreal.Transform()
            pole.translation = foot.translation + unreal.Vector(0., 85., 70.)
            frame_controls['knee_' + side + '_pole'] = pole
        frames.append((frame, frame_controls))
    PLAN = {'sequence': seq, 'binding': binding, 'rig': rig, 'last_frame': last,
        'frames': frames, 'offset': prefix - consumed, 'prefix': prefix,
        'source': windup, 'travel_world_cm': 205., 'step_land_frame': 36,
        'hit_start_frame': round((.346667 + prefix - consumed) * FPS),
        'hit_end_frame': round((.486667 + prefix - consumed) * FPS)}
    existing_marks = {m.label for m in seq.get_marked_frames()}
    for label, frame in [('준비', 0), ('오른발 들기', 10), ('오른발 착지', 36),
            ('왼손 판정 시작', PLAN['hit_start_frame']), ('왼손 판정 종료', PLAN['hit_end_frame']),
            ('회복 · 자세 정돈', 87)]:
        if label not in existing_marks:
            seq.add_marked_frame(unreal.MovieSceneMarkedFrame(frame_number=unreal.FrameNumber(frame), label=label))
    print('PREPARED', SEQ, 'frames', last, 'controls', len(names) + 6, 'native leg IK, no jog donor')
    return {'last_frame': last, 'key_frames': len(frames), 'prefix': prefix}


def write_keys(start=0, end=10000):
    assert PLAN
    names = list(PLAN['frames'][0][1])
    write_control_keys(names, start, end)
    frames = [unreal.FrameNumber(f) for f, _ in PLAN['frames'] if start <= f < end]
    for side in ['l', 'r']:
        unreal.ControlRigSequencerLibrary.set_local_control_rig_floats(
            PLAN['sequence'], PLAN['rig'], 'leg_' + side + '_ik_weight', frames, [1.] * len(frames))
    print('KEYED', SEQ, start, end, 'poses', len(frames))


def write_control_keys(names, start=0, end=10000):
    """Bulk native keys for targeted corrections, without rewriting other poses."""
    assert PLAN
    selected = [(f, c) for f, c in PLAN['frames'] if start <= f < end]
    frames = [unreal.FrameNumber(frame) for frame, _ in selected]
    for name in names:
        values = []
        previous = None
        for _, controls in selected:
            t = controls[name]
            r = t.rotation.rotator()
            candidates = [(r.roll, r.pitch, r.yaw), (r.roll + 180., 180. - r.pitch, r.yaw + 180.)]
            if previous:
                candidates = [tuple(v + round((p - v) / 360.) * 360. for v, p in zip(c, previous)) for c in candidates]
                angles = min(candidates, key=lambda c: sum((v - p) ** 2 for v, p in zip(c, previous)))
            else:
                angles = candidates[0]
            previous = angles
            rotation = unreal.Rotator(roll=angles[0], pitch=angles[1], yaw=angles[2])
            values.append(unreal.EulerTransform(location=t.translation, rotation=rotation, scale=t.scale3d))
        unreal.ControlRigSequencerLibrary.set_local_control_rig_euler_transforms(
            PLAN['sequence'], PLAN['rig'], name, frames, values)
    print('KEYED corrected controls', names)


def bake_attack():
    assert PLAN
    save(PLAN['sequence'])
    result = bake(PLAN['sequence'], PLAN['binding'], BAKED, PLAN['last_frame'])
    result.set_editor_property('enable_root_motion', True)
    result.set_editor_property('force_root_lock', False)
    result.set_editor_property('root_motion_root_lock', unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
    save(result)
    print('BAKED', BAKED, 'from Control Rig / Sequencer; root motion enabled')
    return result


def integrate_motion_lab():
    require_editor()
    assert PLAN and PLAN.get('foot_error_cm', 100.) < .1, 'Validate baked foot goals before integration'
    base_path = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Left'
    card_path = '/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant'
    montage_path = ROOT + '/AM_Crunch_RightStep_LeftSwing'
    base = unreal.EditorAssetLibrary.load_asset(base_path)
    card = unreal.EditorAssetLibrary.load_asset(card_path)
    assert card and base
    ams = unreal.AnimMontageService
    if not unreal.EditorAssetLibrary.does_asset_exist(montage_path):
        assert ams.create_montage_from_animation(BAKED, ROOT, 'AM_Crunch_RightStep_LeftSwing')
        print('CREATED', montage_path)
        montage = unreal.EditorAssetLibrary.load_asset(montage_path)
        assert ams.set_slot_name(montage_path, 0, 'UpperBody')
    montage = unreal.EditorAssetLibrary.load_asset(montage_path)
    if not ams.list_notifies(montage_path):
        # Partial runs retain the existing montage/track rather than recreating it.
        if 'ContactFX' not in [str(n) for n in unreal.AnimationLibrary.get_animation_notify_track_names(montage)]:
            unreal.AnimationLibrary.add_animation_notify_track(montage, 'ContactFX', unreal.LinearColor(1., .4, .1, 1.))
        source_montage = base.get_editor_property('Montage')
        source_fx = next(o for o in unreal.ObjectIterator(unreal.AnimNotifyState)
            if o.get_outer() == source_montage and 'ScaledParticle' in o.get_name())
        physical_class = unreal.EditorAssetLibrary.load_asset('/Game/BossArena/Boss/Animations/Notifies/ANS_PhysicalStrike_0').generated_class()
        offset = PLAN['offset']
        fx = unreal.AnimationLibrary.add_animation_notify_state_event(montage, 'ContactFX',
            .106667 + offset, .843333, source_fx.get_class())
        for prop in ['FXScale', 'MatchSocket', 'MatchTemplate']:
            fx.set_editor_property(prop, source_fx.get_editor_property(prop))
        assert unreal.AnimationLibrary.add_animation_notify_state_event(montage, 'ContactFX',
            .346667 + offset, .14, physical_class)
        # No manual AttackStep notify: the baked root exclusively owns body travel.
        assert ams.set_blend_in(montage_path, .10, 'Cubic')
        assert ams.set_blend_out(montage_path, .16, 'Cubic')
        assert ams.set_enable_root_motion_translation(montage_path, True)
        assert ams.set_enable_root_motion_rotation(montage_path, False)
    montage = unreal.EditorAssetLibrary.load_asset(montage_path)
    save(montage)
    old_montage = card.get_editor_property('Montage').get_path_name()
    old_display = card.get_editor_property('DisplayName')
    card.modify()
    card.set_editor_property('Montage', montage)
    card.set_editor_property('DisplayName', '오른발 디딤 → 왼손 · Control Rig 제작 v1')
    rate = base.get_editor_property('PlayRate')
    card.set_editor_property('PlayRate', rate)
    card.set_editor_property('TelegraphSeconds', base.get_editor_property('TelegraphSeconds'))
    card.set_editor_property('ImpactTimes', [t + PLAN['offset'] / rate for t in base.get_editor_property('ImpactTimes')])
    card.set_editor_property('HitWindowEnds', [t + PLAN['offset'] for t in base.get_editor_property('HitWindowEnds')])
    card.set_editor_property('TotalSeconds', unreal.EditorAssetLibrary.load_asset(BAKED).get_play_length() / rate
        + base.get_editor_property('TelegraphSeconds') + .05)
    card.set_editor_property('MaxDistance', 550.)
    card.set_editor_property('DashMaxDistance', 0.)
    save(card)
    assert len(ams.list_notifies(montage_path)) == 2
    assert all('AttackStep' not in n.notify_name for n in ams.list_notifies(montage_path))
    report = {'rig': RIG, 'sequence': SEQ, 'baked': BAKED, 'montage': montage_path,
        'lab_card': card_path, 'previous_montage': old_montage, 'previous_display': old_display,
        'source_policy': 'Crunch original only; no jog donor', 'animation_fps': FPS,
        'last_frame': PLAN['last_frame'], 'root_travel_world_cm': PLAN['travel_world_cm'],
        'foot_goal_max_error_cm': PLAN['foot_error_cm'], 'impact_seconds': list(card.get_editor_property('ImpactTimes')),
        'notify_window_montage_seconds': [.346667 + PLAN['offset'], .486667 + PLAN['offset']],
        'quality_approved': False, 'reach_550_verified': False, 'arena_integrated': False}
    path = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/crunch_control_rig_attack_20261007.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('MODIFIED', card_path, 'L mode 3 + 1; original attack/Arena unchanged')
    print('REPORT', str(path))
    return report
