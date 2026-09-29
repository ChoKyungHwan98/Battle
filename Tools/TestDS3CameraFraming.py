"""PIE camera measurements against the visible boss and player skeletons."""
import unreal
import json
import TestSwordShield as T

records=[]
cube=None


def boss():
    return next(a for a in unreal.GameplayStatics.get_all_actors_of_class(T.world(),unreal.Actor)
                if 'BP_Boss_Crunch' in a.get_class().get_name())


def setup():
    records.clear()
    return T.setup()


def place(distance):
    p=T.player();b=boss()
    boss_half=b.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    player_half=p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    b.set_actor_location(p.get_actor_location()+p.get_actor_forward_vector()*distance+
                         unreal.Vector(0,0,boss_half-player_half),False,False)
    b.set_actor_rotation(unreal.Rotator(yaw=(p.get_actor_rotation().yaw+180)%360),False)
    return True


def lock():
    p=T.player()
    if not p.get_editor_property('LockOnTarget'):p.call_method('ToggleLockOn')
    return bool(p.get_editor_property('LockOnTarget'))


def unlock():
    p=T.player()
    if p.get_editor_property('LockOnTarget'):p.call_method('ToggleLockOn')
    return not bool(p.get_editor_property('LockOnTarget'))


def record(label):
    p,b=T.player(),boss();pc=p.get_controller()
    cam=p.get_component_by_class(unreal.CameraComponent)
    arm=p.get_component_by_class(unreal.SpringArmComponent)
    pm=p.get_component_by_class(unreal.SkeletalMeshComponent)
    bm=b.get_component_by_class(unreal.SkeletalMeshComponent)
    w,h=pc.get_viewport_size()
    def screen(v):
        xy=pc.project_world_location_to_screen(v,True)
        return [round(xy.x/w,3),round(xy.y/h,3)] if xy else None
    data={'label':label,'distance':round((b.get_actor_location()-p.get_actor_location()).length(),1),
          'locked':bool(p.get_editor_property('LockOnTarget')),
          'arm':round(arm.target_arm_length,1),
          'camera_distance':round((cam.get_world_location()-p.get_actor_location()).length(),1),
          'pitch':round(pc.get_control_rotation().pitch,1),
          'fov':round(cam.field_of_view,1),
          'boss_head':screen(bm.get_socket_location('head')),
          'boss_foot':screen(bm.get_socket_location('foot_l')),
          'player_head':screen(pm.get_socket_location('head')),
          'player_foot':screen(pm.get_socket_location('foot_l')),
          'camera_collision':arm.do_collision_test,'camera_probe':arm.probe_size}
    records.append(data)
    print('FRAME',json.dumps(data))
    return True


def save():
    path=unreal.Paths.project_saved_dir()+'VibeUE/ds3-camera-frame-measurements.json'
    with open(path,'w',encoding='utf-8') as f:json.dump(records,f,indent=2)
    print('SAVED',path)
    return True


def prepare_wall():
    global cube
    cube=unreal.load_object(None,'/Engine/BasicShapes/Cube.Cube')
    return bool(cube)


def camera_distance():
    p=T.player();cam=p.get_component_by_class(unreal.CameraComponent)
    return (cam.get_world_location()-p.get_actor_location()).length()


def spawn_wall_behind():
    assert cube
    p=T.player();cam=p.get_component_by_class(unreal.CameraComponent)
    result=json.loads(unreal.PIEActorService.spawn_actor('server','/Script/Engine.StaticMeshActor',unreal.Transform()))
    assert result['success'],result
    wall=unreal.find_object(None,result['actor_path'])
    wall.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    wall.static_mesh_component.set_static_mesh(cube)
    wall.static_mesh_component.set_collision_profile_name('BlockAll')
    wall.set_actor_scale3d(unreal.Vector(.3,4,4))
    wall.set_actor_rotation(p.get_actor_rotation(),False)
    wall.set_actor_location(p.get_actor_location()+(cam.get_world_location()-p.get_actor_location())*.5,False,False)
    return True


def remove_wall():
    unreal.PIEActorService.destroy_all()
    return True


def wall_scenario():
    Q="__import__('TestDS3CameraFraming')"
    def check(expr,expected=1,op='eq'):
        return {'action':'python_assert_number','expression':expr,'expected':expected,'operator':op}
    return {'name':'Free camera spring arm contracts at wall and restores',
      'steps':[check(f'int({Q}.prepare_wall())'),
        {'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
        check(f'int({Q}.setup())'),{'action':'wait','seconds':.7},
        check(f'{Q}.camera_distance()',350,'gt'),
        check(f'int({Q}.spawn_wall_behind())'),{'action':'wait','seconds':.3},
        check(f'{Q}.camera_distance()',300,'lt'),
        {'action':'capture_game','name':'free-camera-wall-collision'},
        check(f'int({Q}.remove_wall())'),{'action':'wait','seconds':.6},
        check(f'{Q}.camera_distance()',350,'gt')],
      'teardown':{'stop_pie':True}}


def baseline_scenario():
    Q="__import__('TestDS3CameraFraming')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(expr):steps.append({'action':'python_assert_number','expression':f'int({expr})','expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    check(f'{Q}.setup()');wait(.5)
    for distance in [300,600,1000]:
        check(f'{Q}.place({distance})')
        if distance==300:check(f'{Q}.lock()')
        wait(1.0);check(f'{Q}.record("lock-{distance}")')
        steps.append({'action':'capture_game','name':f'camera-lock-{distance}'})
    check(f'{Q}.unlock()');wait(1.0);check(f'{Q}.record("free-1000")')
    steps.append({'action':'capture_game','name':'camera-free-1000'})
    check(f'{Q}.place(300)');wait(1.0);check(f'{Q}.record("free-300")')
    steps.append({'action':'capture_game','name':'camera-free-300'})
    check(f'{Q}.save()')
    return {'name':'Boss skeletal screen framing at DS3 camera ranges','steps':steps,
            'teardown':{'stop_pie':True}}
