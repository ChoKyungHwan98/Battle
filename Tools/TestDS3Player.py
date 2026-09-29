"""Timed PIE evidence for DS3 inspired controls. No persistent asset changes."""
import unreal
import TestSwordShield as T

handle = None
samples = []
last_time = -1000
starts = []
cube = None


def observe():
    global handle, samples, starts, last_time
    stop_observing()
    samples = []
    starts = []
    last_time = T.player().get_editor_property('DodgeTimeNewest')
    def tick(delta):
        global last_time
        p = T.player()
        if not p:
            return
        now = unreal.GameplayStatics.get_time_seconds(T.world())
        stamp = p.get_editor_property('DodgeTimeNewest')
        if stamp > last_time + .001:
            # The observer sees the first completed movement tick. Use the
            # Blueprint's captured origin, not an already advanced capsule.
            starts.append((stamp, p.get_editor_property('DodgeMoveStartLocation'), p.get_actor_rotation().yaw))
            last_time = stamp
        samples.append((now, T.state(), p.get_editor_property('bInvincible'), p.get_actor_location()))
    handle = unreal.register_slate_post_tick_callback(tick)
    return True


def stop_observing():
    global handle
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    return True


def metric(kind):
    assert starts and samples
    start = starts[0][0]
    if kind == 'rolls':
        return len(starts)
    if kind == 'interval':
        return starts[1][0] - starts[0][0]
    if kind == 'iframe':
        return next(t - start for t, state, inv, loc in samples if t > start and not inv)
    if kind == 'recovery':
        return next(t - start for t, state, inv, loc in samples if t > start and state == 5)
    if kind == 'distance':
        return (samples[-1][3] - starts[0][1]).length()


def facing_error():
    return abs((T.player().get_actor_rotation().yaw - starts[0][2] + 180) % 360 - 180)


def move_target():
    boss = T.player().get_editor_property('LockOnTarget')
    boss.set_actor_location(boss.get_actor_location() + unreal.Vector(450, 0, 0), False, False)
    return True


def free_fixture():
    T.reset_motion_fixture()
    if T.player().get_editor_property('LockOnTarget'):
        T.player().call_method('ToggleLockOn')
    return True


def wall():
    assert cube, 'Preload Cube in the editor before starting PIE'
    p = T.player()
    unreal.PIEActorService.spawn_actor('server', '/Script/Engine.StaticMeshActor', unreal.Transform())
    actor = next(a for a in reversed(list(unreal.GameplayStatics.get_all_actors_of_class(T.world(), unreal.Actor)))
                 if a.get_class() == unreal.StaticMeshActor.static_class())
    actor.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    actor.static_mesh_component.set_static_mesh(cube)
    actor.static_mesh_component.set_collision_profile_name('BlockAll')
    actor.set_actor_scale3d(unreal.Vector(1, 4, 4))
    actor.set_actor_rotation(p.get_actor_rotation(), False)
    actor.set_actor_location(p.get_actor_location() + p.get_actor_forward_vector() * 200, False, False)
    return True


def travel():
    p = T.player()
    return (p.get_actor_location() - p.get_editor_property('DodgeMoveStartLocation')).length()


def motion_scenario():
    M = "__import__('TestDS3Player')"
    B = "__import__('TestSwordShield')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]
    def wait(t): steps.append({'action': 'wait', 'seconds': t})
    def key(k, event): steps.append({'action': 'inject_key', 'key': k, 'event': event})
    def check(expr): steps.append({'action': 'python_assert_number', 'expression': expr,
                                   'expected': 1, 'operator': 'eq', 'tolerance': 0})
    check(f'int({B}.setup_strafe())'); wait(.8)
    key('W', 'down'); wait(.4)
    check(f'int({B}.player().mesh.get_anim_instance().get_editor_property("GroundSpeed") > 150)')
    check(f'int({M}.observe())'); key('SpaceBar', 'down'); wait(.07)
    check(f'int({B}.state() == 2)'); key('SpaceBar', 'up'); key('W', 'up'); key('D', 'down')
    check(f'int({M}.move_target())'); wait(.22)
    check(f'int({M}.facing_error() < 1)')
    # With animation-driven root motion, CharacterMovement reports the montage's
    # velocity while the committed roll is in progress.
    check(f'int({B}.player().character_movement.velocity.length() > 2)')
    key('D', 'up'); wait(.55)
    check(f'int({B}.state() == 5)'); check(f'int(abs({M}.travel() - 320) < 6)')
    check(f'int({M}.stop_observing())'); check(f'int({M}.free_fixture())'); wait(.35)
    check(f'int({M}.wall())'); key('W', 'down'); wait(.1)
    key('SpaceBar', 'down'); wait(.06); key('SpaceBar', 'up'); key('W', 'up'); wait(.8)
    check(f'int({B}.state() == 5)'); check(f'int(50 < {M}.travel() < 145)')
    steps.append({'action': 'capture_game', 'name': 'roll-stops-before-wall'})
    steps.append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return {'name': 'Moving medium roll keeps direction, freezes body facing and respects walls',
            'steps': steps, 'teardown': {'stop_pie': True}}


