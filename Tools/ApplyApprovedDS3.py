"""Scoped Blueprint deltas for the approved DS3 plan.

Numerical geometry is Battle-specific. No AI decision graph is rewritten.
The original disconnected graphs and pre-change backups remain available.
"""
import json
import unreal
import PolishSoulsHits as H

P,B,S=H.P,H.B,H.S
node,call,get,put=H.node,H.call,H.get,H.put
ROOT=unreal.Paths.project_saved_dir()+'VibeUE/'


def build(path,graph,label,nodes,wires=(),defaults=()):
    old=S.get_nodes_in_graph(path,graph,0,label,False)
    if any(n.node_title==label for n in old):
        with open(ROOT+'approved-ids-'+label.replace(' ','_')+'.json') as f:return json.load(f)
    r=S.build_graph(path,graph,nodes,
        [{'from_':a,'to':b} for a,b in wires],
        [{'node_ref':a,'pin_name':p,'value':str(v)} for a,p,v in defaults],False,False)
    print('MODIFIED:',path,graph,label,r.success,list(r.errors))
    assert r.success,list(r.errors)
    ids=dict(r.ref_to_node_id)
    assert S.add_comment_around_nodes(path,graph,label,list(ids.values()))
    S.auto_layout_selected_nodes(path,graph,list(ids.values()))
    with open(ROOT+'approved-ids-'+label.replace(' ','_')+'.json','w') as f:json.dump(ids,f,indent=2)
    return ids


def wire(path,graph,ids,wires):
    for a,b in wires:
        ar,ap=a.split('.',1);br,bp=b.split('.',1)
        assert S.connect_nodes(path,graph,ids.get(ar,ar),ap,ids.get(br,br),bp),(graph,a,b)


def default(path,graph,ids,ref,pin,value):
    assert S.set_node_pin_value(path,graph,ids.get(ref,ref),pin,str(value)),(graph,ref,pin)


def compile_save(path):
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(path))
    result=S.compile_blueprint(path)
    print('COMPILED:',path,result.success,result.num_errors,list(result.warnings))
    assert result.success,list(result.errors)
    assert unreal.EditorAssetLibrary.save_asset(path)
    print('SAVED:',path)


def member(ref,name,cls,write=False):
    return node(ref,'member_set' if write else 'member_get',member=name,**{'class':cls})


def camera():
    # Remove the existing framing solver; no arbitrary screen X target replaces it.
    wire(P,'UpdateLockOnRotation',{},[
        ('93FA2CC34693EF5FF156159A2824F8DB.then','2863F7D14E733373E8B01B84663A3693.execute'),
        ('FC75EDAC4FFECED954598DA6603B9D13.Yaw','E1043B3545A02EE6DE1306B365F03362.Yaw'),
        ('1FA2707B4D0823C5A358DFB7DD77DF00.ReturnValue','227300A744C56B907B8F8883F362FDF3.Value')])
    S.disconnect_pin(P,'UpdateCameraFraming','05D9E1194C7A74FDBF518A99A50DF670','SocketOffset')
    default(P,'UpdateCameraFraming',{},'05D9E1194C7A74FDBF518A99A50DF670','SocketOffset','0,0,0')
    print('MODIFIED:',P,'removed forced framing and shoulder offset')
    compile_save(P)


