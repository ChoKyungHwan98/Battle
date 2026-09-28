"""Run phases from Unreal MCP. Preserves source clips and pre-change backups."""
import unreal
import vibeue
import json

P = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
A = '/Game/BossArena/Player/Animation/ABP_Player_Combat'
B = '/Game/BossArena/Player/Animation/SwordShield'
SKELETON = '/Game/Characters/Mannequins/Meshes/SK_Mannequin'
BP = unreal.BlueprintService
AG = unreal.AnimGraphService
AS = unreal.AnimSequenceService
AM = unreal.AnimMontageService


def seq(name, part=1):
    return B + '/Sequences/Q_SwordShieldAnimsetPro_part%d_%s' % (part, name)


def save(path):
    assert unreal.EditorAssetLibrary.save_asset(path), path
    print('MODIFIED:', path)


def props(asset, values):
    obj = unreal.load_asset(asset)
    assert vibeue.exec_tool('editor_toolset.toolsets.object.ObjectTools', 'set_properties',
                           {'instance': {'refPath': obj.get_path_name()}, 'values': json.dumps(values)})


def pin(path, graph, node, name, value):
    assert BP.set_node_pin_value(path, graph, node, name, str(value)), (graph, node, name)


def wire(path, graph, source, source_pin, target, target_pin):
    assert BP.connect_nodes(path, graph, source, source_pin, target, target_pin), (source_pin, target_pin)


def graph(path, name, nodes, wires, defaults=()):
    out = BP.build_graph(path, name, nodes,
                         [{'from_': x, 'to': y} for x, y in wires],
                         [{'node_ref': n, 'pin_name': p, 'value': str(v)} for n, p, v in defaults],
                         True, False)
    print('GRAPH', name, out.success, out.errors, out.warnings)
    assert out.success, str(out.errors)
    return dict(out.ref_to_node_id)


def node(ref, kind, **params):
    return {'ref': ref, 'type': kind, 'params': params}


def call(ref, cls, function):
    return node(ref, 'function_call', **{'class': cls, 'function': function})


def variable(path, name, type_name, default=None):
    if name not in [v.variable_name for v in BP.list_variables(path)]:
        obj = unreal.load_asset(path)
        if type_name=='Actor':
            assert unreal.BlueprintEditorLibrary.add_member_variable(obj,name,
                unreal.BlueprintEditorLibrary.get_member_variable_type(obj,'LockOnTarget'))
        else:
            vibeue.exec_tool('editor_toolset.toolsets.blueprint.BlueprintTools','add_variable',
                            {'blueprint': {'refPath': obj.get_path_name()}, 'name': name, 'type_name': type_name})
            assert name in [v.variable_name for v in BP.list_variables(path)], name
        print('ADDED:', name)
        unreal.BlueprintEditorLibrary.compile_blueprint(obj)
    if default is not None:
        assert BP.set_variable_default_value(path, name, str(default))


