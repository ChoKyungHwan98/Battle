"""Incremental intent-polish migration. Run inside Unreal MCP; never starts PIE.

Stage 1 centralizes execution eligibility and records actual accepted requests.
Graph deltas retain original nodes and record each changed connection for rollback.
"""
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G
import ApplyCombatQA as Q

B, S = H.B, unreal.BlueprintService
D = '/Game/BossArena/Boss/AI/BP_BossActionDefinition'
get, put, call, node = H.get, H.put, H.call, H.node


def build(graph, nodes, links=(), defaults=()):
    return G.build(B, graph, nodes, links, defaults)


def wire(graph, src, pin, dst, dest):
    existing = [c for c in S.get_connections(B, graph)
                if c.target_node_id == dst and c.target_pin_name == dest]
    if any(c.source_node_id == src and c.source_pin_name == pin for c in existing):
        return
    for c in existing:
        print('REWIRE', graph, c.source_node_id, c.source_pin_name, dst, dest)
    assert S.disconnect_pin(B, graph, dst, dest)
    assert S.connect_nodes(B, graph, src, pin, dst, dest)
    print('CONNECTED', graph, src, pin, dst, dest)


def source_hook(graph, target, source):
    marker = 'IntentPolish: request source ' + source
    if any(n.node_title == marker for n in S.get_nodes_in_graph(B, graph, 0, '', False)):
        return
    edge = next(c for c in S.get_connections(B, graph)
                if c.target_node_id == target and c.target_pin_name == 'execute')
    ids = build(graph, [put('Source', 'AttackRequestSource')], [],
                [('Source', 'AttackRequestSource', source)])
    wire(graph, edge.source_node_id, edge.source_pin_name, ids['Source'], 'execute')
    wire(graph, ids['Source'], 'then', target, 'execute')
    assert S.add_comment_around_nodes(B, graph, marker, list(ids.values()))