def sword():
    H.variable(P,'PrevSwordBase','vector','0,0,0')
    compile_save(P)
    # Initialize the complete blade history at the opening animation notify.
    ids=build(P,'DoAttackHitCheck','Approved blade history',[
        call('Base','KismetMathLibrary','TransformLocation'),put('History','PrevSwordBase')],
        [('7592159A460AD8ED513FDCA90C68EC1C.then','History.execute'),
         ('2F7E13EA4F8746A39994DC8A107505CC.ReturnValue','Base.T'),
         ('Base.ReturnValue','History.PrevSwordBase'),
         ('History.then','C9FF5BFC481EC7DBB0ADE591AD50D0CF.execute')],
        [('Base','Location','0,0,8')])
    entry=H.function(P,'TraceSweptBlade')
    loop=S.add_macro_instance_node(P,'TraceSweptBlade','ForLoop')
    assert loop
    print('LOOP PINS',[(p.pin_name) for p in S.get_node_details(P,'TraceSweptBlade',loop).input_pins],
          [(p.pin_name) for p in S.get_node_details(P,'TraceSweptBlade',loop).output_pins])
    nodes=[get('Open','bSwordWindowOpen'),get('State','ActionState'),
        call('Attack','KismetMathLibrary','EqualEqual_ByteByte'),call('Both','KismetMathLibrary','BooleanAND'),
        node('Gate','branch'),get('Sword','Sword'),call('World','SceneComponent','K2_GetComponentToWorld'),
        call('Base','KismetMathLibrary','TransformLocation'),call('Tip','KismetMathLibrary','TransformLocation'),
        get('PreviousBase','PrevSwordBase'),get('PreviousTip','PrevSwordTip'),get('Radius','SwordTraceRadius'),
        call('LengthVector','KismetMathLibrary','Subtract_VectorVector'),call('Length','KismetMathLibrary','VSize'),
        call('SafeRadius','KismetMathLibrary','FMax'),call('Divide','KismetMathLibrary','Divide_DoubleDouble'),
        call('Ceil','KismetMathLibrary','FCeil'),call('Count','KismetMathLibrary','Clamp'),
        call('IndexFloat','KismetMathLibrary','Conv_IntToDouble'),call('CountFloat','KismetMathLibrary','Conv_IntToDouble'),
        call('Alpha','KismetMathLibrary','Divide_DoubleDouble'),
        call('OldPoint','KismetMathLibrary','VLerp'),call('NewPoint','KismetMathLibrary','VLerp'),
        call('StaticTrace','KismetSystemLibrary','SphereTraceSingle'),call('StaticResolve',P,'ResolveSwordContact'),
        call('Sweep','KismetSystemLibrary','SphereTraceSingle'),call('Resolve',P,'ResolveSwordContact'),
        put('SaveBase','PrevSwordBase'),put('SaveTip','PrevSwordTip')]
    m=build(P,'TraceSweptBlade','Approved full blade temporal sampling',nodes)
    m['Loop']=loop
    wire(P,'TraceSweptBlade',m,[(entry+'.then','Gate.execute'),('Open.bSwordWindowOpen','Both.A'),
        ('State.ActionState','Attack.A'),('Attack.ReturnValue','Both.B'),('Both.ReturnValue','Gate.Condition'),
        ('Sword.Sword','World.self'),('World.ReturnValue','Base.T'),('World.ReturnValue','Tip.T'),
        ('Gate.then','StaticTrace.execute'),('Base.ReturnValue','StaticTrace.Start'),('Tip.ReturnValue','StaticTrace.End'),
        ('Radius.SwordTraceRadius','StaticTrace.Radius'),('StaticTrace.then','StaticResolve.execute'),
        ('StaticTrace.OutHit','StaticResolve.Contact'),('StaticResolve.then','Loop.execute'),
        ('Tip.ReturnValue','LengthVector.A'),('Base.ReturnValue','LengthVector.B'),('LengthVector.ReturnValue','Length.A'),
        ('Length.ReturnValue','Divide.A'),('Radius.SwordTraceRadius','SafeRadius.A'),('SafeRadius.ReturnValue','Divide.B'),
        ('Divide.ReturnValue','Ceil.A'),('Ceil.ReturnValue','Count.Value'),('Count.ReturnValue','Loop.LastIndex'),
        ('Loop.Index','IndexFloat.InInt'),('Count.ReturnValue','CountFloat.InInt'),
        ('IndexFloat.ReturnValue','Alpha.A'),('CountFloat.ReturnValue','Alpha.B'),
        ('PreviousBase.PrevSwordBase','OldPoint.A'),('PreviousTip.PrevSwordTip','OldPoint.B'),('Alpha.ReturnValue','OldPoint.Alpha'),
        ('Base.ReturnValue','NewPoint.A'),('Tip.ReturnValue','NewPoint.B'),('Alpha.ReturnValue','NewPoint.Alpha'),
        ('Loop.LoopBody','Sweep.execute'),('OldPoint.ReturnValue','Sweep.Start'),('NewPoint.ReturnValue','Sweep.End'),
        ('Radius.SwordTraceRadius','Sweep.Radius'),('Sweep.then','Resolve.execute'),('Sweep.OutHit','Resolve.Contact'),
        ('Loop.Completed','SaveBase.execute'),('Base.ReturnValue','SaveBase.PrevSwordBase'),
        ('SaveBase.then','SaveTip.execute'),('Tip.ReturnValue','SaveTip.PrevSwordTip')])
    for ref,pin,value in [('Attack','B',4),('Base','Location','0,0,8'),('Tip','Location','0,0,99'),
                          ('SafeRadius','B',1),('Count','Min',1),('Count','Max',64),('Loop','FirstIndex',0)]:
        default(P,'TraceSweptBlade',m,ref,pin,value)
    for ref in ['StaticTrace','Sweep']:
        default(P,'TraceSweptBlade',m,ref,'TraceChannel','TraceTypeQuery1')
        default(P,'TraceSweptBlade',m,ref,'DrawDebugType','None')
    n=build(P,'TraceSwordWindow','Approved blade trace dispatch',[call('Full',P,'TraceSweptBlade')],
        [('B5297567449CD772263FBDAC26B7E1E9.then','Full.execute')])
    compile_save(P)


def scoped_hitstop():
    for name,kind,value in [('bScopedHitStop','bool','false'),('HitStopSelfPrevious','real',1),
                            ('HitStopOtherPrevious','real',1)]:H.variable(P,name,kind,value)
    actor_type=unreal.BlueprintEditorLibrary.get_member_variable_type(H.asset(P),'LockOnTarget')
    for name in ['HitStopTarget','FrozenHitStopTarget']:
        if name not in {v.variable_name for v in S.list_variables(P)}:
            assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(P),name,actor_type)
            print('ADDED:',P,name)
    compile_save(P)


def bypass_timer(graph,identifier):
    connections=S.get_connections(P,graph)
    incoming=[c for c in connections if c.target_node_id==identifier and c.target_pin_name=='execute']
    outgoing=[c for c in connections if c.source_node_id==identifier and c.source_pin_name=='then']
    for source in incoming:
        for target in outgoing:
            wire(P,graph,{},[(source.source_node_id+'.'+source.source_pin_name,
                             target.target_node_id+'.'+target.target_pin_name)])
    S.disconnect_pin(P,graph,identifier,'execute')
    print('MODIFIED:',P,graph,'disabled duplicate world timer',identifier)


