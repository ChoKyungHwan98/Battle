"""Screen bounds at actual minimum contact, side views and changing range."""
import unreal
import json
import math
import TestSwordShield as T
import TestDS3CameraFraming as F

frames=[]
stats=[]
handle=None


def setup():
    frames.clear();stats.clear()
    assert T.setup()
    # Idle presentation, allowing the component animation to tick normally.
    b=F.boss();b.mesh.get_anim_instance().montage_stop(.1)
    return True


def frame(label):
    p,b=T.player(),F.boss();pc=p.get_controller();w,h=pc.get_viewport_size()
    cam=p.get_component_by_class(unreal.CameraComponent);arm=p.get_component_by_class(unreal.SpringArmComponent)
    def point(mesh,name):
        xy=pc.project_world_location_to_screen(mesh.get_socket_location(name),True)
        return [xy.x/w,xy.y/h] if xy else [-99,-99]
    rot=pc.get_control_rotation()
    data={'label':label,'distance':p.get_horizontal_distance_to(b),
          'pitch':rot.pitch,'camera_z':cam.get_world_location().z-p.get_actor_location().z,
          'arm':arm.target_arm_length,'actual_arm':(cam.get_world_location()-arm.get_world_location()-arm.target_offset).length(),
          'fov':cam.field_of_view,'player_head':point(p.mesh,'head'),
          'player_foot_l':point(p.mesh,'foot_l'),'player_foot_r':point(p.mesh,'foot_r'),
          'boss_head':point(b.mesh,'head'),'boss_foot_l':point(b.mesh,'foot_l'),
          'boss_foot_r':point(b.mesh,'foot_r'),'boss_chest':point(b.mesh,'spine_03')}
    frames.append(data);print('FRAME',json.dumps(data))
    return True


def bounds_ok():
    d=frames[-1]
    return (abs(d['arm']-650)<.1 and abs(d['actual_arm']-650)<1 and d['pitch']<=.15 and
            d['boss_head'][1]>.065 and max(d['boss_foot_l'][1],d['boss_foot_r'][1])<.92 and
            max(d['player_foot_l'][1],d['player_foot_r'][1])<.94 and
            .45<d['player_head'][1]<.75 and .23<d['boss_chest'][1]<.60)


def observe():
    global handle
    def tick(dt):
        p=T.player()
        if p:
            arm=p.get_component_by_class(unreal.SpringArmComponent)
            cam=p.get_component_by_class(unreal.CameraComponent)
            stats.append([p.get_horizontal_distance_to(F.boss()),p.get_controller().get_control_rotation().pitch,
                          arm.target_arm_length,cam.field_of_view])
    handle=unreal.register_slate_post_tick_callback(tick)
    return True


def end_observe():
    global handle
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    return True


def no_zoom():
    return len(stats)>20 and all(abs(d[2]-650)<.1 for d in stats) and max(d[3] for d in stats)-min(d[3] for d in stats)<.01


def contact_distance():
    p,b=T.player(),F.boss()
    print('CONTACT_DISTANCE',p.get_horizontal_distance_to(b))
    return 150<p.get_horizontal_distance_to(b)<350


def side_camera(degrees):
    p,b=T.player(),F.boss()
    origin=b.get_actor_location();r=p.get_horizontal_distance_to(b)
    phi=math.atan2(p.get_actor_location().y-origin.y,p.get_actor_location().x-origin.x)+math.radians(degrees)
    old=p.get_actor_location()
    p.set_actor_location(unreal.Vector(origin.x+r*math.cos(phi),origin.y+r*math.sin(phi),old.z),False,False)
    return True


def save():
    end_observe()
    path=unreal.Paths.project_saved_dir()+'VibeUE/close-lock-framing.json'
    with open(path,'w',encoding='utf-8') as stream:json.dump({'frames':frames,'samples':stats},stream,indent=2)
    print('SAVED:',path)
    return True


def scenario():
    Q="__import__('TestCloseLockFraming')";G="__import__('TestDS3CameraFraming')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    def shot(name):steps.append({'action':'capture_game','name':name})
    check(f'{Q}.setup()');wait(.6);check(f'{G}.place(600)');check(f'{G}.lock()');wait(1)
    check(f'{Q}.frame("mid-600")');check(f'{Q}.bounds_ok()');shot('mid-ground-visible')
    check(f'{Q}.observe()');wait(.4)
    steps.append({'action':'inject_key','key':'W','event':'down'});wait(1.8)
    steps.append({'action':'inject_key','key':'W','event':'up'});wait(.4)
    check(f'{Q}.contact_distance()');check(f'{Q}.frame("actual-contact")');check(f'{Q}.bounds_ok()');shot('actual-contact-ground-visible')
    check(f'{Q}.side_camera(90)');wait(1)
    check(f'{Q}.frame("contact-side")');check(f'{Q}.bounds_ok()');shot('contact-side-ground-visible')
    check(f'{Q}.side_camera(90)');wait(1)
    check(f'{Q}.frame("contact-back")');check(f'{Q}.bounds_ok()');shot('contact-back-ground-visible')
    check(f'{G}.place(1000)');wait(1)
    check(f'{Q}.frame("far-1000")');check(f'{Q}.bounds_ok()');shot('far-ground-visible')
    check(f'{Q}.no_zoom()');check(f'{Q}.save()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Close lock framing at physical contact without zoom or upward pitch',
      'dependencies':['Tools/TestCloseLockFraming.py','Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset'],
      'steps':steps,'teardown':{'stop_pie':True}}