def eligibility():
    for name, kind, value in [
        ('bActionStartAllowed', 'bool', 'false'), ('ActionStartReason', 'string', ''),
        ('AttackRequestSource', 'string', 'unknown'), ('AttackStartedSource', 'string', ''),
        ('AttackStartedActionId', 'int', -1), ('AttackStartedName', 'string', ''),
        ('AttackStartedMontage', 'string', ''), ('AttackStartDistance', 'real', 0),
        ('AttackStartFacing', 'real', 0), ('AttackStartMinDot', 'real', .5),
        ('bAttackPreview', 'bool', 'false')]:
        if name not in {v.variable_name for v in S.list_variables(B)}:
            H.variable(B, name, kind, value)
    e = H.function(B, 'ValidateCombatActionStart')
    g = 'ValidateCombatActionStart'
    if G.empty_body(B, g):
        ns = [put('Reset', 'bActionStartAllowed'), get('Action', 'ActiveAction'),
              get('Player', 'ObservedPlayer'), get('State', 'BossState'),
              call('Ready', 'BlueprintGameplayTagLibrary', 'MatchesTag'),
              call('ValidAction', 'KismetSystemLibrary', 'IsValid'),
              call('ValidPlayer', 'KismetSystemLibrary', 'IsValid'),
              node('Health', 'member_get', **{'class': H.P, 'member': 'CurrentHealth'}),
              node('Down', 'member_get', **{'class': H.P, 'member': 'bKnockedDown'}),
              call('Alive', 'KismetMathLibrary', 'Greater_DoubleDouble'),
              call('Standing', 'KismetMathLibrary', 'Not_PreBool'),
              call('TargetOK', 'KismetMathLibrary', 'BooleanAND'),
              call('Distance', 'Actor', 'GetHorizontalDistanceTo'),
              call('Facing', 'Actor', 'GetHorizontalDotProductTo'),
              put('LiveDistance', 'UtilityDistance'), put('StartDistance', 'AttackStartDistance'),
              put('StartFacing', 'AttackStartFacing'),
              get('Slot', 'SelectedSlot'), get('Cooldowns', 'CooldownUntil'),
              call('IndexValid', 'KismetArrayLibrary', 'Array_IsValidIndex'),
              call('Cooldown', 'KismetArrayLibrary', 'Array_Get'),
              call('Now', 'GameplayStatics', 'GetTimeSeconds'),
              call('Cooled', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'),
              get('Source', 'AttackRequestSource'),
              call('IsPhaseRequest', 'KismetStringLibrary', 'EqualEqual_StrStr'),
              call('IsSlam', 'KismetMathLibrary', 'EqualEqual_IntInt'),
              get('PhaseTwo', 'bPhaseTwo'),
              call('PhaseSlam', 'KismetMathLibrary', 'BooleanAND'),
              call('PhaseException', 'KismetMathLibrary', 'BooleanAND'),
              call('NotApproach', 'KismetMathLibrary', 'NotEqual_IntInt'),
              call('HasMontage', 'KismetSystemLibrary', 'IsValid'),
              call('FarEnough', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'),
              call('NearEnough', 'KismetMathLibrary', 'LessEqual_DoubleDouble'),
              call('InRange', 'KismetMathLibrary', 'BooleanAND'),
              call('RangeAllowed', 'KismetMathLibrary', 'BooleanOR'),
              get('MinDot', 'AttackStartMinDot'),
              call('FacingOK', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble'),
              call('FacingAllowed', 'KismetMathLibrary', 'BooleanOR'),
              call('CooldownAllowed', 'KismetMathLibrary', 'BooleanOR'),
              put('Allow', 'bActionStartAllowed'), put('Accepted', 'ActionStartReason')]
        for ref, member in [('Min', 'MinDistance'), ('Max', 'MaxDistance'),
                            ('Enabled', 'bEnabled'), ('Id', 'ActionId'), ('Montage', 'Montage')]:
            ns.append(node(ref, 'member_get', **{'class': D, 'member': member}))
        links = [(e+'.then', 'Reset.execute'), ('State.BossState', 'Ready.TagOne'),
                 ('Action.ActiveAction', 'ValidAction.Object'), ('Player.ObservedPlayer', 'ValidPlayer.Object'),
                 ('Player.ObservedPlayer', 'Health.self'), ('Player.ObservedPlayer', 'Down.self'),
                 ('Health.CurrentHealth', 'Alive.A'), ('Down.bKnockedDown', 'Standing.A'),
                 ('Alive.ReturnValue', 'TargetOK.A'), ('Standing.ReturnValue', 'TargetOK.B'),
                 ('Player.ObservedPlayer', 'Distance.OtherActor'), ('Player.ObservedPlayer', 'Facing.OtherActor'),
                 ('Distance.ReturnValue', 'LiveDistance.UtilityDistance'),
                 ('LiveDistance.Output_Get', 'StartDistance.AttackStartDistance'),
                 ('Facing.ReturnValue', 'StartFacing.AttackStartFacing'),
                 ('Cooldowns.CooldownUntil', 'IndexValid.TargetArray'), ('Slot.SelectedSlot', 'IndexValid.IndexToTest'),
                 ('Cooldowns.CooldownUntil', 'Cooldown.TargetArray'), ('Slot.SelectedSlot', 'Cooldown.Index'),
                 ('Cooldown.Item', 'Cooled.B'), ('Now.ReturnValue', 'Cooled.A'),
                 ('Source.AttackRequestSource', 'IsPhaseRequest.A'), ('Id.ActionId', 'IsSlam.A'),
                 ('PhaseTwo.bPhaseTwo', 'PhaseSlam.A'), ('IsSlam.ReturnValue', 'PhaseSlam.B'),
                 ('PhaseSlam.ReturnValue', 'PhaseException.A'), ('IsPhaseRequest.ReturnValue', 'PhaseException.B'),
                 ('Id.ActionId', 'NotApproach.A'), ('Montage.Montage', 'HasMontage.Object'),
                 ('Distance.ReturnValue', 'FarEnough.A'), ('Min.MinDistance', 'FarEnough.B'),
                 ('Distance.ReturnValue', 'NearEnough.A'), ('Max.MaxDistance', 'NearEnough.B'),
                 ('FarEnough.ReturnValue', 'InRange.A'), ('NearEnough.ReturnValue', 'InRange.B'),
                 ('InRange.ReturnValue', 'RangeAllowed.A'), ('PhaseException.ReturnValue', 'RangeAllowed.B'),
                 ('Facing.ReturnValue', 'FacingOK.A'), ('MinDot.AttackStartMinDot', 'FacingOK.B'),
                 ('FacingOK.ReturnValue', 'FacingAllowed.A'), ('PhaseException.ReturnValue', 'FacingAllowed.B'),
                 ('Cooled.ReturnValue', 'CooldownAllowed.A'), ('PhaseException.ReturnValue', 'CooldownAllowed.B'),
                 ('Allow.then', 'Accepted.execute')]
        for ref in ['Min', 'Max', 'Enabled', 'Id', 'Montage']:
            links.append(('Action.ActiveAction', ref+'.self'))
        defaults = [('Reset', 'bActionStartAllowed', 'false'), ('Allow', 'bActionStartAllowed', 'true'),
                    ('Accepted', 'ActionStartReason', 'accepted'),
                    ('Ready', 'TagTwo', '(TagName="Boss.Combat.Ready")'), ('Ready', 'bExactMatch', 'true'),
                    ('Alive', 'B', 0), ('IsPhaseRequest', 'B', 'phase_intro'), ('IsSlam', 'B', 8),
                    ('NotApproach', 'B', 7)]
        prev = 'Reset.then'
        checks = [('Ready.ReturnValue','not_ready'), ('ValidAction.ReturnValue','invalid_action'),
                  ('ValidPlayer.ReturnValue','invalid_target'), ('TargetOK.ReturnValue','target_unavailable'),
                  ('Enabled.bEnabled','disabled'), ('NotApproach.ReturnValue','movement_only'),
                  ('HasMontage.ReturnValue','missing_montage'), ('IndexValid.ReturnValue','invalid_cooldown_index'),
                  ('CooldownAllowed.ReturnValue','cooldown'), ('RangeAllowed.ReturnValue','distance'),
                  ('FacingAllowed.ReturnValue','facing')]
        for i, (condition, reason) in enumerate(checks):
            if reason == 'disabled':
                links += [(prev, 'LiveDistance.execute'), ('LiveDistance.then', 'StartDistance.execute'),
                          ('StartDistance.then', 'StartFacing.execute')]
                prev = 'StartFacing.then'
            ns += [put('Reason'+str(i), 'ActionStartReason'), node('Gate'+str(i), 'branch')]
            links += [(prev, 'Reason'+str(i)+'.execute'), ('Reason'+str(i)+'.then','Gate'+str(i)+'.execute'),
                      (condition, 'Gate'+str(i)+'.Condition')]
            defaults.append(('Reason'+str(i), 'ActionStartReason', reason))
            prev = 'Gate'+str(i)+'.then'
        links.append((prev, 'Allow.execute'))
        build(g, ns, links, defaults)


def begin_gate():
    g = 'BeginCombatAction'; marker = 'IntentPolish: validate before changing attack state'
    if any(n.node_title == marker for n in S.get_nodes_in_graph(B, g, 0, '', False)):
        return
    e = G.entry(B, g)
    first = next(c.target_node_id for c in S.get_connections(B,g) if c.source_node_id==e and c.source_pin_name=='then')
    ns = [call('Check', B, 'ValidateCombatActionStart'), get('Allowed', 'bActionStartAllowed'),
          node('Gate','branch'), call('Rejected', B, 'RecordCombatQA'), put('IdleAction','UtilityAction'),
          get('Action','ActiveAction'), get('Source','AttackRequestSource'),
          put('StoreSource','AttackStartedSource'), put('StoreId','AttackStartedActionId'),
          put('StoreName','AttackStartedName'), put('StoreMontage','AttackStartedMontage'),
          call('MontageName','KismetSystemLibrary','GetObjectName'), call('Log',B,'RecordCombatQA')]
    for ref,member in [('Id','ActionId'),('Name','DisplayName'),('Montage','Montage')]:
        ns.append(node(ref,'member_get',**{'class':D,'member':member}))
    links = [('Check.then','Gate.execute'), ('Allowed.bActionStartAllowed','Gate.Condition'),
             ('Gate.else','Rejected.execute'), ('Gate.then','StoreSource.execute'),
             ('Source.AttackRequestSource','StoreSource.AttackStartedSource'),
             ('StoreSource.then','StoreId.execute'), ('Id.ActionId','StoreId.AttackStartedActionId'),
             ('StoreId.then','StoreName.execute'), ('Name.DisplayName','StoreName.AttackStartedName'),
             ('StoreName.then','StoreMontage.execute'), ('Montage.Montage','MontageName.Object'),
             ('MontageName.ReturnValue','StoreMontage.AttackStartedMontage'),
             ('StoreMontage.then','Log.execute'), ('Log.then',first+'.execute'),
             ('Rejected.then','IdleAction.execute')]
    for ref in ['Id','Name','Montage']:
        links.append(('Action.ActiveAction',ref+'.self'))
    ids=build(g,ns,links,[('Rejected','Event','attack_rejected'),('Log','Event','attack_accepted'),('IdleAction','UtilityAction',0)])
    wire(g,e,'then',ids['Check'],'execute')
    assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))


def qa_fields():
    g='RecordCombatQA'; marker='IntentPolish: actual execution identity v2'
    if any(n.node_title == marker for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    write='7351315649F7330AF5C248810231A881'
    before=next(c for c in S.get_connections(B,g) if c.target_node_id==write and c.target_pin_name=='InString')
    row=Q.Row(''); row.last=before.source_node_id+'.'+before.source_pin_name
    for key,var,kind in [('request_source','AttackRequestSource','string'),
                         ('started_source','AttackStartedSource','string'),
                         ('started_action_id','AttackStartedActionId','int'),
                         ('started_name','AttackStartedName','string'),
                         ('started_montage','AttackStartedMontage','string'),
                         ('start_distance','AttackStartDistance','real'),
                         ('start_facing','AttackStartFacing','real'),
                         ('start_allowed','bActionStartAllowed','bool'),
                         ('start_reason','ActionStartReason','string'),
                         ('preview','bAttackPreview','bool')]:
        ref='Value'+var;row.nodes.append(get(ref,var));row.add(key,kind,ref+'.'+var)
    ids=build(g,row.nodes,row.links,row.defaults)
    ref,pin=row.last.split('.')
    wire(g,ids[ref],pin,write,'InString')
    assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))


