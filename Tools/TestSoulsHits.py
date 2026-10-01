"""Transient, isolated combat fixtures; no saved level/asset changes in PIE."""
import unreal
import json

start = None
boss_hp = 0
player_hp = 0
samples=[]
observer=None
cube=None
committed_name=''


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def player():
    return unreal.GameplayStatics.get_player_character(world(),0)


def boss():
    return next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world(),unreal.Actor)
                if 'BP_Boss_Crunch' in a.get_class().get_name())


def tag(name):
    result=unreal.GameplayTag()
    result.import_text('(TagName="'+name+'")')
    return result


def setup(distance=300):
    global start, boss_hp, player_hp
    p,b=player(),boss()
    for fn in ['EvaluateCombatUtility','EvaluateUtility','FinishBossIntro','FinishBossObserve',
               'OpenActionImpact','CloseActionImpact','FinishCombatAction','OnAttackHit','OnAttackEnd','OnHitWindowClose']:
        unreal.SystemLibrary.clear_timer(b,fn)
    b.set_actor_tick_enabled(False)
    move=b.get_component_by_class(unreal.CharacterMovementComponent)
    move.stop_movement_immediately();move.disable_movement();move.set_component_tick_enabled(False)
    p.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
    if start is None: start=p.get_actor_location()
    p.set_actor_location(start,False,False)
    p.set_actor_rotation(unreal.Rotator(yaw=0),False)
    p.get_controller().set_control_rotation(unreal.Rotator(yaw=0))
    boss_half_height=b.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    player_half_height=p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    b.set_actor_location(start+unreal.Vector(distance,0,boss_half_height-player_half_height),False,False)
    b.set_actor_rotation(unreal.Rotator(yaw=180),False)
    b.call_method('TransitionBossState',(tag('Boss.Combat.Ready'),'isolated test',b.get_editor_property('BossState')))
    b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().montage_stop(0)
    unreal.GameplayStatics.apply_damage(b,-1200,None,None,unreal.DamageType)
    p.set_editor_property('MaxHealth',2000)
    if p.get_editor_property('CurrentHealth')<2000:
        unreal.GameplayStatics.apply_damage(p,-2000,None,None,unreal.DamageType)
    boss_hp=b.get_editor_property('CurrentHealth');player_hp=p.get_editor_property('CurrentHealth')
    return True


def damage():
    return boss_hp-boss().get_editor_property('CurrentHealth')


def take_damage():
    return player_hp-player().get_editor_property('CurrentHealth')


def state():
    return player().get_editor_property('ActionState').value


def channels():
    return all(a.get_component_by_class(unreal.CapsuleComponent).get_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY)==unreal.CollisionResponseType.ECR_IGNORE for a in [player(),boss()])


def hurt_probe():
    p,b=player(),boss()
    hit=unreal.SystemLibrary.sphere_trace_single(world(),b.get_actor_location()+unreal.Vector(-600,0,0),
        b.get_actor_location()+unreal.Vector(600,0,0),12,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[p],unreal.DrawDebugTrace.NONE,False)
    return hit


def contact():
    player().call_method('DoAttackHitCheck')
    player().call_method('ResolveSwordContact',(hurt_probe(),))
    return True


def repeat_contact():
    player().call_method('ResolveSwordContact',(hurt_probe(),))
    return True


def reaction(direction):
    p,b=player(),boss()
    vectors={'front':b.get_actor_forward_vector(),'back':-b.get_actor_forward_vector(),
             'right':b.get_actor_right_vector(),'left':-b.get_actor_right_vector()}
    p.set_actor_location(b.get_actor_location()+vectors[direction]*400,False,False)
    unreal.GameplayStatics.apply_damage(b,12,p.get_controller(),p,unreal.DamageType)
    return True


def reaction_name():
    m=boss().get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_current_active_montage()
    return m.get_editor_property('slot_anim_tracks')[0].export_text() if m else ''


def committed():
    b,p=boss(),player()
    b.call_method('TransitionBossState',(tag('Boss.Combat.Attack.Active'),'isolated test',b.get_editor_property('BossState')))
    b.call_method('StartActionMontage')
    return True