def assets():
    # In-place animation: the gameplay capsule owns translation, preventing double travel.
    for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(B+'/Sequences', False):
        obj = data.get_asset()
        obj.set_editor_property('force_root_lock', True)
        assert AS.set_root_motion_root_lock(str(data.package_name), 'AnimFirstFrame')
        obj.set_editor_property('enable_root_motion', False)
        save(str(data.package_name))

    # Shield block contains a transient impact. Bake a stable raised-shield pose for holding guard.
    guard = B+'/Sequences/AS_Shield_GuardHold'
    if not unreal.EditorAssetLibrary.does_asset_exist(guard):
        pose = AS.get_pose_at_time(seq('Sword_Block_Right_Shield'), .10, False)
        tracks = []
        for bone in pose:
            t = bone.transform
            keys = [unreal.AnimKeyframe(frame=i, time=i/30, position=t.translation,
                                       rotation=t.rotation, scale=t.scale3d) for i in range(31)]
            tracks.append(unreal.BoneTrackData(bone_name=bone.bone_name, keyframes=keys))
        guard = AS.create_anim_sequence(SKELETON, 'AS_Shield_GuardHold', B+'/Sequences', 1, 30, tracks)
        assert guard
        save(guard)

    bs_path = B+'/BS_SwordShield_8Dir'
    if not unreal.EditorAssetLibrary.does_asset_exist(bs_path):
        f = unreal.BlendSpaceFactoryNew()
        f.set_editor_property('target_skeleton', unreal.load_asset(SKELETON))
        f.set_editor_property('preview_skeletal_mesh', unreal.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'))
        assert unreal.AssetToolsHelpers.get_asset_tools().create_asset('BS_SwordShield_8Dir', B, unreal.BlendSpace, f)
    params = [{'displayName':'Direction','min':-180,'max':180,'gridNum':8,'bSnapToGrid':True,'bWrapInput':True},
              {'displayName':'Speed','min':0,'max':650,'gridNum':13,'bSnapToGrid':False,'bWrapInput':False},
              {'displayName':'None','min':0,'max':100,'gridNum':4,'bSnapToGrid':False,'bWrapInput':False}]
    walks = ['Sword_WalkBwd','Sword_StrafeLeft135','Sword_StrafeLeft','Sword_StrafeLeft45','Sword_WalkFwd','Sword_StrafeRight45','Sword_StrafeRight','Sword_StrafeRight135','Sword_WalkBwd']
    runs = ['Sword_RunBwd','Sword_RunStrafeLeft135','Sword_StrafeRunLeft','Sword_RunStrafeLeft45','Sword_RunFwd','Sword_RunStrafeRight45','Sword_StrafeRunRight','Sword_RunStrafeRight135','Sword_RunBwd']
    samples = []
    for speed, names in [(0, ['Sword_Idle']*9), (220, walks), (450, runs), (650, runs)]:
        for direction, name in zip(range(-180,181,45), names):
            part = 5 if '45' in name or '135' in name else 1
            obj = unreal.load_asset(seq(name,part))
            samples.append({'animation': {'refPath':obj.get_path_name()},
                            'sampleValue':{'x':direction,'y':speed,'z':0},
                            'rateScale':1.25 if speed==650 else 1,
                            'bMirror':False,'bUseSingleFrameForBlending':False})
    props(bs_path, {'BlendParameters':params,'SampleData':samples,
                    'TargetWeightInterpolationSpeedPerSec':8.0,'bInterpolateUsingGrid':False})
    save(bs_path)

    for name, source, slot, end, rate in [
        *[(f'AM_Sword_Attack_{i+1}',seq(n,2),'DefaultSlot',1.10,1.0) for i,n in enumerate(['Sword_Attack_R','Sword_Attack_RL','Sword_Attack_RLL','Sword_Attack_RLLR'])],
        ('AM_Shield_BlockImpact',seq('Sword_Block_Right_Shield'),'AttackUpperBody',.58,1.25),
        ('AM_Shield_HitFront',seq('Sword_Shield_Hit_C_1'),'DefaultSlot',.75,1.25),
        ('AM_Shield_HitLeft',seq('Sword_Shield_Hit_L_1'),'DefaultSlot',.75,1.25),
        ('AM_Shield_HitRight',seq('Sword_Shield_Hit_R_2'),'DefaultSlot',.75,1.25),
        ('AM_Shield_Knockdown',seq('KnockdownFront1'),'DefaultSlot',4.266667,1.15),
    ]:
        path = B+'/Montages/'+name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            assert AM.create_montage_from_animation(source,B+'/Montages',name)
            print('CREATED:',path)
        assert AM.set_slot_name(path,0,slot)
        assert AM.set_segment_end_position(path,0,0,end)
        assert AM.set_segment_play_rate(path,0,0,rate)
        assert AM.set_blend_in(path,.055)
        assert AM.set_blend_out(path,.10)
        save(path)
    print('ASSETS READY')


def inputs():
    # Edit mappings in place: retain all triggers/modifiers and gamepad bindings.
    for path in ['/Game/BossArena/Player/Input/IMC_Player_Combat','/Game/Input/IMC_Default']:
        obj = unreal.load_asset(path)
        data = vibeue.exec_tool('editor_toolset.toolsets.object.ObjectTools','get_properties',
                               {'instance':{'refPath':obj.get_path_name()},'properties':['DefaultKeyMappings']})
        mappings = data['DefaultKeyMappings']['mappings']
        for i in range(len(mappings)):
            m = mappings[i]
            action = m['action']['refPath'].rsplit('.',1)[1]
            key_text = m['key']
            target = None
            if action in ['IA_Dodge','IA_Sprint'] and 'LeftShift' in key_text: target='SpaceBar'
            if action=='IA_Jump' and 'SpaceBar' in key_text: target='F'
            if target:
                m['key']=target; mappings[i]=m
                print('MODIFIED mapping:',action,target)
        props(path,{'DefaultKeyMappings':data['DefaultKeyMappings']}); save(path)
    # Also reset sprint on a short release (Hold trigger emits Canceled below threshold).
    wire(P,'EventGraph','C8A98E9A4E8C8A3FEFA71D9DDA3FAEE0','Canceled','E2A6631846202CB9D664EC8FFC4C0B3A','execute')
    print('INPUT VERIFIED',unreal.InputService.get_mapping_context_info('/Game/BossArena/Player/Input/IMC_Player_Combat'),unreal.InputService.get_mapping_context_info('/Game/Input/IMC_Default'))


def animation():
    assert AG.set_blend_space_asset(A,'AnimGraph','0E38F389478678412D8ADD93DC2BFE2A',B+'/BS_SwordShield_8Dir')
    # The same locomotion pose supplies the state machine in free and locked modes.
    wire(A,'AnimGraph','95B8FD0A490F538841BA3D98FCC7DEB1','Pose','B3066FD5430359B70B4DD0B780185B55','Pose')
    assert AG.set_sequence_player_asset(A,'AnimGraph','7CDEF01444683654D39EAC8245CD90E0',seq('Sword_Idle'))
    if not any(c.target_node_id=='0E38F389478678412D8ADD93DC2BFE2A' and c.target_pin_name=='Y'
               for c in BP.get_connections(A,'AnimGraph')):
        graph(A,'AnimGraph',[node('SwordSpeed','variable_get',variable='GroundSpeed')],
              [('SwordSpeed.GroundSpeed','0E38F389478678412D8ADD93DC2BFE2A.Y')])
    for state, name, loop in [('Jump','Sword_Jump_Platformer_Start',False),('Fall Loop','Sword_Jump_Platformer_Fall',True),('Land','Sword_Jump_Platformer_Land',False)]:
        assert AG.set_state_animation(A,'Main States',state,seq(name,4),loop,1.15)
    variable(A,'bShieldGuard','bool','false')
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(A))
    ids = graph(A,'EventGraph',[
        node('GuardState','member_get',member='ActionState',**{'class':P}),
        call('GuardEqual','KismetMathLibrary','EqualEqual_ByteByte'),
        node('GuardSet','variable_set',variable='bShieldGuard')],
        [('E98C6F9E4AF8E0F2217AC8A60347899C.AsBP Player Combat','GuardState.self'),
         ('GuardState.ActionState','GuardEqual.A'),('GuardEqual.ReturnValue','GuardSet.bShieldGuard'),
         ('61CB6B34440B00C9CB01ADBC4DBA19C2.then','GuardSet.execute')], [('GuardEqual','B',3)])
    guard = AG.add_sequence_player(A,'AnimGraph',B+'/Sequences/AS_Shield_GuardHold')
    blend = AG.add_blend_by_bool(A,'AnimGraph')
    assert guard and blend
    flag = graph(A,'AnimGraph',[node('GuardFlag','variable_get',variable='bShieldGuard')],[])
    wire(A,'AnimGraph',flag['GuardFlag'],'bShieldGuard',blend,'bActiveValue')
    wire(A,'AnimGraph',guard,'Pose',blend,'BlendPose_0')
    wire(A,'AnimGraph','D316F97045C64E2BDF5E5080CC672A95','Pose',blend,'BlendPose_1')
    wire(A,'AnimGraph',blend,'Pose','11ECDE3A4135F431D7A0CCB1A9142CE5','Source')
    pin(A,'AnimGraph',blend,'BlendTime_0',.08)
    pin(A,'AnimGraph',blend,'BlendTime_1',.10)
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(A))
    save(A)


