"""MCP-only delta edits: visible real traces and faster SwordShield combo.

DS3 supplies the structural reference. Values below are Battle tuning.
Backups preserve the project state before this change.
"""
import unreal
import vibeue
import PolishSoulsHits as H

S, P, B = H.S, H.P, H.B


def trace_display(path, graph, color):
    traces = [n for n in S.get_nodes_in_graph(path, graph, 0, 'Sphere Trace By Channel')
              if any(p.pin_name == 'execute' and p.is_connected for p in n.pins)]
    if not traces:
        return
    title = 'Attack display: exact damage sweeps; orange boss / blue sword, green contact'
    getters = S.get_nodes_in_graph(path, graph, 0, 'Get AttackDebugDrawMode', False)
    if getters:
        ident = getters[0].node_id
    else:
        r = S.build_graph(path, graph, [H.get('Mode', 'AttackDebugDrawMode')], [], [], False, False)
        assert r.success, list(r.errors)
        ident = r.ref_to_node_id['Mode']
        print('ADDED:', path, graph, 'AttackDebugDrawMode', ident)
    for n in traces:
        assert S.connect_nodes(path, graph, ident, 'AttackDebugDrawMode', n.node_id, 'DrawDebugType')
        for pin, value in [('TraceColor', color), ('TraceHitColor', '(R=0.1,G=1,B=0.2,A=1)'),
                           ('DrawTime', '.06')]:
            assert S.set_node_pin_value(path, graph, n.node_id, pin, value), (graph, pin)
        print('MODIFIED:', path, graph, n.node_id, 'actual sweep display')
    if not any(n.node_title == title for n in S.get_nodes_in_graph(path, graph, 0, '', False)):
        S.add_comment_around_nodes(path, graph, title, [ident]+[n.node_id for n in traces])
    connections = S.get_connections(path, graph)
    assert all(any(c.source_node_id == ident and c.target_node_id == n.node_id
                   and c.target_pin_name == 'DrawDebugType' for c in connections) for n in traces)


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    for path in [P, B]:
        if 'AttackDebugDrawMode' not in {v.variable_name for v in S.list_variables(path)}:
            assert S.add_member_variable(path, 'AttackDebugDrawMode', 'EDrawDebugTrace',
                                         'ForOneFrame', False, '', True)
            print('ADDED:', path, 'AttackDebugDrawMode')
        assert S.set_variable_default_value(path, 'AttackDebugDrawMode', 'ForOneFrame')
        result = S.compile_blueprint(path)
        assert result.success, list(result.errors)
    trace_display(P, 'TraceSwordWindow', '(R=0.1,G=0.65,B=1,A=1)')
    trace_display(B, 'EventGraph', '(R=1,G=0.28,B=0.02,A=1)')
    trace_display(B, 'TraceOtherHand', '(R=1,G=0.28,B=0.02,A=1)')
    polish_impact()
    contact_marks()

    # Existing bShowHitDebug draws the constant body capsule and socket points.
    # Keep it available for inspection, with the new attack display independent.
    assert S.set_variable_default_value(B, 'bShowHitDebug', 'false')
    for name, value in [('AttackPlayRate', 1.4), ('HitStopDuration', .045),
                        ('HitStopDilation', .12), ('ComboWindowRatio', .62/1.1),
                        ('AttackRollCancelRatio', .60/1.1)]:
        assert S.set_variable_default_value(P, name, str(value))
        print('MODIFIED:', P, name, value)
    for i in range(1, 5):
        path = f'/Game/BossArena/Player/Animation/SwordShield/Montages/AM_Sword_Attack_{i}'
        for notify in unreal.AnimMontageService.list_notifies(path):
            time = { 'AN_AttackComboQueue': .62 if i < 4 else .748,
                     'AN_AttackRollCancel': .60 if i < 4 else .66,
                     'AN_AttackRecovery': .94 }.get(str(notify.notify_name))
            if time is not None:
                assert unreal.AnimMontageService.set_notify_trigger_time(path, notify.notify_index, time)
                print('MODIFIED:', path, str(notify.notify_name), time)
        assert unreal.AnimMontageService.set_blend_in(path, .04)
        assert unreal.AnimMontageService.set_blend_out(path, .08)
        assert unreal.EditorAssetLibrary.save_asset(path, False)
    for path in [P, B]:
        result = S.compile_blueprint(path)
        print('COMPILE', path, result)
        assert result.success and result.num_errors == 0, list(result.errors)
        assert unreal.EditorAssetLibrary.save_asset(path, False)
        cdo = unreal.get_default_object(H.asset(path).generated_class())
        print('VERIFIED', path, 'AttackDebugDrawMode', cdo.get_editor_property('AttackDebugDrawMode'))
    # A compile can reinstate inherited collision responses on the placed boss.
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if 'BP_Boss_Crunch' in actor.get_class().get_name():
            actor.set_editor_property('bShowHitDebug', False)
            actor.set_editor_property('AttackDebugDrawMode', unreal.DrawDebugTrace.FOR_ONE_FRAME)
            capsule = actor.get_component_by_class(unreal.CapsuleComponent)
            for channel in [unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionChannel.ECC_CAMERA]:
                capsule.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
            print('MODIFIED:', actor.get_path_name(), 'attack display on, body display off, capsule ignores traces/camera')
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('SAVED: current arena')


