"""Match ordinary punch travel to its own foot pose, via Unreal MCP. No PIE.

Separate Jog prefixes remain as archived assets, with no live selection path.
Curve samples use animation +Y (Crunch mesh yaw -90 => actor forward).
"""
import json
from pathlib import Path
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G

B, S, A = H.B, unreal.BlueprintService, unreal.AnimMontageService
ROOT = '/Game/BossArena/Boss/Animations/'
CARDS = '/Game/BossArena/Boss/AI/Actions/'
node, get, put, call = H.node, H.get, H.put, H.call
START, END, SCALE = 1/30, .4, 1.3
MARKER = 'PunchFootSync: source foot displacement and montage clock'


def build(g, nodes, links=(), defaults=()):
    return G.build(B, g, nodes, links, defaults)


def wire(g, src, pin, dst, dstpin):
    incoming = [(c.source_node_id, c.source_pin_name) for c in S.get_connections(B,g)
                if c.target_node_id == dst and c.target_pin_name == dstpin]
    if incoming == [(src,pin)]:
        return
    if incoming:
        assert S.disconnect_pin(B,g,dst,dstpin)
    assert S.connect_nodes(B,g,src,pin,dst,dstpin)


def make_curve(side, sequence):
    samples = []
    for frame in range(1,13):
        pose = {str(p.bone_name):p.transform for p in
                unreal.AnimSequenceService.get_pose_at_time(sequence,frame/30,True)}
        samples.append((frame/30,float(pose['foot_l'].translation.y)))
    baseline = samples[0][1]
    span = max(y for _,y in samples)-baseline
    assert span > 20
    keys = [(0.,0.)]
    previous = 0.
    for time,y in samples:
        previous = max(previous,max(0.,min(1.,(y-baseline)/span)))
        keys.append((time,previous))
    keys.append((2.,1.))
    path = ROOT+'Curves/CF_PunchFoot_'+side
    csv = Path(unreal.Paths.project_dir()).resolve()/'Tools'/'data'/('CF_PunchFoot_'+side+'.csv')
    csv.parent.mkdir(parents=True,exist_ok=True)
    csv.write_text(''.join(f'{t:.9f},{v:.9f}\n' for t,v in keys),encoding='utf-8')
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        factory = unreal.CSVImportFactory()
        factory.set_editor_property('automated_import_settings',unreal.CSVImportSettings(
            import_type=unreal.CSVImportType.ECSV_CURVE_FLOAT,
            import_curve_interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR))
        task = unreal.AssetImportTask()
        for k,v in {'filename':str(csv),'destination_path':ROOT+'Curves',
                    'destination_name':path.rsplit('/',1)[-1], 'factory':factory,
                    'automated':True,'replace_existing':False,'save':False}.items():
            task.set_editor_property(k,v)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        assert unreal.EditorAssetLibrary.does_asset_exist(path),list(task.imported_object_paths)
        print('CREATED',path)
    curve = H.asset(path)
    assert isinstance(curve,unreal.CurveFloat)
    for time,value in keys:
        assert abs(curve.get_float_value(time)-value)<.001,(side,time,value)
    assert unreal.EditorAssetLibrary.save_loaded_asset(curve,False)
    return path,span*SCALE,keys