def player():
    obj = unreal.load_asset(P)
    cdo = unreal.get_default_object(obj.generated_class())
    cdo.set_editor_property('AttackMontages',[unreal.load_asset(B+f'/Montages/AM_Sword_Attack_{i}') for i in range(1,5)])
    for key,value in {'AttackPlayRate':1.1,'ComboWindowRatio':.68,'AttackHitRatio':.36,
                      'AttackHitRange':150.0,'AttackHitRadius':95.0,'DodgeDistance':320.0,
                      'DodgePlayRate':1.15,'DodgeBurstRate':1.15,'DodgeMoveWindow':.82,
                      'DodgeRecoveryRatio':.95,'DodgeCooldown':.035,'IFrameDuration':.30,
                      'LateDodgeGrace':.025}.items():
        cdo.set_editor_property(key,value)
    # Select the existing roll branch for both lock modes.
    BP.disconnect_pin(P,'TryEnterDodge','5878EE1B49FC441BDB209C94161049D6','bSelectA')
    pin(P,'TryEnterDodge','5878EE1B49FC441BDB209C94161049D6','bSelectA','false')
    BP.disconnect_pin(P,'TryEnterDodge','4BF321554758630CB1A7C39E1F061951','bPickA')
    pin(P,'TryEnterDodge','4BF321554758630CB1A7C39E1F061951','bPickA','true')
    # Guard is now an AnimGraph pose; the old looping block montage would conflict with impacts.
    wire(P,'TryEnterBlock','74C435BC4459FCBB6E75C1BF3ED3898A','then','1B7D9968483926A082F4DAAE474F7AB0','execute')
    # Jump only begins from locomotion. It cannot bypass attack / roll / hit recovery.
    BP.disconnect_pin(P,'EventGraph','62FBF30B49A577AB1100518235AB87C3','Started')
    ids=graph(P,'EventGraph',[node('JumpState','variable_get',variable='ActionState'),
        call('JumpReady','KismetMathLibrary','EqualEqual_ByteByte'),node('JumpGate','branch')],
        [('62FBF30B49A577AB1100518235AB87C3.Started','JumpGate.execute'),
         ('JumpState.ActionState','JumpReady.A'),('JumpReady.ReturnValue','JumpGate.Condition'),
         ('JumpGate.then','232527674F4380C1B936B8B8D6E4853A.execute')],[('JumpReady','B',5)])
    unreal.BlueprintEditorLibrary.compile_blueprint(obj)
    save(P)