def apply_stage1():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    eligibility()
    source_hook('ChooseCombatAction','D6C8DBF54591DF08F662A79DF4396DD5','utility')
    source_hook('RequestCombatAction','78B761954BA2583D31A0F79DA1108AFD','manual')
    source_hook('BeginPendingSlam','9CC306814F416827E84EAA87B1C0DAD2','phase_intro')
    # Keep the legacy function for comparison, but remove its ONLY normal caller.
    g='FinishCombatAction'; old='FCC89C124A7336A890474BB039B169B4'
    if any(c.target_node_id==old and c.target_pin_name=='execute' for c in S.get_connections(B,g)):
        assert S.disconnect_pin(B,g,old,'execute')
        print('DISCONNECTED',g,'post-recovery random followup')
    begin_gate(); qa_fields()
    r=S.compile_blueprint(B)
    print('COMPILE',r.success,list(r.errors),list(r.warnings))
    assert r.success and not r.errors and not r.warnings
    assert unreal.EditorAssetLibrary.save_asset(B)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==H.asset(B).generated_class():
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
            print('MODIFIED capsule Visibility Ignore',actor.get_path_name())
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('SAVED stage1')


def inspect_stage1():
    """Read graph topology, not a gameplay or hand-contact test."""
    import json
    from pathlib import Path
    g = 'BeginCombatAction'
    ns = list(S.get_nodes_in_graph(B, g, 0, '', False))
    edges = list(S.get_connections(B, g))
    e = G.entry(B, g)
    check = next(n.node_id for n in ns if n.node_title.startswith('Validate Combat Action Start'))
    assert any(c.source_node_id == e and c.target_node_id == check for c in edges)
    gate = next(c.target_node_id for c in edges if c.source_node_id == check and c.source_pin_name == 'then')
    assert next(n.node_type for n in ns if n.node_id == gate) == 'K2Node_IfThenElse'
    first = '764E2CFC44444A34E762FEB8B3C9C6CB'
    # No direct execution path from entry to the old mutating body remains.
    incoming = [c for c in edges if c.target_node_id == first and c.target_pin_name == 'execute']
    assert len(incoming) == 1
    assert next(n.node_title for n in ns if n.node_id == incoming[0].source_node_id).startswith('Record Combat QA')
    validation = list(S.get_nodes_in_graph(B, 'ValidateCombatActionStart', 0, '', False))
    assert sum(n.node_type == 'K2Node_IfThenElse' for n in validation) == 11
    index = next(n for n in validation if n.node_title == 'Is Valid Index')
    assert next(p.is_connected for p in S.get_node_pins(B, 'ValidateCombatActionStart', index.node_id)
                if p.pin_name == 'IndexToTest')
    legacy_callers = []
    for graph in S.list_graphs(B):
        calls = list(S.get_nodes_in_graph(B, graph.graph_name, 0, 'Try Begin Followup', False))
        for n in calls:
            if any(p.pin_name == 'execute' and p.is_connected
                   for p in S.get_node_pins(B, graph.graph_name, n.node_id)):
                legacy_callers.append((graph.graph_name, n.node_id))
    assert not legacy_callers, legacy_callers
    report = {'stage': 1, 'pie_run': False, 'compile_errors': 0, 'compile_warnings': 0,
              'checks': {'entry_checks_before_mutation': True, 'sequential_validation_gates': 11,
                         'cooldown_index_connected': True, 'live_legacy_followup_callers': legacy_callers},
              'remaining': ['attack intent navigation', 'explicit GOAP goal and collision paths',
                            'single/two-hit weighted routes', 'motion contact calibration',
                            'HUD and MotionLab rejection feedback', 'user gameplay verification']}
    path = Path(unreal.Paths.project_dir())/'Saved/VibeUE/Reports/crunch_intent_polish_stage1.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('VERIFIED', json.dumps(report, ensure_ascii=False))
    return str(path)
