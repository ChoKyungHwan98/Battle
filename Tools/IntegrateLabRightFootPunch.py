"""Hook the scoped native lab variant after existing punch setup; no PIE."""
import unreal
import vibeue
import ApplyBossAttackSteps as G
import PolishSoulsHits as H

B,S=H.B,unreal.BlueprintService
GRAPH='BeginCombatAction'
MARKER='MotionLab: right-foot plant variant after ordinary setup'
SOURCE='919090C14EC1AC0001BEA694F50C3E82'
DEST='A85354F344BDF910C4BFCEB22D13644B'
SNAPSHOT='E519628747B28FE5A829A89869A327C0'
AUDIT='52C2F5224DBC497681C7A082790794C0'
PREPARE='764E2CFC44444A34E762FEB8B3C9C6CB'
ALLOWED='F3B1A6B54FBAF697D89160A81D8D2E2F'


def verify():
    nodes=list(S.get_nodes_in_graph(B,GRAPH,0,'',False))
    hook=next(n.node_id for n in nodes if n.node_title=='Configure Lab Right Foot Punch')
    edges=list(S.get_connections(B,GRAPH))
    assert any(e.source_node_id==SOURCE and e.source_pin_name=='then' and e.target_node_id==hook and e.target_pin_name=='execute' for e in edges)
    assert any(e.source_node_id==hook and e.source_pin_name=='then' and e.target_node_id==SNAPSHOT and e.target_pin_name=='execute' for e in edges)
    assert any(e.source_node_id==AUDIT and e.target_node_id==DEST and e.target_pin_name=='execute' for e in edges)
    assert any(e.source_node_id==ALLOWED and e.source_pin_name=='then' and e.target_node_id==PREPARE for e in edges)
    cdo=unreal.get_default_object(unreal.EditorAssetLibrary.load_asset(B).generated_class())
    assert len(cdo.get_editor_property('Actions'))==10
    assert cdo.get_editor_property('Actions')[0].get_name()=='DA_Attack_Left'
    print('VERIFIED lab hook after ordinary setup; original Arena Actions unchanged')


def prepare_manual_request():
    """Bind the lab definition before validation so its 550cm range is checked."""
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    g='RequestCombatAction'; marker='MotionLab: bind foot-plant definition before start validation'
    source='ECECADD342CE4CFC58FA9EBA8CEF4EED'; destination='78B761954BA2583D31A0F79DA1108AFD'
    if not any(n.node_title==marker for n in S.get_nodes_in_graph(B,g,0,'',False)):
        assert any(e.source_node_id==source and e.target_node_id==destination and e.target_pin_name=='execute' for e in S.get_connections(B,g))
        ids=G.build(B,g,[H.get('Mesh','Mesh'),H.call('Owner','ActorComponent','GetOwner'),
            H.call('Prepare','BossCombatIntentLibrary','ConfigureLabRightFootPunch')],
            [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Prepare.Boss')])
        assert S.disconnect_pin(B,g,destination,'execute')
        assert S.connect_nodes(B,g,source,'then',ids['Prepare'],'execute')
        assert S.connect_nodes(B,g,ids['Prepare'],'then',destination,'execute')
        assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))
        print('MODIFIED',B,g,marker)
    compiled=S.compile_blueprint(B)
    assert compiled.success and not compiled.errors and not compiled.warnings
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('COMPILED manual request 0 errors/warnings; native scoped guard retains Arena behavior')


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    assert hasattr(unreal.BossCombatIntentLibrary,'configure_lab_right_foot_punch')
    assert B not in {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    if not any(n.node_title==MARKER for n in S.get_nodes_in_graph(B,GRAPH,0,'',False)):
        assert any(e.source_node_id==SOURCE and e.target_node_id==DEST and e.target_pin_name=='execute' for e in S.get_connections(B,GRAPH))
        ids=G.build(B,GRAPH,[H.get('Mesh','Mesh'),H.call('Owner','ActorComponent','GetOwner'),
            H.call('Configure','BossCombatIntentLibrary','ConfigureLabRightFootPunch')],
            [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Configure.Boss')])
        assert S.disconnect_pin(B,GRAPH,DEST,'execute')
        assert S.connect_nodes(B,GRAPH,SOURCE,'then',ids['Configure'],'execute')
        assert S.connect_nodes(B,GRAPH,ids['Configure'],'then',DEST,'execute')
        assert S.add_comment_around_nodes(B,GRAPH,MARKER,list(ids.values()))
        print('MODIFIED',B,GRAPH,MARKER)
    # Snapshot the action after its final configuration, so QA names the actual lab montage.
    hook=next(n.node_id for n in S.get_nodes_in_graph(B,GRAPH,0,'',False) if n.node_title=='Configure Lab Right Foot Punch')
    for source,target in [(ALLOWED,PREPARE),(hook,SNAPSHOT),(AUDIT,DEST)]:
        incoming=[e for e in S.get_connections(B,GRAPH) if e.target_node_id==target and e.target_pin_name=='execute']
        if len(incoming)==1 and incoming[0].source_node_id==source and incoming[0].source_pin_name=='then':
            continue
        assert S.disconnect_pin(B,GRAPH,target,'execute')
        assert S.connect_nodes(B,GRAPH,source,'then',target,'execute')
    print('MODIFIED QA snapshot follows final montage selection; validation still runs first')
    verify()
    compiled=S.compile_blueprint(B)
    assert compiled.success and not compiled.errors and not compiled.warnings, (compiled.errors,compiled.warnings)
    assert unreal.EditorAssetLibrary.save_asset(B)
    # Reapply placed response after compilation. Reload may discard it; BeginPlay owns initialization.
    bp=unreal.EditorAssetLibrary.load_asset(B)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==bp.generated_class():
            actor.modify()
            capsule=actor.get_component_by_class(unreal.CapsuleComponent)
            capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('COMPILED',B,'0 errors/warnings; no PIE')
