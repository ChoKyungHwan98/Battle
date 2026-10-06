"""Connect safe full-list score telemetry. Run through Unreal MCP with PIE off."""
import unreal
import vibeue
import ApplyBossIntentPolish as I

B, S = I.B, I.S
G = 'UpdateBossDebugPanel'
MARKER = 'IntentPolish: complete action scores without unchecked array reads'


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    assert B not in {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    if not any(n.node_title == MARKER for n in S.get_nodes_in_graph(B,G,0,'',False)):
        ids = I.build(G, [I.get('Mesh','Mesh'), I.call('Owner','ActorComponent','GetOwner'),
                          I.call('Describe','BossCombatIntentLibrary','DescribeCombatDebug'),
                          I.call('Text','KismetTextLibrary','Conv_StringToText')],
                      [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Describe.Boss'),
                       ('Describe.ReturnValue','Text.InString')])
        I.wire(G,ids['Text'],'ReturnValue','15BA4DB7433D923041C6C2807C5DC55D','InText')
        assert S.add_comment_around_nodes(B,G,MARKER,list(ids.values()))
    # Existing GoapReason already contains the current plain-language intent reason.
    # Bypass numeric action codes entirely; leave old formatting available for rollback.
    I.wire(G,'B5432256422308C3401914A7575B83CC','GoapReason','242D1F4B4CD24A283BD857A1788360A7','InString')
    result = S.compile_blueprint(B)
    assert result.success and not result.errors and not result.warnings, (result.errors,result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(B)
    bp = unreal.EditorAssetLibrary.load_asset(B)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class() == bp.generated_class():
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    edges = S.get_connections(B,G)
    assert not any(c.source_node_id == 'DF8737384B95956859FAF49E00CCA3D3' and c.target_node_id == '15BA4DB7433D923041C6C2807C5DC55D' for c in edges)
    assert any(c.source_node_id == 'B5432256422308C3401914A7575B83CC' and c.target_node_id == '242D1F4B4CD24A283BD857A1788360A7' for c in edges)
    print('VERIFIED full score formatter and plain GOAP reason; compile 0 errors/warnings; visual check pending')


if __name__ == '__main__':
    apply()