def boss_window(invincible=False,both=False):
    p,b=player(),boss()
    b.call_method('RequestCombatAction',(0,))
    b.call_method('StartActionMontage')
    b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().montage_stop(0)
    b.call_method('OpenActionImpact')
    hand=b.get_component_by_class(unreal.SkeletalMeshComponent).get_socket_location(b.get_editor_property('AttackSocket'))
    p.set_actor_location(hand+unreal.Vector(0,0,-30),False,False)
    if invincible:
        p.call_method('TryEnterDodge')
        p.set_actor_tick_enabled(False)
        p.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().montage_stop(0)
        movement=p.get_component_by_class(unreal.CharacterMovementComponent)
        movement.stop_movement_immediately();movement.disable_movement();movement.set_component_tick_enabled(False)
    for name in ['StartActionMontage','OpenActionImpact','CloseActionImpact','FinishCombatAction']:
        unreal.SystemLibrary.clear_timer(b,name)
    b.set_actor_tick_enabled(True)
    return True


def close_boss_window():
    b=boss()
    b.call_method('TransitionBossState',(tag('Boss.Combat.Ready'),'isolated test end',b.get_editor_property('BossState')))
    return True


def observe():
    global observer,samples
    samples=[]
    def tick(delta):
        p=player()
        if state()==4:
            sword=next(c for c in p.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='Sword')
            transform=sword.get_world_transform()
            base=transform.transform_location(unreal.Vector(0,0,8));tip=transform.transform_location(unreal.Vector(0,0,99))
            hit=unreal.SystemLibrary.sphere_trace_single(world(),base,tip,12,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[p],unreal.DrawDebugTrace.NONE,False)
            samples.append({'time':unreal.GameplayStatics.get_time_seconds(world()),'open':p.get_editor_property('bSwordWindowOpen'),
                'hit':p.get_editor_property('bSwordHasHit'),'base':base.to_tuple(),'tip':tip.to_tuple(),
                'contact':hit.export_text() if hit else '', 'hp':boss().get_editor_property('CurrentHealth')})
    observer=unreal.register_slate_post_tick_callback(tick)
    return True


def stop_observing():
    global observer
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer);observer=None
    out=unreal.Paths.project_saved_dir()+'VibeUE/blade-samples.json'
    with open(out,'w',encoding='utf-8') as f:json.dump(samples,f,indent=2)
    return True


def scenario():
    T="__import__('TestSoulsHits')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e,v=1,t=0):steps.append({'action':'python_assert_number','expression':e,'expected':v,'operator':'eq','tolerance':t})
    def click():
        steps.append({'action':'inject_key','key':'LeftMouseButton','event':'down'});wait(.055)
        steps.append({'action':'inject_key','key':'LeftMouseButton','event':'up'})
    check(f'int({T}.setup())');wait(1.2);check(f'int({T}.channels())')
    check(f'int({T}.contact())');wait(.02);check(f'{T}.damage()',12)
    check(f'int({T}.repeat_contact())');wait(.02);check(f'{T}.damage()',12)
    for direction,angle in [('front',0),('right',90),('back',180),('left',-90)]:
        check(f'int({T}.setup(700))');wait(.35)
        check(f'int({T}.reaction("{direction}"))');wait(.11)
        check(f'abs({T}.boss().get_editor_property("LastHitReactionDirection"))' if angle==180 else f'{T}.boss().get_editor_property("LastHitReactionDirection")',abs(angle) if angle==180 else angle,.2)
        check(f'int("HitReact_{direction.capitalize()}" in {T}.reaction_name())')
        steps.append({'action':'capture_game','name':'boss-hit-'+direction});wait(.8)
    check(f'int({T}.setup(250))');wait(1.2);click();wait(.1);check(f'{T}.state()',4);wait(.7)
    check(f'{T}.damage()',12)
    steps.append({'action':'capture_game','name':'blade-contact'});wait(.8)
    check(f'int({T}.setup(650))');wait(1.2);click();wait(.1);check(f'{T}.state()',4);wait(.7);check(f'{T}.damage()',0);wait(.8)
    check(f'int({T}.setup())');wait(1.2);check(f'int({T}.boss_window(True))');wait(.18)
    check(f'int({T}.boss().get_editor_property("bHitWindowOpen"))')
    check(f'{T}.take_damage()',0);check(f'int({T}.boss().get_editor_property("bHasHitThisAttack"))',0)
    wait(.40)
    check(f'{T}.take_damage()-{T}.boss().get_editor_property("ActiveAction").get_editor_property("Damage")',0)
    check(f'int({T}.boss().get_editor_property("bHasHitThisAttack"))')
    wait(.3);check(f'{T}.take_damage()-{T}.boss().get_editor_property("ActiveAction").get_editor_property("Damage")',0)
    check(f'int({T}.close_boss_window())');wait(.5)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Souls physical contacts and directional monster reactions','steps':steps,'teardown':{'stop_pie':True}}


def prepare():
    global cube
    cube=unreal.load_object(None,'/Engine/BasicShapes/Cube.Cube')
    return bool(cube)