def player_animation_clock():
    montage_type=unreal.BlueprintEditorLibrary.get_member_variable_type(H.asset(P),'ActiveDodgeMontage')
    if 'ActiveAttackMontage' not in {v.variable_name for v in S.list_variables(P)}:
        assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(P),'ActiveAttackMontage',montage_type)
    compile_save(P)
    build(P,'StartComboStep','Approved attack animation identity',[put('Store','ActiveAttackMontage')],
        [('9FF23A0D48B5B20D3DCFB5AF0DAF8F89.then','Store.execute'),
         ('FEA60F1F4948FC8280C77AA44570EBEB.Output','Store.ActiveAttackMontage'),
         ('Store.then','0B46362E4BA64754693BA1A36832A00D.execute')])
    # Existing attack notifies own hit, combo/cancel and recovery, exclusively.
    for identifier in ['F57424704E1B45030AAEB694DF325AAD','3DFA620643BF19E40FC359A5B8256700',
                       'AFCFDCB749D0974F8883DD8A18287391','A8E1CF7B4CD13C65CF29E0B0DFC49C49']:
        bypass_timer('StartComboStep',identifier)
    # The direction lock follows the same montage position even during a local freeze.
    build(P,'UpdateAttackSteering','Approved steering animation clock',[
        get('MeshClock','Mesh'),call('AnimClock','SkeletalMeshComponent','GetAnimInstance'),
        get('AttackClock','ActiveAttackMontage'),call('Position','AnimInstance','Montage_GetPosition'),
        call('Length','AnimationAsset','GetPlayLength')],
        [('MeshClock.Mesh','AnimClock.self'),('AnimClock.ReturnValue','Position.self'),
         ('AttackClock.ActiveAttackMontage','Position.Montage'),
         ('AttackClock.ActiveAttackMontage','Length.self'),
         ('Position.ReturnValue','8780AB884BE2D35CFE2005A4D8FB8A73.A'),
         ('Length.ReturnValue','7F3424294BF9A2D8D25FABA740D37983.A')])
    # Retain the existing Battle 0.433/0.70 times. They are C until original linkage is proved.
    bypass_timer('TryEnterDodge','BE651E364A144B5D41A139A5A517F29E')
    bypass_timer('TryEnterDodge','BCB0A6D0483A9196161BF59AEB99AA0E')
    entry=H.function(P,'UpdateRollAnimationClock')
    build(P,'UpdateRollAnimationClock','Approved roll queue animation clock',[
        get('State','ActionState'),call('Rolling','KismetMathLibrary','EqualEqual_ByteByte'),node('Gate','branch'),
        get('Mesh','Mesh'),call('Anim','SkeletalMeshComponent','GetAnimInstance'),get('Roll','ActiveDodgeMontage'),
        call('Position','AnimInstance','Montage_GetPosition'),call('Length','AnimationAsset','GetPlayLength'),
        call('Ratio','KismetMathLibrary','SafeDivide'),get('Duration','MediumRollDuration'),
        call('Time','KismetMathLibrary','Multiply_DoubleDouble'),put('Save','DodgeMoveElapsed')],
        [(entry+'.then','Gate.execute'),('State.ActionState','Rolling.A'),('Rolling.ReturnValue','Gate.Condition'),
         ('Gate.then','Save.execute'),('Mesh.Mesh','Anim.self'),('Anim.ReturnValue','Position.self'),
         ('Roll.ActiveDodgeMontage','Position.Montage'),('Roll.ActiveDodgeMontage','Length.self'),
         ('Position.ReturnValue','Ratio.A'),('Length.ReturnValue','Ratio.B'),
         ('Ratio.ReturnValue','Time.A'),('Duration.MediumRollDuration','Time.B'),('Time.ReturnValue','Save.DodgeMoveElapsed')],
        [('Rolling','B',2)])
    cs=S.get_connections(P,'EventGraph')
    target='D5471E004BF38B078E0B89B1E794894B'
    before=next(c for c in cs if c.target_node_id==target and c.target_pin_name=='execute')
    build(P,'EventGraph','Approved roll animation clock Tick',[call('Clock',P,'UpdateRollAnimationClock')],
        [(before.source_node_id+'.'+before.source_pin_name,'Clock.execute'),('Clock.then',target+'.execute')])
    compile_save(P)
    c=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(P))
    for name,fn in [('AN_RollIFrameEnd','OnIFrameEnd'),('AN_RollRecovery','OnDodgeRecoveryTimer')]:
        path='/Game/BossArena/Player/Animation/Notifies/'+name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            factory=unreal.BlueprintFactory();factory.set_editor_property('ParentClass',unreal.AnimNotify)
            assert unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,path.rsplit('/',1)[0],unreal.Blueprint,factory)
            print('CREATED:',path)
        assert S.override_function(path,'Received_Notify')
        ns=S.get_nodes_in_graph(path,'Received_Notify',0,'',False)
        entry=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionEntry')
        ret=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionResult')
        m=build(path,'Received_Notify','Approved roll animation event '+fn,[
            call('Owner','ActorComponent','GetOwner'),node('Player','cast',target_class=P),call('Event',P,fn)])
        pin=next(p.pin_name for p in S.get_node_details(path,'Received_Notify',m['Player']).output_pins if p.pin_category=='object')
        wire(path,'Received_Notify',m,[(entry+'.then','Player.execute'),(entry+'.MeshComp','Owner.self'),
            ('Owner.ReturnValue','Player.Object'),('Player.then','Event.execute'),('Player.'+pin,'Event.self'),
            ('Event.then',ret+'.execute'),('Player.CastFailed',ret+'.execute')])
        default(path,'Received_Notify',{},ret,'ReturnValue','true');compile_save(path)
    for path in unreal.EditorAssetLibrary.list_assets('/Game/BossArena/Player/Animation/SwordShield/Sequences',False,False):
        if '/RM_Shield_A_Roll_' not in path:continue
        path=path.split('.')[0];sequence=unreal.EditorAssetLibrary.load_asset(path);length=sequence.get_play_length()
        backup='/Game/BossArena/Backup/'+path.rsplit('/',1)[-1]+'_PreTimeline_20260929'
        if not unreal.EditorAssetLibrary.does_asset_exist(backup):
            assert unreal.EditorAssetLibrary.duplicate_asset(path,backup);unreal.EditorAssetLibrary.save_asset(backup)
        for name,t in [('AN_RollIFrameEnd',length*c.get_editor_property('IFrameDuration')/c.get_editor_property('MediumRollDuration')),
                       ('AN_RollRecovery',length-.001)]:
            if any(n.notify_name==name for n in unreal.AnimSequenceService.list_notifies(path)):continue
            cls='/Game/BossArena/Player/Animation/Notifies/'+name+'.'+name+'_C'
            idx=unreal.AnimSequenceService.add_notify(path,cls,t,name);assert idx>=0
            unreal.AnimSequenceService.set_notify_trigger_weight_threshold(path,idx,.0001)
            print('MODIFIED:',path,name,t)
        assert unreal.EditorAssetLibrary.save_asset(path)


