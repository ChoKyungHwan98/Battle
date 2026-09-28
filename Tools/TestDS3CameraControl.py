"""Read-only PIE probes for camera framing and attack/root-motion timing."""
import unreal
import TestSwordShield as T

attack_start = None
attack_right = None
facing_initial = None
facing_committed = None


def begin_attack():
    global attack_start,attack_right
    p=T.player()
    attack_start=p.get_actor_location()
    attack_right=p.get_actor_right_vector()
    return True


def attack_travel():
    return (T.player().get_actor_location()-attack_start).length()


def lateral_travel():
    return abs((T.player().get_actor_location()-attack_start).dot(attack_right))


def mark_facing(stage):
    global facing_initial, facing_committed
    if stage == 'initial':facing_initial=T.player().get_actor_rotation().yaw
    else:facing_committed=T.player().get_actor_rotation().yaw
    return True


def turn_since(stage):
    ref=facing_initial if stage=='initial' else facing_committed
    return abs((T.player().get_actor_rotation().yaw-ref+180)%360-180)


def shift_boss(side):
    p=T.player()
    b=p.get_editor_property('LockOnTarget')
    b.set_actor_location(b.get_actor_location()+p.get_actor_right_vector()*side,False,False)
    return True


def place_boss(distance):
    p=T.player()
    b=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(T.world(),unreal.Actor)
           if 'BP_Boss_Crunch' in a.get_class().get_name())
    b.set_actor_location(p.get_actor_location()+p.get_actor_forward_vector()*distance+unreal.Vector(0,0,100),False,False)
    return True


def vertical_fov():
    import math
    p=T.player();w,h=p.get_controller().get_viewport_size()
    fov=p.get_component_by_class(unreal.CameraComponent).field_of_view
    return math.degrees(2*math.atan(math.tan(math.radians(fov/2))*h/w))


def scenario():
    TQ="__import__('TestDS3CameraControl')"
    T0="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq','tolerance':0})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    check(f'int({T0}.setup())');wait(1.1)
    check(f'int({T0}.state()==5)')
    check(f'int(abs({TQ}.vertical_fov()-43)<.3)')
    check(f'int(abs({T0}.player().get_component_by_class(unreal.SpringArmComponent).target_arm_length-400)<2)')
    check(f'int({TQ}.begin_attack())')
    key('LeftMouseButton','down');wait(.12);key('LeftMouseButton','up')
    steps.append({'action':'python_assert_number','expression':f'{T0}.state()',
                  'expected':4,'operator':'eq','tolerance':0})
    key('D','down');wait(.40);key('D','up')
    check(f'int({TQ}.attack_travel()>5)')
    check(f'int({TQ}.lateral_travel()<5)')
    wait(.65)
    check(f'int({T0}.state()==5)')
    steps.append({'action':'capture_game','name':'ds3-reference-free-attack'})
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'DS3 selected camera row and committed root driven sword attack',
            'steps':steps,'teardown':{'stop_pie':True}}


def guard_scenario():
    TQ="__import__('TestDS3CameraControl')"
    T0="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq','tolerance':0})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    check(f'int({T0}.setup_strafe())');wait(1.1)
    check(f'int({T0}.state()==5)')
    check(f'int(abs({TQ}.vertical_fov()-43)<.3)')
    check(f'int(abs({T0}.player().get_component_by_class(unreal.SpringArmComponent).target_arm_length-600)<5)')
    steps.append({'action':'capture_game','name':'ds3-reference-locked-frame'})
    key('LeftMouseButton','down');wait(.06);key('LeftMouseButton','up');wait(.16)
    check(f'int({T0}.state()==4)')
    key('RightMouseButton','down');wait(.1)
    check(f'int({T0}.state()==4)')
    check(f'int({T0}.player().get_editor_property("bGuardRequested"))')
    wait(.9);check(f'int({T0}.state()==3)')
    key('RightMouseButton','up');wait(.12)
    check(f'int({T0}.state()==5)')
    check(f'int(not {T0}.player().get_editor_property("bGuardRequested"))')
    key('LeftMouseButton','down');wait(.06);key('LeftMouseButton','up');wait(.16)
    key('RightMouseButton','down');wait(.08);key('RightMouseButton','up')
    wait(.95);check(f'int({T0}.state()==5)')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'DS3 lock composition and held guard after committed recovery',
            'steps':steps,'teardown':{'stop_pie':True}}


def cancel_scenario():
    T0="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq','tolerance':0})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    check(f'int({T0}.setup())');wait(1.1)
    check(f'int({T0}.state()==5)')
    key('LeftMouseButton','down');wait(.06);key('LeftMouseButton','up');wait(.08)
    key('SpaceBar','down');wait(.05);key('SpaceBar','up')
    check(f'int({T0}.state()==4)')
    check(f'int({T0}.player().get_editor_property("bDodgeBuffered"))')
    steps.append({'action':'python_assert_number',
                  'expression':f'{T0}.player().get_editor_property("CurrentAttackDuration")',
                  'expected':0,'operator':'eq','tolerance':2})
    wait(.12);check(f'int({T0}.state()==4)')
    wait(.36);check(f'int({T0}.state()==2)')
    check(f'int(not {T0}.player().get_editor_property("bDodgeBuffered"))')
    wait(.82);check(f'int({T0}.state()==5)')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Attack dodge cancel at separate 60 percent phase with one buffered intent',
            'steps':steps,'teardown':{'stop_pie':True}}


def steering_scenario():
    TQ="__import__('TestDS3CameraControl')"; T0="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq','tolerance':0})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    check(f'int({T0}.setup_strafe())');wait(1.1)
    check(f'int({T0}.state()==5)')
    check(f'int({TQ}.mark_facing("initial"))')
    key('LeftMouseButton','down');wait(.04);key('LeftMouseButton','up')
    check(f'int({TQ}.shift_boss(450))');wait(.08)
    check(f'int(2 < {TQ}.turn_since("initial") < 50)')
    wait(.20);check(f'int({TQ}.mark_facing("committed"))')
    check(f'int({TQ}.shift_boss(-900))');wait(.16)
    check(f'int({TQ}.turn_since("committed") < 3)')
    steps.append({'action':'capture_game','name':'attack-rotation-committed'})
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Sword startup tracking then locked rotation despite moving target',
            'steps':steps,'teardown':{'stop_pie':True}}


def range_scenario():
    TQ="__import__('TestDS3CameraControl')"; T0="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq','tolerance':0})
    check(f'int({T0}.setup())');wait(1.1)
    check(f'int({TQ}.place_boss(1600))')
    check(f'int({T0}.player().call_method("ToggleLockOn") is None)')
    check(f'int({T0}.player().get_editor_property("MovementMode").value==0)')
    check(f'int({TQ}.place_boss(1200))')
    check(f'int({T0}.player().call_method("ToggleLockOn") is None)')
    check(f'int({T0}.player().get_editor_property("MovementMode").value==1)')
    wait(.8)
    check(f'int(abs({T0}.player().get_component_by_class(unreal.SpringArmComponent).target_arm_length-600)<5)')
    check(f'int({TQ}.place_boss(1700))');wait(.12)
    check(f'int({T0}.player().get_editor_property("MovementMode").value==1)')
    check(f'int({TQ}.place_boss(2100))');wait(.18)
    check(f'int({T0}.player().get_editor_property("MovementMode").value==0)')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Camera lock 15m acquisition and 20m release hysteresis',
            'steps':steps,'teardown':{'stop_pie':True}}
