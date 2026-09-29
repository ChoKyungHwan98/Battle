"""Transient PIE measurements for animation-driven roll motion."""
import unreal

start = None
asset = None


def prepare():
    global asset
    asset = unreal.EditorAssetLibrary.load_asset(
        '/Game/BossArena/Player/Animation/SwordShield/Sequences/RM_Shield_A_Roll_IdleFwd')
    return asset is not None


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def player():
    return unreal.GameplayStatics.get_player_character(world(), 0)


def play_forward():
    global start
    p = player()
    for b in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor):
        if 'BP_Boss_Crunch' in b.get_class().get_name():
            b.set_actor_tick_enabled(False)
            b.set_actor_enable_collision(False)
    p.set_actor_rotation(unreal.Rotator(yaw=0), False)
    p.get_controller().set_control_rotation(unreal.Rotator(yaw=0))
    p.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
    p.set_actor_tick_enabled(False)
    start = p.get_actor_location()
    anim = p.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance()
    montage = anim.play_slot_animation_as_dynamic_montage(asset, 'DefaultSlot', .025, .06, 1/.70, 1)
    return montage is not None


def travel():
    delta = player().get_actor_location() - start
    return delta.length()


def forward():
    delta = player().get_actor_location() - start
    return delta.dot(player().get_actor_forward_vector())


def lateral():
    delta = player().get_actor_location() - start
    return delta.dot(player().get_actor_right_vector())


def actual_distance():
    p = player()
    return (p.get_actor_location() - p.get_editor_property('DodgeMoveStartLocation')).length()


def alignment():
    p = player()
    delta = p.get_actor_location() - p.get_editor_property('DodgeMoveStartLocation')
    intended = p.get_editor_property('DodgeMoveDirection')
    return delta.normal().dot(intended.normal())


def eight_directions():
    B = "__import__('TestSwordShield')"
    T = "__import__('TestDS3RootMotion')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20}]
    def wait(t): steps.append({'action': 'wait', 'seconds': t})
    def key(k, event): steps.append({'action': 'inject_key', 'key': k, 'event': event})
    def check(expr, expected=1, tolerance=0):
        steps.append({'action': 'python_assert_number', 'expression': expr,
                      'expected': expected, 'operator': 'eq', 'tolerance': tolerance})
    check(f'int({B}.setup_strafe())')
    wait(.5)
    for name, keys in [('fwd',['W']), ('fwd_left',['W','A']), ('left',['A']),
                       ('back_left',['S','A']), ('back',['S']), ('back_right',['S','D']),
                       ('right',['D']), ('fwd_right',['W','D'])]:
        check(f'int({B}.reset_motion_fixture())')
        wait(.1)
        for k in keys: key(k, 'down')
        wait(.08)
        key('SpaceBar', 'down'); wait(.06); key('SpaceBar', 'up')
        for k in keys: key(k, 'up')
        wait(.74)
        check(f'{T}.actual_distance()', 320, 12)
        check(f'int({T}.alignment() >= .95)')
        check(f'{B}.state()', 5)
        if name in ('fwd','back','left','right'):
            steps.append({'action': 'capture_game', 'name': 'root-roll-'+name})
    steps.append({'action': 'assert_log', 'not_contains': 'LogScript: Warning'})
    return {'name': 'Eight locked-on medium rolls follow animation root and input direction',
            'steps': steps, 'teardown': {'stop_pie': True}}
