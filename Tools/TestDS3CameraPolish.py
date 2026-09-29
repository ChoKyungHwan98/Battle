"""PIE acceptance checks for camera profiles, lock mark, sprint and target lifecycle."""
import unreal
import math
import TestSwordShield as T
import TestDS3CameraFraming as F


def setup():
    assert F.setup()
    assert F.place(600)
    return True


def mark():
    for w in unreal.ObjectIterator(unreal.TextBlock):
        if w.get_name() == 'LockOnMark' and '.WBP_PlayerHUD_C_' in w.get_path_name():
            return w
    raise AssertionError('Runtime HUD lock mark not found')


def visible():
    return mark().get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE


def mark_error():
    p=T.player();pc=p.get_controller()
    projected=unreal.WidgetLayoutLibrary.project_world_location_to_widget_position(
        pc,p.get_editor_property('LockAimPoint'),True)
    return (mark().get_editor_property('slot').get_position()-projected).length()


def arm():
    return T.player().get_component_by_class(unreal.SpringArmComponent).target_arm_length


def pivot():
    return T.player().get_component_by_class(unreal.SpringArmComponent).target_offset.z


def vfov():
    p=T.player();w,h=p.get_controller().get_viewport_size()
    hf=p.get_component_by_class(unreal.CameraComponent).field_of_view
    return math.degrees(2*math.atan(math.tan(math.radians(hf/2))*h/w))


def locked():
    return T.player().get_editor_property('LockOnTarget') is not None


def rear_camera():
    p=T.player()
    p.get_controller().set_control_rotation(unreal.Rotator(yaw=p.get_actor_rotation().yaw+180,pitch=-8))
    return True


def yaw_error():
    p=T.player()
    return abs((p.get_controller().get_control_rotation().yaw-p.get_actor_rotation().yaw+180)%360-180)


def health(value):
    b=F.boss()
    unreal.GameplayStatics.apply_damage(b,max(0,b.get_editor_property('CurrentHealth')-value),
                                      None,T.player(),unreal.DamageType)
    return True


def torso_error():
    p=T.player()
    return (p.get_editor_property('LockAimPoint')-F.boss().mesh.get_socket_location('spine_03')).length()


def scenario():
    Q="__import__('TestDS3CameraPolish')";FQ="__import__('TestDS3CameraFraming')"
    TQ="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(t):steps.append({'action':'wait','seconds':t})
    def key(k,e):steps.append({'action':'inject_key','key':k,'event':e})
    def click(k):key(k,'down');wait(.06);key(k,'up');wait(.15)
    def capture(n):steps.append({'action':'capture_game','name':n});wait(.4)
    check(f'{Q}.setup()');wait(.7)
    check(f'not {Q}.visible()');check(f'abs({Q}.arm()-400)<2')
    check(f'abs({Q}.pivot()-52)<2');check(f'abs({Q}.vfov()-43)<.3')
    click('MiddleMouseButton');wait(.7)
    check(f'{Q}.locked()');check(f'{Q}.visible()')
    check(f'abs({Q}.arm()-550)<2');check(f'abs({Q}.pivot()-92)<2')
    check(f'{Q}.torso_error()<15');check(f'{Q}.mark_error()<2')
    capture('gundyr-reference-lock-mark')
    key('W','down');key('SpaceBar','down');wait(.48)
    check(f'{TQ}.player().get_editor_property("bIsSprinting")')
    check(f'not {Q}.locked()');check(f'not {Q}.visible()')
    check(f'abs({Q}.arm()-550)<5');check(f'abs({Q}.pivot()-92)<3')
    check(f'abs({Q}.vfov()-43)<.3')
    capture('sprint-free-camera-no-lock-mark')
    key('SpaceBar','up');key('W','up');wait(.5)
    check(f'{Q}.locked()');check(f'{Q}.visible()');check(f'{Q}.mark_error()<2')
    click('MiddleMouseButton');check(f'not {Q}.locked()')
    # No target in view: same button resets camera behind player.
    check(f'{FQ}.place(600)');check(f'{Q}.rear_camera()');wait(.15)
    click('MiddleMouseButton');check(f'not {Q}.locked()');check(f'{Q}.yaw_error()<3')
    wait(.2);click('MiddleMouseButton');wait(.7)
    check(f'{Q}.locked()');check(f'{Q}.visible()')
    check(f'{FQ}.place(1700)');wait(.4)
    check(f'not {Q}.locked()');check(f'not {Q}.visible()')
    # Use the damage event rather than overriding an instance-restricted property.
    check(f'{FQ}.place(600)');click('MiddleMouseButton');wait(.3)
    check(f'{Q}.locked()');check(f'{Q}.health(0)');wait(.3)
    check(f'not {Q}.locked()');check(f'not {Q}.visible()')
    click('MiddleMouseButton');check(f'not {Q}.locked()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'DS3 camera and Gundyr framing, lock mark, sprint and reset lifecycle',
            'steps':steps,'teardown':{'stop_pie':True}}


def saved_target_scenario():
    Q="__import__('TestDS3CameraPolish')";FQ="__import__('TestDS3CameraFraming')"
    TQ="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(t):steps.append({'action':'wait','seconds':t})
    check(f'{Q}.setup()');wait(.7);check(f'{FQ}.lock()');wait(.5)
    check(f'{TQ}.player().call_method("SetSprinting",(True,)) is None');wait(.1)
    check(f'not {Q}.locked()');check(f'not {Q}.visible()')
    check(f'{FQ}.place(1700)')
    check(f'{TQ}.player().call_method("SetSprinting",(False,)) is None');wait(.2)
    check(f'not {Q}.locked()')
    check(f'{TQ}.player().get_editor_property("SprintResumeLockTarget") is None')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Sprint discards saved lock target that leaves range',
            'steps':steps,'teardown':{'stop_pie':True}}