def prepare_physical():
    for name,kind,value in [('bPhysicalStrikeOpen','bool','false'),('bPhysicalStrikeHit','bool','false'),
                            ('PhysicalStrikeIndex','int',-1),('PhysicalActionID','int',0),
                            ('PhysicalStrikeDamage','real',0),('PhysicalHandRadiusLocal','real',30.891403),
                            ('PhysicalStrikeSocket','name','hand_l')]:
        H.variable(B,name,kind,value)
    vector_type=unreal.BlueprintEditorLibrary.get_member_variable_type(H.asset(P),'PrevSwordBase')
    for name in ['PrevPhysicsLeftA','PrevPhysicsLeftZ','PrevPhysicsRightA','PrevPhysicsRightZ','LastContactPoint','LastContactDirection']:
        if name not in {v.variable_name for v in S.list_variables(B)}:
            assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(B),name,vector_type)
            print('ADDED:',B,name)
    for path in [P,B]:
        for name in ['LastContactPoint','LastContactDirection']:
            if name not in {v.variable_name for v in S.list_variables(path)}:
                assert unreal.BlueprintEditorLibrary.add_member_variable(H.asset(path),name,vector_type)
    for g,params in [('BeginPhysicalStrike',[('Strike','int')]),('EndPhysicalStrike',[('Strike','int')]),
                     ('TracePhysicalStrike',[]),('CapturePhysicalHistory',[]),
                     ('TracePhysicalLeft',[]),('TracePhysicalRight',[]),
                     ('ResolvePhysicalContact',[('Contact','FHitResult')])]:
        H.function(B,g,params)
    compile_save(B);compile_save(P)


def reaction_animation_clock():
    path='/Game/BossArena/Player/Animation/Notifies/AN_ShieldReactionEnd'
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        factory=unreal.BlueprintFactory();factory.set_editor_property('ParentClass',unreal.AnimNotify)
        assert unreal.AssetToolsHelpers.get_asset_tools().create_asset('AN_ShieldReactionEnd',path.rsplit('/',1)[0],unreal.Blueprint,factory)
    assert S.override_function(path,'Received_Notify')
    ns=S.get_nodes_in_graph(path,'Received_Notify',0,'',False)
    entry=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionEntry')
    ret=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionResult')
    m=build(path,'Received_Notify','Approved reaction animation end',[
        call('Owner','ActorComponent','GetOwner'),node('Player','cast',target_class=P),call('End',P,'EndShieldReaction')])
    pin=next(p.pin_name for p in S.get_node_details(path,'Received_Notify',m['Player']).output_pins if p.pin_category=='object')
    wire(path,'Received_Notify',m,[(entry+'.then','Player.execute'),(entry+'.MeshComp','Owner.self'),
        ('Owner.ReturnValue','Player.Object'),('Player.then','End.execute'),('Player.'+pin,'End.self'),
        ('End.then',ret+'.execute'),('Player.CastFailed',ret+'.execute')])
    default(path,'Received_Notify',{},ret,'ReturnValue','true');compile_save(path)
    for name in ['AM_Shield_HitFront','AM_Shield_HitLeft','AM_Shield_HitRight','AM_Shield_Knockdown']:
        montage='/Game/BossArena/Player/Animation/SwordShield/Montages/'+name
        backup='/Game/BossArena/Backup/'+name+'_PreTimeline_20260929'
        if not unreal.EditorAssetLibrary.does_asset_exist(backup):
            assert unreal.EditorAssetLibrary.duplicate_asset(montage,backup);unreal.EditorAssetLibrary.save_asset(backup)
        if not any(n.notify_name=='ShieldReactionEnd' for n in unreal.AnimMontageService.list_notifies(montage)):
            length=unreal.EditorAssetLibrary.load_asset(montage).get_play_length()
            assert unreal.AnimMontageService.add_notify(montage,path+'.AN_ShieldReactionEnd_C',length-.001,'ShieldReactionEnd')>=0
            print('MODIFIED:',montage,'reaction end at',length-.001)
            assert unreal.EditorAssetLibrary.save_asset(montage)
    for n in S.get_nodes_in_graph(P,'PlayShieldReaction',0,'',False):
        if 'Set Timer' not in n.node_title:continue
        if any(p.pin_name=='FunctionName' and p.default_value=='EndShieldReaction' for p in S.get_node_details(P,'PlayShieldReaction',n.node_id).input_pins):
            bypass_timer('PlayShieldReaction',n.node_id)
    compile_save(P)


def physics_nodes(side):
    from TestApprovedDS3 import geometry,length
    socket='hand_slide_'+side;center,rotation=geometry[socket]
    axis=unreal.MathLibrary.get_up_vector(unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))
    offsets=[unreal.Vector(*center)+axis*s*length/2 for s in [-1,1]]
    nodes=[get('Mesh','Mesh'),call('Socket','SceneComponent','GetSocketTransform'),
        call('A','KismetMathLibrary','TransformLocation'),call('Z','KismetMathLibrary','TransformLocation'),
        call('Scale','SceneComponent','K2_GetComponentScale'),call('ScaleXYZ','KismetMathLibrary','BreakVector'),
        call('ScaleAbs','KismetMathLibrary','Abs'),get('Radius','PhysicalHandRadiusLocal'),
        call('WorldRadius','KismetMathLibrary','Multiply_DoubleDouble')]
    wires=[('Mesh.Mesh','Socket.self'),('Socket.ReturnValue','A.T'),('Socket.ReturnValue','Z.T'),
           ('Mesh.Mesh','Scale.self'),('Scale.ReturnValue','ScaleXYZ.InVec'),('ScaleXYZ.X','ScaleAbs.A'),
           ('ScaleAbs.ReturnValue','WorldRadius.B'),('Radius.PhysicalHandRadiusLocal','WorldRadius.A')]
    defaults=[('Socket','InSocketName',socket),('Socket','TransformSpace','RTS_World'),
              ('A','Location',','.join(str(v) for v in offsets[0].to_tuple())),
              ('Z','Location',','.join(str(v) for v in offsets[1].to_tuple()))]
    return nodes,wires,defaults