def reactions():
    for name, typ, default in [('PendingDamageSource','Actor',None),('ReactionDirection','float',0),
                               ('bKnockedDown','bool','false'),('KnockdownDamageThreshold','float',150),
                               ('bPendingHeavyAction','bool','false')]:
        variable(P,name,typ,default)
    # Save the damage source; decide heavy attacks from the boss's action data when valid.
    event = 'EventGraph'
    entry='D4C71F6F4DF514BC95A16EBCD8BA9B7B'
    damage='6D0EB5894D4E708AA34DDCB7161DBE30'
    BP.disconnect_pin(P,event,entry,'else')
    ids=graph(P,event,[
        node('DownNow','variable_get',variable='bKnockedDown'),node('IgnoreDown','branch'),
        node('StoreSource','variable_set',variable='PendingDamageSource'),
        node('ClearHeavy','variable_set',variable='bPendingHeavyAction'),
        node('BossSource','cast',target_class='/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'),
        node('BossAction','member_get',member='ActiveAction',**{'class':'/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch'}),
        call('ValidAction','KismetSystemLibrary','IsValid'),node('CheckAction','branch'),
        node('BossId','member_get',member='ActionId',**{'class':'/Game/BossArena/Boss/AI/BP_BossActionDefinition'}),
        call('IsUppercut','KismetMathLibrary','EqualEqual_IntInt'),
        call('IsSweep','KismetMathLibrary','EqualEqual_IntInt'),
        call('IsGuardBreak','KismetMathLibrary','EqualEqual_IntInt'),
        call('HeavyA','KismetMathLibrary','BooleanOR'),call('HeavyB','KismetMathLibrary','BooleanOR'),
        node('StoreHeavy','variable_set',variable='bPendingHeavyAction')],
        [(entry+'.else','IgnoreDown.execute'),('DownNow.bKnockedDown','IgnoreDown.Condition'),
         ('IgnoreDown.else','StoreSource.execute'),(damage+'.DamageCauser','StoreSource.PendingDamageSource'),
         ('StoreSource.then','ClearHeavy.execute'),('ClearHeavy.then','BossSource.execute'),
         (damage+'.DamageCauser','BossSource.Object'),('BossSource.AsBP Boss Crunch','BossAction.self'),
         ('BossAction.ActiveAction','ValidAction.Object'),('ValidAction.ReturnValue','CheckAction.Condition'),
         ('BossSource.then','CheckAction.execute'),('BossAction.ActiveAction','BossId.self'),
         ('BossId.ActionId','IsUppercut.A'),('BossId.ActionId','IsSweep.A'),('BossId.ActionId','IsGuardBreak.A'),
         ('IsUppercut.ReturnValue','HeavyA.A'),('IsSweep.ReturnValue','HeavyA.B'),
         ('HeavyA.ReturnValue','HeavyB.A'),('IsGuardBreak.ReturnValue','HeavyB.B'),
         ('HeavyB.ReturnValue','StoreHeavy.bPendingHeavyAction'),('CheckAction.then','StoreHeavy.execute'),
         ('StoreHeavy.then','8EDD21BD4073D0A3E4FAB68BEDDC1DEF.execute'),
         ('BossSource.CastFailed','8EDD21BD4073D0A3E4FAB68BEDDC1DEF.execute'),
         ('CheckAction.else','8EDD21BD4073D0A3E4FAB68BEDDC1DEF.execute')],
        [('ClearHeavy','bPendingHeavyAction','false'),('IsUppercut','B',2),('IsSweep','B',3),('IsGuardBreak','B',5)])

    name='PlayShieldReaction'
    assert BP.create_function_graph(P,name)
    entry_id=next(n.node_id for n in BP.get_nodes_in_graph(P,name,0,'',False) if n.node_type=='K2Node_FunctionEntry')
    nodes=[node('State','variable_get',variable='ActionState'),call('Guard','KismetMathLibrary','EqualEqual_ByteByte'),
           node('GuardGate','branch'),call('BlockImpact','Character','PlayAnimMontage'),
           node('ResetDir','variable_set',variable='ReactionDirection'),
           node('Source','validated_get',variable='PendingDamageSource'),
           call('MyLoc','Actor','K2_GetActorLocation'),call('SourceLoc','Actor','K2_GetActorLocation'),
           call('LookAt','KismetMathLibrary','FindLookAtRotation'),call('MyRot','Actor','K2_GetActorRotation'),
           call('Delta','KismetMathLibrary','NormalizedDeltaRotator'),call('BreakRot','KismetMathLibrary','BreakRotator'),
           node('StoreDir','variable_set',variable='ReactionDirection'),
           node('HitState','variable_set',variable='ActionState'),
           node('Unbuffer','variable_set',variable='bAttackBuffered'),node('CloseWindow','variable_set',variable='bComboWindowOpen'),
           node('Direction','variable_get',variable='ReactionDirection'),
           call('FromLeft','KismetMathLibrary','Less_DoubleDouble'),call('FromRight','KismetMathLibrary','Greater_DoubleDouble'),
           call('PickLeft','KismetMathLibrary','SelectObject'),call('PickRight','KismetMathLibrary','SelectObject'),
           node('Damage','variable_get',variable='PendingDamage'),node('Threshold','variable_get',variable='KnockdownDamageThreshold'),
           call('Huge','KismetMathLibrary','GreaterEqual_DoubleDouble'),node('HeavyAction','variable_get',variable='bPendingHeavyAction'),
           call('Heavy','KismetMathLibrary','BooleanOR'),call('PickHeavy','KismetMathLibrary','SelectObject'),
           node('SetDown','variable_set',variable='bKnockedDown'),call('Play','Character','PlayAnimMontage'),
           node('MontageCast','cast',target_class='AnimMontage'),
           call('Recovery','KismetSystemLibrary','K2_SetTimer'),node('Me','variable_get',variable='Mesh'),
           call('Owner','ActorComponent','GetOwner')]
    wires=[(entry_id+'.then','GuardGate.execute'),('State.ActionState','Guard.A'),('Guard.ReturnValue','GuardGate.Condition'),
           ('GuardGate.then','BlockImpact.execute'),('GuardGate.else','ResetDir.execute'),('ResetDir.then','Source.execute'),
           ('Source.PendingDamageSource','SourceLoc.self'),('MyLoc.ReturnValue','LookAt.Start'),('SourceLoc.ReturnValue','LookAt.Target'),
           ('LookAt.ReturnValue','Delta.A'),('MyRot.ReturnValue','Delta.B'),('Delta.ReturnValue','BreakRot.InRot'),
           ('BreakRot.Yaw','StoreDir.ReactionDirection'),('Source.then','StoreDir.execute'),
           ('StoreDir.then','HitState.execute'),('Source.else','HitState.execute'),('HitState.then','Unbuffer.execute'),
           ('Unbuffer.then','CloseWindow.execute'),('Direction.ReactionDirection','FromLeft.A'),('Direction.ReactionDirection','FromRight.A'),
           ('FromLeft.ReturnValue','PickLeft.bSelectA'),('FromRight.ReturnValue','PickRight.bSelectA'),
           ('PickLeft.ReturnValue','PickRight.B'),('PickRight.ReturnValue','PickHeavy.B'),
           ('Damage.PendingDamage','Huge.A'),('Threshold.KnockdownDamageThreshold','Huge.B'),
           ('Huge.ReturnValue','Heavy.A'),('HeavyAction.bPendingHeavyAction','Heavy.B'),
           ('Heavy.ReturnValue','SetDown.bKnockedDown'),('Heavy.ReturnValue','PickHeavy.bSelectA'),
           ('PickHeavy.ReturnValue','MontageCast.Object'),('MontageCast.As애님 몽타주','Play.AnimMontage'),
           ('MontageCast.then','Play.execute'),('Me.Mesh','Owner.self'),('Owner.ReturnValue','Recovery.Object'),
           ('Play.then','Recovery.execute'),('Play.ReturnValue','Recovery.Time')]
    previous='CloseWindow.then'
    for i,function in enumerate(['OnAttackHitCheck','OnAttackRecoveryTimer','OnComboWindowOpen','OnDodgeRecoveryTimer','OnDodgeBurstEnd','EndShieldReaction']):
        ref='Cancel'+str(i);nodes.append(call(ref,'KismetSystemLibrary','K2_ClearTimer'))
        wires.extend([(previous,ref+'.execute'),('Owner.ReturnValue',ref+'.Object')]);previous=ref+'.then'
    wires.extend([(previous,'SetDown.execute'),('SetDown.then','MontageCast.execute')])
    defs=[('Guard','B',3),('BlockImpact','AnimMontage',B+'/Montages/AM_Shield_BlockImpact.AM_Shield_BlockImpact'),
          ('ResetDir','ReactionDirection',0),('HitState','ActionState','NewEnumerator1'),
          ('Unbuffer','bAttackBuffered','false'),('CloseWindow','bComboWindowOpen','false'),
          ('FromLeft','B',-45),('FromRight','B',45),
          ('PickLeft','A',B+'/Montages/AM_Shield_HitLeft.AM_Shield_HitLeft'),
          ('PickLeft','B',B+'/Montages/AM_Shield_HitFront.AM_Shield_HitFront'),
          ('PickRight','A',B+'/Montages/AM_Shield_HitRight.AM_Shield_HitRight'),
          ('PickHeavy','A',B+'/Montages/AM_Shield_Knockdown.AM_Shield_Knockdown'),
          ('Recovery','FunctionName','EndShieldReaction')]
    defs.extend([('Cancel'+str(i),'FunctionName',fn) for i,fn in enumerate(['OnAttackHitCheck','OnAttackRecoveryTimer','OnComboWindowOpen','OnDodgeRecoveryTimer','OnDodgeBurstEnd','EndShieldReaction'])])
    graph(P,name,nodes,wires,defs)
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P))
    # Replace only the old hit playback. Preserve HP calculation, death, and hit-stop flow.
    BP.disconnect_pin(P,event,'5B11BA1A4D0E1FC8D90739AFBB42DED5','then')
    graph(P,event,[call('React',P,'PlayShieldReaction')],
          [('5B11BA1A4D0E1FC8D90739AFBB42DED5.then','React.execute'),
           ('React.then','CF1DDB254F4D62AE3FD006B31A7FC9DB.execute')])
    graph(P,event,[node('EndReact','custom_event',name='EndShieldReaction'),
          node('CurrentState','variable_get',variable='ActionState'),call('StillHit','KismetMathLibrary','EqualEqual_ByteByte'),
          node('EndGate','branch'),node('Resume','variable_set',variable='ActionState'),
          node('ClearDown','variable_set',variable='bKnockedDown')],
          [('EndReact.then','EndGate.execute'),('CurrentState.ActionState','StillHit.A'),
           ('StillHit.ReturnValue','EndGate.Condition'),('EndGate.then','Resume.execute'),('Resume.then','ClearDown.execute')],
          [('StillHit','B',1),('Resume','ActionState','NewEnumerator5'),('ClearDown','bKnockedDown','false')])
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P));save(P)


