"""Connect the prepared two-hit pattern using small, idempotent graph deltas. No PIE."""
import unreal
import vibeue
import ApplyBossIntentPolish as I
import ApplyCombatQA as Q
import PrepareBossTwoHit as P

B, S, H = I.B, I.S, I.H
get, put, call, node = I.get, I.put, I.call, I.node


def marked(graph, marker):
    return any(n.node_title == marker for n in S.get_nodes_in_graph(B, graph, 0, '', False))


def mark(graph, marker, ids):
    assert S.add_comment_around_nodes(B, graph, marker, list(ids.values()))


def native_hook(graph, target, function):
    marker = 'TwoHit: ' + function
    if marked(graph, marker):
        return
    edge = next(e for e in S.get_connections(B, graph)
                if e.target_node_id == target and e.target_pin_name == 'execute')
    ids = I.build(graph, [get('Mesh', 'Mesh'), call('Owner', 'ActorComponent', 'GetOwner'),
                         call('Native', 'BossCombatIntentLibrary', function)],
                  [('Mesh.Mesh', 'Owner.self'), ('Owner.ReturnValue', 'Native.Boss')])
    I.wire(graph, edge.source_node_id, edge.source_pin_name, ids['Native'], 'execute')
    I.wire(graph, ids['Native'], 'then', target, 'execute')
    mark(graph, marker, ids)


def include_two_hit(graph, slot_node, slot_pin, previous, targets, label):
    marker = 'TwoHit: ' + label
    if marked(graph, marker):
        return
    ids = I.build(graph, [call('Two', 'KismetMathLibrary', 'EqualEqual_IntInt'),
                         call('Include', 'KismetMathLibrary', 'BooleanOR')],
                  [(slot_node + '.' + slot_pin, 'Two.A'),
                   ('Two.ReturnValue', 'Include.B'), (previous + '.ReturnValue', 'Include.A')],
                  [('Two', 'B', 9)])
    for dst, pin in targets:
        I.wire(graph, ids['Include'], 'ReturnValue', dst, pin)
    mark(graph, marker, ids)


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    assert hasattr(unreal.BossCombatIntentLibrary, 'continue_two_hit_or_recover'), 'Build native code first'
    if 'IntentFinalScores' not in {v.variable_name for v in S.list_variables(B)}:
        H.variable(B, 'IntentFinalScores', 'string', '')
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))
    native_hook('BeginBossEncounter', '5F5D7E4545A64485C63893AA4997A40C', 'EnsureActionCooldownCapacity')
    native_hook('EvaluateCombatUtility', '071BE9324A4CA14332E54AB6A9CAECD5', 'FinalizeIntentScores')
    g = 'CloseActionImpact'; marker = 'TwoHit: check link before second strike'
    if not marked(g, marker):
        target = '4EF3AC2744FBF3277E19F9AE94364B44'
        edge = next(e for e in S.get_connections(B, g) if e.target_node_id == target and e.target_pin_name == 'execute')
        ids = I.build(g, [get('Mesh', 'Mesh'), call('Owner', 'ActorComponent', 'GetOwner'),
                          call('Link', 'BossCombatIntentLibrary', 'ContinueTwoHitOrRecover'), node('Continue', 'branch')],
                      [('Mesh.Mesh', 'Owner.self'), ('Owner.ReturnValue', 'Link.Boss'),
                       ('Link.then', 'Continue.execute'), ('Link.ReturnValue', 'Continue.Condition')])
        I.wire(g, edge.source_node_id, edge.source_pin_name, ids['Link'], 'execute')
        I.wire(g, ids['Continue'], 'then', target, 'execute')
        mark(g, marker, ids)
    include_two_hit('ComputeActionScore', '6CE13BF14561EFEE9E2AC998E47EE257', 'EvaluatedSlot',
                    '04C7FB5346AC04F9A72F379456B0CBC7', [('B046707449504A04FB172AAFC97ABA9B', 'bPickA')], 'selection range')
    include_two_hit('ComputeActionScore', '33F15069440EDCE64C8C45AF764951A3', 'EvaluatedSlot',
                    'E8B1CE244142AA1D42DD759BD7E5E853', [('51C4A43541B00D37833CB5B8950F291E', 'bPickA')], 'family repeat penalty')
    include_two_hit('RecordPunchFamilyUse', 'F690B027481E9D6E31EEC9B2F0A59B3E', 'ActionId',
                    '119120BB4DA50863293C67B2DD6F0D90', [('64CD7E3745BAB85A932C128AFFB65B5F', 'Condition')], 'record punch family')
    include_two_hit('TransitionBossState', 'EBEF206747DA5739996F7FB6E0B519E7', 'SelectedSlot',
                    '77B996084DEE08DBEE83F4AA680470A3',
                    [('5B1BCB08480670216CE351A50ECA1B80', 'B'), ('1EC1D4A64582504CDC5B5794860FF084', 'B')], 'ordinary punch turning rules')
    g='RecordCombatQA'; marker='TwoHit: finalized score evidence'
    if not marked(g, marker):
        write='7351315649F7330AF5C248810231A881'
        edge=next(e for e in S.get_connections(B,g) if e.target_node_id==write and e.target_pin_name=='InString')
        row=Q.Row(''); row.last=edge.source_node_id+'.'+edge.source_pin_name
        row.nodes.append(get('FinalScores','IntentFinalScores'))
        row.add('intent_final_scores','string','FinalScores.IntentFinalScores')
        ids=I.build(g,row.nodes,row.links,row.defaults); ref,pin=row.last.split('.')
        I.wire(g,ids[ref],pin,write,'InString'); mark(g,marker,ids)
    # Preserve IDs 0..8 and initialize only the new storage slot. Setter updates Blueprint defaults.
    cdo=unreal.get_default_object(H.asset(B).generated_class())
    actions=list(cdo.get_editor_property('Actions'))
    card=H.asset(P.CARD)
    if card not in actions:
        assert len(actions)==9
        actions.append(card)
        defaults='('+','.join('"'+a.get_path_name()+'"' for a in actions)+')'
        assert S.set_variable_default_value(B,'Actions',defaults)
        print('MODIFIED',B,'Actions: appended slot 9')
    cooldowns=list(cdo.get_editor_property('CooldownUntil'))
    if len(cooldowns)<len(actions):
        cooldowns += [0.0]*(len(actions)-len(cooldowns))
        assert S.set_variable_default_value(B,'CooldownUntil','('+','.join(map(str,cooldowns))+')')
    result=S.compile_blueprint(B)
    print('COMPILE',result.success,list(result.errors),list(result.warnings))
    assert result.success and not result.errors and not result.warnings
    cdo=unreal.get_default_object(H.asset(B).generated_class())
    assert len(cdo.get_editor_property('Actions'))==10 and cdo.get_editor_property('Actions')[9]==card
    assert len(cdo.get_editor_property('CooldownUntil'))>=10
    card.set_editor_property('bEnabled',True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(card)
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('ENABLED',P.CARD)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==H.asset(B).generated_class():
            actor.modify()
            placed=list(actor.get_editor_property('Actions'))
            if card not in placed:
                assert len(placed)==9
                placed.append(card); actor.set_editor_property('Actions',placed)
            unreal.BossCombatIntentLibrary.ensure_action_cooldown_capacity(actor)
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('SAVED two-hit integration; no PIE')
