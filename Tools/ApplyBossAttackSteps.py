"""Author bounded attack steps through Unreal MCP; does not run PIE."""
import unreal
import vibeue
import PolishSoulsHits as H

B = H.B
N = '/Game/BossArena/Boss/Animations/ANS_BossAttackStep'
S = unreal.BlueprintService
get, put, call, node = H.get, H.put, H.call, H.node


def build(path, graph, nodes, links=(), defaults=()):
    result = S.build_graph(path, graph, nodes,
        [{'from_': a, 'to': b} for a, b in links],
        [{'node_ref': a, 'pin_name': b, 'value': str(c)} for a, b, c in defaults],
        False, False)
    print('MODIFIED', path, graph, result.success, list(result.errors))
    assert result.success, list(result.errors)
    return dict(result.ref_to_node_id)


def entry(path, graph):
    return next(n.node_id for n in S.get_nodes_in_graph(path, graph, 0, '', False)
                if n.node_type == 'K2Node_FunctionEntry')


def empty_body(path, graph):
    return all(n.node_type in {'K2Node_FunctionEntry', 'K2Node_FunctionResult'}
               for n in S.get_nodes_in_graph(path, graph, 0, '', False))


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    for name, kind, value in [
            ('bAttackStepActive', 'bool', 'false'),
            ('AttackStepDistance', 'real', 0), ('AttackStepDuration', 'real', .3),
            ('AttackStepElapsed', 'real', 0), ('AttackStepProgress', 'real', 0),
            ('AttackStepDirection', 'vector', '(X=0,Y=0,Z=0)')]:
        if kind == 'vector':
            if name not in {v.variable_name for v in S.list_variables(B)}:
                vector_type = unreal.BlueprintEditorLibrary.get_member_variable_type(
                    H.asset(H.P), 'DodgeMoveDirection')
                assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(B), name, vector_type)
                print('ADDED', B, name)
            assert S.set_variable_default_value(B, name, value)
        else:
            H.variable(B, name, kind, value)
    for name, params in [
            ('BeginAttackStep', [('Distance', 'double'), ('SourceDuration', 'double')]),
            ('AdvanceAttackStep', [('DeltaSeconds', 'double')]),
            ('EndAttackStep', [])]:
        if name not in {g.graph_name for g in S.list_graphs(B)}:
            assert S.create_function_graph(B, name)
            for param, kind in params:
                assert S.add_function_parameter(B, name, param, kind)
            print('ADDED', B, name)
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))

    # Step direction is committed once, independently of later aiming.
    g = 'BeginAttackStep'
    if empty_body(B, g):
        e = entry(B, g)
        build(B, g, [
            get('State', 'BossState'), call('Attack', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
            call('Recovery', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
            call('NotRecovery', 'KismetMathLibrary', 'Not_PreBool'),
            call('Allowed', 'KismetMathLibrary', 'BooleanAND'), node('Gate', 'branch'),
            call('ClampDistance', 'KismetMathLibrary', 'FClamp'), put('Distance', 'AttackStepDistance'),
            get('Rate', 'AttackPlayRate'), call('SafeRate', 'KismetMathLibrary', 'FMax'),
            call('Duration', 'KismetMathLibrary', 'Divide_DoubleDouble'),
            call('SafeDuration', 'KismetMathLibrary', 'FMax'), put('Time', 'AttackStepDuration'),
            put('ResetTime', 'AttackStepElapsed'), put('ResetProgress', 'AttackStepProgress'),
            call('Forward', 'Actor', 'GetActorForwardVector'), put('Direction', 'AttackStepDirection'),
            put('Enable', 'bAttackStepActive')], [
            (e+'.then', 'Gate.execute'), ('State.BossState', 'Attack.TagOne'),
            ('State.BossState', 'Recovery.TagOne'), ('Recovery.ReturnValue', 'NotRecovery.A'),
            ('Attack.ReturnValue', 'Allowed.A'), ('NotRecovery.ReturnValue', 'Allowed.B'),
            ('Allowed.ReturnValue', 'Gate.Condition'), ('Gate.then', 'Distance.execute'),
            (e+'.Distance', 'ClampDistance.Value'), ('ClampDistance.ReturnValue', 'Distance.AttackStepDistance'),
            ('Distance.then', 'Time.execute'), (e+'.SourceDuration', 'Duration.A'),
            ('Rate.AttackPlayRate', 'SafeRate.A'), ('SafeRate.ReturnValue', 'Duration.B'),
            ('Duration.ReturnValue', 'SafeDuration.A'), ('SafeDuration.ReturnValue', 'Time.AttackStepDuration'),
            ('Time.then', 'ResetTime.execute'), ('ResetTime.then', 'ResetProgress.execute'),
            ('ResetProgress.then', 'Direction.execute'), ('Forward.ReturnValue', 'Direction.AttackStepDirection'),
            ('Direction.then', 'Enable.execute')], [
            ('Attack', 'TagTwo', '(TagName="Boss.Combat.Attack")'), ('Attack', 'bExactMatch', 'false'),
            ('Recovery', 'TagTwo', '(TagName="Boss.Combat.Attack.Recovery")'),
            ('Recovery', 'bExactMatch', 'false'), ('ClampDistance', 'Min', 0), ('ClampDistance', 'Max', 85),
            ('SafeRate', 'B', .01), ('SafeDuration', 'B', .03),
            ('ResetTime', 'AttackStepElapsed', 0), ('ResetProgress', 'AttackStepProgress', 0),
            ('Enable', 'bAttackStepActive', 'true')])

    # Smooth cumulative progress avoids constant sliding and limits low-FPS travel.
    g = 'AdvanceAttackStep'
    if empty_body(B, g):
        e = entry(B, g)
        build(B, g, [
            get('Active', 'bAttackStepActive'), node('ActiveGate', 'branch'),
            get('State', 'BossState'), call('Attack', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
            call('Recovery', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
            call('NotRecovery', 'KismetMathLibrary', 'Not_PreBool'),
            call('Allowed', 'KismetMathLibrary', 'BooleanAND'), node('StateGate', 'branch'),
            put('Cancel', 'bAttackStepActive'),
            get('Elapsed', 'AttackStepElapsed'), call('NextTime', 'KismetMathLibrary', 'Add_DoubleDouble'),
            get('Duration', 'AttackStepDuration'), call('BoundTime', 'KismetMathLibrary', 'FClamp'),
            put('Time', 'AttackStepElapsed'), call('Ratio', 'KismetMathLibrary', 'Divide_DoubleDouble'),
            call('Ease', 'KismetMathLibrary', 'Ease'), get('Distance', 'AttackStepDistance'),
            call('Target', 'KismetMathLibrary', 'Multiply_DoubleDouble'),
            get('Previous', 'AttackStepProgress'), call('Delta', 'KismetMathLibrary', 'Subtract_DoubleDouble'),
            get('Direction', 'AttackStepDirection'), call('Offset', 'KismetMathLibrary', 'Multiply_VectorFloat'),
            call('Move', 'Actor', 'K2_AddActorWorldOffset'), put('Progress', 'AttackStepProgress'),
            call('Hit', 'GameplayStatics', 'BreakHitResult'), node('Blocked', 'branch'),
            put('Stop', 'bAttackStepActive')], [
            (e+'.then', 'ActiveGate.execute'), ('Active.bAttackStepActive', 'ActiveGate.Condition'),
            ('ActiveGate.then', 'StateGate.execute'), ('State.BossState', 'Attack.TagOne'),
            ('State.BossState', 'Recovery.TagOne'), ('Recovery.ReturnValue', 'NotRecovery.A'),
            ('Attack.ReturnValue', 'Allowed.A'), ('NotRecovery.ReturnValue', 'Allowed.B'),
            ('Allowed.ReturnValue', 'StateGate.Condition'), ('StateGate.else', 'Cancel.execute'),
            ('StateGate.then', 'Time.execute'), ('Elapsed.AttackStepElapsed', 'NextTime.A'),
            (e+'.DeltaSeconds', 'NextTime.B'), ('NextTime.ReturnValue', 'BoundTime.Value'),
            ('Duration.AttackStepDuration', 'BoundTime.Max'), ('BoundTime.ReturnValue', 'Time.AttackStepElapsed'),
            ('Time.then', 'Move.execute'), ('Time.AttackStepElapsed', 'Ratio.A'),
            ('Duration.AttackStepDuration', 'Ratio.B'), ('Ratio.ReturnValue', 'Ease.Alpha'),
            ('Ease.ReturnValue', 'Target.A'), ('Distance.AttackStepDistance', 'Target.B'),
            ('Target.ReturnValue', 'Delta.A'), ('Previous.AttackStepProgress', 'Delta.B'),
            ('Direction.AttackStepDirection', 'Offset.A'), ('Delta.ReturnValue', 'Offset.B'),
            ('Offset.ReturnValue', 'Move.DeltaLocation'), ('Move.then', 'Progress.execute'),
            ('Target.ReturnValue', 'Progress.AttackStepProgress'), ('Move.SweepHitResult', 'Hit.Hit'),
            ('Progress.then', 'Blocked.execute'), ('Hit.bBlockingHit', 'Blocked.Condition'),
            ('Blocked.then', 'Stop.execute')], [
            ('Attack', 'TagTwo', '(TagName="Boss.Combat.Attack")'), ('Attack', 'bExactMatch', 'false'),
            ('Recovery', 'TagTwo', '(TagName="Boss.Combat.Attack.Recovery")'),
            ('Recovery', 'bExactMatch', 'false'), ('Cancel', 'bAttackStepActive', 'false'),
            ('BoundTime', 'Min', 0), ('Ease', 'A', 0), ('Ease', 'B', 1),
            ('Ease', 'EasingFunc', 'EaseInOut'), ('Ease', 'BlendExp', 2),
            ('Move', 'bSweep', 'true'), ('Move', 'bTeleport', 'false'),
            ('Stop', 'bAttackStepActive', 'false')])
    g = 'EndAttackStep'
    if empty_body(B, g):
        build(B, g, [put('Stop', 'bAttackStepActive')],
              [(entry(B, g)+'.then', 'Stop.execute')], [('Stop', 'bAttackStepActive', 'false')])
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))

    if not unreal.EditorAssetLibrary.does_asset_exist(N):
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', unreal.AnimNotifyState)
        created = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            N.rsplit('/', 1)[-1], N.rsplit('/', 1)[0], unreal.Blueprint, factory)
        assert created
        print('CREATED', N)
    H.variable(N, 'StepDistance', 'real', 40)
    assert S.set_variable_instance_editable(N, 'StepDistance', True)
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(N))
    for g, function in [('Received_NotifyBegin', 'BeginAttackStep'),
                        ('Received_NotifyTick', 'AdvanceAttackStep'),
                        ('Received_NotifyEnd', 'EndAttackStep')]:
        assert S.override_function(N, g)
        if not empty_body(N, g):
            continue
        e = entry(N, g)
        result = next(n.node_id for n in S.get_nodes_in_graph(N, g, 0, '', False)
                      if n.node_type == 'K2Node_FunctionResult')
        nodes = [call('Owner', 'ActorComponent', 'GetOwner'),
                 node('Boss', 'cast', target_class=B), call('Step', B, function)]
        links = [(e+'.then', 'Boss.execute'), (e+'.MeshComp', 'Owner.self'),
                 ('Owner.ReturnValue', 'Boss.Object'), ('Boss.then', 'Step.execute'),
                 ('Boss.AsBP Boss Crunch', 'Step.self'), ('Step.then', result+'.execute'),
                 ('Boss.CastFailed', result+'.execute')]
        if g == 'Received_NotifyBegin':
            nodes += [get('Distance', 'StepDistance')]
            links += [('Distance.StepDistance', 'Step.Distance'), (e+'.TotalDuration', 'Step.SourceDuration')]
        elif g == 'Received_NotifyTick':
            links += [(e+'.FrameDeltaTime', 'Step.DeltaSeconds')]
        build(N, g, nodes, links, [(result, 'ReturnValue', 'true')])
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(N))

    # The step window follows the lifted/planting foot, not the entire attack.
    root = '/Game/BossArena/Boss/Animations/'
    windows = {
        'AM_Boss_Combo_01_LowRecover': [(.10, .40, 40)],
        'AM_Boss_Combo_02_SlowRecover': [(.04, .40, 45)],
        'AM_Boss_Combo_03': [(.01, .25, 25)],
        'AM_Boss_Hook_Empowered': [(.20, .60, 25)],
        'AM_Boss_GutPunch': [(.12, .44, 50)]}
    chain = root+'AM_Boss_Jab_Jab_Hook_Matched'
    segments = unreal.AnimMontageService.list_anim_segments(chain, 0)
    windows['AM_Boss_Jab_Jab_Hook_Matched'] = [
        (s.start_time+start/s.play_rate, s.start_time+end/s.play_rate, distance)
        for s, start, end, distance in [(segments[0], .10, .40, 40),
                                       (segments[3], .04, .40, 45),
                                       (segments[5], .04, .38, 35)]]
    notify_class = H.asset(N).generated_class()
    for name, steps in windows.items():
        path = root+name
        montage = H.asset(path)
        existing = [e.notify_state_class for e in unreal.AnimationLibrary.get_animation_notify_events(montage)
                    if e.notify_state_class and e.notify_state_class.get_class() == notify_class]
        if not existing:
            montage.modify()
            unreal.AnimationLibrary.add_animation_notify_track(montage, 'AttackStep', unreal.LinearColor(.1,.7,1,1))
            for start, end, distance in steps:
                notify = unreal.AnimationLibrary.add_animation_notify_state_event(
                    montage, 'AttackStep', start, end-start, notify_class)
                notify.set_editor_property('StepDistance', distance)
                print('ADDED step', name, round(start,3), round(end,3), distance)
        print('SAVED', path, unreal.EditorAssetLibrary.save_loaded_asset(montage, False))
    # Replace old whole-windup glide; dash retains its separate committed launch.
    for name in ['Left', 'Right', 'Uppercut', 'Sweep', 'Combo', 'GuardBreak']:
        path = '/Game/BossArena/Boss/AI/Actions/DA_Attack_'+name
        action = H.asset(path)
        action.modify()
        action.set_editor_property('DashMaxDistance', 0)
        print('MODIFIED old windup lunge off', path)
        assert unreal.EditorAssetLibrary.save_loaded_asset(action)
    for path in [B, N]:
        print('SAVED', path, unreal.EditorAssetLibrary.save_asset(path))


if __name__ == '__main__':
    apply()
