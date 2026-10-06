"""Integrate the accepted punch step with varied close-range Utility choices.

Run in Unreal through MCP with PIE stopped. Does not start gameplay.
The 145cm movement calculation is native; this script adjusts shared action cards
and removes the standalone uppercut from ordinary-punch family suppression.
"""
import json
from pathlib import Path
import unreal
import vibeue

B = '/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'
C = '/Game/BossArena/Boss/AI/Actions/'
S = unreal.BlueprintService
FAMILY_PINS = [
    ('ComputeActionScore', '40A18D924D91AD245976FA984931EB8E'),
    ('RecordPunchFamilyUse', '51B1171B499F0D2B2C3453AFA8D3CCC1'),
]
WEIGHTS = {'DA_Attack_Left': 28., 'DA_Attack_Right': 28.,
           'DA_Attack_Uppercut': 30., 'DA_Attack_Sweep': 30.,
           'DA_Attack_Dash': 20., 'DA_Approach': 70.}


def verify():
    cdo = unreal.get_default_object(unreal.EditorAssetLibrary.load_asset(B).generated_class())
    actions = list(cdo.get_editor_property('Actions'))
    assert len(actions) == 10
    for a in actions:
        assert a.get_editor_property('bEnabled'), a.get_name()
        if a.get_name() in WEIGHTS:
            assert abs(a.get_editor_property('BaseWeight')-WEIGHTS[a.get_name()]) < .001
        if a.get_editor_property('ActionId') != 7:
            assert a.get_editor_property('Montage'), a.get_name()
    for i in [0, 1, 2, 3]:
        assert actions[i].get_editor_property('MinDistance') <= 175 <= actions[i].get_editor_property('MaxDistance')
    assert all(actions[i].get_editor_property('MaxDistance') == 400 for i in [0, 1])
    assert actions[6].get_editor_property('MinDistance') == 500
    assert actions[8].get_editor_property('MinDistance') == 1000
    for g, n in FAMILY_PINS:
        p = next(p for p in S.get_node_pins(B, g, n) if p.pin_name == 'B')
        assert p.default_value == '1' and not p.is_connected
    # Verify the real weighted selection path, not the uncalled legacy executor.
    edges = S.get_connections(B, 'ChooseCombatAction')
    assert any(e.source_node_id == '0BC147FE445DB45244605D9E261FFAA5'
               and e.source_pin_name == 'then'
               and e.target_node_id == '7301F11243BDE60E5951CFA54285A697'
               and e.target_pin_name == 'execute' for e in edges)
    assert not any(e.target_node_id == 'D6C8DBF54591DF08F662A79DF4396DD5'
                   and e.target_pin_name == 'execute' for e in edges)
    assert any(e.source_node_id == 'E42AB61F4851449E943A668E6DE25A42'
               and e.source_pin_name == 'then' and e.target_node_id == '071BE9324A4CA14332E54AB6A9CAECD5'
               for e in S.get_connections(B, 'EvaluateCombatUtility'))
    print('VERIFIED 10 shared cards, weighted draw -> retained attack -> position executor; no PIE')
    return actions


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    affected = {B, *(C+n for n in WEIGHTS)}
    dirty = {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    assert not dirty.intersection(affected), dirty
    target = Path(unreal.Paths.project_saved_dir()).resolve()/'VibeUE/Reports/crunch_combat_variety_20261006.json'
    report = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'before': {}, 'gameplay_verified': False}
    for name, value in WEIGHTS.items():
        obj = unreal.EditorAssetLibrary.load_asset(C+name)
        report['before'].setdefault(name, obj.get_editor_property('BaseWeight'))
        obj.modify()
        obj.set_editor_property('BaseWeight', value)
        assert unreal.EditorAssetLibrary.save_loaded_asset(obj, False)
        print('MODIFIED', C+name, 'BaseWeight', value)
    for graph, node in FAMILY_PINS:
        old = next(p.default_value for p in S.get_node_pins(B, graph, node) if p.pin_name == 'B')
        report['before'].setdefault(graph+'.family_max_id', old)
        assert S.set_node_pin_value(B, graph, node, 'B', '1')
        print('MODIFIED', B, graph, 'ordinary punch family excludes standalone uppercut')
    compiled = S.compile_blueprint(B)
    assert compiled.success and not compiled.errors and not compiled.warnings, compiled
    assert unreal.EditorAssetLibrary.save_asset(B)
    actions = verify()
    cls = unreal.EditorAssetLibrary.load_asset(B).generated_class()
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class() != cls: continue
        assert list(actor.get_editor_property('Actions')) == actions
        actor.modify()
        actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
            unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionResponseType.ECR_IGNORE)
        print('MODIFIED placed boss collision', actor.get_name())
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    report.update({'weights': WEIGHTS, 'compile_errors': 0, 'compile_warnings': 0,
                   'shared_executor_verified': True, 'midrange_step_request_cm': 145,
                   'close_family': [0, 1, 4, 9], 'standalone_uppercut_id': 2})
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SAVED', target)


if __name__ == '__main__': apply()
