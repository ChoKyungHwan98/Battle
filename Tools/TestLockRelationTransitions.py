"""Diagonal basis, free/sprint restoration, and camera obstruction regressions."""
import unreal
import math
import TestSwordShield as T
import TestDS3CameraFraming as F

baseline=None
start_fov=None


def setup():
    global start_fov
    assert T.setup()
    F.boss().mesh.get_anim_instance().montage_stop(.1)
    start_fov=T.player().get_component_by_class(unreal.CameraComponent).field_of_view
    return True


def diagonal(x,y):
    p,b=T.player(),F.boss();d=b.get_actor_location()-p.get_actor_location();d.z=0;d=d/d.length()
    right=unreal.Vector(-d.y,d.x,0);v=p.get_last_movement_input_vector()
    radial=v.dot(d);tangent=v.dot(right)
    print('DIAGONAL:',x,y,radial,tangent,p.get_velocity().length())
    return (radial*y>.6 and tangent*x>.6 and p.get_velocity().length()>150 and
            p.get_velocity().length()<=p.character_movement.max_walk_speed+1 and
            abs(p.get_editor_property('OrbitBias'))<.001)


def skew_camera():
    p=T.player();r=p.get_controller().get_control_rotation()
    p.get_controller().set_control_rotation(unreal.Rotator(pitch=r.pitch,yaw=r.yaw+65))
    return True


def radial_while_camera_lags():
    p,b=T.player(),F.boss();d=b.get_actor_location()-p.get_actor_location();d.z=0;d=d/d.length()
    inp=p.get_last_movement_input_vector()
    return inp.dot(d)>.98


def free_forward():
    p=T.player();yaw=math.radians(p.get_controller().get_control_rotation().yaw)
    forward=unreal.Vector(math.cos(yaw),math.sin(yaw),0)
    return p.get_last_movement_input_vector().dot(forward)>.98


def lens():
    p=T.player();arm=p.get_component_by_class(unreal.SpringArmComponent);cam=p.get_component_by_class(unreal.CameraComponent)
    return abs(arm.target_arm_length-650)<.1 and abs(cam.field_of_view-start_fov)<.01


def side(value):
    return abs(T.player().get_component_by_class(unreal.SpringArmComponent).socket_offset.y-value)<1


def mark():
    global baseline
    p=T.player();arm=p.get_component_by_class(unreal.SpringArmComponent);cam=p.get_component_by_class(unreal.CameraComponent)
    baseline=(cam.get_world_location()-arm.get_world_location()-arm.target_offset).length()
    return baseline>640


def obstructed():
    p=T.player();arm=p.get_component_by_class(unreal.SpringArmComponent);cam=p.get_component_by_class(unreal.CameraComponent)
    return (cam.get_world_location()-arm.get_world_location()-arm.target_offset).length()<baseline*.8


def restored():
    p=T.player();arm=p.get_component_by_class(unreal.SpringArmComponent);cam=p.get_component_by_class(unreal.CameraComponent)
    return abs((cam.get_world_location()-arm.get_world_location()-arm.target_offset).length()-baseline)<1


def scenario():
    Q="__import__('TestLockRelationTransitions')";G="__import__('TestDS3CameraFraming')";U="__import__('TestSwordShield')"
    steps=[]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    def key(k,e):steps.append({'action':'inject_key','key':k,'event':e})
    check(f'{G}.prepare_wall()')
    steps += [{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    check(f'{Q}.setup()');wait(.8);check(f'{G}.place(600)');check(f'{G}.lock()');wait(1.2)
    for x,y in [(1,1),(-1,1),(1,-1),(-1,-1)]:
        check(f'{G}.place(600)');wait(.5)
        sx='D' if x>0 else 'A';sy='W' if y>0 else 'S'
        key(sx,'down');key(sy,'down');wait(.3);check(f'{Q}.diagonal({x},{y})')
        key(sx,'up');key(sy,'up');wait(.3)
    check(f'{Q}.skew_camera()');key('W','down');wait(.12)
    check(f'{Q}.radial_while_camera_lags()');key('W','up');wait(.5)
    check(f'{G}.place(900)');wait(1);wait(.4)
    key('W','down');key('SpaceBar','down');wait(.55)
    check(f'{U}.player().get_editor_property("bIsSprinting")')
    check(f'{U}.player().get_editor_property("LockOnTarget") is None')
    check(f'{U}.player().get_editor_property("SprintResumeLockTarget") is not None')
    check(f'{Q}.side(-55)');check(f'{Q}.lens()')
    key('SpaceBar','up');key('W','up');wait(.8)
    check(f'{U}.player().get_editor_property("LockOnTarget") is not None')
    check(f'{Q}.lens()');check(f'{G}.unlock()');wait(1.1);check(f'{Q}.side(0)')
    key('W','down');wait(.25);check(f'{Q}.free_forward()');check(f'{Q}.lens()');key('W','up');wait(.3)
    check(f'{G}.place(600)');check(f'{G}.lock()');wait(1.2);check(f'{Q}.mark()')
    check(f'{G}.spawn_wall_behind()');wait(.4);check(f'{Q}.obstructed()')
    steps.append({'action':'capture_game','name':'wall-protection'})
    check(f'{G}.remove_wall()');wait(.8);check(f'{Q}.restored()');check(f'{Q}.lens()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Lock diagonals independent of camera yaw, sprint restore and wall protection',
      'dependencies':['Tools/TestLockRelationTransitions.py','Tools/TestLockRelation.py',
                      'Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset'],
      'steps':steps,'teardown':{'stop_pie':True}}
