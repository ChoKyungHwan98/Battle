"""One-time migration for Battle's Space tap/hold split.

Run only against the pre-migration assets with PIE stopped. The 0.10 s threshold
is a Battle choice; the installed DS3 HKS does not verify that exact rule.
"""
import unreal
import vibeue

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
IMC = '/Game/BossArena/Player/Input/IMC_Player_Combat'
BACKSTEP = '/Game/FightAnimations_FBX/A_Slip_Back_Step'
S = unreal.BlueprintService


def edge(graph, source, source_pin, target, target_pin):
    assert S.connect_nodes(P, graph, source, source_pin, target, target_pin), (graph, source_pin, target_pin)


def make(graph, nodes, links=(), defaults=()):
    result = S.build_graph(
        P, graph, nodes,
        [{'from_': a, 'to': b} for a, b in links],
        [{'node_ref': a, 'pin_name': b, 'value': str(c)} for a, b, c in defaults],
        False, False)
    assert result.success, (list(result.errors), list(result.warnings))
    return dict(result.ref_to_node_id)


def node(ref, kind, **params):
    return {'ref': ref, 'type': kind, 'params': params}


def call(ref, function):
    return node(ref, 'function_call', **{'class': 'KismetMathLibrary', 'function': function})


assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
assert unreal.EditorAssetLibrary.does_asset_exist(BACKSTEP)
run_id = unreal.WorkflowService.start_run('DS3-inspired Space tap/hold and lock-retaining sprint', '{}')
print('RUN', run_id)

# Two explicit trigger types share Space: Tap fires on short release; Hold fires
# while the key remains pressed. UE 5.8 source confirms Tap uses strict < time.
maps = unreal.InputService.get_mappings(IMC)
dodge_index = next(i for i, m in enumerate(maps) if m.action_name == 'IA_Dodge' and m.key_name == 'SpaceBar')
sprint_index = next(i for i, m in enumerate(maps) if m.action_name == 'IA_Sprint' and m.key_name == 'SpaceBar')
if not unreal.InputService.get_triggers(IMC, dodge_index):
    assert unreal.InputService.add_trigger(IMC, dodge_index, 'Tap')
    print('MODIFIED:', IMC, 'IA_Dodge SpaceBar Tap trigger')
ctx = unreal.EditorAssetLibrary.load_asset(IMC)
mappings = ctx.get_editor_property('default_key_mappings').get_editor_property('mappings')
tap = mappings[dodge_index].get_editor_property('triggers')[0]
hold = mappings[sprint_index].get_editor_property('triggers')[0]
assert tap.get_class().get_name() == 'InputTriggerTap'
assert hold.get_class().get_name() == 'InputTriggerHold'
tap.set_editor_property('tap_release_time_threshold', 0.10)
hold.set_editor_property('hold_time_threshold', 0.10)
print('MODIFIED:', IMC, 'Tap <0.10s; Hold >=0.10s')

bp = unreal.EditorAssetLibrary.load_asset(P)
existing = {v.variable_name for v in S.list_variables(P)}
if 'bIsBackstep' not in existing:
    assert unreal.BlueprintEditorLibrary.add_member_variable(
        bp, 'bIsBackstep', unreal.BlueprintEditorLibrary.get_basic_type_by_name('bool'))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    print('ADDED:', P, 'bIsBackstep')

# Roll/backstep happens on release, never on key-down.
g = 'EventGraph'
ia_dodge = '6EC1090C424F97BCD7A74BBC1E66520E'
try_dodge = '6B07A46449832F3B8D2F9B9B6ABA9234'
assert S.disconnect_pin(P, g, ia_dodge, 'Started')
edge(g, ia_dodge, 'Triggered', try_dodge, 'execute')
print('MODIFIED:', P, 'IA_Dodge Triggered -> TryEnterDodge')

# Hold may trigger while stationary; only moving input starts the sprint. As
# IA_Sprint stays Triggered after threshold, starting movement later also works.
ids = make(g, [node('MoveInput', 'variable_get', variable='LastMoveInput'),
               call('InputSizeSq', 'VSize2DSquared'),
               call('IsMoving', 'Greater_DoubleDouble'),
               node('SprintGate', 'branch')],
           [('MoveInput.LastMoveInput', 'InputSizeSq.A'),
            ('InputSizeSq.ReturnValue', 'IsMoving.A'),
            ('IsMoving.ReturnValue', 'SprintGate.Condition')],
           [('IsMoving', 'B', '0.01')])
ia_sprint = 'C8A98E9A4E8C8A3FEFA71D9DDA3FAEE0'
start_sprint = '67897D9243632B8BAD2092A185AEC96D'
stop_sprint = 'E2A6631846202CB9D664EC8FFC4C0B3A'
assert S.disconnect_pin(P, g, ia_sprint, 'Triggered')
edge(g, ia_sprint, 'Triggered', ids['SprintGate'], 'execute')
edge(g, ids['SprintGate'], 'then', start_sprint, 'execute')
edge(g, ids['SprintGate'], 'else', stop_sprint, 'execute')
print('MODIFIED:', P, 'Sprint requires live movement input')

# Keep LockOnTarget bound during sprint. Existing camera and movement then
# continue to use the target, and manual lock toggle can still operate.
g = 'SetSprinting'
assert S.disconnect_pin(P, g, '43F91F104D3EE5590C5D089E8CDC355B', 'then')
g = 'ToggleLockOn'
assert S.disconnect_pin(P, g, 'B08601A34C9C0FB9482F9498197D27FF', 'then')
edge(g, 'B08601A34C9C0FB9482F9498197D27FF', 'then',
     '57014A2746821C7BDD4C0AB3CAE6BB0E', 'execute')
print('MODIFIED:', P, 'sprint no longer clears lock; lock toggle permitted')

# The existing idle fallback already points backward, but plays a backward
# *roll*. Select a separate mannequin-compatible backstep clip. Its root track
# supplies travel; the old manual DodgeMove distance graph has no exec path.
g = 'TryEnterDodge'
is_idle = '5D7DBB4D484DC969231F10B7C1482EB3'
select_anim = '5878EE1B49FC441BDB209C94161049D6'
start_location = '350180CE40DA5297DE96CBB6CB6E2323'
set_direction = 'C7C59DAC4EC3F6969A1DC38642717BFB'
assert S.disconnect_pin(P, g, select_anim, 'A')
assert S.set_node_pin_value(P, g, select_anim, 'A', BACKSTEP)
edge(g, is_idle, 'ReturnValue', select_anim, 'bSelectA')
ids2 = make(g, [node('LatchBackstep', 'variable_set', variable='bIsBackstep')])
assert S.disconnect_pin(P, g, start_location, 'then')
edge(g, start_location, 'then', ids2['LatchBackstep'], 'execute')
edge(g, is_idle, 'ReturnValue', ids2['LatchBackstep'], 'bIsBackstep')
edge(g, ids2['LatchBackstep'], 'then', set_direction, 'execute')
print('MODIFIED:', P, 'stationary tap selects separate backstep clip')
backstep_asset = unreal.EditorAssetLibrary.load_asset(BACKSTEP)
backstep_asset.set_editor_property('enable_root_motion', True)
print('MODIFIED:', BACKSTEP, 'enable_root_motion=True')

unreal.BlueprintEditorLibrary.compile_blueprint(bp)
print('COMPILED:', P)
assert unreal.EditorAssetLibrary.save_asset(IMC, False)
assert unreal.EditorAssetLibrary.save_asset(P, False)
assert unreal.EditorAssetLibrary.save_asset(BACKSTEP, False)
print('SAVED:', IMC, P, BACKSTEP)
