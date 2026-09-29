"""Camera regression with no arbitrary DS3 screen-center target."""
import json
import unreal
import TestSwordShield as T
import TestDS3CameraFraming as F
import TestCloseLockFraming as C
import TestLockRelation as R

samples=[]
frames=[]
handle=None


def setup():
    global handle
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    samples.clear();frames.clear()
    R.segments.clear();R.samples.clear()
    return int(C.setup())


def observe():
    global handle
    def tick(dt):
        if T.world():samples.append(R.snapshot())
    handle=unreal.register_slate_post_tick_callback(tick)
    return 1


def frame(label):
    C.frame(label);data=C.frames[-1].copy();data['socket_y']=T.player().get_component_by_class(unreal.SpringArmComponent).socket_offset.y
    frames.append(data)
    return int(abs(data['socket_y'])<.01)


def orbit(sign):
    d=R.segments[-1];angle=(d['last']['angle']-d['first']['angle']+180)%360-180
    vals=[s for s in d['samples'] if s['speed']>150 and abs(s['input_tangent'])>.7]
    return int(len(vals)>15 and angle*-sign>25 and abs(d['last']['distance']-d['first']['distance'])<d['first']['distance']*.05
               and all(abs(s['input_radial'])<.28 and s['input_tangent']*sign>.8 and s['locked'] for s in vals))


def finish():
    global handle
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    path=unreal.Paths.project_saved_dir()+'VibeUE/approved-camera-evidence.json'
    with open(path,'w') as f:json.dump({'samples':samples,'frames':frames,'segments':R.segments},f,indent=2)
    print('CAMERA evidence',len(samples),'distance',min(s['arm'] for s in samples),max(s['arm'] for s in samples),
          'FOV',min(s['fov'] for s in samples),max(s['fov'] for s in samples))
    return int(len(samples)>30 and max(s['arm'] for s in samples)-min(s['arm'] for s in samples)<=1
               and max(s['fov'] for s in samples)-min(s['fov'] for s in samples)<=.1 and all(abs(s['side'])<.01 for s in samples))


def scenario():
    q="__import__('TestApprovedCamera')";g="__import__('TestDS3CameraFraming')";t="__import__('TestSwordShield')";r="__import__('TestLockRelation')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    def key(k,e):steps.append({'action':'inject_key','key':k,'event':e})
    check(f'{q}.setup()');wait(.8);check(f'{g}.place(500)');check(f'{g}.lock()');wait(1)
    check(f'{q}.observe()')
    for distance in [300,500,1000]:
        check(f'{g}.place({distance})');wait(.9);check(f'{q}.frame("range-{distance}")')
    check(f'{g}.place(500)');wait(.7)
    for k,sign in [('D',1),('A',-1)]:
        check(f'{r}.begin("orbit-{k}")');key(k,'down');wait(2);key(k,'up');wait(.2)
        check(f'{r}.end()');check(f'{q}.orbit({sign})')
    key('W','down');key('SpaceBar','down');wait(.8)
    check(f'{t}.player().get_editor_property("bIsSprinting")')
    check(f'{t}.player().get_editor_property("LockOnTarget") is None')
    check(f'{t}.player().get_editor_property("SprintResumeLockTarget") is not None')
    key('W','up');key('SpaceBar','up');wait(.5)
    check(f'{t}.player().get_editor_property("LockOnTarget") is not None')
    check(f'{q}.finish()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Camera without shoulder framing, target orbit and sprint suspension','steps':steps,'teardown':{'stop_pie':True}}
