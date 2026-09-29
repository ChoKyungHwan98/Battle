"""PIE regression: suspending lock for sprint must not punch the camera inward."""
import unreal
import TestSwordShield as T

baseline_arm = None


def arm():
    return T.player().get_component_by_class(unreal.SpringArmComponent).target_arm_length


def prepare_locked():
    assert T.setup_strafe()
    p = T.player()
    boss = p.get_editor_property('LockOnTarget')
    boss.set_actor_location(p.get_actor_location() + p.get_actor_forward_vector() * 1450, False, False)
    return True


def prepare_near_locked():
    assert prepare_locked()
    p = T.player()
    boss = p.get_editor_property('LockOnTarget')
    boss.set_actor_location(p.get_actor_location() + p.get_actor_forward_vector() * 700, False, False)
    return True


def mark_arm():
    global baseline_arm
    baseline_arm = arm()
    print('CAMERA_ARM_BEFORE_SPRINT', round(baseline_arm, 2))
    return True


def arm_drift():
    drift = abs(arm() - baseline_arm)
    print('CAMERA_ARM_SPRINT_DRIFT', round(drift, 2))
    return drift


def scenario():
    Q = "__import__('TestDS3CameraSprint')"
    TQ = "__import__('TestSwordShield')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]

    def check(expression):
        steps.append({'action': 'python_assert_number', 'expression': f'int({expression})',
                      'expected': 1, 'operator': 'eq'})

    def wait(seconds):
        steps.append({'action': 'wait', 'seconds': seconds})

    def key(name, event):
        steps.append({'action': 'inject_key', 'key': name, 'event': event})

    check(f'{Q}.prepare_locked()')
    wait(1.0)
    check(f'abs({Q}.arm() - 550) < 5')
    steps.append({'action': 'capture_game', 'name': 'lock-before-sprint'})
    wait(.4)  # Exclude capture readback stall from the input hold measurement.
    key('W', 'down')
    key('SpaceBar', 'down')
    wait(.48)
    check(f'{TQ}.player().get_editor_property("bIsSprinting")')
    check(f'{TQ}.player().get_editor_property("LockOnTarget") is None')
    check(f'{TQ}.player().get_editor_property("SprintResumeLockTarget") is not None')
    check(f'abs({Q}.arm() - 550) < 10')
    steps.append({'action': 'capture_game', 'name': 'sprint-without-zoom'})
    wait(.35)
    check(f'abs({Q}.arm() - 550) < 10')
    key('SpaceBar', 'up')
    key('W', 'up')
    wait(.45)
    check(f'{TQ}.player().get_editor_property("LockOnTarget") is not None')
    check(f'abs({Q}.arm() - 550) < 20')
    steps.append({'action': 'capture_game', 'name': 'lock-after-sprint'})
    steps.append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return {'name': 'DS3 camera distance stays stable through lock sprint',
            'steps': steps, 'teardown': {'stop_pie': True}}


def near_scenario():
    Q = "__import__('TestDS3CameraSprint')"
    TQ = "__import__('TestSwordShield')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]

    def check(expression):
        steps.append({'action': 'python_assert_number', 'expression': f'int({expression})',
                      'expected': 1, 'operator': 'eq'})

    def wait(seconds):
        steps.append({'action': 'wait', 'seconds': seconds})

    def key(name, event):
        steps.append({'action': 'inject_key', 'key': name, 'event': event})

    check(f'{Q}.prepare_near_locked()')
    wait(1.2)
    check(f'abs({Q}.arm() - 550) < 5')
    steps.append({'action': 'capture_game', 'name': 'near-lock-before-sprint'})
    wait(.4)
    key('W', 'down')
    wait(.15)
    key('SpaceBar', 'down')
    wait(.48)
    check(f'{TQ}.player().get_editor_property("bIsSprinting")')
    check(f'{Q}.mark_arm()')
    wait(.25)
    check(f'{Q}.arm_drift() < 5')
    steps.append({'action': 'capture_game', 'name': 'near-lock-sprint-stable'})
    key('SpaceBar', 'up')
    key('W', 'up')
    wait(.35)
    check(f'{TQ}.player().get_editor_property("LockOnTarget") is not None')
    steps.append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return {'name': 'Close boss lock camera does not zoom in on sprint',
            'steps': steps, 'teardown': {'stop_pie': True}}
