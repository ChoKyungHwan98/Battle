"""Transient PIE camera stability checks including real sprint input and walls."""
import unreal
import json
import TestSwordShield as T
import TestDS3CameraFraming as F

samples=[]
handle=None
baseline=None



def camera():
    p=T.player();arm=p.get_component_by_class(unreal.SpringArmComponent)
    cam=p.get_component_by_class(unreal.CameraComponent)
    pivot=arm.get_world_location()+arm.target_offset
    return {'arm':arm.target_arm_length, 'pivot':arm.target_offset.z,
            'fov':cam.field_of_view, 'distance':(cam.get_world_location()-pivot).length(),
            'lag':arm.enable_camera_lag}


def setup():
    samples.clear()
    assert F.setup()
    return True


def observe():
    global handle
    def tick(dt):
        if T.world():samples.append(camera())
    handle=unreal.register_slate_post_tick_callback(tick)
    return True


def stable():
    print('CAMERA_SAMPLES',len(samples), 'arm',min(s['arm'] for s in samples),max(s['arm'] for s in samples),
          'actual',min(s['distance'] for s in samples),max(s['distance'] for s in samples))
    return len(samples)>30 and all(abs(s['arm']-650)<.1 and abs(s['distance']-650)<1 and
        abs(s['pivot']-92)<.1 and not s['lag'] for s in samples) and \
        max(s['fov'] for s in samples)-min(s['fov'] for s in samples)<.01


def save():
    global handle
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    path=unreal.Paths.project_saved_dir()+'VibeUE/stable-lock-camera.json'
    with open(path,'w',encoding='utf-8') as stream:json.dump(samples,stream,indent=2)
    print('SAVED:',path)
    return True


def record(label):
    assert F.record(label)
    print('CAMERA',camera())
    return True


def scenario():
    Q="__import__('TestStableLockCamera')";G="__import__('TestDS3CameraFraming')";U="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(expr):steps.append({'action':'python_assert_number','expression':f'int({expr})','expected':1,'operator':'eq'})
    def wait(seconds):steps.append({'action':'wait','seconds':seconds})
    def key(name,event):steps.append({'action':'inject_key','key':name,'event':event})
    def capture(name):steps.append({'action':'capture_game','name':name})
    check(f'{Q}.setup()');wait(.6);check(f'{G}.place(600)');wait(.4)
    check(f'{Q}.observe()');check(f'{Q}.record("free-650")');capture('free-fixed-650')
    check(f'{G}.lock()');wait(1)
    check(f'{Q}.record("lock-600")');capture('lock-fixed-650-mid')
    check(f'{G}.place(300)');wait(.6);check(f'{Q}.record("lock-300")');capture('lock-fixed-650-near')
    check(f'{G}.place(1000)');wait(.6);check(f'{Q}.record("lock-1000")')
    check(f'{G}.unlock()');wait(.3);check(f'{G}.lock()');wait(.5)
    wait(.4);key('W','down');key('SpaceBar','down');wait(.48)
    check(f'{U}.player().get_editor_property("bIsSprinting")')
    check(f'{U}.player().get_editor_property("LockOnTarget") is None')
    check(f'{U}.player().get_editor_property("SprintResumeLockTarget") is not None')
    wait(.4);check(f'{Q}.record("sprint")');capture('sprint-fixed-650')
    key('SpaceBar','up');key('W','up');wait(.5)
    check(f'{U}.player().get_editor_property("LockOnTarget") is not None')
    check(f'{Q}.stable()');check(f'{Q}.save()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Stable 650cm free lock sprint distance and unchanged FOV',
      'dependencies':['Tools/TestStableLockCamera.py','Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset'],
      'steps':steps,'teardown':{'stop_pie':True}}


def mark_wall_distance():
    global baseline
    baseline=camera()['distance']
    return baseline>640


def wall_scenario():
    Q="__import__('TestStableLockCamera')";G="__import__('TestDS3CameraFraming')"
    def check(expr):return {'action':'python_assert_number','expression':f'int({expr})','expected':1,'operator':'eq'}
    return {'name':'Stable camera retains wall obstruction protection',
      'steps':[check(f'{G}.prepare_wall()'),{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
        check(f'{Q}.setup()'),{'action':'wait','seconds':.6},check(f'{G}.place(600)'),check(f'{G}.lock()'),
        {'action':'wait','seconds':.8},check(f'{Q}.mark_wall_distance()'),check(f'{G}.spawn_wall_behind()'),
        {'action':'wait','seconds':.3},check(f'{Q}.camera()["distance"] < {Q}.baseline*.8'),
        {'action':'capture_game','name':'locked-wall-obstruction'},check(f'{G}.remove_wall()'),
        {'action':'wait','seconds':.5},check(f'abs({Q}.camera()["distance"]-650)<1')],
      'teardown':{'stop_pie':True}}
