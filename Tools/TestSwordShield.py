"""PIE scenario helpers. Only transient PIE actors/settings are changed."""
import unreal
import json

start_location = None
start_foot_pose = None
start_rotation = None
start_control_rotation = None


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def player():
    return unreal.GameplayStatics.get_player_character(world(),0)


def setup():
    global start_location, start_rotation, start_control_rotation
    p=player()
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world(),unreal.Actor):
        if 'BP_Boss_Crunch' in actor.get_class().get_name():
            actor.set_actor_location(unreal.Vector(10000,10000,190),False,False)
            actor.set_actor_tick_enabled(False)
            # CharacterMovement ticks separately from the Actor and can keep
            # executing a queued boss charge even after Actor Tick is disabled.
            movement = actor.get_component_by_class(unreal.CharacterMovementComponent)
            if movement:
                movement.stop_movement_immediately()
                movement.disable_movement()
                movement.set_component_tick_enabled(False)
    p.set_editor_property('MaxHealth',2000)
    unreal.GameplayStatics.apply_damage(p,-2000,None,None,unreal.DamageType)
    start_location=p.get_actor_location()
    start_rotation=p.get_actor_rotation()
    start_control_rotation=p.get_controller().get_control_rotation()
    return p is not None


def begin_roll():
    global start_location
    start_location=player().get_actor_location()
    return True


def roll_distance():
    return (player().get_actor_location()-start_location).length()


def state():
    return player().get_editor_property('ActionState').value


def montage():
    m=player().mesh.get_anim_instance().get_current_active_montage()
    return m.get_name() if m else ''


def hit(amount,direction='front'):
    p=player()
    # Spawn a plain transient damage source, not another gameplay Blueprint.
    unreal.PIEActorService.spawn_actor('server','/Script/Engine.StaticMeshActor',unreal.Transform())
    source=next(a for a in reversed(list(unreal.GameplayStatics.get_all_actors_of_class(world(),unreal.Actor))) if a.get_class()==unreal.StaticMeshActor.static_class())
    source.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    vector=p.get_actor_right_vector() if direction=='right' else -p.get_actor_right_vector() if direction=='left' else p.get_actor_forward_vector()
    source.set_actor_location(p.get_actor_location()+vector*300,False,False)
    assert (source.get_actor_location()-p.get_actor_location()).length()>290
    unreal.GameplayStatics.apply_damage(p,amount,None,source,unreal.DamageType)
    return True


def guard_break():
    p=player()
    boss=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world(),unreal.Actor)
              if 'BP_Boss_Crunch' in a.get_class().get_name())
    # Match the existing boss event order: remove guard, drain stamina, then damage.
    p.call_method('ReceiveBossGuardBreak')
    unreal.GameplayStatics.apply_damage(p,160,None,boss,unreal.DamageType)
    return True


def commitment_scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr,expected=1):steps.append({'action':'python_assert_number','expression':expr,'expected':expected,'operator':'eq','tolerance':0})
    def click(k):key(k,'down');wait(.055);key(k,'up')
    check(f'int({T}.setup())');wait(.8)
    click('LeftMouseButton');wait(.1);check(f'{T}.state()',4)
    click('SpaceBar');check(f'{T}.state()',4)
    check(f'int({T}.player().get_editor_property("bDodgeBuffered"))')
    wait(.55);check(f'{T}.state()',2)
    check(f'int({T}.player().get_editor_property("bDodgeBuffered"))',0)
    steps.append({'action':'capture_game','name':'buffered-roll'})
    wait(.8);check(f'{T}.state()',5)
    # Late attack recovery accepts a roll immediately, without waiting for full attack end.
    click('LeftMouseButton');wait(.70);check(f'{T}.state()',4)
    click('SpaceBar');check(f'{T}.state()',2)
    wait(.8);check(f'{T}.state()',5)
    check(f'int({T}.hit(40))');wait(.13)
    click('SpaceBar');check(f'{T}.state()',1)
    check(f'int({T}.player().get_editor_property("bDodgeBuffered"))',0)
    wait(.65);check(f'{T}.state()',5)
    key('RightMouseButton','down');wait(.15);check(f'{T}.state()',3)
    check(f'int({T}.guard_break())');wait(.95)
    # The old 0.8-second guard-break timer must not unlock the 3.7-second knockdown.
    check(f'{T}.state()',1)
    check(f'int({T}.player().get_editor_property("bKnockedDown"))')
    steps.append({'action':'capture_game','name':'guard-break-knockdown'})
    key('RightMouseButton','up');wait(3.15)
    check(f'{T}.state()',5)
    check(f'int({T}.player().get_editor_property("bKnockedDown"))',0)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'SwordShield attack commitment and guard-break recovery','steps':steps,'teardown':{'stop_pie':True}}


