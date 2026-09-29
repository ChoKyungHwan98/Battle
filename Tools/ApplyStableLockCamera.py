"""User comfort override: one camera distance across free/lock/sprint."""
import unreal

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
S = unreal.BlueprintService


def apply():
    backup = '/Game/BossArena/Backup/BP_Player_Combat_PreStableCamera_20260929'
    if not unreal.EditorAssetLibrary.does_asset_exist(backup):
        assert unreal.EditorAssetLibrary.duplicate_asset(P, backup)
        assert unreal.EditorAssetLibrary.save_asset(backup)
        print('CREATED:', backup)
    for name, value in [('CamFreeArm', 650), ('CamLockArm', 650),
                        ('CamFreeOffsetZ', 92), ('CamLockOffsetZ', 92),
                        ('CamCloseMaxExtra', 0)]:
        assert S.set_variable_default_value(P, name, str(value))
        print('MODIFIED:', P, name, value)
    for prop, value in [('TargetArmLength', '650'), ('TargetOffset', '(X=0,Y=0,Z=92)'),
                        ('bEnableCameraLag', 'false')]:
        assert S.set_component_property(P, 'CameraBoom', prop, value)
        print('MODIFIED:', P, 'CameraBoom', prop, value)
    assert S.set_node_pin_value(P, 'UpdateCameraFraming',
        'CF85F5AC46FAF79D115FD38F9C655A75', 'bEnableCameraLag', 'false')
    print('MODIFIED:', P, 'UpdateCameraFraming camera lag disabled')
    # The HUD marker still uses animated spine_03. Camera aim uses the stable
    # boss actor location + existing height, so breathing/punches do not nod it.
    assert S.connect_nodes(P, 'UpdateLockOnRotation',
        '7CDE6FE94BA1E8467ADE1C9AEE71E63A', 'ReturnValue',
        'FC8E11D24A431E00CC469899305E891C', 'Target')
    assert S.set_node_pin_value(P, 'UpdateLockOnRotation',
        'DD028903432B425343A7059445B8A2A8', 'InterpSpeed', '5')
    print('MODIFIED:', P, 'Stable camera aim; lock rotation interpolation 5')
    result = S.compile_blueprint(P)
    print('COMPILED:', result.success, result.num_errors, result.num_warnings)
    assert result.success and result.num_errors == 0
    # Account for already placed instances as well as the SCS template.
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name() == 'BP_Player_Combat_C':
            for name, value in [('CamFreeArm',650),('CamLockArm',650),
                                ('CamFreeOffsetZ',92),('CamLockOffsetZ',92)]:
                actor.set_editor_property(name, value)
            arm = actor.get_component_by_class(unreal.SpringArmComponent)
            arm.set_editor_property('target_arm_length', 650)
            arm.set_editor_property('target_offset', unreal.Vector(0,0,92))
            arm.set_editor_property('enable_camera_lag', False)
            print('MODIFIED:', actor.get_path_name(), 'camera instance')
    assert unreal.EditorAssetLibrary.save_asset(P)
    print('SAVED:', P)
    wires = S.get_connections(P,'UpdateLockOnRotation')
    assert any(c.source_node_id=='7CDE6FE94BA1E8467ADE1C9AEE71E63A' and
               c.target_node_id=='FC8E11D24A431E00CC469899305E891C' and
               c.target_pin_name=='Target' for c in wires)
    return True
