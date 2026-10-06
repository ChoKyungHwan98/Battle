"""User-directed combat feel changes; MCP only, no PIE or midrange band edits."""
import json
from pathlib import Path
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G

P, B, S = H.P, H.B, unreal.BlueprintService
AURA = '/Game/BossArena/Boss/Materials/M_Crunch_GuardBodyAura'
REPORT = Path(unreal.Paths.project_saved_dir()).resolve()/'VibeUE/Reports/designer_combat_feel_20261006.json'


def report():
    return json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else {'before': {}, 'gameplay_verified': False, 'midrange_motion_edited': False}


def store(r):
    REPORT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')


def marked(path, graph, title):
    return any(n.node_title == title for n in S.get_nodes_in_graph(path, graph, 0, '', False))


def build(path, graph, title, nodes, links, defaults=()):
    ids = G.build(path, graph, nodes, links, defaults)
    assert S.add_comment_around_nodes(path, graph, title, list(ids.values()))
    return ids


def wire(path, graph, src, pin, dst, dpin):
    assert S.disconnect_pin(path, graph, dst, dpin)
    assert S.connect_nodes(path, graph, src, pin, dst, dpin)


def compile_save(path):
    result = S.compile_blueprint(path)
    assert result.success and not result.errors and not result.warnings, (path,result.errors,result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(path, False)
    print('COMPILED/SAVED', path, '0 errors/warnings')


def player():
    r = report(); cdo = unreal.get_default_object(H.asset(P).generated_class())
    values = {'AttackPlayRate': 1.25, 'AttackStaminaCost': (cdo.get_editor_property('MaxStamina')-cdo.get_editor_property('DodgeStaminaCost'))/6,
              'HitStopDuration': .06}
    for name, value in values.items():
        r['before'].setdefault('player.'+name, cdo.get_editor_property(name))
        assert S.set_variable_default_value(P, name, str(value))
        print('MODIFIED',P,name,value)
    # Change only attack and roll permission, keeping full-cost guard checks intact.
    for g, gate in [('TryEnterAttack','5E6808C140432D07C7E173BE0BA16FC8'),
                    ('TryEnterDodge','6ECB81E54BB637E01C3852855566A5D8')]:
        title='Designer last stamina: positive reserve permits one action'
        if not marked(P,g,title):
            ids=build(P,g,title,[H.get('Reserve','CurrentStamina'),H.call('Positive','KismetMathLibrary','Greater_DoubleDouble')],
                      [('Reserve.CurrentStamina','Positive.A')],[('Positive','B',0)])
            wire(P,g,ids['Positive'],'ReturnValue',gate,'Condition')
    # Recheck at execution too: an input buffered while stamina was positive can
    # become invalid before a notify calls StartComboStep.
    g='StartComboStep'; title='Designer last stamina: reject empty buffered strike at execution'
    if not marked(P,g,title):
        ids=build(P,g,title,[H.get('Reserve','CurrentStamina'),H.call('Positive','KismetMathLibrary','Greater_DoubleDouble'),
                            H.node('Gate','branch'),H.put('Discard','bAttackBuffered')],
                  [('Reserve.CurrentStamina','Positive.A'),('Positive.ReturnValue','Gate.Condition'),('Gate.else','Discard.execute')],
                  [('Positive','B',0),('Discard','bAttackBuffered','false')])
        wire(P,g,'1250382E48D9B81565BEF8887AD28334','then',ids['Gate'],'execute')
        wire(P,g,ids['Gate'],'then','01B4A3134FE107CA7ACC56942DFA89CE','execute')
    g='EventGraph'; title='Designer six strikes: no stamina regeneration during attacking'
    if not marked(P,g,title):
        ids=build(P,g,title,[H.get('State','ActionState'),H.call('Attacking','KismetMathLibrary','EqualEqual_ByteByte'),
                            H.call('Blocked','KismetMathLibrary','BooleanOR')],
                  [('State.ActionState','Attacking.A'),('Attacking.ReturnValue','Blocked.B'),
                   ('FC856C7A42052E50F7521E915676948A.bStaminaRegenBlocked','Blocked.A')],[('Attacking','B',4)])
        wire(P,g,ids['Blocked'],'ReturnValue','5A9D94254D317D3125A2F1A4CE9A04D4','Condition')
    g='TryEnterDodge'; title='Designer refund: capture actual roll payment before spending'
    if not marked(P,g,title):
        ids=build(P,g,title,[H.get('Reserve','CurrentStamina'),H.get('Cost','DodgeStaminaCost'),
                            H.call('Paid','KismetMathLibrary','FClamp')],
                  [('Reserve.CurrentStamina','Paid.Value'),('Cost.DodgeStaminaCost','Paid.Max')],[('Paid','Min',0)])
        wire(P,g,ids['Paid'],'ReturnValue','3063530B42B722CB820D95886D9B4335','DodgePaidStamina')
        for n in ['BDD1C33C4069F02424A14F8DF8241745','9E09BB774516805FBF697EAFF6C9D350','3063530B42B722CB820D95886D9B4335']:
            assert S.disconnect_pin(P,g,n,'then')
        wire(P,g,'BDD1C33C4069F02424A14F8DF8241745','then','3063530B42B722CB820D95886D9B4335','execute')
        wire(P,g,'3063530B42B722CB820D95886D9B4335','then','9E09BB774516805FBF697EAFF6C9D350','execute')
        wire(P,g,'9E09BB774516805FBF697EAFF6C9D350','then','20AE92114CF0CB37EC48AC83D4FE570F','execute')
    g='TryEnterAttack'; title='Designer guard attack: exit held guard before normal attack entry'
    if not marked(P,g,title):
        ids=build(P,g,title,[H.get('State','ActionState'),H.call('Guard','KismetMathLibrary','EqualEqual_ByteByte'),
                            H.node('Gate','branch'),H.call('Exit','/Game/BossArena/Player/Blueprints/BP_Player_Combat','ExitBlock')],
                  [('State.ActionState','Guard.A'),('Guard.ReturnValue','Gate.Condition'),('Gate.then','Exit.execute')],
                  [('Guard','B',3)])
        wire(P,g,'5E6808C140432D07C7E173BE0BA16FC8','then',ids['Gate'],'execute')
        assert S.disconnect_pin(P,g,'7EDCD7654B9F40ABF0317E86904E653B','execute')
        assert S.connect_nodes(P,g,ids['Gate'],'else','7EDCD7654B9F40ABF0317E86904E653B','execute')
        assert S.connect_nodes(P,g,ids['Exit'],'then','7EDCD7654B9F40ABF0317E86904E653B','execute')
    assert S.set_node_pin_value(P,'ResolveSwordContact','5C63381746F739763391A8B630A8D458','Scale','(X=.55,Y=.55,Z=.55)')
    # The old class pin is empty and the value-only setter does not bind DefaultObject.
    # A native class load, connected after the build, binds the actual shake class.
    compile_save(P); r['player']=values;store(r)


def body_aura():
    if not unreal.EditorAssetLibrary.does_asset_exist(AURA):
        mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset(AURA.rsplit('/',1)[-1],AURA.rsplit('/',1)[0],
                                                                  unreal.Material,unreal.MaterialFactoryNew())
        print('CREATED',AURA)
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_ADDITIVE)
        mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property('used_with_skeletal_mesh',True)
        M=unreal.MaterialEditingLibrary
        color=M.create_material_expression(mat,unreal.MaterialExpressionVectorParameter,-600,0)
        color.set_editor_property('parameter_name','AuraColor'); color.set_editor_property('default_value',unreal.LinearColor(1,.015,.002,1))
        rim=M.create_material_expression(mat,unreal.MaterialExpressionFresnel,-600,170)
        rim.set_editor_property('exponent',2.5);rim.set_editor_property('base_reflect_fraction',.12)
        strength=M.create_material_expression(mat,unreal.MaterialExpressionScalarParameter,-600,330)
        strength.set_editor_property('parameter_name','AuraStrength');strength.set_editor_property('default_value',8.)
        pulse_time=M.create_material_expression(mat,unreal.MaterialExpressionTime,-600,500)
        pulse=M.create_material_expression(mat,unreal.MaterialExpressionSine,-420,500);pulse.set_editor_property('period',.22)
        amp=M.create_material_expression(mat,unreal.MaterialExpressionMultiply,-250,500);amp.set_editor_property('const_b',.15)
        base=M.create_material_expression(mat,unreal.MaterialExpressionAdd,-100,500);base.set_editor_property('const_b',.85)
        glow=M.create_material_expression(mat,unreal.MaterialExpressionMultiply,-250,0)
        brightness=M.create_material_expression(mat,unreal.MaterialExpressionMultiply,-100,0)
        final=M.create_material_expression(mat,unreal.MaterialExpressionMultiply,70,0)
        for a,ap,b,bp in [(color,'',glow,'A'),(rim,'',glow,'B'),(glow,'',brightness,'A'),(strength,'',brightness,'B'),
                          (pulse_time,'',pulse,''),(pulse,'',amp,'A'),(amp,'',base,'A'),
                          (brightness,'',final,'A'),(base,'',final,'B')]:
            assert M.connect_material_expressions(a,ap,b,bp)
        assert M.connect_material_property(final,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        assert M.connect_material_property(rim,'',unreal.MaterialProperty.MP_OPACITY)
        errors=M.recompile_material(mat); assert not errors,errors
        assert unreal.EditorAssetLibrary.save_loaded_asset(mat,False)
    else:
        # Preserve partially-created nodes after a failed connection, without recreating.
        mat=unreal.EditorAssetLibrary.load_asset(AURA);M=unreal.MaterialEditingLibrary
        current=json.loads(unreal.MaterialNodeService.export_material_graph(AURA))
        assert len(current['expressions'])==10
        nodes={(o.get_editor_property('material_expression_editor_x'),o.get_editor_property('material_expression_editor_y')):o
               for o in unreal.ObjectIterator(unreal.MaterialExpression) if o.get_outer()==mat}
        for a,b,pin in [((-600,500),(-420,500),''),((-420,500),(-250,500),'A'),
                        ((-250,500),(-100,500),'A'),((-100,0),(70,0),'A'),((-100,500),(70,0),'B')]:
            assert M.connect_material_expressions(nodes[a],'',nodes[b],pin),(a,b,pin)
        assert M.connect_material_property(nodes[(70,0)],'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        assert M.connect_material_property(nodes[(-600,170)],'',unreal.MaterialProperty.MP_OPACITY)
        errors=M.recompile_material(mat);assert not errors,errors
        assert unreal.EditorAssetLibrary.save_loaded_asset(mat,False)
    diag=unreal.MaterialNodeService.get_material_diagnostics(AURA)
    assert diag.success and diag.is_compiled_ok,diag.compile_errors
    print('VERIFIED body aura material',diag.expression_count,'expressions')


def boss_assets():
    r=report(); cdo=unreal.get_default_object(H.asset(B).generated_class())
    r['before'].setdefault('boss.TurnSpeed',cdo.get_editor_property('TurnSpeed'))
    assert S.set_variable_default_value(B,'TurnSpeed','160')
    for n in S.get_nodes_in_graph(B,'TryPlayTurnMontage',0,'',False):
        if 'Play Anim Montage' not in n.node_title: continue
        p=next(p for p in S.get_node_pins(B,'TryPlayTurnMontage',n.node_id) if p.pin_name=='InPlayRate')
        r['before'].setdefault('turn.'+n.node_id,p.default_value)
        assert S.set_node_pin_value(B,'TryPlayTurnMontage',n.node_id,'InPlayRate',str(1.6 if float(r['before']['turn.'+n.node_id])<1.5 else 1.85))
    assert S.set_node_pin_value(B,'TryPlayTurnMontage','AC3ACC3B4E2B69682AA176B4810D87CB','A','1.71')
    assert S.set_node_pin_value(B,'TryPlayTurnMontage','AC3ACC3B4E2B69682AA176B4810D87CB','B','.94')
    # Retire the old floor-ring display. Runtime component adds an overlay to the mesh.
    assert S.disconnect_pin(B,'UpdateAttackExtras','899880A44252036F683B669D4561E39D','bNewVisibility')
    assert S.set_node_pin_value(B,'UpdateAttackExtras','899880A44252036F683B669D4561E39D','bNewVisibility','false')
    upper=H.asset('/Game/BossArena/Boss/AI/Actions/DA_Attack_Uppercut')
    for k,v in {'TelegraphSeconds':.4,'PlayRate':.75,'ImpactTimes':[.6],'ActiveSeconds':.12,'TotalSeconds':2.396}.items():
        old=upper.get_editor_property(k);r['before'].setdefault('upper.'+k,list(old) if k=='ImpactTimes' else old)
        upper.modify();upper.set_editor_property(k,v)
    assert unreal.EditorAssetLibrary.save_loaded_asset(upper,False)
    dash=H.asset('/Game/BossArena/Boss/Animations/AM_Boss_DashingCross_Staged')
    expected={'P_Crunch_Cross_DirtTrail':2.,'P_Crunch_Fist_Fire_UpperCut':1.5,
              'P_Crunch_Cross_AmpedFLames':1.25,'P_Crunch_Cross_Jets':1.15}
    count=0;dash.modify()
    for obj in unreal.ObjectIterator(unreal.AnimNotifyState):
        if obj.get_outer()!=dash or obj.get_class().get_name()!='ANS_BossScaledParticle_C':continue
        template=obj.get_editor_property('MatchTemplate');name=template.get_name()
        assert name in expected,name
        r['before'].setdefault('dash_fx.'+obj.get_name(),list(obj.get_editor_property('FXScale').to_tuple()))
        obj.modify();obj.set_editor_property('FXScale',unreal.Vector(*([expected[name]]*3)));count+=1
        print('MODIFIED dash FX',name,str(obj.get_editor_property('MatchSocket')),expected[name])
    assert count==5,count
    assert unreal.EditorAssetLibrary.save_loaded_asset(dash,False)
    compile_save(B);r.update({'boss_turn_degrees_per_second':160,'upper_charge_seconds':.4,'dash_fx':expected});store(r)


def combo_links():
    g='BeginAttackStep';title='Designer combo: snapshot a fresh forward step then commit direction'
    if not marked(B,g,title):
        ids=build(B,g,title,[H.get('Mesh','Mesh'),H.call('Owner','ActorComponent','GetOwner'),
                            H.call('Follow','BossCombatIntentLibrary','IsComboFollowStep'),
                            H.call('Any','KismetMathLibrary','BooleanOR'),
                            H.call('Commit','BossCombatIntentLibrary','CommitComboStep')],
                  [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Follow.Boss'),('Owner.ReturnValue','Commit.Boss'),
                   ('Follow.ReturnValue','Any.B'),('F800E36247312CDB686A308BEF7CA87C.ReturnValue','Any.A')])
        wire(B,g,ids['Any'],'ReturnValue','12FD688143170C76D867CFA6196AFD47','bPickA')
        wire(B,g,'9074FDD04B7329ED0C8E70A51F1ACDB4','then',ids['Commit'],'execute')
        wire(B,g,ids['Commit'],'then','AFE3DB134002543BA67BA58CBDB8D4D6','execute')
    compile_save(B)


def save_instances():
    cls=H.asset(B).generated_class()
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()!=cls:continue
        actor.modify();actor.set_editor_property('TurnSpeed',160.)
        actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
            unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
        print('MODIFIED placed boss',actor.get_name(),'turn and capsule response')
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


def before_build():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    player();body_aura();boss_assets();save_instances()


def after_build():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    combo_links();hit_shake();save_instances()


def hit_shake():
    g='EventGraph';title='Designer hit feedback: bind the real camera shake class after contact'
    if not marked(P,g,title):
        old='0936537344D0AA886A3F98809E22C73A'
        edges=S.get_connections(P,g)
        incoming=[c for c in edges if c.target_node_id==old and c.target_pin_name=='execute']
        outgoing=[c for c in edges if c.source_node_id==old and c.source_pin_name=='then']
        assert incoming and len(outgoing)==1
        ids=build(P,g,title,[H.get('Mesh','Mesh'),H.call('Owner','ActorComponent','GetOwner'),
                            H.call('Shake','BossCombatIntentLibrary','PlayPlayerHitShake')],
                  [('Mesh.Mesh','Owner.self'),('Owner.ReturnValue','Shake.Player')],[('Shake','Scale',1.15)])
        assert S.disconnect_pin(P,g,old,'execute')
        assert S.disconnect_pin(P,g,old,'then')
        for c in incoming: assert S.connect_nodes(P,g,c.source_node_id,c.source_pin_name,ids['Shake'],'execute')
        c=outgoing[0];assert S.connect_nodes(P,g,ids['Shake'],'then',c.target_node_id,c.target_pin_name)
    compile_save(P)


def verify():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    cdo=unreal.get_default_object(H.asset(P).generated_class())
    cost=cdo.get_editor_property('AttackStaminaCost')
    reserve=cdo.get_editor_property('MaxStamina')-6*cost
    assert abs(reserve-cdo.get_editor_property('DodgeStaminaCost'))<.001
    assert cdo.get_editor_property('AttackPlayRate')==1.25
    titles={
        'TryEnterAttack':['Designer last stamina: positive reserve permits one action','Designer guard attack: exit held guard before normal attack entry'],
        'TryEnterDodge':['Designer last stamina: positive reserve permits one action','Designer refund: capture actual roll payment before spending'],
        'StartComboStep':['Designer last stamina: reject empty buffered strike at execution'],
        'EventGraph':['Designer six strikes: no stamina regeneration during attacking','Designer hit feedback: bind the real camera shake class after contact'],
    }
    for g,labels in titles.items():
        assert all(marked(P,g,t) for t in labels),(g,labels)
    # The low-reserve refund must capture payment BEFORE the spending call.
    edges=S.get_connections(P,'TryEnterDodge')
    assert any(e.source_node_id=='3063530B42B722CB820D95886D9B4335' and e.source_pin_name=='then'
               and e.target_node_id=='9E09BB774516805FBF697EAFF6C9D350' and e.target_pin_name=='execute' for e in edges)
    ns={n.node_id:n.node_title for n in S.get_nodes_in_graph(P,'TryEnterDodge',0,'',False)}
    assert any(ns.get(e.source_node_id)=='Clamp (Float)' and e.target_node_id=='3063530B42B722CB820D95886D9B4335'
               and e.target_pin_name=='DodgePaidStamina' for e in edges)
    ns={n.node_id:n.node_title for n in S.get_nodes_in_graph(P,'EventGraph',0,'',False)}
    shake=next(i for i,t in ns.items() if t=='Play Player Hit Shake')
    incoming=[e for e in S.get_connections(P,'EventGraph') if e.target_node_id==shake and e.target_pin_name=='execute']
    assert len(incoming)==4,len(incoming)
    assert marked(B,'BeginAttackStep','Designer combo: snapshot a fresh forward step then commit direction')
    bcdo=unreal.get_default_object(H.asset(B).generated_class())
    assert bcdo.get_editor_property('TurnSpeed')==160
    actions=bcdo.get_editor_property('Actions')
    assert actions[0].get_editor_property('MaxDistance')==400 and actions[1].get_editor_property('MaxDistance')==400
    assert abs(actions[2].get_editor_property('TelegraphSeconds')-.4)<.001
    assert abs(actions[2].get_editor_property('ImpactTimes')[0]-(.4+.15/.75))<.001
    assert actions[6].get_editor_property('MinDistance')==500 and actions[8].get_editor_property('MinDistance')==1000
    diag=unreal.MaterialNodeService.get_material_diagnostics(AURA)
    assert diag.success and diag.is_compiled_ok
    r=report();r['asset_verification']={'six_strikes_without_regen_reserve':reserve,'player_attack_rate':1.25,
        'refund_captured_before_spend':True,'shake_exec_paths':len(incoming),'body_aura_compiles':True,
        'old_midrange_bands_preserved':True,'new_combo_step_connected':True}
    store(r);print('VERIFIED asset settings, stamina/guard/refund paths, hit shake and combo hooks; no gameplay')