def physical_history():
    entry=H.function(B,'CapturePhysicalHistory');previous=entry+'.then'
    for side,label in [('l','Left'),('r','Right')]:
        nodes,wires,defs=physics_nodes(side)
        nodes += [put('SaveA','PrevPhysics'+label+'A'),put('SaveZ','PrevPhysics'+label+'Z')]
        wires += [(previous,'SaveA.execute'),('A.ReturnValue','SaveA.PrevPhysics'+label+'A'),
                  ('SaveA.then','SaveZ.execute'),('Z.ReturnValue','SaveZ.PrevPhysics'+label+'Z')]
        ids=build(B,'CapturePhysicalHistory','Approved physics history '+label,nodes,wires,defs)
        previous=ids['SaveZ']+'.then'


def physical_events():
    entry=H.function(B,'BeginPhysicalStrike',[('Strike','int')])
    D='/Game/BossArena/Boss/AI/BP_BossActionDefinition'
    m=build(B,'BeginPhysicalStrike','Approved notify opens one physical strike',[
        get('Action','ActiveAction'),call('Valid','KismetSystemLibrary','IsValid'),node('Gate','branch'),
        put('Index','PhysicalStrikeIndex'),put('Open','bPhysicalStrikeOpen'),put('Hit','bPhysicalStrikeHit'),
        member('Sockets','HitSockets',D),member('Damages','HitDamages',D),
        node('SocketAt','spawner_key',key='NODE K2Node_GetArrayItem'),node('DamageAt','spawner_key',key='NODE K2Node_GetArrayItem'),
        put('Socket','PhysicalStrikeSocket'),put('Damage','PhysicalStrikeDamage'),call('History',B,'CapturePhysicalHistory')])
    wire(B,'BeginPhysicalStrike',m,[(entry+'.then','Gate.execute'),('Action.ActiveAction','Valid.Object'),('Valid.ReturnValue','Gate.Condition'),
        ('Gate.then','Index.execute'),(entry+'.Strike','Index.PhysicalStrikeIndex'),('Index.then','Open.execute'),('Open.then','Hit.execute'),
        ('Hit.then','Socket.execute'),('Socket.then','Damage.execute'),('Damage.then','History.execute'),
        ('Action.ActiveAction','Sockets.self'),('Action.ActiveAction','Damages.self'),
        ('Sockets.HitSockets','SocketAt.Array'),(entry+'.Strike','SocketAt.Dimension 1'),('SocketAt.Output','Socket.PhysicalStrikeSocket'),
        ('Damages.HitDamages','DamageAt.Array'),(entry+'.Strike','DamageAt.Dimension 1'),('DamageAt.Output','Damage.PhysicalStrikeDamage')])
    default(B,'BeginPhysicalStrike',m,'Open','bPhysicalStrikeOpen','true')
    default(B,'BeginPhysicalStrike',m,'Hit','bPhysicalStrikeHit','false')
    entry=H.function(B,'EndPhysicalStrike',[('Strike','int')])
    build(B,'EndPhysicalStrike','Approved notify closes only matching physical strike',[
        get('Index','PhysicalStrikeIndex'),call('Same','KismetMathLibrary','EqualEqual_IntInt'),
        node('Gate','branch'),put('Close','bPhysicalStrikeOpen')],
        [(entry+'.then','Gate.execute'),(entry+'.Strike','Same.A'),('Index.PhysicalStrikeIndex','Same.B'),
         ('Same.ReturnValue','Gate.Condition'),('Gate.then','Close.execute')],[('Close','bPhysicalStrikeOpen','false')])
    entry=next(n.node_id for n in S.get_nodes_in_graph(B,'BeginCombatAction',0,'',False) if n.node_type=='K2Node_FunctionEntry')
    before=next(c for c in S.get_connections(B,'BeginCombatAction') if c.source_node_id==entry and c.source_pin_name=='then')
    build(B,'BeginCombatAction','Approved physical action identity reset',[
        get('ID','PhysicalActionID'),call('Next','KismetMathLibrary','Add_IntInt'),put('SaveID','PhysicalActionID'),
        put('Close','bPhysicalStrikeOpen'),put('Hit','bPhysicalStrikeHit')],
        [(entry+'.then','SaveID.execute'),('ID.PhysicalActionID','Next.A'),('Next.ReturnValue','SaveID.PhysicalActionID'),
         ('SaveID.then','Close.execute'),('Close.then','Hit.execute'),('Hit.then',before.target_node_id+'.'+before.target_pin_name)],
        [('Next','B',1),('Close','bPhysicalStrikeOpen','false'),('Hit','bPhysicalStrikeHit','false')])


