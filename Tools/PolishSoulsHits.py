"""Unreal MCP delta edits. Original DS3 structure, Battle-specific dimensions/times."""
import unreal
import vibeue

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
B = '/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'
S = unreal.BlueprintService


def asset(path):
    return unreal.load_object(None, path + '.' + path.rsplit('/', 1)[-1])


def node(ref, kind, **params):
    return {'ref': ref, 'type': kind, 'params': params}


def call(ref, cls, function):
    return node(ref, 'function_call', **{'class': cls, 'function': function})


def get(ref, name):
    return node(ref, 'variable_get', variable=name)


def put(ref, name):
    return node(ref, 'variable_set', variable=name)


def block(path, graph, label, nodes, wires, defaults=()):
    if any(n.node_title == label for n in S.get_nodes_in_graph(path, graph, 0, '', False)):
        return
    r = S.build_graph(path, graph, nodes,
        [{'from_': src, 'to': dst} for src, dst in wires],
        [{'node_ref': ref, 'pin_name': pin, 'value': str(value)} for ref, pin, value in defaults], False, True)
    print('MODIFIED:', path, graph, label, r.success, list(r.errors), list(r.warnings))
    assert r.success, list(r.errors)
    ids = list(r.ref_to_node_id.values())
    S.auto_layout_selected_nodes(path, graph, ids)
    assert S.add_comment_around_nodes(path, graph, label, ids)


def variable(path, name, kind, value):
    if name not in {v.variable_name for v in S.list_variables(path)}:
        pin_type = (unreal.BlueprintEditorLibrary.get_member_variable_type(asset(path),'DodgeMoveDirection')
                    if kind == 'vector' else unreal.BlueprintEditorLibrary.get_basic_type_by_name(kind))
        assert unreal.BlueprintEditorLibrary.add_member_variable(asset(path), name, pin_type)
        print('ADDED:', path, name)
    assert S.set_variable_default_value(path, name, str(value))


def function(path, name, params=()):
    if name not in {g.graph_name for g in S.list_graphs(path)}:
        unreal.BlueprintEditorLibrary.add_function_graph(asset(path), name)
        for param, kind in params:
            assert S.add_function_parameter(path, name, param, kind)
        unreal.BlueprintEditorLibrary.compile_blueprint(asset(path))
        print('ADDED:', path, name)
    return next(n.node_id for n in S.get_nodes_in_graph(path, name, 0, '', False)
                if n.node_type == 'K2Node_FunctionEntry')


