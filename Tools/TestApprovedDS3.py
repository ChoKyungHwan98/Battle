"""Transient PIE measurements for the approved DS3 adaptation scope."""
import json
import unreal
import TestSoulsHits as T

observer = None
samples = []
index = 0
geometry = {
    'hand_slide_l': ((39.274921,-5.075858,3.627527), (0.548949,89.825554,-78.753815)),
    'hand_slide_r': ((-28.981632,5.911167,-1.559819), (0.548949,89.825562,-84.378960))}
radius = 30.891403
length = 54.540031
case_start=0
case_damage=0


def ends(mesh, socket):
    center, rotation = geometry[socket]
    axis = unreal.MathLibrary.get_up_vector(unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))
    transform = mesh.get_socket_transform(socket,unreal.RelativeTransformSpace.RTS_WORLD)
    return tuple(transform.transform_location(unreal.Vector(*center)+axis*s*length/2) for s in [-1,1])


def prepare(distance=320):
    T.setup(distance)
    mesh=T.player().get_component_by_class(unreal.SkeletalMeshComponent)
    mesh.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
    mesh.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA,unreal.CollisionResponseType.ECR_BLOCK)
    return 1


def begin(action=0):
    global observer,samples,index
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer)
    samples=[];index=action
    b=T.boss();mesh=b.get_component_by_class(unreal.SkeletalMeshComponent)
    b.call_method('RequestCombatAction',(action,))
    # Preserve the real attack movement; legacy damage cannot see this fixture.
    b.set_actor_tick_enabled(True)
    anim=mesh.get_anim_instance();montage=anim.get_current_active_montage()
    started=unreal.GameplayStatics.get_time_seconds(T.world());previous={}
    def tick(delta):
        current=anim.get_current_active_montage()
        row={'t':unreal.GameplayStatics.get_time_seconds(T.world())-started,
             'pos':anim.montage_get_position(current) if current else 0,'state':b.get_editor_property('BossState').export_text(),
             'player':T.player().get_actor_location().to_tuple(),'boss':b.get_actor_location().to_tuple(),
             'hp':T.player().get_editor_property('CurrentHealth'),'hands':{}}
        for socket in geometry:
            a,z=ends(mesh,socket);old=previous.get(socket,(a,z));hit=False
            for fraction in [0,.5,1]:
                now=unreal.MathLibrary.v_lerp(a,z,fraction);before=unreal.MathLibrary.v_lerp(*old,fraction)
                contact=unreal.SystemLibrary.sphere_trace_single(T.world(),before,now,radius*1.8,
                    unreal.TraceTypeQuery.ECC_CAMERA,False,[b],unreal.DrawDebugTrace.NONE,True)
                hit=hit or (contact is not None and 'BP_Player_Combat' in contact.export_text())
            previous[socket]=(a,z)
            row['hands'][socket]={'ends':[a.to_tuple(),z.to_tuple()],'hit':bool(hit)}
        samples.append(row)
    observer=unreal.register_slate_post_tick_callback(tick)
    return int(b.get_editor_property('ActiveAction')==b.get_editor_property('Actions')[action])


def finish():
    global observer
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer);observer=None
    path=unreal.Paths.project_saved_dir()+f'VibeUE/measured-hand-volume-{index}.json'
    with open(path,'w') as f:json.dump(samples,f,indent=2)
    for socket in geometry:
        hits=[s['pos'] for s in samples if s['hands'][socket]['hit'] and s['pos']>0]
        print('MEASURED',index,socket,len(hits),min(hits,default=None),max(hits,default=None))
    print('ARTIFACT',path)
    return 1


