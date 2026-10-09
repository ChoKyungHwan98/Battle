"""Audit keys 1 / 2 / 5 (left, right, jab-jab-hook) as they move from mid range.

Lab mode "실전 자동" uses the real-combat step planner, so this records what a mid-range
attack does today: boss travel, foot positions and hand reach per start distance.
Measurement only: nothing is changed. Samples per run go to
Saved/VibeUE/Reports/midrange_audit.json; analysis lives in the caller.
"""
import json
from pathlib import Path
import unreal
import TestDonorPunch as fixture

OUT = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/midrange_audit.json'
RESULTS = {}
DISTANCES = [300, 350, 400, 450, 500]
KEYS = {'One': 4.2, 'Two': 4.2, 'Three': 5.5, 'Four': 5.5, 'Five': 11.0, 'Six': 5.0, 'Zero': 7.5, 'K': 4.5}      # seconds to let the whole action (and recovery) play


def begin(distance):
    fixture.begin(distance)
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0], 1.)
    return 1


def finish(tag):
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
        fixture.OBSERVER = None
    RESULTS[tag] = list(fixture.SAMPLES)
    OUT.write_text(json.dumps(RESULTS, ensure_ascii=False), encoding='utf-8')
    return 1


def reset():
    RESULTS.clear()
    return 1


def scenario(key, step_mode=False, distances=None):
    """step_mode: press L twice first (auto -> in-place -> step), so the key runs its new foot-step motion; tags get an S_ prefix."""
    m = "__import__('TestMidrangeAudit')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': .8}]
    if step_mode:
        for _ in range(2 if step_mode is True else int(step_mode)):     # 1 = in-place mode, 2 = foot-step mode
            steps += [{'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .3}]
    prefix = {0:'',1:'P_',2:'S_'}[int(step_mode) if step_mode is not True else 2]
    for d in (distances or DISTANCES):
        steps += [{'action': 'python_assert_number', 'expression': f'{m}.begin({d})', 'operator': 'eq', 'expected': 1},
                  {'action': 'inject_key', 'key': key}, {'action': 'wait', 'seconds': KEYS[key]},
                  {'action': 'python_assert_number', 'expression': f"{m}.finish('{prefix}{key}_{d}')", 'operator': 'eq', 'expected': 1}]
    return {'name': f'Mid-range audit: key {key}' + (' (step mode)' if step_mode else ''), 'dependencies': ['Tools/TestMidrangeAudit.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def move_player_beside():
    """Teleport the player to the boss's side (90 degrees, 300cm), as if it circled round during the attack."""
    w, b, p = fixture.actors()
    loc = b.get_actor_location()
    p.set_actor_location(unreal.Vector(loc.x, loc.y + 300., p.get_actor_location().z), False, False)
    return 1


def recovery_turn_scenario(key='One', distance=250, move_after=1.0):
    """One in-place attack; the player jumps to the boss's side after the hit. finish() keeps the yaw samples."""
    m = "__import__('TestMidrangeAudit')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': .8},
             {'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .3},
             {'action': 'python_assert_number', 'expression': f'{m}.begin({distance})', 'operator': 'eq', 'expected': 1},
             {'action': 'inject_key', 'key': key}, {'action': 'wait', 'seconds': move_after},
             {'action': 'python_assert_number', 'expression': f'{m}.move_player_beside()', 'operator': 'eq', 'expected': 1},
             {'action': 'wait', 'seconds': 4.5},
             {'action': 'python_assert_number', 'expression': f"{m}.finish('turn_{key}')", 'operator': 'eq', 'expected': 1}]
    return {'name': 'Recovery turn: second half only', 'dependencies': ['Tools/TestMidrangeAudit.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}


def move_player_behind(distance=200.):
    """Teleport the player straight behind the boss, as if it rolled through during the attack."""
    w, b, p = fixture.actors()
    loc = b.get_actor_location()
    back = b.get_actor_forward_vector() * -distance
    p.set_actor_location(unreal.Vector(loc.x + back.x, loc.y + back.y, p.get_actor_location().z), False, False)
    return 1


def rear_response_scenario(distance_behind=200, key='One', tag='rear'):
    """In-place attack, the player gets behind after the hit. The answer is a 60% roll, so run it a few times.
    (Setting the chance with set_editor_property re-runs the boss's construction and kills it: do not.)"""
    m = "__import__('TestMidrangeAudit')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': .8},
             {'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .3},
             {'action': 'python_assert_number', 'expression': f'{m}.begin(250)', 'operator': 'eq', 'expected': 1},
             {'action': 'inject_key', 'key': key}, {'action': 'wait', 'seconds': 1.0},
             {'action': 'python_assert_number', 'expression': f'{m}.move_player_behind({distance_behind})', 'operator': 'eq', 'expected': 1},
             {'action': 'wait', 'seconds': 7.0},
             {'action': 'python_assert_number', 'expression': f"{m}.finish('{tag}_{distance_behind}')", 'operator': 'eq', 'expected': 1}]
    return {'name': 'Rear response after an attack', 'dependencies': ['Tools/TestMidrangeAudit.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}