def player_hits():
    for name, kind, value in [('bSwordWindowOpen', 'bool', 'false'),
            ('bSwordHasHit', 'bool', 'false'), ('SwordHitUntil', 'real', 0),
            ('SwordActiveDuration', 'real', .18), ('SwordActiveRatio', 'real', .30),
            ('SwordTraceRadius', 'real', 12)]:
        variable(P, name, kind, value)
    assert S.set_variable_default_value(P,'AttackHitRatio','.12')
    for name in ['AttackHitRatio','SwordActiveRatio','SwordTraceRadius']:
        assert S.set_variable_instance_editable(P,name,True)
    for name in ['PrevSwordTip', 'PrevSwordMid']:
        variable(P, name, 'vector', '(X=0,Y=0,Z=0)')
    unreal.BlueprintEditorLibrary.compile_blueprint(asset(P))

    # The existing impact timer opens a window. The former radial graph is kept
    # disconnected for comparison/rollback, rather than replacing the function.
    entry = '7592159A460AD8ED513FDCA90C68EC1C'
    block(P, 'DoAttackHitCheck', 'Souls hit: open blade window, initialize history at current pose',
        [get('Sword', 'Sword'), call('Transform', 'SceneComponent', 'K2_GetComponentToWorld'),
         call('Tip', 'KismetMathLibrary', 'TransformLocation'),
         call('Mid', 'KismetMathLibrary', 'TransformLocation'),
         put('TipHistory', 'PrevSwordTip'), put('MidHistory', 'PrevSwordMid'),
         put('Open', 'bSwordWindowOpen'), get('TimeWindow', 'SwordActiveDuration'),
         call('Now', 'GameplayStatics', 'GetTimeSeconds'), call('Until', 'KismetMathLibrary', 'Add_DoubleDouble'),
         put('Expiry', 'SwordHitUntil')],
        [(entry+'.then', 'TipHistory.execute'), ('Sword.Sword', 'Transform.self'),
         ('Transform.ReturnValue', 'Tip.T'), ('Transform.ReturnValue', 'Mid.T'),
         ('Tip.ReturnValue', 'TipHistory.PrevSwordTip'), ('Mid.ReturnValue', 'MidHistory.PrevSwordMid'),
         ('TipHistory.then', 'MidHistory.execute'), ('MidHistory.then', 'Open.execute'),
         ('Open.then', 'Expiry.execute'), ('Now.ReturnValue', 'Until.A'),
         ('TimeWindow.SwordActiveDuration', 'Until.B'), ('Until.ReturnValue', 'Expiry.SwordHitUntil')],
        [('Tip','Location','0,0,99'), ('Mid','Location','0,0,54'), ('Open','bSwordWindowOpen','true')])

    block(P, 'StartComboStep', 'Souls hit: each combo strike has its own shared hit record',
        [put('ResetHit', 'bSwordHasHit'), put('CloseOld', 'bSwordWindowOpen'),
         get('Ratio','SwordActiveRatio'), call('Window','KismetMathLibrary','Multiply_DoubleDouble'),
         put('Duration','SwordActiveDuration')],
        [('647F83974787827293060DBB9BE53B5B.then','ResetHit.execute'),
         ('ResetHit.then','CloseOld.execute'), ('CloseOld.then','0B46362E4BA64754693BA1A36832A00D.execute'),
         ('AFCFDCB749D0974F8883DD8A18287391.then','Duration.execute'),
         ('2FF4905046BC4E6E45EC51A79F55655E.ReturnValue','Window.A'),
         ('Ratio.SwordActiveRatio','Window.B'), ('Window.ReturnValue','Duration.SwordActiveDuration')],
        [('ResetHit','bSwordHasHit','false'),('CloseOld','bSwordWindowOpen','false')])

    entry = function(P, 'ResolveSwordContact', [('Contact', 'FHitResult')])
    block(P, 'ResolveSwordContact', 'Souls hit: one target once, point damage and actual impact feedback',
        [call('Break', 'GameplayStatics', 'BreakHitResult'),
         node('Boss', 'cast', target_class=B), get('Already', 'bSwordHasHit'), node('Gate','branch'),
         put('Record','bSwordHasHit'), get('Damage','AttackDamage'), call('Self','Actor','GetActorForwardVector'),
         call('Controller','Pawn','GetController'), call('Apply','GameplayStatics','ApplyPointDamage'),
         get('FX','HitImpactFX'), call('Emitter','GameplayStatics','SpawnEmitterAtLocation'),
         call('HitStop',P,'StartHitStop')],
        [(entry+'.then','Boss.execute'),(entry+'.Contact','Break.Hit'),('Break.HitActor','Boss.Object'),
         ('Boss.then','Gate.execute'),('Already.bSwordHasHit','Gate.Condition'),('Gate.else','Record.execute'),
         ('Record.then','Apply.execute'),('Boss.AsBP Boss Crunch','Apply.DamagedActor'),
         ('Damage.AttackDamage','Apply.BaseDamage'),('Self.ReturnValue','Apply.HitFromDirection'),
         (entry+'.Contact','Apply.HitInfo'),('Controller.ReturnValue','Apply.EventInstigator'),
         ('Apply.then','Emitter.execute'),('FX.HitImpactFX','Emitter.EmitterTemplate'),
         ('Break.ImpactPoint','Emitter.Location'),('Emitter.then','HitStop.execute')],
        [('Record','bSwordHasHit','true')])
    # DamageCauser must be the attacking player so the boss can resolve direction.
    # A Self reference node supplies an actor rather than a component.
    block(P, 'ResolveSwordContact', 'Souls hit: preserve damage source',
        [get('MeshSource','Mesh'),call('PlayerSelf','ActorComponent','GetOwner')],
        [('MeshSource.Mesh','PlayerSelf.self'),('PlayerSelf.ReturnValue',next(n.node_id for n in S.get_nodes_in_graph(P,'ResolveSwordContact',0,'Apply Point Damage',False))+'.DamageCauser')])
    cast=next(n.node_id for n in S.get_nodes_in_graph(P,'ResolveSwordContact',0,'Cast To BP_Boss',False))
    break_hit=next(n.node_id for n in S.get_nodes_in_graph(P,'ResolveSwordContact',0,'Break Hit Result',False))
    block(P,'ResolveSwordContact','Souls hit: first wall contact closes this strike; no traces through obstruction',
        [get('Open','bSwordWindowOpen'),node('OpenGate','branch'),
         call('Solid','KismetSystemLibrary','IsValid'),node('Wall','branch'),put('Close','bSwordWindowOpen')],
        [(entry+'.then','OpenGate.execute'),('Open.bSwordWindowOpen','OpenGate.Condition'),
         ('OpenGate.then',cast+'.execute'),(cast+'.CastFailed','Wall.execute'),
         (break_hit+'.HitActor','Solid.Object'),('Solid.ReturnValue','Wall.Condition'),('Wall.then','Close.execute')],
        [('Close','bSwordWindowOpen','false')])

    entry = function(P, 'TraceSwordWindow')
    nodes=[get('Open','bSwordWindowOpen'), get('State','ActionState'),
        call('Attacking','KismetMathLibrary','EqualEqual_ByteByte'),
        call('Now','GameplayStatics','GetTimeSeconds'), get('Until','SwordHitUntil'),
        call('InTime','KismetMathLibrary','LessEqual_DoubleDouble'),
        call('Both','KismetMathLibrary','BooleanAND'),call('All','KismetMathLibrary','BooleanAND'),
        node('Gate','branch'), get('Sword','Sword'), call('Transform','SceneComponent','K2_GetComponentToWorld'),
        call('Base','KismetMathLibrary','TransformLocation'),call('Tip','KismetMathLibrary','TransformLocation'),
        call('Mid','KismetMathLibrary','TransformLocation'),get('PrevTip','PrevSwordTip'),get('PrevMid','PrevSwordMid'),
        get('Radius','SwordTraceRadius'),put('TipHistory','PrevSwordTip'),put('MidHistory','PrevSwordMid'),
        put('Close','bSwordWindowOpen')]
    wires=[(entry+'.then','Gate.execute'),('Open.bSwordWindowOpen','Both.A'),('State.ActionState','Attacking.A'),
        ('Attacking.ReturnValue','Both.B'),('Now.ReturnValue','InTime.A'),('Until.SwordHitUntil','InTime.B'),
        ('Both.ReturnValue','All.A'),('InTime.ReturnValue','All.B'),('All.ReturnValue','Gate.Condition'),
        ('Gate.else','Close.execute'),('Sword.Sword','Transform.self'),
        *[('Transform.ReturnValue',x+'.T') for x in ['Base','Tip','Mid']],
        ('Tip.ReturnValue','TipHistory.PrevSwordTip'),('Mid.ReturnValue','MidHistory.PrevSwordMid'),
        ('TipHistory.then','MidHistory.execute')]
    defs=[('Attacking','B','4'),('Base','Location','0,0,8'),('Tip','Location','0,0,99'),
          ('Mid','Location','0,0,54'),('Close','bSwordWindowOpen','false')]
    previous='Gate.then'
    for i,(start,end) in enumerate([('Base.ReturnValue','Tip.ReturnValue'),
                ('PrevTip.PrevSwordTip','Tip.ReturnValue'),('PrevMid.PrevSwordMid','Mid.ReturnValue')]):
        trace='Trace'+str(i); resolve='Resolve'+str(i)
        nodes += [call(trace,'KismetSystemLibrary','SphereTraceSingle'),call(resolve,P,'ResolveSwordContact')]
        wires += [(previous,trace+'.execute'),(start,trace+'.Start'),(end,trace+'.End'),
                  ('Radius.SwordTraceRadius',trace+'.Radius'),(trace+'.then',resolve+'.execute'),
                  (trace+'.OutHit',resolve+'.Contact')]
        defs += [(trace,'TraceChannel','TraceTypeQuery1'),(trace,'DrawDebugType','None')]
        previous=resolve+'.then'
    wires.append((previous,'TipHistory.execute'))
    block(P,'TraceSwordWindow','Souls hit: blade capsule plus temporal tip and midpoint sweeps',nodes,wires,defs)
    # Prepend a call; existing movement/camera Tick graph stays intact.
    block(P,'EventGraph','Souls hit: update blade collision while active',
        [call('Trace',P,'TraceSwordWindow')],
        [('B009E31544426A949F9522890F075C27.then','Trace.execute'),
         ('Trace.then','FE7BA48340435E31AD9C849E367AEBE6.execute')])


