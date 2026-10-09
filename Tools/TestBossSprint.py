"""Does the boss sprint when it runs in from far away? Run on the Arena map (autonomous AI).

Places the boss `distance` cm in front of the player and records its ground speed and the montage it plays.
Measurement only: PIE actors, nothing saved. Results: Saved/VibeUE/Reports/boss_sprint.json
"""
import json
import math
from pathlib import Path
import unreal
import TestDonorPunch as fixture

OBSERVER = None
SAMPLES = []


def begin(distance=1200.):
    global OBSERVER, SAMPLES
    w, b, p = fixture.actors()
    ph = p.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    bh = b.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    here = p.get_actor_location()
    b.set_actor_location(unreal.Vector(here.x + distance, here.y, here.z + bh - ph), False, False)
    b.set_actor_rotation(unreal.Rotator(yaw=180), False)
    SAMPLES = []

    def sample(_):
        w, b, p = fixture.actors()
        anim = b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance()
        m = anim.get_current_active_montage()
        SAMPLES.append({'t': unreal.GameplayStatics.get_time_seconds(w),
            'speed': b.get_velocity().length(), 'montage': m.get_name() if m else '',
            'state': b.get_editor_property('BossState').export_text(),
            'distance': math.hypot(b.get_actor_location().x - p.get_actor_location().x, b.get_actor_location().y - p.get_actor_location().y),
            'choice': str(b.get_editor_property('UtilityChoice')),
            'boss': [b.get_actor_location().x, b.get_actor_location().y], 'player': [p.get_actor_location().x, p.get_actor_location().y],
            'yaw': b.get_actor_rotation().yaw, 'velocity': [b.get_velocity().x, b.get_velocity().y],
            'reason': str(b.get_editor_property('GoapReason')), 'hp': float(p.get_editor_property('CurrentHealth')),
            'mesh': list(b.get_component_by_class(unreal.SkeletalMeshComponent).get_editor_property('relative_location').to_tuple()),
            'look': (b.get_controller().get_control_rotation().yaw - b.get_actor_rotation().yaw + 180.) % 360. - 180. if b.get_controller() else 0.,
            'pitch': (b.get_controller().get_control_rotation().pitch + 180.) % 360. - 180. if b.get_controller() else 0.,
            'abp_pitch': float(anim.get_editor_property('Pitch'))})
    OBSERVER = unreal.register_slate_post_tick_callback(sample)
    return 1


def finish():
    global OBSERVER
    if OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(OBSERVER)
        OBSERVER = None
    path = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/boss_sprint.json'
    path.write_text(json.dumps(SAMPLES, ensure_ascii=False), encoding='utf-8')
    return 1


