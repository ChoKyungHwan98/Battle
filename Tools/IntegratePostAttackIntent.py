"""Move the post-recovery probe behind Utility selection. Unreal MCP only; no PIE."""
import unreal
import vibeue
import ApplyBossIntentPolish as I

B, S = I.B, I.S
MARKER = 'IntentPolish: post-recovery preparation belongs to selected attack'


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    assert hasattr(unreal.BossCombatIntentLibrary, 'record_attack_recovery_end'), 'Build native code first'
    bp = unreal.EditorAssetLibrary.load_asset(B)
    dirty = {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    assert B not in dirty, 'Preserve unsaved boss work before graph integration'
    g = 'FinishCombatAction'
    if not any(n.node_title == MARKER for n in S.get_nodes_in_graph(B,g,0,'',False)):
        target = '7D6B23CE4AABB15CAD521D9F60D5481D'
        edge = next(e for e in S.get_connections(B,g) if e.target_node_id == target and e.target_pin_name == 'execute')
        assert edge.source_node_id == '275ADADB44149CEE25E68E9699132104'
        ids = I.build(g, [I.get('Mesh','Mesh'), I.call('Owner','ActorComponent','GetOwner'),
                          I.call('Notify','BossCombatIntentLibrary','RecordAttackRecoveryEnd')],
                      [('Mesh.Mesh','Owner.self'), ('Owner.ReturnValue','Notify.Boss')])
        I.wire(g,edge.source_node_id,edge.source_pin_name,ids['Notify'],'execute')
        I.wire(g,ids['Notify'],'then',target,'execute')
        assert S.add_comment_around_nodes(B,g,MARKER,list(ids.values()))
        print('MODIFIED',B,g,'record recovery only after Ready transition')
    # Retain the legacy graph for rollback, but its movement branch has no execution root.
    # The caller still reads GoapStepHandled=False and continues the Utility draw.
    g = 'MaybeGoapProbe'
    I.wire(g,'88CB743A4D8D7F08844B9CA7FEAFDDA1','then','ADC9DDF84D11EA1E41DFA5BEBD1D824A','execute')
    assert S.set_node_pin_value(B,g,'88CB743A4D8D7F08844B9CA7FEAFDDA1','GoapStepHandled','false')
    assert not any(c.target_node_id == 'FDAEFC8C457747197CBA75B3B8590690' and c.target_pin_name == 'execute'
                   for c in S.get_connections(B,g))
    result = S.compile_blueprint(B)
    assert result.success and not result.errors and not result.warnings, (result.errors,result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('COMPILED',B,'0 errors/warnings')
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class() == bp.generated_class():
            actor.modify()
            capsule = actor.get_component_by_class(unreal.CapsuleComponent)
            capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,
                                                       unreal.CollisionResponseType.ECR_IGNORE)
            assert capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_IGNORE
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    verify()


def verify():
    g = 'MaybeGoapProbe'
    edges = S.get_connections(B,g)
    assert any(c.source_node_id == '88CB743A4D8D7F08844B9CA7FEAFDDA1' and c.source_pin_name == 'then'
               and c.target_node_id == 'ADC9DDF84D11EA1E41DFA5BEBD1D824A' for c in edges)
    assert not any(c.target_node_id == 'FDAEFC8C457747197CBA75B3B8590690' and c.target_pin_name == 'execute' for c in edges)
    g = 'FinishCombatAction'
    hook = next(n.node_id for n in S.get_nodes_in_graph(B,g,0,'',False) if n.node_title == 'Record Attack Recovery End')
    edges = S.get_connections(B,g)
    assert any(c.source_node_id == '275ADADB44149CEE25E68E9699132104' and c.target_node_id == hook and c.target_pin_name == 'execute' for c in edges)
    assert any(c.source_node_id == hook and c.source_pin_name == 'then' and c.target_node_id == '7D6B23CE4AABB15CAD521D9F60D5481D' for c in edges)
    print('VERIFIED selected-attack probe handoff; no PIE performed')


if __name__ == '__main__':
    apply()