def boss_traces():
    # Keep the two existing anatomical sweeps and action-specific time windows.
    # Visibility channel makes world obstruction and physical hurtboxes part of
    # the SAME sweep, rather than a pawn-only query passing through walls.
    for graph, old_ids in [('EventGraph',['E8D0D3634033F13FA29285903436385B','EAA8B69540ADEF7C92BAE69549C18D6B']),
                          ('TraceOtherHand',['CD110F4345D0C4A44D9788BD97EE887C','DD79EB7E4936BA30F20D46B1A703E75A'])]:
        for old in old_ids:
            label='Souls hit: mesh and world sweep '+old
            if any(n.node_title==label for n in S.get_nodes_in_graph(B,graph,0,'',False)): continue
            connections=list(S.get_connections(B,graph))
            wires=[]
            for c in connections:
                if c.target_node_id==old and c.target_pin_name in ['execute','Start','End','Radius']:
                    wires.append((c.source_node_id+'.'+c.source_pin_name,'Trace.'+c.target_pin_name))
                elif c.source_node_id==old:
                    wires.append(('Trace.'+c.source_pin_name,c.target_node_id+'.'+c.target_pin_name))
            block(B,graph,label,[call('Trace','KismetSystemLibrary','SphereTraceSingle')],wires,
                  [('Trace','TraceChannel','TraceTypeQuery1'),('Trace','DrawDebugType','None')])
            S.disconnect_pin(B,graph,old,'execute')
            # Output pins allow multiple consumers; explicitly remove legacy
            # sources so the new trace is the only driver of hit resolution.
            for c in connections:
                if c.source_node_id==old:
                    S.disconnect_pin(B,graph,old,c.source_pin_name)
            print('MODIFIED:',B,graph,'disconnected legacy pawn-only trace',old)
    # Confirm invulnerability BEFORE guard break and consuming a hit record.
    block(B,'EventGraph','Souls hit: invulnerable contact does not apply damage or guard break',
        [node('Vulnerable','branch')],
        [('E51D583D4E8434B85B391AB4A94F9329.then','Vulnerable.execute'),
         ('7CB2112F488515BC04F4B884CCC3E7F6.bInvincible','Vulnerable.Condition'),
         ('Vulnerable.else','E404AAF04675F45146782ABBFCF82A68.execute')])
    block(B,'TraceOtherHand','Souls hit: secondary hand shares the successful hit record',
        [node('Vulnerable','branch')],
        [('C3EB4D294DA141F1981EEAACBD2CBB7B.then','Vulnerable.execute'),
         ('C2C2FB2944C85F327840BA9853434B34.bInvincible','Vulnerable.Condition'),
         ('Vulnerable.else','BFF531C9487C9D3A735EA2A5080FD869.execute')])
    assert S.set_node_pin_value(B,'TraceOtherHand','BE54BC234079E2C9F3109E8E59EBCF08','bHasHitThisAttack','true')