def weapons():
    # Derive offsets from actual source and target hand poses rather than guessed Euler angles.
    source={b.bone_name:b.transform for b in AS.get_pose_at_time('/Game/ThirdParty/Kubold/SwordShieldAnimsetPro/Animations/Part1/SwordShieldAnimsetPro_part1_Sword_Idle',.5,True)}
    target={b.bone_name:b.transform for b in AS.get_pose_at_time(seq('Sword_Idle'),.5,True)}
    existing=[c.component_name for c in BP.list_components(P)]
    for comp,mesh,src_hand,prop,hand in [('Sword','SM_Kubold_Sword','RightHand','RightHandProp','hand_r'),
                                        ('Shield','SM_Kubold_Shield','LeftHand','LeftHandProp','hand_l')]:
        if comp not in existing: assert BP.add_component(P,'StaticMeshComponent',comp,'CharacterMesh0')
        world=unreal.Transform(location=target[hand].translation+(source[prop].translation-source[src_hand].translation),rotation=source[prop].rotation.rotator(),scale=[1,1,1])
        rel=world.make_relative(target[hand])
        for key,value in [('StaticMesh','/Game/ThirdParty/Kubold/SwordShieldAnimsetPro/Models/'+mesh+'.'+mesh),
                          ('AttachSocketName',hand),('RelativeLocation',rel.translation.export_text()),
                          ('RelativeRotation',rel.rotation.rotator().export_text())]:
            assert BP.set_component_property(P,comp,key,value),(comp,key,value)
        bp_asset=unreal.load_asset(P)
        ss=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        handles=ss.k2_gather_subobject_data_for_blueprint(bp_asset)
        pairs=[(h,unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(
            unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))) for h in handles]
        parent=next(h for h,o in pairs if o and o.get_name()=='CharacterMesh0')
        child,template=next((h,o) for h,o in pairs if o and o.get_name()==comp+'_GEN_VARIABLE')
        template.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        template.set_editor_property('relative_location',rel.translation)
        template.set_editor_property('relative_rotation',rel.rotation.rotator())
        print('MODIFIED:',comp,rel)
    construction='UserConstructionScript'
    entry=next(n.node_id for n in BP.get_nodes_in_graph(P,construction,0,'',False) if n.node_type=='K2Node_FunctionEntry')
    if len(BP.get_nodes_in_graph(P,construction,0,'',False))==1:
        graph(P,construction,[node('Mesh','variable_get',variable='Mesh'),
              node('Sword','variable_get',variable='Sword'),node('Shield','variable_get',variable='Shield'),
              call('AttachSword','SceneComponent','K2_AttachToComponent'),call('AttachShield','SceneComponent','K2_AttachToComponent')],
              [(entry+'.then','AttachSword.execute'),('Sword.Sword','AttachSword.self'),('Mesh.Mesh','AttachSword.Parent'),
               ('AttachSword.then','AttachShield.execute'),('Shield.Shield','AttachShield.self'),('Mesh.Mesh','AttachShield.Parent')],
              [('AttachSword','SocketName','hand_r'),('AttachShield','SocketName','hand_l'),
               ('AttachSword','LocationRule','KeepRelative'),('AttachSword','RotationRule','KeepRelative'),
               ('AttachShield','LocationRule','KeepRelative'),('AttachShield','RotationRule','KeepRelative')])
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P));save(P)
    # Inspect placed actors after SCS modifications; inherited templates can be overridden there.
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class()==unreal.load_asset(P).generated_class():
            print('PLACED PLAYER',actor.get_name(),[(c.get_name(),str(c.get_editor_property('static_mesh'))) for c in actor.get_components_by_class(unreal.StaticMeshComponent)])


