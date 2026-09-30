"""One-time migration: make stationary Space a no-op and widen Battle tap timing.

Run in the open Unreal Editor with PIE stopped against commit 12732bd.
The 0.18 s threshold is a Battle input correction, not a confirmed DS3 value.
"""
import unreal
import vibeue

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
IMC = '/Game/BossArena/Player/Input/IMC_Player_Combat'
BACKSTEP = '/Game/FightAnimations_FBX/A_Slip_Back_Step'
S = unreal.BlueprintService

assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
run_id = unreal.WorkflowService.start_run('Space roll usability and no stationary backstep', '{}')
print('RUN:', run_id)

ctx = unreal.EditorAssetLibrary.load_asset(IMC)
mappings = ctx.get_editor_property('default_key_mappings').get_editor_property('mappings')
mapping_info = unreal.InputService.get_mappings(IMC)
for action_name, trigger_class, threshold_name in [
        ('IA_Dodge', 'InputTriggerTap', 'tap_release_time_threshold'),
        ('IA_Sprint', 'InputTriggerHold', 'hold_time_threshold')]:
    index = next(i for i, m in enumerate(mapping_info)
                 if m.action_name == action_name and m.key_name == 'SpaceBar')
    trigger = mappings[index].get_editor_property('triggers')[0]
    assert trigger.get_class().get_name() == trigger_class
    trigger.set_editor_property(threshold_name, 0.18)
    print('MODIFIED:', IMC, action_name, threshold_name, '=0.18')

# Reject a stationary tap before any dodge state, timer, or montage starts.
g = 'TryEnterDodge'
entry = 'D4F3ADD14203EA2BDE51E7A40B877FCB'
old_first = '00DCCD464D173355501145A6627A3DFD'
assert S.disconnect_pin(P, g, entry, 'then')
nodes = [
    {'ref': 'LiveMoveInput', 'type': 'variable_get', 'params': {'variable': 'LastMoveInput'}},
    {'ref': 'MoveLengthSq', 'type': 'function_call', 'params': {'class': 'KismetMathLibrary', 'function': 'VSize2DSquared'}},
    {'ref': 'HasMoveInput', 'type': 'function_call', 'params': {'class': 'KismetMathLibrary', 'function': 'Greater_DoubleDouble'}},
    {'ref': 'AllowMovingDodge', 'type': 'branch', 'params': {}},
]
links = [
    {'from_': 'LiveMoveInput.LastMoveInput', 'to': 'MoveLengthSq.A'},
    {'from_': 'MoveLengthSq.ReturnValue', 'to': 'HasMoveInput.A'},
    {'from_': 'HasMoveInput.ReturnValue', 'to': 'AllowMovingDodge.Condition'},
]
defaults = [{'node_ref': 'HasMoveInput', 'pin_name': 'B', 'value': '0.01'}]
result = S.build_graph(P, g, nodes, links, defaults, False, False)
assert result.success, (list(result.errors), list(result.warnings))
gate = dict(result.ref_to_node_id)['AllowMovingDodge']
assert S.connect_nodes(P, g, entry, 'then', gate, 'execute')
assert S.connect_nodes(P, g, gate, 'then', old_first, 'execute')
print('MODIFIED:', P, 'stationary Space exits TryEnterDodge before state changes')

# Remove every reachable reference to the temporary backstep choice.
select_anim = '5878EE1B49FC441BDB209C94161049D6'
roll_anim = 'A91A59DD486BFBC47339F2A501E67898'
assert S.connect_nodes(P, g, roll_anim, 'ReturnValue', select_anim, 'A')
assert S.disconnect_pin(P, g, select_anim, 'bSelectA')
assert S.set_node_pin_value(P, g, select_anim, 'bSelectA', 'false')
set_backstep = 'B80F1F6B4B13F9BED79901BD2A6EA5C0'
assert S.disconnect_pin(P, g, set_backstep, 'bIsBackstep')
assert S.set_node_pin_value(P, g, set_backstep, 'bIsBackstep', 'false')
print('MODIFIED:', P, 'backstep clip unselected and bIsBackstep always false')

backstep = unreal.EditorAssetLibrary.load_asset(BACKSTEP)
assert backstep.get_editor_property('enable_root_motion')
backstep.set_editor_property('enable_root_motion', False)
print('MODIFIED:', BACKSTEP, 'restored root motion disabled')

bp = unreal.EditorAssetLibrary.load_asset(P)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE
print('COMPILED:', P)
for path in (IMC, P, BACKSTEP):
    assert unreal.EditorAssetLibrary.save_asset(path, False)
    print('SAVED:', path)
