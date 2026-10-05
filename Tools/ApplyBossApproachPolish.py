"""Polish the existing Utility/GOAP approach executor via Unreal MCP; no PIE."""
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G

B, S = H.B, unreal.BlueprintService
get, put, call, node = H.get, H.put, H.call, H.node


def build(graph, nodes, links=(), defaults=()):
    r = S.build_graph(B, graph, nodes,
        [{'from_': a, 'to': b} for a, b in links],
        [{'node_ref': a, 'pin_name': b, 'value': str(c)} for a, b, c in defaults], False, False)
    print('MODIFIED', graph, r.success, list(r.errors), list(r.warnings))
    assert r.success and not r.warnings, (list(r.errors), list(r.warnings))
    ids = dict(r.ref_to_node_id)
    if ids:
        S.auto_layout_selected_nodes(B, graph, list(ids.values()))
    return ids


def hook(graph, source, pin, target, target_pin, function):
    if any(function.lower() == ''.join(c for c in n.node_title.split('\n')[0] if c.isalnum()).lower()
           for n in S.get_nodes_in_graph(B, graph, 0, '', False)):
        return
    ids = build(graph, [call('Policy', B, function)])
    assert S.disconnect_pin(B, graph, source, pin)
    assert S.connect_nodes(B, graph, source, pin, ids['Policy'], 'execute')
    assert S.connect_nodes(B, graph, ids['Policy'], 'then', target, target_pin)


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    settings = [('bCombatApproachActive', 'bool', 'false'),
        ('ApproachGoalDistance', 'real', 190), ('ApproachChoiceRoll', 'real', 0),
        ('ApproachDeadline', 'real', 0), ('ApproachCooldownUntil', 'real', 0),
        ('ApproachArrivalBiasUntil', 'real', 0), ('ApproachCurrentSpeed', 'real', 170),
        ('ApproachRunSpeed', 'real', 440), ('ApproachWalkSpeed', 'real', 170),
        ('ApproachMaxDuration', 'real', 8), ('ApproachNearWeightMultiplier', 'real', .18),
        ('ApproachAttackBias', 'real', 1.35)]
    for name, kind, value in settings:
        H.variable(B, name, kind, value)
    for name in ['ConfigureCombatApproach', 'BeginCombatApproach', 'UpdateCombatApproach',
                 'CompleteCombatApproach', 'AdjustApproachUtility']:
        if name not in {g.graph_name for g in S.list_graphs(B)}:
            assert S.create_function_graph(B, name)
            if name == 'CompleteCombatApproach':
                assert S.add_function_parameter(B, name, 'Arrived', 'bool')
            print('ADDED', name)
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))

    g = 'ConfigureCombatApproach'
    if G.empty_body(B, g):
        e = G.entry(B, g)
        build(g, [call('Random', 'KismetMathLibrary', 'RandomFloatInRange'),
            put('Roll', 'ApproachChoiceRoll'), get('Distance', 'UtilityDistance'),
            call('Far', 'KismetMathLibrary', 'Greater_DoubleDouble'),
            call('CloseRoll', 'KismetMathLibrary', 'Less_DoubleDouble'),
            call('FarGoal', 'KismetMathLibrary', 'SelectFloat'),
            call('NearGoal', 'KismetMathLibrary', 'SelectFloat'),
            call('GoalChoice', 'KismetMathLibrary', 'SelectFloat'),
            call('StepRoom', 'KismetMathLibrary', 'Subtract_DoubleDouble'),
            call('TargetMin', 'KismetMathLibrary', 'FMin'), call('SafeGoal', 'KismetMathLibrary', 'FClamp'),
            put('Goal', 'ApproachGoalDistance'), call('Remaining', 'KismetMathLibrary', 'Subtract_DoubleDouble'),
            call('Speed', 'KismetMathLibrary', 'MapRangeClamped'),
            get('Run', 'ApproachRunSpeed'), get('Walk', 'ApproachWalkSpeed'),
            put('InitialSpeed', 'ApproachCurrentSpeed'),
            call('Description', 'KismetMathLibrary', 'SelectString'), put('Label', 'UtilityChoice')], [
            (e+'.then', 'Roll.execute'), ('Random.ReturnValue', 'Roll.ApproachChoiceRoll'),
            ('Roll.then', 'Goal.execute'), ('Roll.Output_Get', 'CloseRoll.A'),
            ('CloseRoll.ReturnValue', 'FarGoal.bPickA'), ('CloseRoll.ReturnValue', 'NearGoal.bPickA'),
            ('Distance.UtilityDistance', 'Far.A'), ('Far.ReturnValue', 'GoalChoice.bPickA'),
            ('FarGoal.ReturnValue', 'GoalChoice.A'), ('NearGoal.ReturnValue', 'GoalChoice.B'),
            ('Distance.UtilityDistance', 'StepRoom.A'), ('StepRoom.ReturnValue', 'TargetMin.A'),
            ('GoalChoice.ReturnValue', 'TargetMin.B'), ('TargetMin.ReturnValue', 'SafeGoal.Value'),
            ('SafeGoal.ReturnValue', 'Goal.ApproachGoalDistance'), ('Goal.then', 'InitialSpeed.execute'),
            ('Distance.UtilityDistance', 'Remaining.A'), ('Goal.Output_Get', 'Remaining.B'),
            ('Remaining.ReturnValue', 'Speed.Value'), ('Walk.ApproachWalkSpeed', 'Speed.OutRangeA'),
            ('Run.ApproachRunSpeed', 'Speed.OutRangeB'), ('Speed.ReturnValue', 'InitialSpeed.ApproachCurrentSpeed'),
            ('InitialSpeed.then', 'Label.execute'), ('Far.ReturnValue', 'Description.bPickA'),
            ('Description.ReturnValue', 'Label.UtilityChoice')], [
            ('Random', 'Min', 0), ('Random', 'Max', 1), ('Far', 'B', 400), ('CloseRoll', 'B', .70),
            ('FarGoal', 'A', 190), ('FarGoal', 'B', 245), ('NearGoal', 'A', 190), ('NearGoal', 'B', 225),
            ('StepRoom', 'B', 40), ('SafeGoal', 'Min', 190), ('SafeGoal', 'Max', 245),
            ('Speed', 'InRangeA', 50), ('Speed', 'InRangeB', 300),
            ('Description', 'A', '접근: 달리기 → 감속 → 일반 공격 검토'),
            ('Description', 'B', '접근: 한두 걸음 → 일반 공격 검토')])

    g = 'BeginCombatApproach'
    if G.empty_body(B, g):
        e = G.entry(B, g)
        build(g, [put('Active', 'bCombatApproachActive'), call('Now', 'GameplayStatics', 'GetTimeSeconds'),
            get('MaxTime', 'ApproachMaxDuration'), call('EndTime', 'KismetMathLibrary', 'Add_DoubleDouble'),
            put('Deadline', 'ApproachDeadline')], [
            (e+'.then', 'Active.execute'), ('Active.then', 'Deadline.execute'),
            ('Now.ReturnValue', 'EndTime.A'), ('MaxTime.ApproachMaxDuration', 'EndTime.B'),
            ('EndTime.ReturnValue', 'Deadline.ApproachDeadline')], [('Active', 'bCombatApproachActive', 'true')])

    g = 'CompleteCombatApproach'
    if G.empty_body(B, g):
        e = G.entry(B, g)
        build(g, [put('Inactive', 'bCombatApproachActive'), put('Ready', 'UtilityAction'),
            call('Stop', B, 'StopBossLocomotion'), call('Now', 'GameplayStatics', 'GetTimeSeconds'),
            call('Cooldown', 'KismetMathLibrary', 'Add_DoubleDouble'), put('CooldownUntil', 'ApproachCooldownUntil'),
            call('BonusEnd', 'KismetMathLibrary', 'Add_DoubleDouble'),
            call('BonusChoice', 'KismetMathLibrary', 'SelectFloat'), put('BiasUntil', 'ApproachArrivalBiasUntil'),
            call('Description', 'KismetMathLibrary', 'SelectString'), put('Label', 'UtilityChoice')], [
            (e+'.then', 'Inactive.execute'), ('Inactive.then', 'Ready.execute'), ('Ready.then', 'Stop.execute'),
            ('Stop.then', 'CooldownUntil.execute'), ('Now.ReturnValue', 'Cooldown.A'),
            ('Cooldown.ReturnValue', 'CooldownUntil.ApproachCooldownUntil'), ('CooldownUntil.then', 'BiasUntil.execute'),
            ('Now.ReturnValue', 'BonusEnd.A'), ('BonusEnd.ReturnValue', 'BonusChoice.A'),
            (e+'.Arrived', 'BonusChoice.bPickA'), ('BonusChoice.ReturnValue', 'BiasUntil.ApproachArrivalBiasUntil'),
            ('BiasUntil.then', 'Label.execute'), (e+'.Arrived', 'Description.bPickA'),
            ('Description.ReturnValue', 'Label.UtilityChoice')], [
            ('Inactive', 'bCombatApproachActive', 'false'), ('Ready', 'UtilityAction', 0),
            ('Cooldown', 'B', 1), ('BonusEnd', 'B', 1), ('BonusChoice', 'B', 0),
            ('Description', 'A', '접근 완료: 닿는 일반 공격 검토'),
            ('Description', 'B', '접근 중단: 거리와 방향 재판단')])

    g = 'UpdateCombatApproach'
    if G.empty_body(B, g):
        e = G.entry(B, g)
        build(g, [get('Active', 'bCombatApproachActive'), node('ActiveGate', 'branch'),
            get('State', 'BossState'), call('Ready', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
            node('ReadyGate', 'branch'), put('Cancel', 'bCombatApproachActive'),
            get('Player', 'ObservedPlayer'), call('Valid', 'KismetSystemLibrary', 'IsValid'),
            node('ValidGate', 'branch'),
            node('Down', 'member_get', **{'class':H.P, 'member':'bKnockedDown'}),
            node('Health', 'member_get', **{'class':H.P, 'member':'CurrentHealth'}),
            call('Alive', 'KismetMathLibrary', 'Greater_DoubleDouble'),
            call('Standing', 'KismetMathLibrary', 'Not_PreBool'),
            call('Allowed', 'KismetMathLibrary', 'BooleanAND'), node('TargetGate', 'branch'),
            call('Distance', 'Actor', 'GetHorizontalDistanceTo'),
            put('LiveDistance', 'UtilityDistance'), get('Goal', 'ApproachGoalDistance'),
            call('Threshold', 'KismetMathLibrary', 'Add_DoubleDouble'),
            call('Reached', 'KismetMathLibrary', 'LessEqual_DoubleDouble'), node('ReachedGate', 'branch'),
            call('Finish', B, 'CompleteCombatApproach'), call('Abort', B, 'CompleteCombatApproach'),
            call('Now', 'GameplayStatics', 'GetTimeSeconds'), get('Deadline', 'ApproachDeadline'),
            call('WithinTime', 'KismetMathLibrary', 'Less_DoubleDouble'), node('TimeGate', 'branch'),
            call('Remaining', 'KismetMathLibrary', 'Subtract_DoubleDouble'),
            call('Speed', 'KismetMathLibrary', 'MapRangeClamped'), get('Run', 'ApproachRunSpeed'),
            get('Walk', 'ApproachWalkSpeed'), call('Delta', 'GameplayStatics', 'GetWorldDeltaSeconds'),
            call('SafeDelta', 'KismetMathLibrary', 'FMax'), call('FrameSpeed', 'KismetMathLibrary', 'Divide_DoubleDouble'),
            call('BoundSpeed', 'KismetMathLibrary', 'FClamp'), put('CurrentSpeed', 'ApproachCurrentSpeed'),
            get('Movement', 'CharacterMovement'), node('ApplySpeed', 'member_set',
                **{'class': 'CharacterMovementComponent', 'member': 'MaxWalkSpeed'})], [
            (e+'.then', 'ActiveGate.execute'), ('Active.bCombatApproachActive', 'ActiveGate.Condition'),
            ('ActiveGate.then', 'ReadyGate.execute'), ('State.BossState', 'Ready.TagOne'),
            ('Ready.ReturnValue', 'ReadyGate.Condition'), ('ReadyGate.else', 'Cancel.execute'),
            ('ReadyGate.then', 'ValidGate.execute'), ('Player.ObservedPlayer', 'Valid.Object'),
            ('Valid.ReturnValue', 'ValidGate.Condition'), ('ValidGate.else', 'Abort.execute'),
            ('ValidGate.then', 'TargetGate.execute'), ('Player.ObservedPlayer', 'Down.self'),
            ('Player.ObservedPlayer', 'Health.self'), ('Health.CurrentHealth', 'Alive.A'),
            ('Down.bKnockedDown', 'Standing.A'), ('Alive.ReturnValue', 'Allowed.A'),
            ('Standing.ReturnValue', 'Allowed.B'), ('Allowed.ReturnValue', 'TargetGate.Condition'),
            ('TargetGate.then', 'LiveDistance.execute'), ('TargetGate.else', 'Abort.execute'),
            ('Player.ObservedPlayer', 'Distance.OtherActor'),
            ('Distance.ReturnValue', 'LiveDistance.UtilityDistance'), ('LiveDistance.then', 'ReachedGate.execute'),
            ('LiveDistance.Output_Get', 'Reached.A'), ('Goal.ApproachGoalDistance', 'Threshold.A'),
            ('Threshold.ReturnValue', 'Reached.B'), ('Reached.ReturnValue', 'ReachedGate.Condition'),
            ('ReachedGate.then', 'Finish.execute'), ('ReachedGate.else', 'TimeGate.execute'),
            ('Now.ReturnValue', 'WithinTime.A'), ('Deadline.ApproachDeadline', 'WithinTime.B'),
            ('WithinTime.ReturnValue', 'TimeGate.Condition'), ('TimeGate.else', 'Abort.execute'),
            ('TimeGate.then', 'CurrentSpeed.execute'), ('LiveDistance.Output_Get', 'Remaining.A'),
            ('Goal.ApproachGoalDistance', 'Remaining.B'), ('Remaining.ReturnValue', 'Speed.Value'),
            ('Walk.ApproachWalkSpeed', 'Speed.OutRangeA'), ('Run.ApproachRunSpeed', 'Speed.OutRangeB'),
            ('Delta.ReturnValue', 'SafeDelta.A'), ('Remaining.ReturnValue', 'FrameSpeed.A'),
            ('SafeDelta.ReturnValue', 'FrameSpeed.B'), ('FrameSpeed.ReturnValue', 'BoundSpeed.Value'),
            ('Speed.ReturnValue', 'BoundSpeed.Max'), ('BoundSpeed.ReturnValue', 'CurrentSpeed.ApproachCurrentSpeed'),
            ('CurrentSpeed.then', 'ApplySpeed.execute'), ('Movement.CharacterMovement', 'ApplySpeed.self'),
            ('CurrentSpeed.Output_Get', 'ApplySpeed.MaxWalkSpeed')], [
            ('Ready', 'TagTwo', '(TagName="Boss.Combat.Ready")'), ('Ready', 'bExactMatch', 'true'),
            ('Cancel', 'bCombatApproachActive', 'false'), ('Threshold', 'B', 6),
            ('Alive', 'B', 0),
            ('Finish', 'Arrived', 'true'), ('Abort', 'Arrived', 'false'),
            ('Speed', 'InRangeA', 50), ('Speed', 'InRangeB', 300),
            ('SafeDelta', 'B', .001), ('BoundSpeed', 'Min', 0)])

    g = 'AdjustApproachUtility'
    if G.empty_body(B, g):
        e = G.entry(B, g)
        build(g, [get('Score', 'ScoreScratch'), call('Positive', 'KismetMathLibrary', 'Greater_DoubleDouble'),
            node('Eligible', 'branch'), get('Slot', 'EvaluatedSlot'),
            call('IsApproach', 'KismetMathLibrary', 'EqualEqual_IntInt'), node('ApproachGate', 'branch'),
            get('Distance', 'UtilityDistance'), get('NearFactor', 'ApproachNearWeightMultiplier'),
            call('DistanceFactor', 'KismetMathLibrary', 'MapRangeClamped'),
            call('Now', 'GameplayStatics', 'GetTimeSeconds'), get('Cooldown', 'ApproachCooldownUntil'),
            call('Cooled', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'),
            call('AvailableFactor', 'KismetMathLibrary', 'SelectFloat'),
            call('ApproachScore', 'KismetMathLibrary', 'Multiply_DoubleDouble'), put('ApplyApproach', 'ScoreScratch'),
            call('Reason', 'KismetMathLibrary', 'SelectString'), put('ApproachReason', 'ScoreReason'),
            call('Basic', 'KismetMathLibrary', 'LessEqual_IntInt'), get('BiasUntil', 'ApproachArrivalBiasUntil'),
            call('RecentArrival', 'KismetMathLibrary', 'Less_DoubleDouble'),
            call('BasicArrival', 'KismetMathLibrary', 'BooleanAND'), node('BiasGate', 'branch'),
            get('Bias', 'ApproachAttackBias'), call('AttackScore', 'KismetMathLibrary', 'Multiply_DoubleDouble'),
            put('ApplyAttack', 'ScoreScratch'), put('AttackReason', 'ScoreReason')], [
            (e+'.then', 'Eligible.execute'), ('Score.ScoreScratch', 'Positive.A'), ('Positive.ReturnValue', 'Eligible.Condition'),
            ('Eligible.then', 'ApproachGate.execute'), ('Slot.EvaluatedSlot', 'IsApproach.A'),
            ('IsApproach.ReturnValue', 'ApproachGate.Condition'), ('ApproachGate.then', 'ApplyApproach.execute'),
            ('Distance.UtilityDistance', 'DistanceFactor.Value'), ('NearFactor.ApproachNearWeightMultiplier', 'DistanceFactor.OutRangeA'),
            ('Now.ReturnValue', 'Cooled.A'), ('Cooldown.ApproachCooldownUntil', 'Cooled.B'),
            ('Cooled.ReturnValue', 'AvailableFactor.bPickA'), ('DistanceFactor.ReturnValue', 'AvailableFactor.A'),
            ('Score.ScoreScratch', 'ApproachScore.A'), ('AvailableFactor.ReturnValue', 'ApproachScore.B'),
            ('ApproachScore.ReturnValue', 'ApplyApproach.ScoreScratch'), ('ApplyApproach.then', 'ApproachReason.execute'),
            ('Cooled.ReturnValue', 'Reason.bPickA'), ('Reason.ReturnValue', 'ApproachReason.ScoreReason'),
            ('ApproachGate.else', 'BiasGate.execute'), ('Slot.EvaluatedSlot', 'Basic.A'),
            ('Now.ReturnValue', 'RecentArrival.A'), ('BiasUntil.ApproachArrivalBiasUntil', 'RecentArrival.B'),
            ('Basic.ReturnValue', 'BasicArrival.A'), ('RecentArrival.ReturnValue', 'BasicArrival.B'),
            ('BasicArrival.ReturnValue', 'BiasGate.Condition'), ('BiasGate.then', 'ApplyAttack.execute'),
            ('Score.ScoreScratch', 'AttackScore.A'), ('Bias.ApproachAttackBias', 'AttackScore.B'),
            ('AttackScore.ReturnValue', 'ApplyAttack.ScoreScratch'), ('ApplyAttack.then', 'AttackReason.execute')], [
            ('Positive', 'B', 0), ('IsApproach', 'B', 7), ('DistanceFactor', 'InRangeA', 285),
            ('DistanceFactor', 'InRangeB', 400), ('DistanceFactor', 'OutRangeB', 1),
            ('AvailableFactor', 'B', 0), ('Basic', 'B', 1),
            ('Reason', 'A', '접근 가능: 가까우면 짧은 걸음, 멀면 달리기'),
            ('Reason', 'B', '접근 직후: 반복 접근 대신 공격 검토'),
            ('AttackReason', 'ScoreReason', '선택 가능: 접근 직후 일반 주먹 선호')])
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))

    hook('ChooseCombatAction', '146054B44F1A41D21C29F1BA104B21B0', 'then',
         'E4626AA14D64BA30459A35A1F1389EAB', 'execute', 'ConfigureCombatApproach')
    hook('ChooseCombatAction', '406E21084D270EFFB724A1B651A73BA4', 'then',
         '816977494FEBA558373CF387EF04EEF8', 'execute', 'BeginCombatApproach')
    hook('EventGraph', '8D1D6B5742B80341649B9AAD90BDC3F6', 'then',
         '527DF14C4DB0932E31ED4E8F3A5B2E52', 'execute', 'UpdateCombatApproach')
    hook('EvaluateCombatUtility', 'A82B8D0648AE95F5F27415AD6409EC50', 'then',
         '0203C44E4592C2ACDEB57AA19A50DEEE', 'execute', 'AdjustApproachUtility')

    # Finish a chosen approach before rerolling attacks every 250ms.
    g = 'EvaluateCombatUtility'
    if not any(n.node_title == 'Get bCombatApproachActive' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('Approaching','bCombatApproachActive'),node('Hold','branch')],
                  [('Approaching.bCombatApproachActive','Hold.Condition')])
        assert S.disconnect_pin(B,g,'F996BD634D8951398E88FD904B663EF6','then')
        assert S.connect_nodes(B,g,'F996BD634D8951398E88FD904B663EF6','then',ids['Hold'],'execute')
        assert S.connect_nodes(B,g,ids['Hold'],'else','1A9456F448BE579CBA199E81C9CB3CC2','execute')
    # Attack movement belongs to the montage once an attack has begun.
    g='BeginCombatAction'
    if not any('bCombatApproachActive' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[put('CancelApproach','bCombatApproachActive')],defaults=[('CancelApproach','bCombatApproachActive','false')])
        assert S.disconnect_pin(B,g,'3993C7B040BA8F6B20D9C7A91E4DC5B4','then')
        assert S.connect_nodes(B,g,'3993C7B040BA8F6B20D9C7A91E4DC5B4','then',ids['CancelApproach'],'execute')
        assert S.connect_nodes(B,g,ids['CancelApproach'],'then','A85354F344BDF910C4BFCEB22D13644B','execute')

    # Existing navigation handles paths. The new tick changes speed only; no direct input bypass.
    g='ChooseCombatAction'
    if not any(n.node_title=='Get ApproachGoalDistance' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('Goal','ApproachGoalDistance'),get('Speed','ApproachCurrentSpeed')])
        S.disconnect_pin(B,g,'2F2B51724DD182DC5CA45DA7483CC15F','AcceptanceRadius')
        S.disconnect_pin(B,g,'816977494FEBA558373CF387EF04EEF8','MaxWalkSpeed')
        assert S.connect_nodes(B,g,ids['Goal'],'ApproachGoalDistance','2F2B51724DD182DC5CA45DA7483CC15F','AcceptanceRadius')
        assert S.connect_nodes(B,g,ids['Speed'],'ApproachCurrentSpeed','816977494FEBA558373CF387EF04EEF8','MaxWalkSpeed')
    if not any(n.node_title=='Complete Combat Approach\n타깃은 BP Boss Crunch' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('GoalTolerance','ApproachGoalDistance'),
            call('NavRadius','KismetMathLibrary','Subtract_DoubleDouble'),
            call('NavResult','KismetMathLibrary','Conv_ByteToInt'),
            call('Failed','KismetMathLibrary','EqualEqual_IntInt'),node('PathGate','branch'),
            call('AbortMove',B,'CompleteCombatApproach'),call('RefreshMove',B,'UpdateCombatApproach')], [
            ('GoalTolerance.ApproachGoalDistance','NavRadius.A'),
            ('2F2B51724DD182DC5CA45DA7483CC15F.ReturnValue','NavResult.InByte'),
            ('NavResult.ReturnValue','Failed.A'),('Failed.ReturnValue','PathGate.Condition'),
            ('2F2B51724DD182DC5CA45DA7483CC15F.then','PathGate.execute'),
            ('PathGate.then','AbortMove.execute'),('PathGate.else','RefreshMove.execute')], [
            ('NavRadius','B',20),('Failed','B',0),('AbortMove','Arrived','false')])
        S.disconnect_pin(B,g,'2F2B51724DD182DC5CA45DA7483CC15F','AcceptanceRadius')
        assert S.connect_nodes(B,g,ids['NavRadius'],'ReturnValue','2F2B51724DD182DC5CA45DA7483CC15F','AcceptanceRadius')
    g='EvaluateGoapPosition'
    if not any(n.node_title=='Get ApproachGoalDistance' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('Goal','ApproachGoalDistance'),get('Intent','UtilityAction'),
            call('ApproachIntent','KismetMathLibrary','EqualEqual_IntInt'),
            get('AttackRange','UtilityAttackRange'),call('PlanRange','KismetMathLibrary','SelectFloat'),
            call('GuardRange','KismetMathLibrary','FMin')], [
            ('Intent.UtilityAction','ApproachIntent.A'),('ApproachIntent.ReturnValue','PlanRange.bPickA'),
            ('Goal.ApproachGoalDistance','PlanRange.A'),('AttackRange.UtilityAttackRange','PlanRange.B'),
            ('PlanRange.ReturnValue','GuardRange.A')], [('ApproachIntent','B',2),('GuardRange','B',260)])
        assert S.connect_nodes(B,g,ids['PlanRange'],'ReturnValue','968829064575E6775AA5FBB7A67E8810','AttackRange')
        assert S.connect_nodes(B,g,ids['GuardRange'],'ReturnValue','968829064575E6775AA5FBB7A67E8810','GuardBreakRange')
    if not any(n.node_title=='Get ApproachCurrentSpeed' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[get('PlanSpeed','ApproachCurrentSpeed')])
        S.disconnect_pin(B,g,'968829064575E6775AA5FBB7A67E8810','MoveSpeed')
        assert S.connect_nodes(B,g,ids['PlanSpeed'],'ApproachCurrentSpeed','968829064575E6775AA5FBB7A67E8810','MoveSpeed')
    g='CompleteCombatApproach'
    if not any('Evaluate Combat Utility' in n.node_title for n in S.get_nodes_in_graph(B,g,0,'',False)):
        label=next(n.node_id for n in S.get_nodes_in_graph(B,g,0,'',False) if n.node_title=='Set UtilityChoice')
        ids=build(g,[node('ArrivedGate','branch'),call('ChooseAttack',B,'EvaluateCombatUtility')], [
            (G.entry(B,g)+'.Arrived','ArrivedGate.Condition'),
            (label+'.then','ArrivedGate.execute'),('ArrivedGate.then','ChooseAttack.execute')])
    card=H.asset('/Game/BossArena/Boss/AI/Actions/DA_Approach')
    card.modify(); card.set_editor_property('MinDistance',225)
    print('MODIFIED approach overlap begins at 225cm')
    assert unreal.EditorAssetLibrary.save_loaded_asset(card)
    r=S.build_graph(B,'UpdateCombatApproach',[],[],[],False,True)
    print('COMPILE',r.success,list(r.errors),list(r.warnings)); assert r.success and not r.errors
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('SAVED',B)


if __name__=='__main__':
    apply()