def contact_resolution():
    entry=H.function(B,'ResolvePhysicalContact',[('Contact','FHitResult')])
    nodes=[get('Open','bPhysicalStrikeOpen'),node('OpenGate','branch'),get('Hit','bPhysicalStrikeHit'),node('HitGate','branch'),
        call('Break','GameplayStatics','BreakHitResult'),node('Player','cast',target_class=P),
        member('Invincible','bInvincible',P),node('InvGate','branch'),
        call('BossPos','Actor','K2_GetActorLocation'),call('WallTrace','KismetSystemLibrary','LineTraceSingle'),
        call('WallHit','GameplayStatics','BreakHitResult'),call('SameActor','KismetMathLibrary','EqualEqual_ObjectObject'),
        call('NoWall','KismetMathLibrary','Not_PreBool'),call('Visible','KismetMathLibrary','BooleanOR'),node('VisibleGate','branch'),
        put('Record','bPhysicalStrikeHit'),get('Damage','PhysicalStrikeDamage'),get('GuardBreak','bActiveGuardBreak'),node('GuardGate','branch'),
        call('BreakGuard',P,'ReceiveBossGuardBreak'),call('DamageApply','GameplayStatics','ApplyPointDamage'),
        call('Controller','Pawn','GetController'),get('Mesh','Mesh'),call('Self','ActorComponent','GetOwner'),
        call('PlayerPos','Actor','K2_GetActorLocation'),call('Direction','KismetMathLibrary','Subtract_VectorVector'),
        call('Normal','KismetMathLibrary','Normal'),put('SavePoint','LastContactPoint'),put('SaveDirection','LastContactDirection'),
        member('PlayerPoint','LastContactPoint',P,True),member('PlayerDirection','LastContactDirection',P,True)]
    m=build(B,'ResolvePhysicalContact','Approved swept contact wall iframe point damage',nodes)
    castpin=next(p.pin_name for p in S.get_node_details(B,'ResolvePhysicalContact',m['Player']).output_pins if p.pin_category=='object')
    player='Player.'+castpin
    wire(B,'ResolvePhysicalContact',m,[(entry+'.then','OpenGate.execute'),('Open.bPhysicalStrikeOpen','OpenGate.Condition'),
        ('OpenGate.then','HitGate.execute'),('Hit.bPhysicalStrikeHit','HitGate.Condition'),('HitGate.else','Player.execute'),
        (entry+'.Contact','Break.Hit'),('Break.HitActor','Player.Object'),('Player.then','InvGate.execute'),
        (player,'Invincible.self'),('Invincible.bInvincible','InvGate.Condition'),('InvGate.else','WallTrace.execute'),
        ('BossPos.ReturnValue','WallTrace.Start'),('Break.ImpactPoint','WallTrace.End'),('WallTrace.then','VisibleGate.execute'),
        ('WallTrace.OutHit','WallHit.Hit'),('WallHit.HitActor','SameActor.A'),(player,'SameActor.B'),
        ('SameActor.ReturnValue','Visible.A'),('WallTrace.ReturnValue','NoWall.A'),('NoWall.ReturnValue','Visible.B'),
        ('Visible.ReturnValue','VisibleGate.Condition'),('VisibleGate.then','Record.execute'),('Record.then','SavePoint.execute'),
        ('Break.ImpactPoint','SavePoint.LastContactPoint'),('SavePoint.then','SaveDirection.execute'),
        (player,'PlayerPos.self'),('PlayerPos.ReturnValue','Direction.A'),('BossPos.ReturnValue','Direction.B'),
        ('Direction.ReturnValue','Normal.A'),('Normal.ReturnValue','SaveDirection.LastContactDirection'),
        ('SaveDirection.then','PlayerPoint.execute'),(player,'PlayerPoint.self'),('Break.ImpactPoint','PlayerPoint.LastContactPoint'),
        ('PlayerPoint.then','PlayerDirection.execute'),(player,'PlayerDirection.self'),('Normal.ReturnValue','PlayerDirection.LastContactDirection'),
        ('PlayerDirection.then','GuardGate.execute'),('GuardBreak.bActiveGuardBreak','GuardGate.Condition'),('GuardGate.then','BreakGuard.execute'),
        (player,'BreakGuard.self'),('GuardGate.else','DamageApply.execute'),('BreakGuard.then','DamageApply.execute'),
        (player,'DamageApply.DamagedActor'),('Damage.PhysicalStrikeDamage','DamageApply.BaseDamage'),
        ('Normal.ReturnValue','DamageApply.HitFromDirection'),(entry+'.Contact','DamageApply.HitInfo'),
        ('Controller.ReturnValue','DamageApply.EventInstigator'),('Mesh.Mesh','Self.self'),('Self.ReturnValue','DamageApply.DamageCauser')])
    for ref,pin,v in [('Record','bPhysicalStrikeHit','true'),('WallTrace','TraceChannel','TraceTypeQuery1'),
                      ('WallTrace','DrawDebugType','None')]:default(B,'ResolvePhysicalContact',m,ref,pin,v)


def physical_traces():
    for side,label in [('l','Left'),('r','Right')]:
        graph='TracePhysical'+label;entry=H.function(B,graph)
        nodes,wires,defs=physics_nodes(side)
        nodes += [get('OldA','PrevPhysics'+label+'A'),get('OldZ','PrevPhysics'+label+'Z'),
                  put('SaveA','PrevPhysics'+label+'A'),put('SaveZ','PrevPhysics'+label+'Z'),get('Draw','AttackDebugDrawMode')]
        previous=entry+'.then'
        paths=[('A.ReturnValue','Z.ReturnValue')]
        for i,alpha in enumerate([0,.5,1]):
            nodes += [call('Old'+str(i),'KismetMathLibrary','VLerp'),call('Now'+str(i),'KismetMathLibrary','VLerp')]
            wires += [('OldA.PrevPhysics'+label+'A','Old'+str(i)+'.A'),('OldZ.PrevPhysics'+label+'Z','Old'+str(i)+'.B'),
                      ('A.ReturnValue','Now'+str(i)+'.A'),('Z.ReturnValue','Now'+str(i)+'.B')]
            defs += [('Old'+str(i),'Alpha',alpha),('Now'+str(i),'Alpha',alpha)]
            paths.append(('Old'+str(i)+'.ReturnValue','Now'+str(i)+'.ReturnValue'))
        for i,(a,z) in enumerate(paths):
            trace='Trace'+str(i);resolve='Resolve'+str(i)
            nodes += [call(trace,'KismetSystemLibrary','SphereTraceSingle'),call(resolve,B,'ResolvePhysicalContact')]
            wires += [(previous,trace+'.execute'),(a,trace+'.Start'),(z,trace+'.End'),
                      ('WorldRadius.ReturnValue',trace+'.Radius'),('Draw.AttackDebugDrawMode',trace+'.DrawDebugType'),
                      (trace+'.then',resolve+'.execute'),(trace+'.OutHit',resolve+'.Contact')]
            defs += [(trace,'TraceChannel','TraceTypeQuery1')];previous=resolve+'.then'
        wires += [(previous,'SaveA.execute'),('A.ReturnValue','SaveA.PrevPhysics'+label+'A'),
                  ('SaveA.then','SaveZ.execute'),('Z.ReturnValue','SaveZ.PrevPhysics'+label+'Z')]
        build(B,graph,'Approved physics capsule temporal sweep '+label,nodes,wires,defs)
    entry=H.function(B,'TracePhysicalStrike');D='/Game/BossArena/Boss/AI/BP_BossActionDefinition'
    m=build(B,'TracePhysicalStrike','Approved physical window dispatch independent of AI phase',[
        get('Open','bPhysicalStrikeOpen'),node('Gate','branch'),get('Action','ActiveAction'),
        member('Montage','Montage',D),get('Mesh','Mesh'),call('Anim','SkeletalMeshComponent','GetAnimInstance'),
        call('Playing','AnimInstance','Montage_IsPlaying'),node('PlayingGate','branch'),put('Stale','bPhysicalStrikeOpen'),
        get('Socket','PhysicalStrikeSocket'),call('Left','KismetMathLibrary','EqualEqual_NameName'),node('LeftGate','branch'),
        call('L',''+B,'TracePhysicalLeft'),call('R',''+B,'TracePhysicalRight'),
        member('Both','bBothHands',D),node('BothL','branch'),node('BothR','branch'),
        call('OtherL',B,'TracePhysicalRight'),call('OtherR',B,'TracePhysicalLeft')],
        [(entry+'.then','Gate.execute'),('Open.bPhysicalStrikeOpen','Gate.Condition'),('Gate.then','PlayingGate.execute'),
         ('Action.ActiveAction','Montage.self'),('Mesh.Mesh','Anim.self'),('Anim.ReturnValue','Playing.self'),
         ('Montage.Montage','Playing.Montage'),('Playing.ReturnValue','PlayingGate.Condition'),
         ('PlayingGate.else','Stale.execute'),('PlayingGate.then','LeftGate.execute'),
         ('Socket.PhysicalStrikeSocket','Left.A'),('Left.ReturnValue','LeftGate.Condition'),
         ('LeftGate.then','L.execute'),('LeftGate.else','R.execute'),('L.then','BothL.execute'),('R.then','BothR.execute'),
         ('Action.ActiveAction','Both.self'),('Both.bBothHands','BothL.Condition'),('Both.bBothHands','BothR.Condition'),
         ('BothL.then','OtherL.execute'),('BothR.then','OtherR.execute')],
        [('Left','B','hand_l'),('Stale','bPhysicalStrikeOpen','false')])
    # Replace the Tick's physical query dispatch while preserving subsequent AI extras.
    build(B,'EventGraph','Approved physical Tick dispatch', [call('Physical',B,'TracePhysicalStrike')],
        [('D9BD81D64E2930FDE0C3549A9BC1C162.then','Physical.execute'),('Physical.then','502B68B74F373939D0DA50B984CFB958.execute')])
    # Main legacy collision sits at the end of the Tick chain; nothing follows its guard.
    S.disconnect_pin(B,'EventGraph','B07B7BE74BAE38A0EC0EDE87F8F023A9','execute')
    archive=build(B,'EventGraph','Legacy collision archive not called',[
        node('Archive','custom_event',name='LegacyCollisionArchive')])
    wire(B,'EventGraph',archive,[('Archive.then','B07B7BE74BAE38A0EC0EDE87F8F023A9.execute')])
    compile_save(B)


