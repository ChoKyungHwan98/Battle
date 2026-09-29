"""Observe unmodified boss AI approaching from just outside its close-attack band."""
import json
import unreal
import TestSoulsHits as T

observer = None
samples = []
initial_health = 0


def begin(distance=320):
    global observer, samples, initial_health
    assert observer is None
    p, b = T.player(), T.boss()
    p.set_editor_property('MaxHealth', 2000)
    if p.get_editor_property('CurrentHealth') < 2000:
        unreal.GameplayStatics.apply_damage(p, -2000, None, None, unreal.DamageType)
    initial_health = p.get_editor_property('CurrentHealth')
    delta_z = (b.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height() -
               p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height())
    b.set_actor_location(p.get_actor_location() + p.get_actor_forward_vector()*distance +
                         unreal.Vector(0, 0, delta_z), False, False)
    b.set_actor_rotation(unreal.Rotator(yaw=(p.get_actor_rotation().yaw+180)%360), False)
    samples = []
    def tick(dt):
        if not T.world():
            return
        samples.append({'t': unreal.GameplayStatics.get_time_seconds(T.world()),
                        'distance': p.get_horizontal_distance_to(b),
                        'hp': p.get_editor_property('CurrentHealth'),
                        'decision': b.get_editor_property('UtilityDecisionCount'),
                        'action': b.get_editor_property('UtilityAction'),
                        'speed': b.get_component_by_class(unreal.CharacterMovementComponent).max_walk_speed,
                        'velocity': b.get_velocity().length(),
                        'move_mode': str(b.get_component_by_class(unreal.CharacterMovementComponent).movement_mode),
                        'actor_tick': b.is_actor_tick_enabled(),
                        'move_tick': b.get_component_by_class(unreal.CharacterMovementComponent).is_component_tick_enabled(),
                        'boss_pos': b.get_actor_location().to_tuple(),
                        'player_pos': p.get_actor_location().to_tuple(),
                        'choice': b.get_editor_property('UtilityChoice'),
                        'state': b.get_editor_property('BossState').export_text()})
    observer = unreal.register_slate_post_tick_callback(tick)
    return 1


def finish():
    global observer
    assert observer is not None
    unreal.unregister_slate_post_tick_callback(observer)
    observer = None
    stable = [x for x in samples if x['t'] >= samples[0]['t']+.6]
    assert stable
    result = {'start_distance': samples[0]['distance'],
              'min_distance': min(x['distance'] for x in samples),
              'last_distance': samples[-1]['distance'],
              'decisions': samples[-1]['decision']-samples[0]['decision'],
              'damage': stable[0]['hp']-min(x['hp'] for x in stable),
              'choices': sorted(set(x['choice'] for x in samples))}
    path = unreal.Paths.project_saved_dir()+'VibeUE/boss-natural-engagement.json'
    with open(path, 'w', encoding='utf-8') as out:
        json.dump({'result': result, 'samples': samples}, out, indent=2)
    print('NATURAL_AI', json.dumps(result))
    return int(result['decisions'] > 0 and result['min_distance'] <= 285 and result['damage'] > 0)


def probe():
    p, b = T.player(), T.boss()
    capsule = b.get_component_by_class(unreal.CapsuleComponent)
    start = b.get_actor_location()
    target = unreal.Vector(p.get_actor_location().x, p.get_actor_location().y, start.z)
    hit = unreal.SystemLibrary.capsule_trace_single(
        T.world(), start, target, capsule.get_scaled_capsule_radius(),
        capsule.get_scaled_capsule_half_height(), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        False, [b], unreal.DrawDebugTrace.NONE, True)
    print('APPROACH_PROBE', hit.export_text()[:1600] if hit else 'NO BLOCKER',
          'start', start, 'target', target)
    return 1


def scenario():
    q = "__import__('TestBossNaturalEngage')"
    return {'name': 'Existing boss AI closes 320cm gap and lands a chosen attack',
            'steps': [{'action': 'start_pie'},
                      {'action': 'wait_for_pie', 'timeout_seconds': 20},
                      {'action': 'python_assert_number', 'expression': f'{q}.begin(320)',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'wait', 'seconds': 12},
                      {'action': 'python_assert_number', 'expression': f'{q}.finish()',
                       'expected': 1, 'operator': 'eq'}],
            'teardown': {'stop_pie': True}}