def collision():
    # Set only the relevant channel. Preserve Pawn blocking for locomotion and
    # Camera blocking for camera collision; update placed instances too.
    ss=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for path in [P,B]:
        for h in ss.k2_gather_subobject_data_for_blueprint(asset(path)):
            obj=unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(
                unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
            if isinstance(obj,unreal.CapsuleComponent):
                obj.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
                print('MODIFIED:',path,obj.get_name(),'movement capsule ignores hit trace')
            elif isinstance(obj,unreal.SkeletalMeshComponent):
                obj.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
                obj.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_BLOCK)
                obj.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
                print('MODIFIED:',path,obj.get_name(),'physical hurtbox query')
        unreal.BlueprintEditorLibrary.compile_blueprint(asset(path))
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if any(x in a.get_class().get_name() for x in ['BP_Player_Combat','BP_Boss_Crunch']):
            a.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
            mesh=a.get_component_by_class(unreal.SkeletalMeshComponent)
            mesh.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
            mesh.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_BLOCK)
            mesh.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
            print('MODIFIED:',a.get_path_name(),'placed hurtbox channel updated')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    for path in [P,B]:
        start=next(n.node_id for n in S.get_nodes_in_graph(path,'EventGraph',0,'',False)
                   if n.node_type=='K2Node_Event' and 'BeginPlay' in n.node_title)
        outgoing=next(c for c in S.get_connections(path,'EventGraph') if c.source_node_id==start and c.source_pin_name=='then')
        block(path,'EventGraph','Souls hit: initialize hurtbox channel on every spawned instance',
            [get('Capsule','CapsuleComponent'),get('Mesh','Mesh'),
             call('CapsuleChannel','PrimitiveComponent','SetCollisionResponseToChannel'),
             call('MeshChannel','PrimitiveComponent','SetCollisionResponseToChannel')],
            [(start+'.then','CapsuleChannel.execute'),('Capsule.CapsuleComponent','CapsuleChannel.self'),
             ('CapsuleChannel.then','MeshChannel.execute'),('Mesh.Mesh','MeshChannel.self'),
             ('MeshChannel.then',outgoing.target_node_id+'.'+outgoing.target_pin_name)],
            [('CapsuleChannel','Channel','ECC_Visibility'),('CapsuleChannel','NewResponse','ECR_Ignore'),
             ('MeshChannel','Channel','ECC_Visibility'),('MeshChannel','NewResponse','ECR_Block')])