def measure_scenario():
    q="__import__('TestApprovedDS3')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    for i,duration in [(0,1.65),(1,1.75),(2,2.4),(3,3.6),(4,6.0),(5,3.0),(6,2.8)]:
        for expression in [f'{q}.prepare(320)']:
            steps.append({'action':'python_assert_number','expression':expression,'expected':1,'operator':'eq'})
        steps.append({'action':'wait','seconds':.4})
        steps.append({'action':'python_assert_number','expression':f'{q}.begin({i})','expected':1,'operator':'eq'})
        steps.append({'action':'wait','seconds':duration})
        steps.append({'action':'python_assert_number','expression':f'{q}.finish()','expected':1,'operator':'eq'})
    return {'name':'Measure actual Crunch physics hand contact before choosing montage windows',
            'steps':steps,'teardown':{'stop_pie':True}}


def settle():
    T.player_hp=T.player().get_editor_property('CurrentHealth')
    T.boss_hp=T.boss().get_editor_property('CurrentHealth')
    return 1


def real_begin(action):
    global observer,samples,index
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer)
    samples=[];index=action;settle()
    b=T.boss();p=T.player();mesh=b.get_component_by_class(unreal.SkeletalMeshComponent)
    b.call_method('RequestCombatAction',(action,));b.set_actor_tick_enabled(True)
    anim=mesh.get_anim_instance();hp=p.get_editor_property('CurrentHealth')
    start=unreal.GameplayStatics.get_time_seconds(T.world())
    def tick(dt):
        if not T.world():return
        current=anim.get_current_active_montage()
        samples.append({'t':unreal.GameplayStatics.get_time_seconds(T.world())-start,
            'pos':anim.montage_get_position(current) if current else 0,
            'open':b.get_editor_property('bPhysicalStrikeOpen'),
            'strike':b.get_editor_property('PhysicalStrikeIndex'),
            'hit':b.get_editor_property('bPhysicalStrikeHit'),
            'hp':p.get_editor_property('CurrentHealth'),
            'world_dilation':unreal.GameplayStatics.get_global_time_dilation(T.world()),
            'self_dilation':p.custom_time_dilation,'other_dilation':b.custom_time_dilation})
    observer=unreal.register_slate_post_tick_callback(tick)
    return int(b.get_editor_property('ActiveAction')==b.get_editor_property('Actions')[action])


def real_finish():
    global observer
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer);observer=None
    with open(unreal.Paths.project_saved_dir()+f'VibeUE/approved-live-contact-{index}.json','w') as f:json.dump(samples,f,indent=2)
    return int(bool(samples) and any(s['open'] for s in samples) and all(s['world_dilation']==1 for s in samples)
               and T.player().custom_time_dilation==1 and T.boss().custom_time_dilation==1)


def freeze_pose(action,position):
    b=T.boss();p=T.player();b.call_method('RequestCombatAction',(action,));b.call_method('StartActionMontage')
    for fn in ['StartActionMontage','OpenActionImpact','CloseActionImpact','FinishCombatAction','EvaluateCombatUtility']:
        unreal.SystemLibrary.clear_timer(b,fn)
    b.set_actor_tick_enabled(False)
    a=b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance()
    montage=a.get_current_active_montage();assert montage
    a.montage_set_position(montage,position);a.montage_pause(montage)
    movement=p.get_component_by_class(unreal.CharacterMovementComponent)
    movement.stop_movement_immediately();movement.disable_movement();movement.set_component_tick_enabled(False)
    p.set_actor_tick_enabled(True)
    return 1