def physical_notify_classes():
    # States close even when a montage is interrupted. Each physical strike owns its record.
    for index in range(3):
        path='/Game/BossArena/Boss/Animations/Notifies/ANS_PhysicalStrike_'+str(index)
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            factory=unreal.BlueprintFactory();factory.set_editor_property('ParentClass',unreal.AnimNotifyState)
            assert unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit('/',1)[-1],path.rsplit('/',1)[0],unreal.Blueprint,factory)
            print('CREATED:',path)
        for graph,fn in [('Received_NotifyBegin','BeginPhysicalStrike'),('Received_NotifyEnd','EndPhysicalStrike')]:
            assert S.override_function(path,graph)
            ns=S.get_nodes_in_graph(path,graph,0,'',False)
            entry=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionEntry')
            ret=next(n.node_id for n in ns if n.node_type=='K2Node_FunctionResult')
            m=build(path,graph,'Approved physical notify '+str(index)+' '+fn,[
                call('Owner','ActorComponent','GetOwner'),node('Boss','cast',target_class=B),call('Call',B,fn)])
            castpin=next(p.pin_name for p in S.get_node_details(path,graph,m['Boss']).output_pins if p.pin_category=='object')
            wire(path,graph,m,[(entry+'.then','Boss.execute'),(entry+'.MeshComp','Owner.self'),('Owner.ReturnValue','Boss.Object'),
                ('Boss.then','Call.execute'),('Boss.'+castpin,'Call.self'),('Call.then',ret+'.execute'),('Boss.CastFailed',ret+'.execute')])
            default(path,graph,m,'Call','Strike',index)
            default(path,graph,{},ret,'ReturnValue','true')
        compile_save(path)


def physical_windows():
    # Montage-local seconds measured from the existing asset poses (C).
    windows={0:[(0,.55,.72)],1:[(0,.14,.32)],2:[(0,.15,.30)],3:[(0,.44,1.0)],
             4:[(0,.55,.72),(1,1.073333,1.253333),(2,2.246667,2.766667)],
             5:[(0,.36,.60)],6:[(0,.50,.78)]}
    b=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(B))
    report=[]
    for index,action in enumerate(b.get_editor_property('Actions')):
        if index not in windows:continue
        montage=action.get_editor_property('Montage').get_path_name().split('.')[0]
        backup='/Game/BossArena/Backup/'+montage.rsplit('/',1)[-1]+'_PrePhysical_20260929'
        if not unreal.EditorAssetLibrary.does_asset_exist(backup):
            assert unreal.EditorAssetLibrary.duplicate_asset(montage,backup)
            assert unreal.EditorAssetLibrary.save_asset(backup)
            print('CREATED:',backup)
        existing=unreal.AnimMontageService.list_notifies(montage)
        for strike,start,end in windows[index]:
            name='PhysicalStrike'+str(strike)
            if any(n.notify_name==name for n in existing):continue
            cls='/Game/BossArena/Boss/Animations/Notifies/ANS_PhysicalStrike_'+str(strike)+'.ANS_PhysicalStrike_'+str(strike)+'_C'
            result=unreal.AnimMontageService.add_notify_state(montage,cls,start,end-start,name)
            assert result>=0,(montage,result)
            print('MODIFIED:',montage,name,start,end)
            report.append({'montage':montage,'strike':strike,'start':start,'end':end,'classification':'C'})
        assert unreal.EditorAssetLibrary.save_asset(montage)
    with open(ROOT+'approved-physical-windows.json','w') as f:json.dump(report,f,indent=2)