def boss_reactions():
    variable(B,'LastHitReactionDirection','real',0)
    entry=function(B,'PlayDirectionalHitReaction',[('Source','AActor')])
    # Source position in local space: +X front, +Y right. No pushback or
    # HFSM transition is introduced for this cosmetic reaction.
    base='/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/HitReact_'
    nodes=[call('SourceLoc','Actor','K2_GetActorLocation'),call('Transform','Actor','GetTransform'),
        call('Local','KismetMathLibrary','InverseTransformLocation'),call('Break','KismetMathLibrary','BreakVector'),
        call('Angle','KismetMathLibrary','DegAtan2'),put('Record','LastHitReactionDirection'),
        call('Abs','KismetMathLibrary','Abs'),call('Back','KismetMathLibrary','Greater_DoubleDouble'),
        call('Left','KismetMathLibrary','Less_DoubleDouble'),call('Right','KismetMathLibrary','Greater_DoubleDouble'),
        call('PickLeft','KismetMathLibrary','SelectObject'),call('PickRight','KismetMathLibrary','SelectObject'),
        call('PickBack','KismetMathLibrary','SelectObject'),node('Anim','cast',target_class='AnimSequence'),
        get('Mesh','Mesh'),call('Instance','SkeletalMeshComponent','GetAnimInstance'),
        call('Play','AnimInstance','PlaySlotAnimationAsDynamicMontage')]
    wires=[(entry+'.then','Record.execute'),(entry+'.Source','SourceLoc.self'),
        ('Transform.ReturnValue','Local.T'),('SourceLoc.ReturnValue','Local.Location'),('Local.ReturnValue','Break.InVec'),
        ('Break.Y','Angle.Y'),('Break.X','Angle.X'),('Angle.ReturnValue','Record.LastHitReactionDirection'),
        ('Angle.ReturnValue','Abs.A'),('Abs.ReturnValue','Back.A'),('Angle.ReturnValue','Left.A'),('Angle.ReturnValue','Right.A'),
        ('Left.ReturnValue','PickLeft.bSelectA'),('Right.ReturnValue','PickRight.bSelectA'),('Back.ReturnValue','PickBack.bSelectA'),
        ('PickLeft.ReturnValue','PickRight.B'),('PickRight.ReturnValue','PickBack.B'),
        ('PickBack.ReturnValue','Anim.Object'),('Record.then','Anim.execute'),('Anim.then','Play.execute'),
        ('Anim.As애님 시퀀스','Play.Asset'),('Mesh.Mesh','Instance.self'),('Instance.ReturnValue','Play.self')]
    defs=[('Back','B',135),('Left','B',-45),('Right','B',45),
        ('PickLeft','A',base+'Left.HitReact_Left'),('PickLeft','B',base+'Front.HitReact_Front'),
        ('PickRight','A',base+'Right.HitReact_Right'),('PickBack','A',base+'Back.HitReact_Back'),
        ('Play','SlotNodeName','UpperBody'),('Play','BlendInTime','.08'),('Play','BlendOutTime','.2'),('Play','InPlayRate','1.3')]
    block(B,'PlayDirectionalHitReaction','Souls hit: four-direction cosmetic reaction, no attack interruption',nodes,wires,defs)
    record=next(n.node_id for n in S.get_nodes_in_graph(B,'PlayDirectionalHitReaction',0,'Set LastHitReactionDirection',False))
    block(B,'PlayDirectionalHitReaction','Souls hit: no direction calculation for missing damage source',
        [call('Valid','KismetSystemLibrary','IsValid'),node('Gate','branch')],
        [(entry+'.then','Gate.execute'),(entry+'.Source','Valid.Object'),
         ('Valid.ReturnValue','Gate.Condition'),('Gate.then',record+'.execute')])
    block(B,'EventGraph','Souls hit: directional reaction when ready only',
        [call('React',B,'PlayDirectionalHitReaction')],
        [('747C5ADC42620ACCF683198A210DF3C1.then','React.execute'),
         ('14FB9A0749365DB9CE257C8B05EC240E.DamageCauser','React.Source')])