def geometry_case(action,mode='inside',strike=0):
    global case_start,case_damage
    p,b=T.player(),T.boss();mesh=b.get_component_by_class(unreal.SkeletalMeshComponent)
    socket='hand_slide_l' if str(b.get_editor_property('ActiveAction').get_editor_property('HitSockets')[strike])=='hand_l' else 'hand_slide_r'
    a,z=ends(mesh,socket);mid=(a+z)*.5
    # Place an actual hurt body inside the fist; actor origin alone can lie well
    # above/below the hurt bodies while an existing knockdown reaction plays.
    torso=p.get_component_by_class(unreal.SkeletalMeshComponent).get_socket_location('pelvis')-p.get_actor_location()
    p.set_actor_location(mid-torso+(unreal.Vector(0,240,0) if mode=='outside' else unreal.Vector()),False,False)
    if mode=='iframe':
        p.call_method('TryEnterDodge')
        p.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().montage_pause()
        assert p.get_editor_property('bInvincible')
    wall=None
    if mode=='wall':
        res=json.loads(unreal.PIEActorService.spawn_actor('server','/Script/Engine.StaticMeshActor',unreal.Transform()))
        wall=unreal.find_object(None,res['actor_path'])
        wall.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        wall.static_mesh_component.set_static_mesh(T.cube)
        wall.static_mesh_component.set_collision_profile_name('BlockAll')
        wall.set_actor_scale3d(unreal.Vector(.12,8,8))
        delta=p.get_actor_location()-b.get_actor_location()
        wall.set_actor_rotation(unreal.MathLibrary.make_rot_from_x(delta),False)
        wall.set_actor_location(b.get_actor_location()+delta*.5,False,False)
    b.call_method('BeginPhysicalStrike',(strike,))
    case_start=p.get_editor_property('CurrentHealth')
    trace='TracePhysicalLeft' if socket=='hand_slide_l' else 'TracePhysicalRight'
    # This is a paused-pose geometry fixture. Live dispatch intentionally closes
    # windows for montages which no longer play, including this fixture's pause.
    for _ in range(4):b.call_method(trace)
    case_damage=b.get_editor_property('PhysicalStrikeDamage') if mode=='inside' else 0
    if wall:unreal.PIEActorService.destroy_actor(res['handle'])
    return int(bool(b.get_editor_property('bPhysicalStrikeHit'))==(mode=='inside'))


def geometry_finish():
    p,b=T.player(),T.boss();damage=case_start-p.get_editor_property('CurrentHealth')
    print('GEOMETRY damage',damage,'expected',case_damage)
    return int(abs(damage-case_damage)<.01 and p.custom_time_dilation==1 and b.custom_time_dilation==1)


