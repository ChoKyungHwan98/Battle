"""PIE regression checks for Battle's Space tap/hold input split."""
import json
import unreal


T = "__import__('TestSwordShield')"


def base(name, locked=False):
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]
    steps.append({'action': 'wait', 'seconds': .9})
    setup = 'setup_strafe' if locked else 'setup'
    steps.append({'action': 'python_assert_number', 'expression': f'int({T}.{setup}())',
                  'expected': 1, 'operator': 'eq', 'tolerance': 0})
    steps.append({'action': 'wait', 'seconds': .9})
    return {'name': name, 'steps': steps, 'teardown': {'stop_pie': True}}


def wait(s, t):
    s['steps'].append({'action': 'wait', 'seconds': t})


def key(s, k, event):
    s['steps'].append({'action': 'inject_key', 'key': k, 'event': event})


def short_tap(s):
    key(s, 'SpaceBar', 'down')
    wait(s, .035)
    key(s, 'SpaceBar', 'up')


def check(s, expression, expected=1):
    s['steps'].append({'action': 'python_assert_number', 'expression': expression,
                       'expected': expected, 'operator': 'eq', 'tolerance': 0})


def stationary_tap_no_action():
    s = base('Space short stationary tap does nothing and locomotion stays available')
    short_tap(s)
    wait(s, .08)
    check(s, f'{T}.state()', 5)
    check(s, f'int(not {T}.player().get_editor_property("bIsBackstep"))')
    check(s, f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    wait(s, .7)
    check(s, f'{T}.state()', 5)
    key(s, 'W', 'down')
    wait(s, .3)
    s['steps'].append({'action': 'python_assert_number',
                       'expression': f'{T}.player().get_velocity().length()',
                       'expected': 50, 'operator': 'gt'})
    key(s, 'W', 'up')
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def moving_tap():
    s = base('Space short moving tap rolls without sprint')
    key(s, 'W', 'down')
    wait(s, .2)
    short_tap(s)
    wait(s, .08)
    check(s, f'{T}.state()', 2)
    check(s, f'int(not {T}.player().get_editor_property("bIsBackstep"))')
    check(s, f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    key(s, 'W', 'up')
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def locked_tap_130ms():
    s = base('Locked 130ms Space tap rolls and recovers', True)
    key(s, 'W', 'down')
    wait(s, .2)
    key(s, 'SpaceBar', 'down')
    wait(s, .13)
    key(s, 'SpaceBar', 'up')
    wait(s, .28)
    check(s, f'{T}.state()', 2)
    check(s, f'int(not {T}.player().get_editor_property("bIsBackstep"))')
    check(s, f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    s['steps'].append({'action': 'python_assert_number',
                       'expression': f'({T}.player().get_actor_location()-{T}.player().get_editor_property("DodgeMoveStartLocation")).length()',
                       'expected': 80, 'operator': 'gt'})
    s['steps'].append({'action': 'capture_game', 'name': 'locked-space-roll'})
    key(s, 'W', 'up')
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def locked_roll_recovery():
    s = base('Locked Space roll returns to locomotion', True)
    key(s, 'W', 'down')
    wait(s, .2)
    short_tap(s)
    wait(s, 1.15)
    check(s, f'{T}.state()', 5)
    check(s, f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    s['steps'].append({'action': 'python_assert_number',
                       'expression': f'{T}.player().get_velocity().length()',
                       'expected': 50, 'operator': 'gt'})
    key(s, 'W', 'up')
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def locked_hold():
    s = base('Space hold starts sprint while retaining lock target', True)
    check(s, f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    key(s, 'W', 'down')
    wait(s, .25)
    key(s, 'SpaceBar', 'down')
    wait(s, .28)
    check(s, f'int({T}.player().get_editor_property("bIsSprinting"))')
    check(s, f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    check(s, f'int({T}.player().get_editor_property("SprintResumeLockTarget") is None)')
    check(s, f'int({T}.player().get_editor_property("MovementMode").value == 1)')
    key(s, 'SpaceBar', 'up')
    wait(s, .2)
    check(s, f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    check(s, f'int({T}.player().get_editor_property("LockOnTarget") is not None)')
    key(s, 'W', 'up')
    s['steps'].append({'action': 'capture_game', 'name': 'ds3-space-lock-retained'})
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def stationary_hold():
    s = base('Space hold at rest does not sprint or backstep')
    key(s, 'SpaceBar', 'down')
    wait(s, .28)
    check(s, f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    key(s, 'SpaceBar', 'up')
    wait(s, .15)
    check(s, f'{T}.state()', 5)
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def released_move_hold():
    s = base('Space hold after releasing movement stays idle')
    key(s, 'W', 'down')
    wait(s, .2)
    key(s, 'W', 'up')
    wait(s, .2)
    key(s, 'SpaceBar', 'down')
    wait(s, .28)
    check(s, f'int(not {T}.player().get_editor_property("bIsSprinting"))')
    s['steps'].append({'action': 'python_assert_number',
                       'expression': f'{T}.player().get_editor_property("LastMoveInput").length()',
                       'expected': .1, 'operator': 'lt'})
    key(s, 'SpaceBar', 'up')
    s['steps'].append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return s


def run(which):
    spec = globals()[which]()
    return unreal.WorkflowService.run_scenario(json.dumps(spec, ensure_ascii=False))