def repair_reactions():
    g='PlayShieldReaction'
    # SelectObject is UObject-typed; cast its result before passing it to AnimMontage.
    BP.disconnect_pin(P,g,'1346FC6A4081241CECFC08A453988F40','then')
    graph(P,g,[node('MontageCast','cast',target_class='AnimMontage'),call('Owner','ActorComponent','GetOwner')],
          [('775C62A94F06DECE97004B9332B2C51E.ReturnValue','MontageCast.Object'),
           ('1346FC6A4081241CECFC08A453988F40.then','MontageCast.execute'),
           ('MontageCast.then','7A8DD9BB4A2089839002458ED5EA7493.execute'),
           ('MontageCast.As애님 몽타주','7A8DD9BB4A2089839002458ED5EA7493.AnimMontage'),
           ('6EC0BE95449AF509DE4F04A906F9FC4B.Mesh','Owner.self'),
           *[('Owner.ReturnValue',n+'.Object') for n in ['D7C852704FD7C52A24F111B5C3B9E08C','74EBB89B49E41B53A8620BAB8F84E31B','04F3DD9740192584B3502F90069EB692','7F9521514960036C926B948A4E094C96','70763B334213E06D88964CB480880DB8','AB45A3AD4B18EBC49FF91687BCEF83C3','9799BFE043C6FAA04D299596E481EC35']]])
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P))
    BP.disconnect_pin(P,'EventGraph','5B11BA1A4D0E1FC8D90739AFBB42DED5','then')
    graph(P,'EventGraph',[call('React',P,'PlayShieldReaction')],
          [('5B11BA1A4D0E1FC8D90739AFBB42DED5.then','React.execute'),
           ('React.then','CF1DDB254F4D62AE3FD006B31A7FC9DB.execute')])
    graph(P,'EventGraph',[node('EndReact','custom_event',name='EndShieldReaction'),
          node('CurrentState','variable_get',variable='ActionState'),call('StillHit','KismetMathLibrary','EqualEqual_ByteByte'),
          node('EndGate','branch'),node('Resume','variable_set',variable='ActionState'),
          node('ClearDown','variable_set',variable='bKnockedDown')],
          [('EndReact.then','EndGate.execute'),('CurrentState.ActionState','StillHit.A'),
           ('StillHit.ReturnValue','EndGate.Condition'),('EndGate.then','Resume.execute'),('Resume.then','ClearDown.execute')],
          [('StillHit','B',1),('Resume','ActionState','NewEnumerator5'),('ClearDown','bKnockedDown','false')])
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P));save(P)