def locomotion_scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr,expected,op='eq'):
        assertion={'action':'python_assert_number','expression':expr,'expected':expected,'operator':op}
        if op=='eq':assertion['tolerance']=0
        steps.append(assertion)
    def cap(name):steps.append({'action':'capture_game','name':name})
    check(f'int({T}.setup())',1);wait(.8)
    check(f'{T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed")',0)
    cap('new-idle')
    key('W','down');wait(.60)
    check(f'{T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed")',150,'gt')
    check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("ShouldMove"))',1)
    cap('forward')
    key('W','up');wait(.20)
    key('S','down');wait(.60)
    check(f'{T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed")',150,'gt')
    cap('backward')
    key('S','up');wait(.20)
    key('A','down');wait(.60);cap('left')
    key('A','up');wait(.20)
    key('D','down');wait(.60);cap('right')
    key('D','up');wait(.30)
    check(f'{T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed")',5,'lt')
    cap('return-idle')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'SwordShield output locomotion','steps':steps,'teardown':{'stop_pie':True}}


def setup_strafe():
    assert setup()
    # Lock to the inert boss so eight inputs exercise target-facing strafing.
    p=player()
    boss=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world(),unreal.Actor)
              if 'BP_Boss_Crunch' in a.get_class().get_name())
    boss.set_actor_location(p.get_actor_location()+p.get_actor_forward_vector()*1200,False,False)
    p.call_method('ToggleLockOn')
    return p.get_editor_property('LockOnTarget') == boss


def anim_direction():
    return player().mesh.get_anim_instance().get_editor_property('Direction')


def begin_foot_pose():
    global start_foot_pose
    mesh = player().mesh
    start_foot_pose = [mesh.get_socket_transform(b, unreal.RelativeTransformSpace.RTS_COMPONENT).translation
                       for b in ['foot_l', 'foot_r']]
    return True


def foot_pose_change():
    mesh = player().mesh
    return max((mesh.get_socket_transform(b, unreal.RelativeTransformSpace.RTS_COMPONENT).translation - initial).length()
               for b, initial in zip(['foot_l', 'foot_r'], start_foot_pose))


def reset_motion_fixture():
    p = player()
    p.character_movement.stop_movement_immediately()
    p.set_actor_location(start_location, False, False)
    p.set_actor_rotation(start_rotation, False)
    p.get_controller().set_control_rotation(start_control_rotation)
    return True


def eight_direction_scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr,expected=1):steps.append({'action':'python_assert_number','expression':expr,'expected':expected,'operator':'eq','tolerance':0})
    def cap(name):steps.append({'action':'capture_game','name':name})
    check(f'int({T}.setup_strafe())');wait(.8);cap('idle')
    # Each capture and angle assertion is taken while the keys remain held.
    for name,keys,lo,hi in [
        ('forward',['W'],0,30),('forward-left',['W','A'],20,75),
        ('left',['A'],60,120),('back-left',['S','A'],105,165),
        ('back',['S'],150,181),('back-right',['S','D'],105,165),
        ('right',['D'],60,120),('forward-right',['W','D'],20,75)]:
        check(f'int({T}.reset_motion_fixture())')
        wait(.35)
        for k in keys:key(k,'down')
        wait(.48)
        check(f'int({lo} <= abs({T}.anim_direction()) <= {hi})')
        check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed") > 100)')
        check(f'int({T}.begin_foot_pose())')
        cap(name)
        wait(.17)
        check(f'int({T}.foot_pose_change() > 10)')
        cap(name+'-step')
        for k in keys:key(k,'up')
        wait(.18)
    wait(.25);check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed") < 5)')
    cap('return-idle')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'SwordShield continuous idle and eight direction blend','steps':steps,'teardown':{'stop_pie':True}}


def free_locomotion_pose_scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr):steps.append({'action':'python_assert_number','expression':expr,'expected':1,'operator':'eq','tolerance':0})
    def cap(name):steps.append({'action':'capture_game','name':name})
    check(f'int({T}.setup())');wait(.5)
    check(f'int({T}.player().get_editor_property("MovementMode").value == 0)')
    check(f'int({T}.player().character_movement.get_editor_property("orient_rotation_to_movement"))')
    cap('free-idle')
    for name,keys,lo,hi in [
        ('free-forward',['W'],0,30),('free-forward-left',['W','A'],20,75),
        ('free-left',['A'],60,120),('free-back-left',['S','A'],105,165),
        ('free-back',['S'],150,181),('free-back-right',['S','D'],105,165),
        ('free-right',['D'],60,120),('free-forward-right',['W','D'],20,75)]:
        for k in keys:key(k,'down')
        wait(.48)
        check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed") > 100)')
        check(f'int({T}.begin_foot_pose())')
        cap(name)
        wait(.17)
        check(f'int({T}.foot_pose_change() > 10)')
        cap(name+'-step')
        for k in keys:key(k,'up')
        wait(.18)
    wait(.25)
    check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed") < 5)')
    cap('free-return-idle')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Free movement faces travel and advances foot pose','steps':steps,'teardown':{'stop_pie':True}}