def wall():
    assert cube
    res=json.loads(unreal.PIEActorService.spawn_actor('server','/Script/Engine.StaticMeshActor',unreal.Transform()))
    assert res['success'],res
    blocker=unreal.find_object(None,res['actor_path'])
    blocker.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    blocker.static_mesh_component.set_static_mesh(cube)
    blocker.static_mesh_component.set_collision_profile_name('BlockAll')
    blocker.set_actor_scale3d(unreal.Vector(.30,3,3))
    blocker.set_actor_location(start+unreal.Vector(150,0,60),False,False)
    return True


def remove_wall():
    unreal.PIEActorService.destroy_all()
    return True


def wall_contact():
    p,b=player(),boss()
    hit=unreal.SystemLibrary.sphere_trace_single(world(),start+unreal.Vector(0,0,60),
        start+unreal.Vector(300,0,60),12,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[p,b],unreal.DrawDebugTrace.NONE,False)
    assert hit and 'StaticMeshActor' in hit.export_text(),hit.export_text() if hit else 'no wall'
    p.call_method('DoAttackHitCheck')
    p.call_method('ResolveSwordContact',(hit,))
    # A later sub-sweep can find a body through/around the obstruction. Once the
    # strike hit the wall, the shared window must reject this second contact.
    p.call_method('ResolveSwordContact',(hurt_probe(),))
    return True


def profile_hit(index,amount):
    global player_hp
    p,b=player(),boss()
    player_hp=p.get_editor_property('CurrentHealth')
    b.call_method('RequestCombatAction',(index,))
    unreal.GameplayStatics.apply_damage(p,amount,p.get_controller(),b,unreal.DamageType)
    return True


def committed_hit():
    global committed_name
    b,p=boss(),player()
    b.call_method('RequestCombatAction',(0,))
    b.call_method('StartActionMontage')
    unreal.SystemLibrary.clear_timer(b,'StartActionMontage')
    m=b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_current_active_montage()
    committed_name=m.get_name() if m else ''
    unreal.GameplayStatics.apply_damage(b,12,p.get_controller(),p,unreal.DamageType)
    return True


def keeps_attack():
    b=boss()
    m=b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance().get_current_active_montage()
    return bool(m and m.get_name()==committed_name and 'Boss.Combat.Attack.' in b.get_editor_property('BossState').export_text())


def kill_boss():
    unreal.GameplayStatics.apply_damage(boss(),5000,player().get_controller(),player(),unreal.DamageType)
    return True


def policy_scenario():
    T="__import__('TestSoulsHits')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e,v=1):steps.append({'action':'python_assert_number','expression':e,'expected':v,'operator':'eq','tolerance':0})
    check(f'int({T}.prepare())')
    check(f'int({T}.setup(250))');wait(1.2);check(f'int({T}.wall())')
    check(f'int({T}.wall_contact())');wait(.06)
    check(f'int({T}.player().get_editor_property("bSwordWindowOpen"))',0)
    check(f'{T}.damage()',0)
    steps.append({'action':'capture_game','name':'wall-blocks-blade'})
    check(f'int({T}.remove_wall())');wait(.6)
    check(f'int({T}.setup(700))');wait(.5);check(f'int({T}.profile_hit(0,160))');wait(.20)
    check(f'int({T}.player().get_editor_property("bHasAttackReactionProfile"))')
    check(f'int({T}.player().get_editor_property("bKnockedDown"))',0)
    check(f'{T}.take_damage()',160);wait(2.8)
    check(f'int({T}.setup(700))');wait(.5);check(f'int({T}.profile_hit(2,10))');wait(.20)
    check(f'int({T}.player().get_editor_property("bKnockedDown"))')
    check(f'{T}.take_damage()',10)
    steps.append({'action':'capture_game','name':'low-damage-heavy-reaction'});wait(3.5)
    check(f'int({T}.setup(700))');wait(.5);check(f'int({T}.committed_hit())');wait(.12)
    check(f'int({T}.keeps_attack())');check(f'{T}.damage()',12)
    steps.append({'action':'capture_game','name':'boss-continues-attack-on-hit'})
    check(f'int({T}.kill_boss())');wait(.1)
    check(f'int("Boss.Dead" in {T}.boss().get_editor_property("BossState").export_text())')
    check(f'int({T}.boss().get_editor_property("bHitWindowOpen"))',0)
    check(f'{T}.boss().get_editor_property("CurrentHealth")',0)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Souls wall occlusion damage levels and boss commitment','steps':steps,'teardown':{'stop_pie':True}}