def controls():
    # Duplicate the roll clips and remove root travel; manual swept capsule movement owns distance.
    seen={}
    for n in BP.get_nodes_in_graph(P,'TryEnterDodge',0,'',True):
        for q in n.pins:
            src=q.default_object.split('.')[0]
            if '/Animations/Roll/' not in src: continue
            dst=B+'/Sequences/AS_Shield_'+src.rsplit('/',1)[1]
            if not unreal.EditorAssetLibrary.does_asset_exist(dst):
                assert unreal.EditorAssetLibrary.duplicate_asset(src,dst);print('CREATED:',dst)
            roll=unreal.load_asset(dst);roll.set_editor_property('force_root_lock',True)
            assert AS.set_enable_root_motion(dst,False)
            assert AS.set_root_motion_root_lock(dst,'AnimFirstFrame')
            save(dst);pin(P,'TryEnterDodge',n.node_id,q.pin_name,roll.get_path_name());seen[src]=dst
    variable(P,'bDodgeBuffered','bool','false')
    g='TryEnterDodge'
    graph(P,g,[node('StateGate','variable_get',variable='ActionState'),
          call('Locomotion','KismetMathLibrary','EqualEqual_ByteByte'),
          call('Guard','KismetMathLibrary','EqualEqual_ByteByte'),
          call('Attack','KismetMathLibrary','EqualEqual_ByteByte'),
          node('Window','variable_get',variable='bComboWindowOpen'),call('LateAttack','KismetMathLibrary','BooleanAND'),
          call('FreeState','KismetMathLibrary','BooleanOR'),call('CanRoll','KismetMathLibrary','BooleanOR'),
          node('CanBuffer','branch'),node('BufferRoll','variable_set',variable='bDodgeBuffered')],
          [('StateGate.ActionState','Locomotion.A'),('StateGate.ActionState','Guard.A'),('StateGate.ActionState','Attack.A'),
           ('Attack.ReturnValue','LateAttack.A'),('Window.bComboWindowOpen','LateAttack.B'),
           ('Locomotion.ReturnValue','FreeState.A'),('Guard.ReturnValue','FreeState.B'),
           ('FreeState.ReturnValue','CanRoll.A'),('LateAttack.ReturnValue','CanRoll.B'),
           ('CanRoll.ReturnValue','787E444941E2EE8D21E9A29E95B1F60E.Condition'),
           ('787E444941E2EE8D21E9A29E95B1F60E.else','CanBuffer.execute'),
           ('Attack.ReturnValue','CanBuffer.Condition'),('CanBuffer.then','BufferRoll.execute')],
          [('Locomotion','B',5),('Guard','B',3),('Attack','B',4),('BufferRoll','bDodgeBuffered','true')])
    # Resolve the existing Set ActionState node by its exact value.
    start=next(n.node_id for n in BP.get_nodes_in_graph(P,g,0,'',True) if n.node_title=='Set ActionState' and any(q.pin_name=='ActionState' and q.default_value=='NewEnumerator2' for q in n.pins))
    old=next(c for c in BP.get_connections(P,g) if c.source_node_id==start and c.source_pin_name=='then')
    BP.disconnect_pin(P,g,start,'then')
    nodes=[node('ClearRollBuffer','variable_set',variable='bDodgeBuffered'),
           node('Mesh','variable_get',variable='Mesh'),call('Owner','ActorComponent','GetOwner')]
    wires=[(start+'.then','ClearRollBuffer.execute'),('Mesh.Mesh','Owner.self')]
    defaults=[('ClearRollBuffer','bDodgeBuffered','false')];previous='ClearRollBuffer.then'
    for i,fn in enumerate(['OnAttackRecoveryTimer','OnComboWindowOpen','OnAttackHitCheck']):
        ref='ClearAttack'+str(i);nodes.append(call(ref,'KismetSystemLibrary','K2_ClearTimer'))
        wires.extend([(previous,ref+'.execute'),('Owner.ReturnValue',ref+'.Object')])
        defaults.append((ref,'FunctionName',fn));previous=ref+'.then'
    wires.append((previous,old.target_node_id+'.'+old.target_pin_name));graph(P,g,nodes,wires,defaults)
    # Dodge buffer has priority when attack recovery opens; otherwise preserve existing combo logic.
    eg='EventGraph'
    BP.disconnect_pin(P,eg,'137C0BF54F29523B116A57AAFD8D8F0E','then')
    graph(P,eg,[node('RollBuffer','variable_get',variable='bDodgeBuffered'),node('RollPriority','branch'),
          node('OpenRollWindow','variable_set',variable='bComboWindowOpen'),call('BufferedRoll',P,'TryEnterDodge')],
          [('137C0BF54F29523B116A57AAFD8D8F0E.then','RollPriority.execute'),
           ('RollBuffer.bDodgeBuffered','RollPriority.Condition'),('RollPriority.then','OpenRollWindow.execute'),
           ('OpenRollWindow.then','BufferedRoll.execute'),('RollPriority.else','6F912BEA47C6AF680DF2FBA30A0DA627.execute')],
          [('OpenRollWindow','bComboWindowOpen','true')])
    graph(P,eg,[node('EndRollBuffer','variable_get',variable='bDodgeBuffered'),node('EndRollGate','branch'),call('EndRoll',P,'TryEnterDodge')],
          [('29F38A744FA07CE59DF721BC42C7A8CE.then','EndRollGate.execute'),
           ('EndRollBuffer.bDodgeBuffered','EndRollGate.Condition'),('EndRollGate.then','EndRoll.execute')])
    # A hit discards old buffered inputs.
    rg='PlayShieldReaction'
    close=next(n.node_id for n in BP.get_nodes_in_graph(P,rg,0,'',False) if n.node_title=='Set bComboWindowOpen')
    old=next(c for c in BP.get_connections(P,rg) if c.source_node_id==close and c.source_pin_name=='then')
    BP.disconnect_pin(P,rg,close,'then')
    graph(P,rg,[node('DropRoll','variable_set',variable='bDodgeBuffered')],
          [(close+'.then','DropRoll.execute'),('DropRoll.then',old.target_node_id+'.'+old.target_pin_name)],
          [('DropRoll','bDodgeBuffered','false')])
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset(P));save(P)


