"""Apply 175 close / 300-400 one step / 500 dash / 1000 phase-two slam.

Runs through Unreal MCP, with PIE stopped. Runtime contact/visual QA is left to the user.
Preserves the existing punch timing curves and all attack-family identities.
"""
import json
from pathlib import Path
import unreal
import vibeue
import ApplyBossIntentPolish as I
import ApplyBossAttackSteps as G

B, S = I.B, I.S
P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
A = '/Game/BossArena/Player/Animation/ABP_Player_Combat'
C = '/Game/BossArena/Boss/AI/Actions/'


def compile_save(path):
    result = S.compile_blueprint(path)
    assert result.success and not result.errors and not result.warnings, (path,result.errors,result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(path)
    print('COMPILED/SAVED',path,'0 errors/warnings')


def edit_card(name, values, report):
    obj = unreal.EditorAssetLibrary.load_asset(C+name)
    assert obj
    before = {k:obj.get_editor_property(k) for k in values}
    before = {k:list(v) if k in ['ImpactTimes','HitWindowEnds'] else v for k,v in before.items()}
    obj.modify()
    for k,v in values.items(): obj.set_editor_property(k,v)
    assert unreal.EditorAssetLibrary.save_loaded_asset(obj,False)
    for k,v in values.items():
        actual=obj.get_editor_property(k)
        if isinstance(v,list): assert all(abs(x-y)<1e-5 for x,y in zip(actual,v)) and len(actual)==len(v)
        elif isinstance(v,(float,int)) and not isinstance(v,bool): assert abs(actual-v)<1e-5
        else: assert actual==v
    report[name]={'before':report.get(name,{}).get('before',before),'after':values}
    print('MODIFIED',C+name,values)


def punch_step():
    g='BeginAttackStep';marker='Designer bands: snapshot single punch step once'
    if not any(n.node_title==marker for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=I.build(g,[I.get('Mesh','Mesh'),I.call('Owner','ActorComponent','GetOwner'),
                       I.call('Distance','BossCombatIntentLibrary','OrdinaryPunchStepDistance')],
                    [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Distance.Boss'),
                     (G.entry(B,g)+'.Distance','Distance.AuthoredDistance')])
        I.wire(g,ids['Distance'],'ReturnValue','12FD688143170C76D867CFA6196AFD47','A')
        assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))
    assert S.set_node_pin_value(B,'ConfigureAdvancingPunch','35F7769642553C67E5C2D4BD55069DEA','AttackAdvanceBudget','145')
    assert S.set_variable_default_value(B,'ApproachAttackHandoffDistance','400')
    # 400-500 is a short entry gap. The native score gate excludes ordinary punches at 500.
    assert S.set_variable_default_value(B,'IntentSelectionMaxDistance','500')
    compile_save(B)


def sprint_pose():
    marker='Designer sprint: player Space state drives walk/run pose'
    if 'bSprintPose' not in {v.variable_name for v in S.list_variables(A)}:
        bp=unreal.EditorAssetLibrary.load_asset(A)
        assert unreal.BlueprintEditorLibrary.add_member_variable(bp,'bSprintPose',
            unreal.BlueprintEditorLibrary.get_basic_type_by_name('bool'))
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        print('ADDED',A,'bSprintPose')
    if not any(n.node_title==marker for n in S.get_nodes_in_graph(A,'EventGraph',0,'',False)):
        cast='E98C6F9E4AF8E0F2217AC8A60347899C'
        cast_out=next(p.pin_name for p in S.get_node_pins(A,'EventGraph',cast)
                      if not p.is_input and p.pin_name.startswith('As'))
        ids=G.build(A,'EventGraph',[
            I.node('Sprint','member_get',**{'class':P,'member':'bIsSprinting'}),I.put('Store','bSprintPose')],
            [(cast+'.'+cast_out,'Sprint.self'),('Sprint.bIsSprinting','Store.bSprintPose')])
        assert S.connect_nodes(A,'EventGraph','648FF1194DF23D3BF4CE04A24CDC3294','then',ids['Store'],'execute')
        assert S.add_comment_around_nodes(A,'EventGraph',marker,list(ids.values()))
    if not any(n.node_title==marker for n in S.get_nodes_in_graph(A,'AnimGraph',0,'',False)):
        ids=G.build(A,'AnimGraph',[
            I.get('Speed','GroundSpeed'),I.get('Sprint','bSprintPose'),
            I.call('WalkScale','KismetMathLibrary','Multiply_DoubleDouble'),
            I.call('RunScale','KismetMathLibrary','Multiply_DoubleDouble'),
            I.call('WalkBound','KismetMathLibrary','FClamp'),I.call('RunBound','KismetMathLibrary','FClamp'),
            I.call('Choose','KismetMathLibrary','SelectFloat')],[
            ('Speed.GroundSpeed','WalkScale.A'),('Speed.GroundSpeed','RunScale.A'),
            ('WalkScale.ReturnValue','WalkBound.Value'),('RunScale.ReturnValue','RunBound.Value'),
            ('RunBound.ReturnValue','Choose.A'),('WalkBound.ReturnValue','Choose.B'),
            ('Sprint.bSprintPose','Choose.bPickA')],[
            ('WalkScale','B',300/450),('RunScale','B',600/650),
            ('WalkBound','Min',0),('WalkBound','Max',300),('RunBound','Min',0),('RunBound','Max',600)])
        assert S.disconnect_pin(A,'AnimGraph','0E38F389478678412D8ADD93DC2BFE2A','Y')
        assert S.connect_nodes(A,'AnimGraph',ids['Choose'],'ReturnValue','0E38F389478678412D8ADD93DC2BFE2A','Y')
        assert S.add_comment_around_nodes(A,'AnimGraph',marker,list(ids.values()))
    compile_save(A)