def configure(curves):
    bp = H.asset(B)
    variables = {v.variable_name for v in S.list_variables(B)}
    for name in ['LeftPunchFootCurve','RightPunchFootCurve','PunchFootCurve']:
        if name not in variables:
            assert unreal.BlueprintEditorLibrary.add_member_variable(bp,name,
                unreal.BlueprintEditorLibrary.get_object_reference_type(unreal.CurveFloat.static_class()))
            print('ADDED',B,name)
    for side in ['Left','Right']:
        assert S.set_variable_default_value(B,side+'PunchFootCurve',H.asset(curves[side][0]).get_path_name())
    H.variable(B,'bPunchFootSync','bool','false')
    H.variable(B,'bPunchFootSampleValid','bool','false')
    H.variable(B,'PunchFootAlpha','real',0)
    H.variable(B,'ApproachAttackHandoffDistance','real',350)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    g='ConfigureAdvancingPunch'
    if not any(n.node_title==MARKER for n in S.get_nodes_in_graph(B,g,0,'',False)):
        ids=build(g,[put('ResetFootSync','bPunchFootSync'),put('ResetSample','bPunchFootSampleValid'),
                     get('LeftCurve','LeftPunchFootCurve'),get('RightCurve','RightPunchFootCurve'),
                     put('LeftStore','PunchFootCurve'),put('RightStore','PunchFootCurve'),
                     put('LeftEnable','bPunchFootSync'),put('RightEnable','bPunchFootSync')],[
            ('ResetFootSync.then','ResetSample.execute'),
            ('ResetSample.then','51FD77284AEBA19CF09A6384EA3B70BF.execute'),
            ('LeftCurve.LeftPunchFootCurve','LeftStore.PunchFootCurve'),
            ('RightCurve.RightPunchFootCurve','RightStore.PunchFootCurve'),
            ('LeftStore.then','LeftEnable.execute'),('RightStore.then','RightEnable.execute'),
            ('LeftEnable.then','5A88A56A4C7D9063A7F12887908A9180.execute'),
            ('RightEnable.then','2A5F337A43F5FEEAA4ACE48DDEC2967C.execute')],[
            ('ResetFootSync','bPunchFootSync','false'),('ResetSample','bPunchFootSampleValid','false'),
            ('LeftEnable','bPunchFootSync','true'),('RightEnable','bPunchFootSync','true')])
        wire(g,'0CB7AD1A42C43D61C7321E9C69933151','then',ids['ResetFootSync'],'execute')
        wire(g,'D41BD9BE4DBCE7A902F94CA3BB204429','then',ids['LeftStore'],'execute')
        wire(g,'B066C92E49B0806A3C906EBC2417D287','then',ids['RightStore'],'execute')
        assert S.add_comment_around_nodes(B,g,MARKER,list(ids.values()))
    # Bypass the old distance branches. Each punch now uses its own source step.
    wire(g,'12D9697742A63AD56C261F8CB18A1154','then','D41BD9BE4DBCE7A902F94CA3BB204429','execute')
    wire(g,'B9A94C9140C5E4E3B35583A7D0F6C197','then','B066C92E49B0806A3C906EBC2417D287','execute')
    if any(c.target_node_id=='35F7769642553C67E5C2D4BD55069DEA' and
           c.target_pin_name=='AttackAdvanceBudget' for c in S.get_connections(B,g)):
        assert S.disconnect_pin(B,g,'35F7769642553C67E5C2D4BD55069DEA','AttackAdvanceBudget')
    assert S.set_node_pin_value(B,g,'35F7769642553C67E5C2D4BD55069DEA','AttackAdvanceBudget','95')
    if not any(n.node_title=='PunchFootSync: reset progress' for n in S.get_nodes_in_graph(B,g,0,'',False)):
        reset=next(n.node_id for n in S.get_nodes_in_graph(B,g,0,'',False) if n.node_title=='Set bPunchFootSampleValid')
        ids=build(g,[put('ResetAlpha','PunchFootAlpha')],defaults=[('ResetAlpha','PunchFootAlpha',0)])
        wire(g,reset,'then',ids['ResetAlpha'],'execute')
        wire(g,ids['ResetAlpha'],'then','51FD77284AEBA19CF09A6384EA3B70BF','execute')
        assert S.add_comment_around_nodes(B,g,'PunchFootSync: reset progress',list(ids.values()))
    print('MODIFIED ordinary punch selection: base montage only; budget 95')


def sampler():
    g='SamplePunchFootProgress'
    H.function(B,g)
    if not G.empty_body(B,g):
        return
    e=G.entry(B,g)
    build(g,[put('ResetValid','bPunchFootSampleValid'),get('Enabled','bPunchFootSync'),node('EnabledGate','branch'),
        get('Curve','PunchFootCurve'),call('CurveValid','KismetSystemLibrary','IsValid'),node('CurveGate','branch'),
        get('Montage','AttackMontage'),call('MontageValid','KismetSystemLibrary','IsValid'),node('MontageGate','branch'),
        get('Mesh','Mesh'),call('Anim','SkeletalMeshComponent','GetAnimInstance'),
        call('AnimValid','KismetSystemLibrary','IsValid'),node('AnimGate','branch'),
        call('Position','AnimInstance','Montage_GetPosition'),call('CurveValue','CurveFloat','GetFloatValue'),
        call('BoundAlpha','KismetMathLibrary','FClamp'),put('Alpha','PunchFootAlpha'),put('Valid','bPunchFootSampleValid')],[
        (e+'.then','ResetValid.execute'),('ResetValid.then','EnabledGate.execute'),
        ('Enabled.bPunchFootSync','EnabledGate.Condition'),('EnabledGate.then','CurveGate.execute'),
        ('Curve.PunchFootCurve','CurveValid.Object'),('CurveValid.ReturnValue','CurveGate.Condition'),
        ('CurveGate.then','MontageGate.execute'),('Montage.AttackMontage','MontageValid.Object'),
        ('MontageValid.ReturnValue','MontageGate.Condition'),('MontageGate.then','AnimGate.execute'),
        ('Mesh.Mesh','Anim.self'),('Anim.ReturnValue','AnimValid.Object'),('AnimValid.ReturnValue','AnimGate.Condition'),
        ('AnimGate.then','Alpha.execute'),('Anim.ReturnValue','Position.self'),('Montage.AttackMontage','Position.Montage'),
        ('Position.ReturnValue','CurveValue.InTime'),('Curve.PunchFootCurve','CurveValue.self'),
        ('CurveValue.ReturnValue','BoundAlpha.Value'),('BoundAlpha.ReturnValue','Alpha.PunchFootAlpha'),
        ('Alpha.then','Valid.execute')],[
        ('ResetValid','bPunchFootSampleValid','false'),('BoundAlpha','Min',0),('BoundAlpha','Max',1),
        ('Valid','bPunchFootSampleValid','true')])
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(B))


