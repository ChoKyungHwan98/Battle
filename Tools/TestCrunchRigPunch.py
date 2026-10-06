"""Functional MotionLab smoke check; visual quality approval belongs to the user."""
import math
import unreal
import TestDonorPunch as fixture


def begin(distance=550):
    result = fixture.begin(distance)
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0], 1.)
    return result


def montage_ok():
    return int(any(s['montage'] == 'AM_Crunch_RightStep_LeftSwing' for s in fixture.SAMPLES))


def travel():
    return max(math.dist(s['boss'], fixture.START_LOCATION) for s in fixture.SAMPLES)


def finish():
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
        fixture.OBSERVER = None
    print('CRUNCH_RIG_SMOKE', 'montage', montage_ok(), 'root_travel_cm', travel(),
        'damage_at_550', fixture.damage(), 'samples', len(fixture.SAMPLES))
    return 1


def scenario():
    module = "__import__('TestCrunchRigPunch')"
    return {'name': 'Crunch Control Rig attack: MotionLab montage and root movement',
        'dependencies': ['Tools/TestCrunchRigPunch.py', 'Tools/CrunchControlRigAuthoring.py',
            'Content/BossArena/Boss/Authoring/AS_Crunch_RightStep_LeftSwing.uasset',
            'Content/BossArena/Boss/Authoring/AM_Crunch_RightStep_LeftSwing.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset'],
        'steps': [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20},
            {'action': 'wait', 'seconds': .5},
            {'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .15},
            {'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .15},
            {'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .15},
            {'action': 'python_assert_number', 'expression': module + '.begin()', 'operator': 'eq', 'expected': 1},
            {'action': 'inject_key', 'key': 'One'}, {'action': 'wait', 'seconds': 4.},
            {'action': 'python_assert_number', 'expression': module + '.finish()', 'operator': 'eq', 'expected': 1},
            {'action': 'python_assert_number', 'expression': module + '.montage_ok()', 'operator': 'eq', 'expected': 1},
            {'action': 'python_assert_number', 'expression': module + '.travel()', 'operator': 'gt', 'expected': 180}],
        'teardown': {'stop_pie': True}}