def guard_recovery():
    # The boss calls ReceiveBossGuardBreak before applying damage. Replace its legacy
    # 0.8-second unlock with the recovery already owned by the new reaction montage.
    rg='PlayShieldReaction'
    drop=next(n.node_id for n in BP.get_nodes_in_graph(P,rg,0,'',False) if n.node_title=='Set bDodgeBuffered')
    old=next(c for c in BP.get_connections(P,rg) if c.source_node_id==drop and c.source_pin_name=='then')
    BP.disconnect_pin(P,rg,drop,'then')
    graph(P,rg,[node('GuardRecoveryMesh','variable_get',variable='Mesh'),
          call('GuardRecoveryOwner','ActorComponent','GetOwner'),
          call('CancelLegacyGuardRecovery','KismetSystemLibrary','K2_ClearTimer')],
          [(drop+'.then','CancelLegacyGuardRecovery.execute'),
           ('GuardRecoveryMesh.Mesh','GuardRecoveryOwner.self'),
           ('GuardRecoveryOwner.ReturnValue','CancelLegacyGuardRecovery.Object'),
           ('CancelLegacyGuardRecovery.then',old.target_node_id+'.'+old.target_pin_name)],
          [('CancelLegacyGuardRecovery','FunctionName','EndBossGuardBreak')])
    obj=unreal.load_asset(P)
    unreal.get_default_object(obj.generated_class()).set_editor_property('bShowHitDebug',False)
    unreal.BlueprintEditorLibrary.compile_blueprint(obj);save(P)


phase = globals().get('sword_phase','assets')
{'assets':assets,'inputs':inputs,'animation':animation,'player':player,'reactions':reactions,'weapons':weapons,'repair':repair_reactions,'controls':controls,'guard_recovery':guard_recovery}[phase]()