def scenario(distance=1200, settle=7., watch=7.):
    m = "__import__('TestBossSprint')"
    return {'name': 'Boss sprint on a long approach', 'smoke': False,
            'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30},
                      {'action': 'wait', 'seconds': settle},       # intro and observe must finish
                      {'action': 'python_assert_number', 'expression': f'{m}.begin({distance})', 'operator': 'eq', 'expected': 1},
                      {'action': 'wait', 'seconds': watch},
                      {'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}],
            'teardown': {'stop_pie': True}}


def probe(tag='probe'):
    """Dump the Blueprint's bookkeeping used by the Utility penalties (cooldown stamps, last slot, family stamp)."""
    w, b, p = fixture.actors()
    row = {'now': unreal.SystemLibrary.get_game_time_in_seconds(b),
        'cooldown_until': [float(v) for v in b.get_editor_property('CooldownUntil')],
        'last_slot': int(b.get_editor_property('LastSelectedSlot')),
        'family_at': float(b.get_editor_property('PunchFamilyLastUsedAt')),
        'weights': [float(v) for v in b.get_editor_property('ActionWeights')],
        'state': b.get_editor_property('BossState').export_text(),
        'multipliers': [float(b.get_editor_property(n)) for n in ('UtilityRepeatMultiplier', 'RecentUseMinMultiplier', 'PunchFamilyMinMultiplier')]}
    path = Path(unreal.Paths.project_saved_dir()) / f'VibeUE/Reports/boss_utility_{tag}.json'
    path.write_text(json.dumps(row), encoding='utf-8')
    return 1


def heal():
    """Keep the stationary player alive so a long run records many decisions."""
    w, b, p = fixture.actors()
    unreal.GameplayStatics.apply_damage(p, -5000., None, None, unreal.DamageType)
    return 1


def long_scenario(distance=250, seconds=70):
    """Stationary player near the boss; the boss's own choices are read afterwards from the BATTLE_QA log."""
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin({distance})', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // 1.5)):      # heal faster than any two hits can land, or the player dies and the boss idles
        steps += [{'action': 'wait', 'seconds': 1.5}, {'action': 'python_assert_number', 'expression': f'{m}.heal()', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss choice sequence', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def away(distance=400.):
    """Put the player `distance` cm in front of the boss (as if they had backed off), and heal them."""
    w, b, p = fixture.actors()
    f = b.get_actor_forward_vector()
    here = b.get_actor_location()
    p.set_actor_location(unreal.Vector(here.x + f.x * distance, here.y + f.y * distance, p.get_actor_location().z), False, False)
    return heal()


def press_scenario(distance=400, seconds=70):
    """The player keeps backing off to `distance`: does the boss walk in (press) instead of only punching from there?"""
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin(250)', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // 1.5)):
        steps += [{'action': 'wait', 'seconds': 1.5}, {'action': 'python_assert_number', 'expression': f'{m}.away({distance})', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss press walk', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def reset_when_idle(distance=450.):
    """Mid-range fixture: while the boss is recovering, put the player back `distance` cm in front of it and heal.
    During an attack the player is left alone, so each attack plays against a standing target."""
    w, b, p = fixture.actors()
    if 'Recovery' in b.get_editor_property('BossState').export_text():
        # Move the boss, not the player: the player stays where the fight started, so neither ends up past a wall.
        here = p.get_actor_location()
        b.set_actor_location(unreal.Vector(here.x + distance, here.y, b.get_actor_location().z), False, False)
        b.set_actor_rotation(unreal.Rotator(yaw=180), False)
    for _ in range(4): heal()      # one heal does not refill; a dead player stops the boss
    return 1


def mid_scenario(distance=450, seconds=70):
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin({distance})', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // .5)):
        steps += [{'action': 'wait', 'seconds': .5}, {'action': 'python_assert_number', 'expression': f'{m}.reset_when_idle({distance})', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss mid-range versions in combat', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def dodge():
    """A dodging player: jump to a random spot 200..560 cm away, up to 65 degrees off the boss's facing. Boss attacks mostly miss."""
    import random
    w, b, p = fixture.actors()
    yaw = math.radians(b.get_actor_rotation().yaw + random.uniform(-65., 65.))
    d = random.uniform(200., 560.)
    here = b.get_actor_location()
    x, y = here.x + math.cos(yaw) * d, here.y + math.sin(yaw) * d
    z = p.get_actor_location().z
    # Only jump where nothing stands between the boss and the spot (and a little past it): never through a wall.
    past = unreal.Vector(here.x + math.cos(yaw) * (d + 150.), here.y + math.sin(yaw) * (d + 150.), z)
    hit = unreal.SystemLibrary.line_trace_single(w, unreal.Vector(here.x, here.y, z), past, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        False, [b, p], unreal.DrawDebugTrace.NONE, True)
    if hit is None:
        p.set_actor_location(unreal.Vector(x, y, z), False, False)
    for _ in range(4): heal()
    return 1


def dodge_scenario(seconds=90, every=1.3):
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin(300)', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // every)):
        steps += [{'action': 'wait', 'seconds': every}, {'action': 'python_assert_number', 'expression': f'{m}.dodge()', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss against a dodging player', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


RETREAT = None


def retreat_begin(speed=.7, far=620.):
    """A player who walks backwards whenever the boss is closer than `far` cm (real movement, so it has a velocity).
    Near a wall it slides sideways instead. Kept alive."""
    global RETREAT
    state = {'n': 0}

    def step(_):
        try:
            w, b, p = fixture.actors()
        except Exception:
            return
        here, boss = p.get_actor_location(), b.get_actor_location()
        dx, dy = here.x - boss.x, here.y - boss.y
        d = math.hypot(dx, dy)
        state['n'] += 1
        if state['n'] % 30 == 0:
            for _ in range(4): heal()
        if d < 1. or d > far: return
        ux, uy = dx / d, dy / d
        wall = unreal.SystemLibrary.line_trace_single(w, here, unreal.Vector(here.x + ux * 250., here.y + uy * 250., here.z),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [b, p], unreal.DrawDebugTrace.NONE, True)
        if wall is not None: ux, uy = -uy, ux          # blocked behind: slide along the wall
        p.add_movement_input(unreal.Vector(ux, uy, 0.), speed, False)
    RETREAT = unreal.register_slate_post_tick_callback(step)
    return 1


def retreat_end():
    global RETREAT
    if RETREAT is not None:
        unreal.unregister_slate_post_tick_callback(RETREAT)
        RETREAT = None
    return 1


def console(command):
    w, b, p = fixture.actors()
    unreal.SystemLibrary.execute_console_command(w, command)
    return 1


def retreat_scenario(seconds=90, lead=.7, memory=1):
    """Backpedalling player. lead=0 and memory=0 give the behaviour before prediction and outcome memory, for comparison."""
    m = "__import__('TestBossSprint')"
    call = lambda e: {'action': 'python_assert_number', 'expression': f'{m}.{e}', 'operator': 'eq', 'expected': 1}
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             call(f"console('boss.LeadTrust {lead}')"), call(f"console('boss.OutcomeMemory {memory}')"),
             call('begin(300)'), call('retreat_begin()'), {'action': 'wait', 'seconds': seconds},
             call('retreat_end()'), call("console('boss.LeadTrust 0.7')"), call("console('boss.OutcomeMemory 1')"), call('finish()')]
    return {'name': 'Boss against a backpedalling player', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def behind(distance=420.):
    """Put the player straight behind the boss (too far for the rear hook), to force a turn in place."""
    w, b, p = fixture.actors()
    if 'Ready' in b.get_editor_property('BossState').export_text() or 'Recovery' in b.get_editor_property('BossState').export_text():
        f = b.get_actor_forward_vector()
        here = b.get_actor_location()
        z = p.get_actor_location().z
        spot = unreal.Vector(here.x - f.x * distance, here.y - f.y * distance, z)
        hit = unreal.SystemLibrary.line_trace_single(w, unreal.Vector(here.x, here.y, z), spot, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [b, p], unreal.DrawDebugTrace.NONE, True)
        if hit is None: p.set_actor_location(spot, False, False)
    for _ in range(4): heal()
    return 1


def turn_scenario(seconds=60, every=4.):
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin(300)', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // every)):
        steps += [{'action': 'wait', 'seconds': every}, {'action': 'python_assert_number', 'expression': f'{m}.behind()', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss turning in place', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def poke():
    """Hit the boss lightly (to exercise the flinch) and keep the player alive."""
    w, b, p = fixture.actors()
    unreal.GameplayStatics.apply_damage(b, 4., None, None, unreal.DamageType)
    for _ in range(4): heal()
    return 1


def acting_scenario(distance=1200, seconds=60, every=1.5):
    """Far start (taunt, then sprint), then a close fight with the boss being hit now and then."""
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin({distance})', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // every)):
        steps += [{'action': 'wait', 'seconds': every}, {'action': 'python_assert_number', 'expression': f'{m}.poke()', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Boss acting', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def shot():
    """Screenshot of the game view with its UI (Saved/Screenshots)."""
    w, b, p = fixture.actors()
    unreal.GameplayStatics.apply_damage(b, 180., None, None, unreal.DamageType)
    unreal.SystemLibrary.execute_console_command(w, 'shot showui')
    return 1


def bar_scenario():
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 9.},
             {'action': 'python_assert_number', 'expression': f'{m}.poke()', 'operator': 'eq', 'expected': 1}, {'action': 'wait', 'seconds': 1.2},
             {'action': 'python_assert_number', 'expression': f'{m}.shot()', 'operator': 'eq', 'expected': 1}, {'action': 'wait', 'seconds': 1.5}]
    return {'name': 'Boss health bar screenshot', 'dependencies': ['Tools/TestBossSprint.py'], 'steps': steps, 'teardown': {'stop_pie': True}}


def guard_and_poke():
    """Hold the guard, and hit the boss once (as a player would after blocking). Keeps the player alive."""
    w, b, p = fixture.actors()
    try:
        p.call_method('TryEnterBlock')
    except Exception as error:
        print('guard failed', error)
    unreal.GameplayStatics.apply_damage(b, 15., None, p, unreal.DamageType)
    for _ in range(4): heal()
    return 1


def guard_scenario(seconds=80):
    m = "__import__('TestBossSprint')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': 8.},
             {'action': 'python_assert_number', 'expression': f'{m}.begin(250)', 'operator': 'eq', 'expected': 1}]
    for _ in range(int(seconds // 1.)):
        steps += [{'action': 'wait', 'seconds': 1.}, {'action': 'python_assert_number', 'expression': f'{m}.guard_and_poke()', 'operator': 'eq', 'expected': 1}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.finish()', 'operator': 'eq', 'expected': 1}]
    return {'name': 'Guard reward', 'dependencies': ['Tools/TestBossSprint.py', 'Tools/TestDonorPunch.py'], 'steps': steps, 'teardown': {'stop_pie': True}}