def sprint_lock_scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr):steps.append({'action':'python_assert_number','expression':expr,'expected':1,'operator':'eq','tolerance':0})
    def cap(name):steps.append({'action':'capture_game','name':name})
    check(f'int({T}.setup_strafe())');wait(.3)
    check(f'int({T}.player().get_editor_property("MovementMode").value == 1)')
    cap('locked-idle')
    # A viewport capture can stall the first input tick past the Hold threshold.
    wait(.35)
    key('SpaceBar','down');wait(.06)
    check(f'int({T}.player().get_editor_property("MovementMode").value == 1)')
    check(f'int({T}.player().get_editor_property("SprintResumeLockTarget") is None)')
    key('SpaceBar','up');wait(.9)
    key('W','down');key('SpaceBar','down');wait(.12)
    check(f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    check(f'int({T}.player().get_editor_property("MovementMode").value == 1)')
    wait(.32)
    check(f'int({T}.player().get_editor_property("bIsSprinting"))')
    check(f'int({T}.player().get_editor_property("MovementMode").value == 0)')
    check(f'int({T}.player().get_editor_property("LockOnTarget") is None)')
    check(f'int({T}.player().get_editor_property("SprintResumeLockTarget") is not None)')
    cap('sprint-free')
    key('SpaceBar','up');key('W','up');wait(.35)
    check(f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    check(f'int({T}.player().get_editor_property("MovementMode").value == 1)')
    check(f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    check(f'int({T}.player().get_editor_property("SprintResumeLockTarget") is None)')
    cap('lock-restored')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Lock-on suspended while Space sprint is held','steps':steps,'teardown':{'stop_pie':True}}


def scenario():
    T="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t): steps.append({'action':'wait','seconds':t})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr,expected=1,op='eq',tol=0):steps.append({'action':'python_assert_number','expression':expr,'expected':expected,'operator':op,'tolerance':tol})
    def cap(name):steps.append({'action':'capture_game','name':name})
    def click(k):key(k,'down');wait(.055);key(k,'up')
    check(f'int({T}.setup())');wait(.8)
    cap('idle')
    check(f'int({T}.begin_roll())')
    key('SpaceBar','down');wait(.06)
    check(f'{T}.state()',2)
    check(f'int({T}.player().character_movement.is_falling())',0)
    key('SpaceBar','up');wait(.75)
    check(f'int({T}.player().get_editor_property("bIsSprinting"))',0)
    check(f'{T}.roll_distance()',320,'eq',4)
    check(f'{T}.state()',5)
    key('W','down');key('SpaceBar','down');wait(.42)
    check(f'int({T}.player().get_editor_property("bIsSprinting"))')
    check(f'{T}.player().character_movement.max_walk_speed',650)
    wait(.45);cap('sprint')
    key('SpaceBar','up');key('W','up');wait(.35)
    check(f'int({T}.player().get_editor_property("bIsSprinting"))',0)
    check(f'{T}.player().character_movement.max_walk_speed',450)
    key('F','down');wait(.13)
    check(f'int({T}.player().character_movement.is_falling())')
    cap('jump');key('F','up');wait(1.2)
    click('LeftMouseButton');wait(.10)
    check(f'int({T}.montage()=="AM_Sword_Attack_1")')
    click('LeftMouseButton');wait(.58)
    check(f'int({T}.montage()=="AM_Sword_Attack_2")')
    click('LeftMouseButton');wait(.62)
    check(f'int({T}.montage()=="AM_Sword_Attack_3")')
    click('LeftMouseButton');wait(.62)
    check(f'int({T}.montage()=="AM_Sword_Attack_4")')
    cap('attack4');wait(1.1)
    check(f'{T}.state()',5)
    key('RightMouseButton','down');wait(.15)
    check(f'{T}.state()',3)
    check(f'int({T}.player().mesh.get_anim_instance().get_editor_property("bShieldGuard"))')
    cap('guard');check(f'int({T}.hit(40))');wait(.13)
    check(f'{T}.state()',3)
    check(f'int({T}.montage()=="AM_Shield_BlockImpact")');cap('block-impact')
    key('RightMouseButton','up');wait(.5)
    check(f'{T}.state()',5)
    check(f'int({T}.hit(40,"right"))');wait(.13)
    check(f'{T}.state()',1)
    check(f'int({T}.montage()=="AM_Shield_HitRight")');wait(.65)
    check(f'{T}.state()',5)
    check(f'int({T}.hit(180))');wait(.35)
    check(f'int({T}.player().get_editor_property("bKnockedDown"))')
    check(f'int({T}.montage()=="AM_Shield_Knockdown")')
    key('F','down');key('SpaceBar','down');wait(.08)
    check(f'{T}.state()',1)
    check(f'int({T}.player().character_movement.is_falling())',0)
    key('F','up');key('SpaceBar','up');wait(.6);cap('knockdown');wait(3.05)
    check(f'{T}.state()',5)
    check(f'int({T}.player().get_editor_property("bKnockedDown"))',0)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'SwordShield player controls and reactions','steps':steps,'teardown':{'stop_pie':True}}