def connect_scoped_hitstop():
    # Entry event names remain public and unchanged; only the freeze implementation changes.
    m=build(P,'EventGraph','Approved actor scoped hit stop',[
        get('Active','bScopedHitStop'),node('Gate','branch'),put('On','bScopedHitStop'),
        member('SelfTime','CustomTimeDilation','Actor'),put('SaveSelf','HitStopSelfPrevious'),
        member('FreezeSelf','CustomTimeDilation','Actor',True),get('Target','HitStopTarget'),
        put('PinTarget','FrozenHitStopTarget'),call('Valid','KismetSystemLibrary','IsValid'),node('OtherGate','branch'),
        member('OtherTime','CustomTimeDilation','Actor'),put('SaveOther','HitStopOtherPrevious'),
        member('FreezeOther','CustomTimeDilation','Actor',True),
        get('Pinned','FrozenHitStopTarget'),get('RestoreSelfTime','HitStopSelfPrevious'),get('RestoreOtherTime','HitStopOtherPrevious'),
        member('RestoreSelf','CustomTimeDilation','Actor',True),member('RestoreOther','CustomTimeDilation','Actor',True),
        put('Off','bScopedHitStop'),call('PinnedValid','KismetSystemLibrary','IsValid'),node('RestoreGate','branch')])
    wire(P,'EventGraph',m,[('5A28E3FA416806889414008A28971A8D.then','Gate.execute'),('Active.bScopedHitStop','Gate.Condition'),
        ('Gate.then','0936537344D0AA886A3F98809E22C73A.execute'),('Gate.else','SaveSelf.execute'),
        ('SelfTime.CustomTimeDilation','SaveSelf.HitStopSelfPrevious'),('SaveSelf.then','FreezeSelf.execute'),
        ('FreezeSelf.then','On.execute'),('On.then','PinTarget.execute'),('Target.HitStopTarget','PinTarget.FrozenHitStopTarget'),
        ('PinTarget.then','OtherGate.execute'),('Target.HitStopTarget','Valid.Object'),('Valid.ReturnValue','OtherGate.Condition'),
        ('OtherGate.then','SaveOther.execute'),('OtherGate.else','0936537344D0AA886A3F98809E22C73A.execute'),
        ('Target.HitStopTarget','OtherTime.self'),('OtherTime.CustomTimeDilation','SaveOther.HitStopOtherPrevious'),
        ('SaveOther.then','FreezeOther.execute'),('Target.HitStopTarget','FreezeOther.self'),
        ('FreezeOther.then','0936537344D0AA886A3F98809E22C73A.execute'),
        ('3184D2D2427CE7C757AC08AC6DEA4032.HitStopDuration','AF17086F48A60EFB6D3290BACB1356A9.Time'),
        ('296033224C986FDA59196FB3029563D2.then','RestoreSelf.execute'),('RestoreSelfTime.HitStopSelfPrevious','RestoreSelf.CustomTimeDilation'),
        ('RestoreSelf.then','Off.execute'),('Off.then','RestoreGate.execute'),('Pinned.FrozenHitStopTarget','PinnedValid.Object'),
        ('PinnedValid.ReturnValue','RestoreGate.Condition'),('RestoreGate.then','RestoreOther.execute'),
        ('Pinned.FrozenHitStopTarget','RestoreOther.self'),('RestoreOtherTime.HitStopOtherPrevious','RestoreOther.CustomTimeDilation')])
    for ref,pin,value in [('On','bScopedHitStop','true'),('Off','bScopedHitStop','false'),
                          ('FreezeSelf','CustomTimeDilation',.0001),('FreezeOther','CustomTimeDilation',.0001)]:
        default(P,'EventGraph',m,ref,pin,value)
    owner=build(P,'EventGraph','Approved hit stop explicit actor context',[
        get('Mesh','Mesh'),call('Owner','ActorComponent','GetOwner')], [('Mesh.Mesh','Owner.self')])
    wire(P,'EventGraph',{**m,**owner},[('Owner.ReturnValue',ref+'.self') for ref in ['SelfTime','FreezeSelf','RestoreSelf']])
    # Both global dilation nodes are now unreachable.
    m=build(P,'ResolveSwordContact','Approved pin sword contact actor for hit stop',[put('Pin','HitStopTarget')])
    ns=S.get_nodes_in_graph(P,'ResolveSwordContact',0,'',False)
    stop=next(n.node_id for n in ns if n.node_title.startswith('Start Hit Stop'))
    boss=next(n.node_id for n in ns if n.node_title.startswith('Cast To BP_Boss'))
    before=next(c for c in S.get_connections(P,'ResolveSwordContact') if c.target_node_id==stop and c.target_pin_name=='execute')
    boss_pin=next(p.pin_name for p in S.get_node_details(P,'ResolveSwordContact',boss).output_pins if p.pin_category=='object')
    wire(P,'ResolveSwordContact',m,[(before.source_node_id+'.'+before.source_pin_name,'Pin.execute'),
        (boss+'.'+boss_pin,'Pin.HitStopTarget'),('Pin.then',stop+'.execute')])
    # Incoming damage sets the other participant before playing the existing reaction.
    event=next(n.node_id for n in S.get_nodes_in_graph(P,'EventGraph',0,'',False) if n.node_type=='K2Node_Event' and 'AnyDamage' in n.node_title)
    cs=S.get_connections(P,'EventGraph');before=next(c for c in cs if c.source_node_id==event and c.source_pin_name=='then')
    m=build(P,'EventGraph','Approved pin incoming damage actor',[put('PinIncoming','HitStopTarget')])
    wire(P,'EventGraph',m,[(event+'.then','PinIncoming.execute'),(event+'.DamageCauser','PinIncoming.HitStopTarget'),
        ('PinIncoming.then',before.target_node_id+'.'+before.target_pin_name)])
    compile_save(P)