def polish_impact():
    # Preserve the existing effect, reducing the screen area it obscures.
    for n in S.get_nodes_in_graph(P, 'ResolveSwordContact', 0, 'Spawn Emitter at Location'):
        assert S.set_node_pin_value(P, 'ResolveSwordContact', n.node_id, 'Scale', '.28,.28,.28')
        print('MODIFIED:', P, 'sword impact effect scale', .28)


def contact_marks():
    # A short green marker makes the brief collision frame readable without
    # accumulating many complete sweep volumes over moving limbs.
    for path, graph, apply, after, a, b, selector in [
        (P, 'ResolveSwordContact', 'DF7022AB412DB9654A4EEA857A777DC5',
         '5C63381746F739763391A8B630A8D458', '27DA10A94F19164B13848A856A5C46AA', '', ''),
        (B, 'EventGraph', 'F4B8A4F74F6801B738475D926C6D47C3',
         'EA0F290B4A470E7CFBA38D8CD6E2C753', 'CFC277AC4A819C1AADB95DA0940F4DC3',
         '2951DD4843C4211CA5BA2793164294AE', 'FEDD45BE4155233A0E2647ABB2568037'),
        (B, 'TraceOtherHand', 'BFF531C9487C9D3A735EA2A5080FD869',
         'BE54BC234079E2C9F3109E8E59EBCF08', '7069066344C5DC99978A4198C3797551',
         '8068EBA148606CD4E72CAAA3453AD128', '1ADC8C9B465A9EBE0EE25E9BF1285C3C')]:
        title = 'Contact marker: green ring at actual mesh impact, 0.12 seconds'
        if any(n.node_title == title for n in S.get_nodes_in_graph(path, graph, 0, '', False)):
            continue
        nodes = [H.call('Mark', 'KismetSystemLibrary', 'DrawDebugSphere')]
        wires = [(apply+'.then','Mark.execute'),('Mark.then',after+'.execute')]
        if b:
            nodes.append(H.call('Point', 'KismetMathLibrary', 'SelectVector'))
            wires.extend([(a+'.ImpactPoint','Point.A'),(b+'.ImpactPoint','Point.B'),
                          (selector+'.ReturnValue','Point.bPickA'),('Point.ReturnValue','Mark.Center')])
        else:
            wires.append((a+'.ImpactPoint','Mark.Center'))
        H.block(path, graph, title, nodes, wires,
                [('Mark','Radius',10),('Mark','Segments',12),('Mark','Duration',.12),
                 ('Mark','Thickness',3),('Mark','LineColor','(R=.1,G=1,B=.2,A=1)')])
