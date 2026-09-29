"""Real-input verification for two-character framing and lock-relative travel."""
import unreal
import json
import math
import TestSwordShield as T
import TestDS3CameraFraming as F
import TestCloseLockFraming as C

samples=[]
frames=[]
segments=[]
handle=None
active=None


def setup():
    samples.clear();frames.clear();segments.clear()
    assert C.setup()
    return True


def snapshot():
    p,b=T.player(),F.boss();pc=p.get_controller()
    cam=p.get_component_by_class(unreal.CameraComponent)
    arm=p.get_component_by_class(unreal.SpringArmComponent)
    v=p.get_velocity();q=b.get_actor_location()-p.get_actor_location();q.z=0
    r=q.length();radial=q/r;right=unreal.Vector(-radial.y,radial.x,0)
    inp=p.get_last_movement_input_vector()
    return {'time':unreal.GameplayStatics.get_time_seconds(T.world()),'distance':r,
      'angle':math.degrees(math.atan2(q.y,q.x)),'speed':v.length(),
      'input_radial':inp.dot(radial),'input_tangent':inp.dot(right),
      'velocity_radial':v.dot(radial),'velocity_tangent':v.dot(right),
      'pitch':pc.get_control_rotation().pitch,'yaw':pc.get_control_rotation().yaw,
      'fov':cam.field_of_view,'arm':arm.target_arm_length,'side':arm.socket_offset.y,
      'frame_player':p.get_editor_property('FramePlayerY'),
      'frame_boss':p.get_editor_property('FrameBossY'),
      'frame_boss_x':p.get_editor_property('FrameBossX'),
      'frame_top':p.get_editor_property('FrameTopY'),'frame_bottom':p.get_editor_property('FrameBottomY'),
      'locked':p.get_editor_property('LockOnTarget') is not None}


def begin(label):
    global handle,active
    active={'label':label,'first':snapshot(),'start':len(samples)}
    def tick(dt):
        if T.world():samples.append(snapshot())
    handle=unreal.register_slate_post_tick_callback(tick)
    return True


def end():
    global handle,active
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    active['last']=snapshot();active['samples']=samples[active['start']:]
    segments.append(active)
    print('SEGMENT:',active['label'],'distance',active['first']['distance'],active['last']['distance'],
          'angle',active['first']['angle'],active['last']['angle'],'samples',len(active['samples']))
    active=None
    return True


def tangent(sign):
    d=segments[-1];r0=d['first']['distance'];r1=d['last']['distance']
    angle=(d['last']['angle']-d['first']['angle']+180)%360-180
    vals=[s for s in d['samples'] if s['speed']>150 and abs(s['input_tangent'])>.7]
    # Integration/acceleration can drift a little; no teleport/radius snapping.
    return (len(vals)>15 and angle*-sign>25 and abs(r1-r0)<r0*.05 and
      all(abs(s['input_radial'])<.28 and s['input_tangent']*sign>.8 for s in vals) and
      all(s['locked'] and .12<s['frame_boss_x']<.86 for s in vals))


def radial(sign):
    d=segments[-1]
    vals=[s for s in d['samples'] if s['speed']>100 and abs(s['input_radial'])>.7]
    return len(vals)>8 and (d['first']['distance']-d['last']['distance'])*sign>55 and \
      all(s['input_radial']*sign>.8 and abs(s['input_tangent'])<.10 for s in vals)


def frame(label):
    C.frame(label);d=C.frames[-1].copy();d.update(snapshot());frames.append(d)
    return True


def visible():
    d=frames[-1]
    points=[d[n] for n in ['player_head','player_foot_l','player_foot_r','boss_head','boss_foot_l','boss_foot_r']]
    return (all(.05<x<.95 and .06<y<.94 for x,y in points) and
      .64<d['frame_player']<.76 and .26<d['frame_boss']<.44 and
      .465<d['frame_boss_x']<.495 and abs(d['arm']-650)<.1)


def still_stable():
    d=segments[-1]['samples']
    return len(d)>20 and max(s['pitch'] for s in d)-min(s['pitch'] for s in d)<.2 and \
      max(s['yaw'] for s in d)-min(s['yaw'] for s in d)<.2


def no_zoom():
    return len(samples)>30 and all(abs(s['arm']-650)<.1 for s in samples) and \
      max(s['fov'] for s in samples)-min(s['fov'] for s in samples)<.01


def save():
    path=unreal.Paths.project_saved_dir()+'VibeUE/lock-relation-evidence.json'
    with open(path,'w',encoding='utf-8') as f:json.dump({'frames':frames,'segments':segments},f,indent=2)
    print('SAVED:',path)
    return True


def scenario():
    Q="__import__('TestLockRelation')";G="__import__('TestDS3CameraFraming')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':f'int({e})','expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    def key(k,e):steps.append({'action':'inject_key','key':k,'event':e})
    def shot(name):steps.append({'action':'capture_game','name':name})
    check(f'{Q}.setup()');wait(.8);check(f'{G}.place(500)');check(f'{G}.lock()');wait(1.4)
    check(f'{Q}.frame("mid-500")');check(f'{Q}.visible()');shot('two-character-mid')
    wait(.4);check(f'{Q}.begin("right-orbit")');key('D','down');wait(2);key('D','up');wait(.2)
    check(f'{Q}.end()');check(f'{Q}.tangent(1)');wait(.8)
    check(f'{Q}.frame("right-orbit-end")');check(f'{Q}.visible()');shot('right-orbit')
    wait(.4);check(f'{Q}.begin("left-orbit")');key('A','down');wait(2);key('A','up');wait(.2)
    check(f'{Q}.end()');check(f'{Q}.tangent(-1)');wait(.8)
    check(f'{Q}.frame("left-orbit-end")');check(f'{Q}.visible()')
    check(f'{Q}.begin("approach")');key('W','down');wait(.5);key('W','up');wait(.2)
    check(f'{Q}.end()');check(f'{Q}.radial(1)');wait(.7)
    check(f'{Q}.begin("retreat")');key('S','down');wait(.5);key('S','up');wait(.2)
    check(f'{Q}.end()');check(f'{Q}.radial(-1)')
    for distance in [300,1000]:
        check(f'{G}.place({distance})');wait(1.4)
        check(f'{Q}.frame("range-{distance}")');check(f'{Q}.visible()');shot(f'two-character-{distance}')
    check(f'{G}.place(600)');wait(1);wait(.4)
    key('W','down');wait(1.8);key('W','up');wait(1)
    check(f'{Q}.frame("minimum-contact")');check(f'{Q}.visible()');shot('two-character-contact')
    wait(.4);check(f'{Q}.begin("idle-stability")');wait(1.5);check(f'{Q}.end()');check(f'{Q}.still_stable()')
    check(f'{Q}.no_zoom()');check(f'{Q}.save()')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Target-relative W S A D with two-character framing at contact and range',
      'dependencies':['Tools/TestLockRelation.py','Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset'],
      'steps':steps,'teardown':{'stop_pie':True}}
