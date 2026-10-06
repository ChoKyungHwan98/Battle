"""Allow scoped manual reach tests in MotionLab; preserve combat validation and contact damage."""
import unreal
import vibeue
import ApplyBossAttackSteps as G
import PolishSoulsHits as H

B, S = H.B, unreal.BlueprintService
GRAPH = 'ValidateCombatActionStart'
MARKER = 'MotionLab measurement: scoped manual start limits only'
GATES = {
    'Cooldown': ('B7C139644022156C185A2F9CB36F7739', '948DD1C94D8477E38CE7179822EE22F6'),
    'Distance': ('E9E6193442CC889CA8858B9712B770C9', '7DC9F07C44853992D5F4749E2B929E89'),
    'Facing': ('8E0A35764E8A72539F5C2D8FCADE5FE9', 'B82D5353472996E5C8D68CB7CB55551F'),
}


def verify():
    nodes = list(S.get_nodes_in_graph(B, GRAPH, 0, '', False))
    edges = list(S.get_connections(B, GRAPH))
    override = next(n.node_id for n in nodes if n.node_title == 'Is Lab Start Limit Override')
    for label, (source, target) in GATES.items():
        condition = next(e for e in edges if e.target_node_id == target and e.target_pin_name == 'Condition')
        or_node = condition.source_node_id
        assert next(n for n in nodes if n.node_id == or_node).node_title == 'OR Boolean', label
        assert any(e.source_node_id == source and e.source_pin_name == 'ReturnValue'
                   and e.target_node_id == or_node and e.target_pin_name == 'A' for e in edges), label
        assert any(e.source_node_id == override and e.source_pin_name == 'ReturnValue'
                   and e.target_node_id == or_node and e.target_pin_name == 'B' for e in edges), label
    print('VERIFIED scoped manual override on distance/facing/cooldown only; no PIE')


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    assert hasattr(unreal.BossCombatIntentLibrary, 'is_lab_start_limit_override'), 'Build native code first'
    bp = unreal.EditorAssetLibrary.load_asset(B)
    assert B not in {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    nodes = list(S.get_nodes_in_graph(B, GRAPH, 0, '', False))
    if not any(n.node_title == MARKER for n in nodes):
        edges = list(S.get_connections(B, GRAPH))
        for label, (source, target) in GATES.items():
            assert any(e.source_node_id == source and e.target_node_id == target
                       and e.target_pin_name == 'Condition' for e in edges), label
        definitions = [H.get('Mesh', 'Mesh'), H.call('Owner', 'ActorComponent', 'GetOwner'),
                       H.call('Override', 'BossCombatIntentLibrary', 'IsLabStartLimitOverride')]
        links = [('Mesh.Mesh', 'Owner.self'), ('Owner.ReturnValue', 'Override.Boss')]
        for label, (source, target) in GATES.items():
            definitions.append(H.call(label, 'KismetMathLibrary', 'BooleanOR'))
            links.extend([(source+'.ReturnValue', label+'.A'), ('Override.ReturnValue', label+'.B')])
        ids = G.build(B, GRAPH, definitions, links)
        for label, (_, target) in GATES.items():
            assert S.disconnect_pin(B, GRAPH, target, 'Condition')
            assert S.connect_nodes(B, GRAPH, ids[label], 'ReturnValue', target, 'Condition')
        assert S.add_comment_around_nodes(B, GRAPH, MARKER, list(ids.values()))
        print('MODIFIED', B, GRAPH, MARKER)
    verify()
    result = S.compile_blueprint(B)
    assert result.success and not result.errors and not result.warnings, (result.errors, result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('COMPILED', B, '0 errors/warnings')
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class() == bp.generated_class():
            actor.modify()
            capsule = actor.get_component_by_class(unreal.CapsuleComponent)
            capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,
                                                       unreal.CollisionResponseType.ECR_IGNORE)
            assert capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_IGNORE
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    verify()


if __name__ == '__main__':
    apply()
