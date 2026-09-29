"""Measure restored root displacement and collision in transient PIE fixtures."""
import json
import math
import unreal
import TestSwordShield as T
import TestSoulsHits as H
from RestoreSwordForwardMotion import SOURCE, SUFFIXES

profiles = []
cube = None
handle = None
samples = []
reports = []
kind = ''
number = 0
origin = None
forward = None
started = 0
done = False


def cache():
    global profiles, cube
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    profiles = []
    for suffix in SUFFIXES:
        roots = [next(b.transform.translation.y for b in unreal.AnimSequenceService.get_pose_at_time(SOURCE+suffix,f/30,False)
                      if str(b.bone_name) == 'Root') for f in range(40)]
        profiles.append([y-roots[0] for y in roots])
    cube = unreal.load_object(None,'/Engine/BasicShapes/Cube.Cube')
    return 1


def prepare(mode='free', attack=3):
    global kind, number
    kind, number = mode, attack
    unreal.PIEActorService.destroy_all()
    p = T.player()
    p.character_movement.stop_movement_immediately()
    p.set_actor_location(unreal.Vector(0,0,p.get_actor_location().z),False,False)
    p.set_actor_rotation(unreal.Rotator(yaw=0),False)
    p.get_controller().set_control_rotation(unreal.Rotator(yaw=0))
    if mode == 'boss':
        H.start = None
        H.setup(205)
        # H.setup's old fixed +108cm offset floats a scaled Crunch above the floor.
        # Align both scaled capsule bottoms before asserting horizontal separation.
        boss = H.boss()
        floor = p.get_actor_location().z-p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
        loc = boss.get_actor_location()
        boss.set_actor_location(unreal.Vector(loc.x,loc.y,floor+boss.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()),False,False)
    else:
        T.setup()
    if mode == 'wall':
        assert cube
        out = json.loads(unreal.PIEActorService.spawn_actor('server','/Script/Engine.StaticMeshActor',unreal.Transform()))
        blocker = unreal.find_object(None,out['actor_path'])
        assert blocker
        c = blocker.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_static_mesh(cube)
        c.set_collision_profile_name('BlockAll')
        blocker.set_actor_scale3d(unreal.Vector(.4,6,6))
        blocker.set_actor_location(unreal.Vector(190,0,200),False,False)
    p.set_editor_property('AttackMontages',[p.get_editor_property('AttackMontages')[attack-1]])
    return 1


def expected(position):
    f = min(max(position*30,0),39)
    lo, hi = int(math.floor(f)), int(math.ceil(f))
    return profiles[number-1][lo]+(profiles[number-1][hi]-profiles[number-1][lo])*(f-lo)


def begin():
    global handle, samples, origin, forward, started, done
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
    p = T.player()
    origin, forward, samples, done = p.get_actor_location(), p.get_actor_forward_vector(), [], False
    started = unreal.GameplayStatics.get_time_seconds(T.world())
    p.call_method('TryEnterAttack')
    assert T.state() == 4
    handle = unreal.register_slate_post_tick_callback(tick)
    return 1


def tick(delta):
    global done
    if not T.world() or done:
        return
    p = T.player()
    a = p.mesh.get_anim_instance()
    m = a.get_current_active_montage()
    if m and 'AM_Sword_Attack_' in m.get_name():
        pos = a.montage_get_position(m)
        travel = p.get_actor_location()-origin
        samples.append({'position':pos,'travel':travel.dot(forward),'expected':expected(pos),
                        'location':p.get_actor_location().to_tuple()})
    elif T.state() == 5:
        done = True


def report():
    global handle
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    if not samples:
        return 0
    relevant = [s for s in samples if .08 < s['position'] < 1.15]
    error = max(abs(s['travel']-s['expected']) for s in relevant)
    last = samples[-1]
    ok = done and T.state() == 5
    if kind == 'free':
        ok = ok and error < 5 and abs(last['travel']-last['expected']) < 5
    elif kind == 'wall':
        # Wall front x=170, player capsule radius about35. Capsule must stay before it.
        ok = ok and max(s['location'][0] for s in samples) < 136 and last['travel'] > 20
    elif kind == 'boss':
        b = H.boss()
        min_radius = p_radius(T.player())+p_radius(b)
        closest = min((unreal.Vector(s['location'][0]-b.get_actor_location().x,
                                   s['location'][1]-b.get_actor_location().y,0)).length() for s in samples)
        ok = ok and closest >= min_radius-2 and last['travel'] < profiles[number-1][-1]*.8
    metrics = {'mode':kind,'number':number,'passed':bool(ok),'source_total_cm':profiles[number-1][-1],
               'measured_cm':last['travel'],'expected_at_last_pose_cm':last['expected'],
               'max_curve_error_cm':error,'last_pose_time':last['position']}
    if kind == 'boss':
        metrics.update({'closest_horizontal_cm':closest,'capsule_radius_sum_cm':min_radius})
    reports.append({'metrics':metrics,'samples':samples})
    with open(unreal.Paths.project_saved_dir()+'VibeUE/sword-forward-pie.json','w',encoding='utf-8') as f:
        json.dump(reports,f,indent=2)
    print('ROOT_MOTION',json.dumps(metrics))
    return int(ok)


def p_radius(actor):
    return actor.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_radius()


def scenario():
    q='__import__("TestSwordForwardMotion")'
    steps=[]
    for mode,n in [('free',1),('free',2),('free',3),('free',4),('wall',1),('boss',1)]:
        steps += [{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
                  {'action':'python_assert_number','expression':q+'.prepare('+repr(mode)+','+str(n)+')','expected':1,'operator':'eq'},
                  {'action':'wait','seconds':.8},
                  {'action':'python_assert_number','expression':q+'.begin()','expected':1,'operator':'eq'},
                  {'action':'wait','seconds':1.8},
                  {'action':'python_assert_number','expression':q+'.report()','expected':1,'operator':'eq'},
                  {'action':'stop_pie'},{'action':'wait','seconds':.15}]
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Restored four sword root curves with wall and boss collision','steps':steps,'teardown':{'stop_pie':True}}
