"""Applied repair record. Run via Unreal MCP with PIE stopped.

Rollback: restore the Control Rig Alpha pin to 1.0, then compile/save.
The template IK cannot be enabled safely until the retargeted IK foot targets
follow the animated feet. The arena currently uses the source foot animation.
"""
import unreal


def apply():
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'Stop PIE first'
    path = '/Game/BossArena/Player/Animation/ABP_Player_Combat'
    node = '8EBB3A3F45204321584231A4FCD1F06C'
    assert unreal.BlueprintService.set_node_pin_value(path, 'AnimGraph', node, 'Alpha', '0.0')
    print('MODIFIED:', path, 'Control Rig Alpha=0; preserve animated feet')
    bp = unreal.EditorAssetLibrary.load_asset(path)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE
    pins = unreal.BlueprintService.get_nodes_in_graph(path, 'AnimGraph', 0, node, True)[0].pins
    assert next(float(p.default_value) for p in pins if p.pin_name == 'Alpha') == 0
    assert unreal.EditorAssetLibrary.save_asset(path, False)
    print('VERIFIED/SAVED:', path)
