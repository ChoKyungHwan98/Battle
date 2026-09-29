"""Measure real boss strike geometry at the AI's configured engagement distances."""
import json
import unreal
import TestSoulsHits as T

observer = None
samples = []
case = None
results = []


def begin(action, distance):
    global observer, samples, case
    assert observer is None
    b, p = T.boss(), T.player()
    a = b.get_editor_property('Actions')[action]
    case = {'action': action, 'distance': distance, 'scale':round(b.get_actor_scale3d().x,2),
            'initial_hp': p.get_editor_property('CurrentHealth')}
    samples = []
    b.call_method('RequestCombatAction', (action,))
    assert b.get_editor_property('ActiveAction') == a
    b.set_actor_tick_enabled(True)
    mesh = b.get_component_by_class(unreal.SkeletalMeshComponent)
    anim = mesh.get_anim_instance()
    sockets = ['hand_l','hand_r']
    begin_time = unreal.GameplayStatics.get_time_seconds(T.world())
    radius = p.get_component_by_class(unreal.CapsuleComponent).get_unscaled_capsule_radius()
    half_height = p.get_component_by_class(unreal.CapsuleComponent).get_unscaled_capsule_half_height()
    def tick(delta):
        if not T.world(): return
        pos = p.get_actor_location()
        gaps = {}
        relative = {}
        for socket in sockets:
            point = mesh.get_socket_location(socket)
            dx,dy,dz = point.x-pos.x, point.y-pos.y, point.z-pos.z
            lateral = max(0., (dx*dx+dy*dy)**.5-radius)
            vertical = max(0., abs(dz)-half_height)
            gaps[socket] = round((lateral*lateral+vertical*vertical)**.5,1)
            relative[socket] = [round(dx,1),round(dy,1),round(dz,1)]
        montage = anim.get_current_active_montage()
        samples.append({'t':round(unreal.GameplayStatics.get_time_seconds(T.world())-begin_time,3),
                        'pos':round(anim.montage_get_position(montage),3) if montage else -1,
                        'open':bool(b.get_editor_property('bPhysicalStrikeOpen')),
                        'strike':b.get_editor_property('PhysicalStrikeIndex'),
                        'gaps':gaps,'relative':relative,'hp':p.get_editor_property('CurrentHealth'),
                        'boss_player_cm':round((b.get_actor_location()-pos).length(),1)})
    observer = unreal.register_slate_post_tick_callback(tick)
    return 1


def finish():
    global observer
    assert observer is not None
    unreal.unregister_slate_post_tick_callback(observer)
    observer = None
    inside = [s for s in samples if s['open']]
    result = dict(case)
    closest=min((s for s in inside if s['gaps']),key=lambda s:min(s['gaps'].values()),default=None)
    result.update({'damage':case['initial_hp']-T.player().get_editor_property('CurrentHealth'),
                   'samples':len(samples),'open_samples':len(inside),
                   'min_open_gap':min((min(s['gaps'].values()) for s in inside if s['gaps']),default=None),
                   'min_open_distance':min((s['boss_player_cm'] for s in inside),default=None),
                   'first_open':inside[0]['t'] if inside else None,
                   'closest':closest})
    results.append(result)
    print('SPACING',json.dumps(result))
    return int(result['open_samples']>0)


def save():
    with open(unreal.Paths.project_saved_dir()+'VibeUE/boss-spacing-matrix.json','w',encoding='utf-8') as f:
        json.dump(results,f,indent=2)
    return 1


def prepare(distance, scale=1.8, capsule_hurt=False):
    assert T.setup(distance)
    b,p=T.boss(),T.player()
    b.set_actor_scale3d(unreal.Vector(scale,scale,scale))
    # Both capsules rest on the same floor; do not sink the smaller boss into it.
    boss_half=b.get_component_by_class(unreal.CapsuleComponent).get_unscaled_capsule_half_height()*scale
    player_half=p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    b.set_actor_location(p.get_actor_location()+unreal.Vector(distance,0,boss_half-player_half),False,False)
    p.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY,
        unreal.CollisionResponseType.ECR_BLOCK if capsule_hurt else unreal.CollisionResponseType.ECR_IGNORE)
    return 1


def scenario():
    Q="__import__('TestBossSpacing')"
    cases = [(i,d) for i in range(6) for d in (240,285)] + [(6,600)]
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
           {'action':'python_assert_number','expression':f'int(not {Q}.results.clear())','expected':1,'operator':'eq'}]
    for i,d in cases:
        expected=145 if i==4 else (160 if i in (3,5,6) else 110)
        steps += [{'action':'python_assert_number','expression':f'{Q}.prepare({d},1.3,True)','expected':1,'operator':'eq'},
                  {'action':'wait','seconds':.6},
                  {'action':'python_assert_number','expression':f'{Q}.begin({i},{d})','expected':1,'operator':'eq'},
                  {'action':'wait','seconds':7.0 if i==4 else (4.0 if i==6 else 3.1)},
                  {'action':'python_assert_number','expression':f'{Q}.finish()','expected':1,'operator':'eq'},
                  {'action':'python_assert_number','expression':f'{Q}.results[-1]["damage"]','expected':expected,'operator':'eq'},
                  {'action':'wait','seconds':4.1}]
    steps += [{'action':'python_assert_number','expression':f'{Q}.save()','expected':1,'operator':'eq'},
              {'action':'assert_log','not_contains':'LogScript: Warning'}]
    return {'name':'Boss strike contact at configured close and dash ranges',
            'steps':steps,'teardown':{'stop_pie':True}}