def damage_levels():
    definition='/Game/BossArena/Boss/AI/BP_BossActionDefinition'
    paths=[definition]+[x.get_path_name().split('.')[0] for x in unreal.get_default_object(asset(B).generated_class()).get_editor_property('Actions')]
    for path in paths:
        obj=asset(path);name=path.rsplit('/',1)[-1]
        backup='/Game/BossArena/Backup/'+name+'_PreSoulsHit_20260929'
        if not unreal.EditorAssetLibrary.does_asset_exist(backup):
            copy=unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(backup.rsplit('/',1)[-1],backup.rsplit('/',1)[0],obj)
            assert copy;unreal.EditorAssetLibrary.save_loaded_asset(copy,False)
            print('CREATED:',backup)
    variable(definition,'HitReactionLevel','int',0)
    assert S.set_variable_instance_editable(definition,'HitReactionLevel',True)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset(definition))
    for path in paths[1:]:
        obj=asset(path)
        level=1 if any(x in path for x in ['Uppercut','GuardBreak','Dash']) else 0
        obj.set_editor_property('HitReactionLevel',level)
        unreal.EditorAssetLibrary.save_loaded_asset(obj,False)
        print('MODIFIED:',path,'HitReactionLevel',level)
    unreal.EditorAssetLibrary.save_loaded_asset(asset(definition),False)
    variable(P,'bHasAttackReactionProfile','bool','false')
    unreal.BlueprintEditorLibrary.compile_blueprint(asset(P))
    block(P,'EventGraph','Souls hit: resolve damage level from the committed attack profile',
        [put('ResetProfile','bHasAttackReactionProfile'),put('Profile','bHasAttackReactionProfile'),
         node('Level','member_get',**{'class':definition,'member':'HitReactionLevel'}),
         call('Heavy','KismetMathLibrary','GreaterEqual_IntInt')],
        [('CB56CC724FF43312938AD3B563AD57F3.then','ResetProfile.execute'),
         ('ResetProfile.then','EA4F1FA74B8C181503F07CAB841BB6C3.execute'),
         ('5CEF9EF74E09CE8C383731B08A14749C.then','Profile.execute'),
         ('Profile.then','15AAE5974423E582723B6AA9472DCB1D.execute'),
         ('1792A8FD40ABF0FA090B6DB34C53C11F.ActiveAction','Level.self'),
         ('Level.HitReactionLevel','Heavy.A'),
         ('Heavy.ReturnValue','15AAE5974423E582723B6AA9472DCB1D.bPendingHeavyAction')],
        [('ResetProfile','bHasAttackReactionProfile','false'),('Profile','bHasAttackReactionProfile','true'),('Heavy','B',1)])
    block(P,'PlayShieldReaction','Souls hit: HP magnitude fallback only for damage without an attack profile',
        [get('Profile','bHasAttackReactionProfile'),call('NoProfile','KismetMathLibrary','Not_PreBool'),
         call('Fallback','KismetMathLibrary','BooleanAND')],
        [('Profile.bHasAttackReactionProfile','NoProfile.A'),('NoProfile.ReturnValue','Fallback.A'),
         ('B7207C6F480A319C1625C5970F82D91F.ReturnValue','Fallback.B'),
         ('Fallback.ReturnValue','964BC516421BF5BB51211C8D0BD3027F.A')])
    entry=function(B,'RequestCombatAction',[('ActionIndex','int')])
    block(B,'RequestCombatAction','Designer preview: request an action only while ready and index valid',
        [get('State','BossState'),call('Ready','BlueprintGameplayTagLibrary','MatchesTag'),
         get('Actions','Actions'),call('Valid','KismetArrayLibrary','Array_IsValidIndex'),
         call('Both','KismetMathLibrary','BooleanAND'),node('Gate','branch'),
         put('Select','SelectedSlot'),call('Begin',B,'BeginCombatAction')],
        [(entry+'.then','Gate.execute'),('State.BossState','Ready.TagOne'),
         ('Actions.Actions','Valid.TargetArray'),(entry+'.ActionIndex','Valid.IndexToTest'),
         ('Ready.ReturnValue','Both.A'),('Valid.ReturnValue','Both.B'),('Both.ReturnValue','Gate.Condition'),
         ('Gate.then','Select.execute'),(entry+'.ActionIndex','Select.SelectedSlot'),('Select.then','Begin.execute')],
        [('Ready','TagTwo','(TagName="Boss.Combat.Ready")'),('Ready','bExactMatch','true')])
    chosen=next(n.node_id for n in S.get_nodes_in_graph(B,'RequestCombatAction',0,'Set SelectedSlot',False))
    begin=next(n.node_id for n in S.get_nodes_in_graph(B,'RequestCombatAction',0,'Begin Combat Action',False))
    block(B,'RequestCombatAction','Designer preview: bind the selected action definition before execution',
        [get('Definitions','Actions'),call('GetChosen','KismetArrayLibrary','Array_Get'),put('Active','ActiveAction')],
        [('Definitions.Actions','GetChosen.TargetArray'),(entry+'.ActionIndex','GetChosen.Index'),
         ('GetChosen.Item','Active.ActiveAction'),(chosen+'.then','Active.execute'),('Active.then',begin+'.execute')])


def save():
    for path in [P,B]:
        bp=asset(path)
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        assert bp.get_editor_property('status')==unreal.BlueprintStatus.BS_UP_TO_DATE
        unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
        print('SAVED:',path)


def apply(phase):
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset','IsPIERunning')
    {'player':player_hits,'boss':boss_traces,'collision':collision,'reaction':boss_reactions,'levels':damage_levels,'save':save}[phase]()
