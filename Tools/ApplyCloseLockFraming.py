"""Close combat composition without changing the locked lens distance/FOV."""
import unreal

P='/Game/BossArena/Player/Blueprints/BP_Player_Combat'


def apply():
    backup='/Game/BossArena/Backup/BP_Player_Combat_PreCloseFraming_20260929'
    if not unreal.EditorAssetLibrary.does_asset_exist(backup):
        assert unreal.EditorAssetLibrary.duplicate_asset(P,backup)
        assert unreal.EditorAssetLibrary.save_asset(backup)
        print('CREATED:',backup)
    # Positive pitch at short distance lowers the spring-arm lens and exposes
    # sky. Bound the lock's elevation instead of zooming or following the head.
    assert unreal.BlueprintService.set_variable_default_value(P,'CamLockPitchMax','0')
    print('MODIFIED:',P,'CamLockPitchMax 25 -> 0')
    result=unreal.BlueprintService.compile_blueprint(P)
    print('COMPILED:',result.success,result.num_errors,result.num_warnings)
    assert result.success and result.num_errors==0
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name()=='BP_Player_Combat_C':
            # The variable is not normally instance editable; current level has
            # a PlayerStart, not a placed combat player. Report rather than
            # silently ignoring a future placed-player override.
            print('PLACED_PLAYER:',actor.get_path_name(),actor.get_editor_property('CamLockPitchMax'))
    assert unreal.EditorAssetLibrary.save_asset(P)
    print('SAVED:',P)
    return True