def scenario():
    M = "__import__('TestDS3Player')"
    B = "__import__('TestSwordShield')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]
    def wait(t): steps.append({'action': 'wait', 'seconds': t})
    def key(k, event): steps.append({'action': 'inject_key', 'key': k, 'event': event})
    def check(expression, expected=1, tolerance=0):
        steps.append({'action': 'python_assert_number', 'expression': expression,
                      'expected': expected, 'operator': 'eq', 'tolerance': tolerance})
    def cap(name): steps.append({'action': 'capture_game', 'name': name})
    def click(k): key(k, 'down'); wait(.05); key(k, 'up')
    check(f'int({B}.setup())'); wait(.8); cap('sword-idle'); wait(.35)
    check(f'int({M}.observe())')
    key('SpaceBar', 'down'); wait(.06)
    check(f'{B}.state()', 2); check(f'int({B}.player().get_editor_property("bInvincible"))')
    # Keep screenshots out of the timing sample. Readback can stall a game tick.
    key('SpaceBar', 'up'); wait(.9)
    check(f'{M}.metric("rolls")')
    check(f'{M}.metric("iframe")', 26/60, .055)
    check(f'{M}.metric("recovery")', .7, .055)
    check(f'{M}.metric("distance")', 320, 6)
    check(f'int({M}.stop_observing())'); cap('sword-idle-return'); wait(.35)
    click('SpaceBar'); wait(.18); cap('medium-roll-air')
    wait(.25); cap('medium-roll-recovery'); wait(.65)
    check(f'int({B}.reset_motion_fixture())'); wait(.35)

    # First half ignores an accidental repeat. A latter-half repeat is accepted once.
    check(f'int({M}.observe())'); click('SpaceBar'); wait(.10); click('SpaceBar')
    check(f'int({B}.player().get_editor_property("bDodgeBuffered"))', 0)
    wait(.25); click('SpaceBar')
    check(f'int({B}.player().get_editor_property("bDodgeBuffered"))')
    check(f'{B}.state()', 2); wait(1.1)
    check(f'{M}.metric("rolls")', 2)
    check(f'{M}.metric("interval")', .7, .055)
    check(f'int({B}.player().get_editor_property("bDodgeBuffered"))', 0)
    wait(.2); check(f'{M}.metric("rolls")', 2)
    check(f'int({M}.stop_observing())')
    check(f'int({B}.reset_motion_fixture())'); wait(.35)

    # An attack alone can be queued during the roll tail.
    click('SpaceBar'); wait(.4); click('LeftMouseButton')
    check(f'int({B}.player().get_editor_property("bAttackBuffered"))')
    check(f'{B}.state()', 2); wait(.3)
    check(f'{B}.state()', 4); check(f'int({B}.player().get_editor_property("bAttackBuffered"))', 0)
    cap('roll-to-attack'); wait(1.1)
    check(f'int({B}.reset_motion_fixture())'); wait(.35)
    click('SpaceBar'); wait(.38); click('SpaceBar'); click('LeftMouseButton')
    # The eligible roll request takes priority when both actions overlap.
    check(f'int(not {B}.player().get_editor_property("bAttackBuffered") and '
          f'({B}.player().get_editor_property("bDodgeBuffered") or {B}.state() == 2))')
    wait(.4); check(f'{B}.state()', 2); wait(1.1)
    check(f'int({B}.reset_motion_fixture())'); wait(.35)

    # A real damage event is ignored inside i-frames and interrupts the vulnerable tail.
    click('SpaceBar'); wait(.20); check(f'int({B}.hit(40))')
    wait(.03); check(f'{B}.state()', 2)
    wait(.24); check(f'int({B}.hit(40))'); wait(.08)
    check(f'{B}.state()', 1)
    wait(.25); check(f'{B}.state()', 1)  # Old .70s roll timer must not release hitstun.
    wait(.5); check(f'{B}.state()', 5)
    steps.append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return {'name': 'Sword Idle and medium roll timing, queue and vulnerability',
            'steps': steps, 'teardown': {'stop_pie': True}}