def movement():
    g='AdvanceAttackStep'
    if any(n.node_title==MARKER for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    ids=build(g,[call('Sample',B,'SamplePunchFootProgress'),get('Alpha','PunchFootAlpha'),
                 get('Valid','bPunchFootSampleValid'),call('SelectProgress','KismetMathLibrary','SelectFloat')],[
        ('Sample.then','EFE446444241480B9AD0B9A03EF69BF7.execute'),
        ('Alpha.PunchFootAlpha','SelectProgress.A'),('Valid.bPunchFootSampleValid','SelectProgress.bPickA'),
        ('800D0045468355DADB40DC8676C3AA75.ReturnValue','SelectProgress.B')])
    wire(g,'1958DEA94AEB2F7986DBEEAD58FE35A4','then',ids['Sample'],'execute')
    wire(g,ids['SelectProgress'],'ReturnValue','68734B4342A5DC6AC93566ADD65FDC03','A')
    assert S.add_comment_around_nodes(B,g,MARKER,list(ids.values()))
    print('MODIFIED punch progress reads real montage position; other steps retain easing')


def retime(side,distance):
    card=H.asset(CARDS+'DA_Attack_'+side)
    path=card.get_editor_property('Montage').get_path_name().split('.')[0]
    montage=H.asset(path)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    cls=H.asset(ROOT+'ANS_BossAttackStep').generated_class()
    events=unreal.AnimationLibrary.get_animation_notify_events(montage)
    ids=[i for i,e in enumerate(events) if e.notify_state_class and e.notify_state_class.get_class()==cls]
    assert len(ids)==1,(side,ids)
    montage.modify()
    index=ids[0]
    assert A.set_notify_trigger_time(path,index,START)
    assert A.set_notify_duration(path,index,END-START)
    events[index].notify_state_class.set_editor_property('StepDistance',distance)
    assert unreal.EditorAssetLibrary.save_loaded_asset(montage,False)
    card.modify();card.set_editor_property('MaxDistance',350)
    assert unreal.EditorAssetLibrary.save_loaded_asset(card,False)
    print('MODIFIED source step window',side,START,END,distance,'range=350')


def qa():
    g='RecordCombatQA';marker='PunchFootSync: QA fields'
    if any(n.node_title==marker for n in S.get_nodes_in_graph(B,g,0,'',False)):
        return
    write='7351315649F7330AF5C248810231A881'
    before=next(c for c in S.get_connections(B,g) if c.target_node_id==write and c.target_pin_name=='InString')
    ids=build(g,[get('FootSync','bPunchFootSync'),get('FootAlpha','PunchFootAlpha'),
                call('AppendSync','KismetStringLibrary','BuildString_Bool'),
                call('AppendAlpha','KismetStringLibrary','BuildString_Double')],[
        (before.source_node_id+'.'+before.source_pin_name,'AppendSync.AppendTo'),
        ('FootSync.bPunchFootSync','AppendSync.InBool'),('AppendSync.ReturnValue','AppendAlpha.AppendTo'),
        ('FootAlpha.PunchFootAlpha','AppendAlpha.InDouble')],[
        ('AppendSync','Prefix','|punch_foot_sync='),('AppendAlpha','Prefix','|foot_alpha=')])
    wire(g,ids['AppendAlpha'],'ReturnValue',write,'InString')
    assert S.add_comment_around_nodes(B,g,marker,list(ids.values()))


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    curves={}
    for side in ['Left','Right']:
        card=H.asset(CARDS+'DA_Attack_'+side)
        mp=card.get_editor_property('Montage').get_path_name().split('.')[0]
        first=A.list_anim_segments(mp,0)[0]
        assert abs(first.start_time)<.0001 and abs(first.anim_start_pos)<.0001 and abs(first.play_rate-1)<.0001
        source=first.anim_sequence_path
        curves[side]=make_curve(side,source)
    configure(curves);sampler();movement();qa()
    for side in ['Left','Right']:
        retime(side,curves[side][1])
    result=S.compile_blueprint(B)
    assert result.success and not result.errors and not result.warnings,(result.errors,result.warnings)
    assert unreal.EditorAssetLibrary.save_asset(B)
    print('COMPILED',B,'errors=0 warnings=0')
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==H.asset(B).generated_class():
            actor.modify()
            # This default-only variable propagates through Blueprint compile.
            # Python rejects per-instance writes even when the value is unchanged.
            assert abs(actor.get_editor_property('ApproachAttackHandoffDistance')-350)<.001
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
            print('MODIFIED placed capsule Visibility Ignore + handoff',actor.get_path_name())
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    return curves


def inspect():
    """Asset/graph evidence only; no gameplay claims and no editor map changes."""
    report={'pie_run':False,'blueprint':B,'attacks':{},'checks':{}}
    cdo=unreal.get_default_object(H.asset(B).generated_class())
    for side in ['Left','Right']:
        card=H.asset(CARDS+'DA_Attack_'+side)
        path=card.get_editor_property('Montage').get_path_name().split('.')[0]
        curve=cdo.get_editor_property(side+'PunchFootCurve')
        samples=[{'time':i/30,'progress':curve.get_float_value(i/30)} for i in range(14)]
        assert all(0<=p['progress']<=1.00001 for p in samples)
        assert all(b['progress']>=a['progress']-.000001 for a,b in zip(samples,samples[1:]))
        notifies=A.list_notifies(path)
        events=unreal.AnimationLibrary.get_animation_notify_events(H.asset(path))
        cls=H.asset(ROOT+'ANS_BossAttackStep').generated_class()
        steps=[(n,e) for n,e in zip(notifies,events) if e.notify_state_class and e.notify_state_class.get_class()==cls]
        assert len(steps)==1
        n,e=steps[0]
        assert abs(n.trigger_time-START)<.0001 and abs(n.duration-(END-START))<.0001
        segments=[{'source':s.anim_sequence_path,'start':s.start_time,'source_start':s.anim_start_pos,
                   'source_end':s.anim_end_pos,'rate':s.play_rate} for s in A.list_anim_segments(path,0)]
        assert not any('Jog' in s['source'] or 'AS_Advance_' in s['source'] for s in segments)
        report['attacks'][side]={'montage':path,'curve':curve.get_path_name(),'samples':samples,'segments':segments,
            'step':{'start':n.trigger_time,'end':n.trigger_time+n.duration,'requested_cm':e.notify_state_class.get_editor_property('StepDistance')},
            'rate':card.get_editor_property('PlayRate'),'telegraph':card.get_editor_property('TelegraphSeconds'),
            'range_max':card.get_editor_property('MaxDistance'),'impact_times':list(card.get_editor_property('ImpactTimes')),
            'hit_ends':list(card.get_editor_property('HitWindowEnds')),
            'notifies':[{'name':str(x.notify_name),'start':x.trigger_time,'duration':x.duration} for x in notifies]}
    adjacency={}
    for c in S.get_connections(B,'ConfigureAdvancingPunch'):
        if c.source_pin_name in ['then','else']:
            adjacency.setdefault(c.source_node_id,[]).append(c.target_node_id)
    pending=[G.entry(B,'ConfigureAdvancingPunch')];reached=set()
    while pending:
        current=pending.pop()
        if current not in reached:
            reached.add(current);pending.extend(adjacency.get(current,[]))
    archived={'D32531004393E0F2C117949FB7B2F201','5FA59E3F48B5D050B0A294B4CCB3786E',
              'FACD264B47FAEE277C7469BAA616BDD3','423C28AD4859C2114FD6ACB9B94CFC5C'}
    assert reached.isdisjoint(archived)
    assert {'D41BD9BE4DBCE7A902F94CA3BB204429','B066C92E49B0806A3C906EBC2417D287'}.issubset(reached)
    report['checks']['jog_variant_selection_unreachable']=True
    report['checks']['approach_handoff_cm']=cdo.get_editor_property('ApproachAttackHandoffDistance')
    for graph in ['ConfigureAdvancingPunch','SamplePunchFootProgress','AdvanceAttackStep']:
        report[graph]={'nodes':[{'id':n.node_id,'title':n.node_title} for n in S.get_nodes_in_graph(B,graph,0,'',False)],
                       'links':[(c.source_node_id,c.source_pin_name,c.target_node_id,c.target_pin_name) for c in S.get_connections(B,graph)]}
    target=Path(unreal.Paths.project_saved_dir()).resolve()/'VibeUE'/'Reports'/'crunch_punch_foot_sync_20261005.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('VERIFIED curves, step windows, base montage paths, executable selection',str(target))
    return target


if __name__=='__main__':
    apply()
    inspect()
