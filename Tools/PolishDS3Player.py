"""Run in Unreal Python with PIE stopped. Delta edits; preserves existing work."""
import unreal
import vibeue

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
A = '/Game/BossArena/Player/Animation/ABP_Player_Combat'
BS = '/Game/BossArena/Player/Animation/SwordShield/BS_SwordShield_8Dir_Runtime'
IDLE = '/Game/BossArena/Player/Animation/SwordShield/Sequences/Q_SwordShieldAnimsetPro_part1_Sword_Idle'
S = unreal.BlueprintService


def node(ref, kind, **params):
    return {'ref': ref, 'type': kind, 'params': params}


def call(ref, cls, function):
    return node(ref, 'function_call', **{'class': cls, 'function': function})


def wire(graph, source, pin, target, target_pin):
    assert S.connect_nodes(P, graph, source, pin, target, target_pin)


def block(graph, label, nodes, connections, defaults=()):
    if any(n.node_title == label for n in S.get_nodes_in_graph(P, graph, 0, '', False)):
        return
    result = S.build_graph(P, graph, nodes,
        [{'from_': src, 'to': dst} for src, dst in connections],
        [{'node_ref': ref, 'pin_name': pin, 'value': str(value)} for ref, pin, value in defaults],
        False, True)
    print('MODIFIED:', P, graph, label, result.success, list(result.errors), list(result.warnings))
    assert result.success, (list(result.errors), list(result.warnings))
    ids = list(result.ref_to_node_id.values())
    S.auto_layout_selected_nodes(P, graph, ids)
    assert S.add_comment_around_nodes(P, graph, label, ids)


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    bp = unreal.EditorAssetLibrary.load_asset(P)
    backup = '/Game/BossArena/Player/Animation/SwordShield/Backup/BP_Player_Combat_PreDS3Polish_20260928'
    if not unreal.EditorAssetLibrary.does_asset_exist(backup):
        assert unreal.EditorAssetLibrary.duplicate_asset(P, backup)
        unreal.EditorAssetLibrary.save_asset(backup, False)
        print('CREATED:', backup, 'snapshot of in-progress player before polish')
    existing = {v.variable_name for v in S.list_variables(P)}
    for name, value in [('MediumRollDuration', .70), ('RollTravelDuration', .56), ('RollQueueOpen', .35)]:
        if name not in existing:
            assert unreal.BlueprintEditorLibrary.add_member_variable(bp, name,
                unreal.BlueprintEditorLibrary.get_basic_type_by_name('real'))
            print('ADDED:', P, name)
        assert S.set_variable_default_value(P, name, str(value))
    for name, value in [('IFrameDuration', 26/60), ('DodgeDistance', 320),
                        ('DodgeMoveEase', 1.6), ('DodgeCooldown', .001)]:
        assert S.set_variable_default_value(P, name, str(value))
        print('MODIFIED:', P, name, value)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)

    g = 'TryEnterDodge'
    block(g, 'DS3 polish: fixed 0.70s roll / 0.56s swept travel / normalized clip rate',
        [node('Duration', 'variable_get', variable='MediumRollDuration'),
         node('Travel', 'variable_get', variable='RollTravelDuration'),
         call('Rate', 'KismetMathLibrary', 'Divide_DoubleDouble'),
         call('StopVelocity', 'MovementComponent', 'StopMovementImmediately')],
        [('Duration.MediumRollDuration', 'BCB0A6D0483A9196161BF59AEB99AA0E.Time'),
         ('Duration.MediumRollDuration', 'Rate.B'),
         ('71F126A147559CB7613D1B8CFC204D02.ReturnValue', 'Rate.A'),
         ('Rate.ReturnValue', '7F207E4F482F91F9CEE4FCB6B9F52272.InPlayRate'),
         ('Travel.RollTravelDuration', '35E968FC41C4CD0D2143959F766CDACE.DodgeMoveDuration'),
         ('FB87E4BB4EF485B05F978DA2CD222847.then', 'BCB0A6D0483A9196161BF59AEB99AA0E.execute'),
         ('544927024DFFA32529F71EB730E7D9F9.CharacterMovement', 'StopVelocity.self'),
         ('F77A988B42CCA1AC02498A81DFE7A74E.then', 'StopVelocity.execute'),
         ('StopVelocity.then', 'BDD1C33C4069F02424A14F8DF8241745.execute')])

    block(g, 'DS3 polish: accept one roll in latter half; replace queued attack',
        [node('Elapsed', 'variable_get', variable='DodgeMoveElapsed'),
         node('Open', 'variable_get', variable='RollQueueOpen'),
         call('Late', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'), node('Gate', 'branch'),
         node('Queue', 'variable_set', variable='bDodgeBuffered'),
         node('ClearAttack', 'variable_set', variable='bAttackBuffered')],
        [('00DCCD464D173355501145A6627A3DFD.then', 'Gate.execute'),
         ('Elapsed.DodgeMoveElapsed', 'Late.A'), ('Open.RollQueueOpen', 'Late.B'),
         ('Late.ReturnValue', 'Gate.Condition'), ('Gate.then', 'Queue.execute'),
         ('Queue.then', 'ClearAttack.execute')],
        [('Queue', 'bDodgeBuffered', 'true'), ('ClearAttack', 'bAttackBuffered', 'false')])

    block(g, 'DS3 polish: starting a roll consumes any previous attack reservation',
        [node('ClearPreviousAttack', 'variable_set', variable='bAttackBuffered')],
        [('D4A507B6483103E1044019A74265E3B2.then', 'ClearPreviousAttack.execute'),
         ('ClearPreviousAttack.then', '2373DE3A446FAB93916D429146972757.execute')],
        [('ClearPreviousAttack', 'bAttackBuffered', 'false')])

    block('TryEnterAttack', 'DS3 polish: accept one attack after roll midpoint; replace queued roll',
        [node('State', 'variable_get', variable='ActionState'),
         call('Rolling', 'KismetMathLibrary', 'EqualEqual_ByteByte'),
         node('Elapsed', 'variable_get', variable='DodgeMoveElapsed'),
         node('Open', 'variable_get', variable='RollQueueOpen'),
         call('Late', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'),
         call('Both', 'KismetMathLibrary', 'BooleanAND'), node('Gate', 'branch'),
         node('QueueAttack', 'variable_set', variable='bAttackBuffered'),
         node('ClearRoll', 'variable_set', variable='bDodgeBuffered')],
        [('7A5DE5AE47918A785BAFCCB7F5C8965C.else', 'Gate.execute'),
         ('State.ActionState', 'Rolling.A'), ('Elapsed.DodgeMoveElapsed', 'Late.A'),
         ('Open.RollQueueOpen', 'Late.B'), ('Rolling.ReturnValue', 'Both.A'),
         ('Late.ReturnValue', 'Both.B'), ('Both.ReturnValue', 'Gate.Condition'),
         ('Gate.then', 'QueueAttack.execute'), ('QueueAttack.then', 'ClearRoll.execute')],
        [('Rolling', 'B', '2'), ('QueueAttack', 'bAttackBuffered', 'true'), ('ClearRoll', 'bDodgeBuffered', 'false')])

    # A damaging hit in the vulnerable tail must not be unlocked by an old roll timer.
    block('EventGraph', 'DS3 polish: roll recovery only while rolling; consume one queued action',
        [node('State', 'variable_get', variable='ActionState'),
         call('StillRolling', 'KismetMathLibrary', 'EqualEqual_ByteByte'), node('RecoveryGate', 'branch'),
         node('Roll', 'variable_get', variable='bDodgeBuffered'), node('RollGate', 'branch'),
         node('ClearRoll', 'variable_set', variable='bDodgeBuffered'), call('RollNow', P, 'TryEnterDodge'),
         node('Attack', 'variable_get', variable='bAttackBuffered'), node('AttackGate', 'branch'),
         node('ClearAttack', 'variable_set', variable='bAttackBuffered'), call('AttackNow', P, 'TryEnterAttack')],
        [('0BFE6D494352AB5C878D71B5C0477EEA.then', 'RecoveryGate.execute'),
         ('State.ActionState', 'StillRolling.A'), ('StillRolling.ReturnValue', 'RecoveryGate.Condition'),
         ('RecoveryGate.then', 'A0202F3A420B00CAEEF6DA9F611EA160.execute'),
         ('320632594D29C73062720D93998B0379.then', 'RollGate.execute'),
         ('Roll.bDodgeBuffered', 'RollGate.Condition'), ('RollGate.then', 'ClearRoll.execute'),
         ('ClearRoll.then', 'RollNow.execute'), ('RollGate.else', 'AttackGate.execute'),
         ('Attack.bAttackBuffered', 'AttackGate.Condition'), ('AttackGate.then', 'ClearAttack.execute'),
         ('ClearAttack.then', 'AttackNow.execute')],
        [('StillRolling', 'B', '2'), ('ClearRoll', 'bDodgeBuffered', 'false'),
         ('ClearAttack', 'bAttackBuffered', 'false')])
    assert S.set_node_pin_value(P, 'EventGraph', 'BF57E195411A6E6D769FF4B5716D497E', 'bDodgeOnCooldown', 'false')
    assert S.set_node_pin_value(P, 'EventGraph', 'A0202F3A420B00CAEEF6DA9F611EA160', 'InBlendOutTime', '.08')

    block('UpdateLockOnRotation', 'DS3 polish: lock camera follows, roll body keeps committed facing',
        [node('State', 'variable_get', variable='ActionState'),
         call('Rolling', 'KismetMathLibrary', 'EqualEqual_ByteByte'), node('Gate', 'branch')],
        [('93FA2CC34693EF5FF156159A2824F8DB.then', 'Gate.execute'),
         ('State.ActionState', 'Rolling.A'), ('Rolling.ReturnValue', 'Gate.Condition'),
         ('Gate.then', '5936F55A42E3B8CC6B90E293BF6F8E37.execute'),
         ('Gate.else', '60B0C3B34F10449FC615B084F617DB53.execute')], [('Rolling', 'B', '2')])

    # The named Idle is already on every zero-speed sample: verify rather than
    # replacing a working BlendSpace or introducing a second idle route.
    bs = unreal.EditorAssetLibrary.load_asset(BS)
    idle = unreal.EditorAssetLibrary.load_asset(IDLE)
    zeros = [s for s in bs.get_editor_property('sample_data') if s.get_editor_property('sample_value').y == 0]
    assert len(zeros) == 9 and all(s.get_editor_property('animation') == idle for s in zeros)
    assert all(not s.get_editor_property('use_single_frame_for_blending') for s in zeros)
    print('VERIFIED:', IDLE, 'all 9 zero-speed samples; continuous playback')
    for graph in ['TryEnterDodge', 'TryEnterAttack', 'EventGraph', 'UpdateLockOnRotation']:
        error = S.auto_layout_graph(P, graph)
        assert not error, error
        print('MODIFIED:', P, graph, 'layout with existing comment groups preserved')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE
    assert unreal.EditorAssetLibrary.save_asset(P, False)
    print('SAVED:', P)


if __name__ == '__main__':
    apply()