def pending_slam_band():
    marker='Designer bands: first phase-two jump also needs 1000cm'
    # Both the pending dispatcher and the priority gate must agree. Otherwise a near pending
    # jump would occupy every Utility update without doing anything.
    for g,target in [('BeginPendingSlam','1C2446A6444616B32356BA8E2ACED20C'),
                     ('EvaluateCombatUtility','113A1C724B1F91009E500EAB2A6AF9D3')]:
        if any(n.node_title==marker for n in S.get_nodes_in_graph(B,g,0,'',False)): continue
        ids=I.build(g,[I.get('Mesh','Mesh'),I.call('Owner','ActorComponent','GetOwner'),
                      I.call('Allowed','BossCombatIntentLibrary','CanStartPendingSlam')],
                    [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Allowed.Boss')])
        I.wire(g,ids['Allowed'],'ReturnValue',target,'Condition')
        assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    assert hasattr(unreal.BossCombatIntentLibrary,'ordinary_punch_step_distance'), 'Build native changes first'
    dirty={p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    affected=[B,A,C+'DA_Attack_Left',C+'DA_Attack_Right',C+'DA_Attack_Uppercut',C+'DA_Attack_Dash']
    assert not dirty.intersection(affected), dirty
    target=Path(unreal.Paths.project_saved_dir()).resolve()/'VibeUE/Reports/crunch_designer_distance_bands_20261006.json'
    report=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'gameplay_verified':False,'cards':{}}
    for side in ['Left','Right']:
        edit_card('DA_Attack_'+side,{'MinDistance':165.0,'MaxDistance':400.0},report['cards'])
    edit_card('DA_Attack_Uppercut',{'bEnabled':True,'MinDistance':165.0,'MaxDistance':250.0,
        'ImpactTimes':[.25],'ActiveSeconds':.15,'HitWindowEnds':[.24]},report['cards'])
    edit_card('DA_Attack_Dash',{'MinDistance':500.0,'MaxDistance':1000.0},report['cards'])
    # Repeat slam already starts at 1000; align the first-phase-entry dispatch below too.
    slam=unreal.EditorAssetLibrary.load_asset(C+'DA_Attack_JumpSlam')
    assert abs(slam.get_editor_property('MinDistance')-1000)<.001
    mp='/Game/BossArena/Boss/Animations/AM_Boss_Combo_03'
    montage=unreal.EditorAssetLibrary.load_asset(mp)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    physical=next(n for n in unreal.AnimMontageService.list_notifies(mp) if str(n.notify_name)=='PhysicalStrike0')
    assert unreal.AnimMontageService.set_notify_duration(mp,physical.notify_index,.24-physical.trigger_time)
    assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
    print('MODIFIED uppercut physical window',physical.trigger_time,.24)
    punch_step();pending_slam_band();compile_save(B);sprint_pose()
    cls=unreal.EditorAssetLibrary.load_asset(B).generated_class()
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==cls:
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SAVED',target)
    verify()


def verify():
    cdo=unreal.get_default_object(unreal.EditorAssetLibrary.load_asset(B).generated_class())
    actions=cdo.get_editor_property('Actions')
    assert all(abs(actions[i].get_editor_property('MaxDistance')-400)<.001 for i in [0,1])
    assert actions[2].get_editor_property('bEnabled') and actions[2].get_editor_property('MinDistance')<=175<=actions[2].get_editor_property('MaxDistance')
    assert actions[6].get_editor_property('MinDistance')==500 and actions[8].get_editor_property('MinDistance')==1000
    assert cdo.get_editor_property('ApproachAttackHandoffDistance')==400
    for g in ['BeginPendingSlam','EvaluateCombatUtility']:
        assert any(n.node_title=='Designer bands: first phase-two jump also needs 1000cm' for n in S.get_nodes_in_graph(B,g,0,'',False))
    nodes={n.node_id:n.node_title for n in S.get_nodes_in_graph(B,'BeginAttackStep',0,'',False)}
    assert any(nodes.get(c.source_node_id)=='Ordinary Punch Step Distance' and c.target_node_id=='12FD688143170C76D867CFA6196AFD47'
               for c in S.get_connections(B,'BeginAttackStep'))
    for g in ['AnimGraph','EventGraph']:
        assert any(n.node_title=='Designer sprint: player Space state drives walk/run pose' for n in S.get_nodes_in_graph(A,g,0,'',False))
    print('VERIFIED distance settings, uppercut eligibility, one-step path and explicit sprint pose; no PIE')


if __name__=='__main__': apply()