def contact_scenario():
    q="__import__('TestApprovedDS3')";t="__import__('TestSoulsHits')"
    steps=[{'action':'python_assert_number','expression':f'int({t}.prepare())','expected':1,'operator':'eq'},
           {'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    for i,pos in [(0,.63),(1,.20),(2,.20),(3,.65),(4,.63),(5,.45),(6,.60)]:
        check(f'int({t}.setup(700))');wait(.6);check(f'{q}.settle()')
        check(f'{q}.freeze_pose({i},{pos})');wait(.3)
        for mode in ['inside','outside','wall']:
            for _ in range(10 if mode!='wall' else 1):
                check(f'{q}.geometry_case({i},"{mode}")');wait(.13);check(f'{q}.geometry_finish()')
                if mode=='inside' and i in [2,3,5,6]:wait(4.05)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Actual hand volumes inside outside walls duplicate and local hit stop','steps':steps,'teardown':{'stop_pie':True}}


def wall_repeat_scenario():
    q="__import__('TestApprovedDS3')";t="__import__('TestSoulsHits')"
    steps=[{'action':'python_assert_number','expression':f'int({t}.prepare())','expected':1,'operator':'eq'},
           {'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    for i,pos in [(0,.63),(1,.20),(2,.20),(3,.65),(4,.63),(5,.45),(6,.60)]:
        check(f'int({t}.setup(700))');wait(.6);check(f'{q}.settle()')
        check(f'{q}.freeze_pose({i},{pos})');wait(.3)
        for _ in range(10):
            check(f'{q}.geometry_case({i},"wall")');wait(.13);check(f'{q}.geometry_finish()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Seven attacks blocked by wall ten independent contacts each','steps':steps,'teardown':{'stop_pie':True}}


def guard_scenario():
    q="__import__('TestApprovedDS3')";t="__import__('TestSoulsHits')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    check(f'int({t}.setup(700))');wait(.6);check(f'{q}.freeze_pose(5,.45)');wait(.3)
    check(f'{q}.geometry_case(5,"iframe")');wait(.13);check(f'{q}.geometry_finish()')
    check(f'int({t}.state()==2 and not {t}.player().get_editor_property("bKnockedDown"))')
    check(f'int({t}.player().mesh.get_anim_instance().montage_resume(None) is None)');wait(.9)
    check(f'int({t}.state()==5 and not {t}.player().get_editor_property("bInvincible"))')
    check(f'{q}.geometry_case(5,"inside")');wait(.13);check(f'{q}.geometry_finish()');wait(4.1)
    check(f'int({t}.state()==5 and not {t}.player().get_editor_property("bKnockedDown"))')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Guard break respects roll iframe and montage recovery','steps':steps,'teardown':{'stop_pie':True}}


def live_scenario():
    q="__import__('TestApprovedDS3')";t="__import__('TestSoulsHits')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    for i,duration in [(0,1.8),(1,1.8),(2,2.5),(3,3.8),(4,6.2),(5,3.2),(6,3.0)]:
        steps.extend([{'action':'python_assert_number','expression':f'int({t}.setup(320))','expected':1,'operator':'eq'},
                      {'action':'wait','seconds':.6},
                      {'action':'python_assert_number','expression':f'{q}.real_begin({i})','expected':1,'operator':'eq'},
                      {'action':'wait','seconds':duration},
                      {'action':'python_assert_number','expression':f'{q}.real_finish()','expected':1,'operator':'eq'}])
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Seven real boss montages drive physical windows','steps':steps,'teardown':{'stop_pie':True}}


def combo_begin():
    global observer,samples
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer)
    samples=[];settle();p=T.player();p.call_method('TryEnterAttack')
    last=[None];queued=[False];seen=[]
    def tick(dt):
        if not T.world():return
        p=T.player();m=p.mesh.get_anim_instance().get_current_active_montage()
        name=m.get_name() if m else ''
        if name.startswith('AM_Sword_Attack_') and m!=last[0]:
            last[0]=m;queued[0]=False;seen.append(name)
        position=p.mesh.get_anim_instance().montage_get_position(m) if m else 0
        if T.state()==4 and name.startswith('AM_Sword_Attack_') and position>=.30 and not queued[0] and len(seen)<4:
            queued[0]=True;p.call_method('TryEnterAttack')
        samples.append({'seen':list(seen),'state':T.state(),'pose':position,'boss_hp':T.boss().get_editor_property('CurrentHealth'),
                        'world':unreal.GameplayStatics.get_global_time_dilation(T.world())})
    observer=unreal.register_slate_post_tick_callback(tick)
    return int(T.state()==4)


def combo_finish():
    global observer
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer);observer=None
    with open(unreal.Paths.project_saved_dir()+'VibeUE/approved-four-hit-evidence.json','w') as f:json.dump(samples,f,indent=2)
    seen=samples[-1]['seen'];damage=T.damage()
    print('FOUR HIT',seen,'damage',damage,'state',T.state())
    return int(seen==['AM_Sword_Attack_'+str(i) for i in range(1,5)] and T.state()==5 and 0<damage<=48
               and all(s['world']==1 for s in samples))


def sword_scenario():
    q="__import__('TestApprovedDS3')";t="__import__('TestSoulsHits')"
    steps=[{'action':'python_assert_number','expression':f'int({t}.prepare())','expected':1,'operator':'eq'},
           {'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    check(f'int({t}.setup(250))');wait(1);check(f'{q}.combo_begin()');wait(2.8);check(f'{q}.combo_finish()')
    check(f'int({t}.setup(250))');wait(1);check(f'{q}.settle()');check(f'int({t}.wall())')
    check(f'int({t}.wall_contact())');wait(.13)
    check(f'int({t}.damage()==0 and not {t}.player().get_editor_property("bSwordWindowOpen"))')
    check(f'int({t}.remove_wall())')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Full blade live four hit combo and wall occlusion','steps':steps,'teardown':{'stop_pie':True}}
