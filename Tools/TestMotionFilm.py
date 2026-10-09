"""Film a MotionLab action from a side camera in slow motion, so the legs are visible.

The player camera sits behind the player, who hides the boss's legs. This places a camera at the
boss's side, hides the player mesh and slows time; the scenario then takes game captures at even
steps. Measurement/inspection only: nothing in the project is changed (PIE-only actors).
"""
import unreal
import TestDonorPunch as fixture

CAMERA = None


def setup(distance, dilation=.1, back=430., height=125.):
    """Place the fixture, then look at the boss from its right side (boss runs toward -X, screen right)."""
    global CAMERA
    fixture.begin(distance)
    w, b, p = fixture.actors()
    if fixture.OBSERVER is not None:        # no sampling here: captures already stall the frame
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
        fixture.OBSERVER = None
    p.set_actor_hidden_in_game(True)
    # The view stays on the player's own camera (changing the view target had no effect here), so that camera
    # component is detached from its boom by making it world-absolute and parked at the boss's side.
    CAMERA = p.get_component_by_class(unreal.CameraComponent)
    CAMERA.set_editor_property('use_pawn_control_rotation', False)
    CAMERA.set_absolute(True, True, False)
    CAMERA.set_world_location_and_rotation(unreal.Vector(distance - 70., -back, height),
        unreal.Rotator(roll=0., pitch=-8., yaw=90.), False, False)
    unreal.GameplayStatics.set_global_time_dilation(w, dilation)
    return 1


def hide_hud():
    """The lab panel covers the right 40% of the frame; hide it for filming (PIE only)."""
    w = fixture.actors()[0]
    for widget in unreal.WidgetLibrary.get_all_widgets_of_class(w, unreal.UserWidget, False):
        widget.set_visibility(unreal.SlateVisibility.HIDDEN)
    hud = unreal.GameplayStatics.get_player_controller(w, 0).get_hud()
    if hud: hud.set_editor_property('show_hud', False)
    return 1


def wide(distance, dilation=.1, travel=190., back=760., height=190.):
    """Like setup, but centred on the whole run from `distance` to `distance - travel`, HUD hidden."""
    setup(distance, dilation, back, height)
    CAMERA.set_world_location_and_rotation(unreal.Vector(distance - travel * .5, -back, height),
        unreal.Rotator(roll=0., pitch=-6., yaw=90.), False, False)
    return hide_hud()


def speed(dilation):
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0], dilation)
    return 1


def scenario(key, tag, l_presses, distance=400, shots=16, game_step=.06, slow=.1, tail_shots=8, tail_step=.26, tail_slow=.3):
    """l_presses: 1 = original in-place motion, 2 = foot-step motion. Captures are named <tag>-NN."""
    m = "__import__('TestMotionFilm')"
    steps = [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 30}, {'action': 'wait', 'seconds': .8}]
    for _ in range(l_presses):
        steps += [{'action': 'inject_key', 'key': 'L'}, {'action': 'wait', 'seconds': .3}]
    steps += [{'action': 'wait', 'seconds': 2.0}]     # the boss intro must finish (Boss.Combat.Ready)
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.setup({distance},{slow})', 'operator': 'eq', 'expected': 1},
              {'action': 'wait', 'seconds': .4}, {'action': 'inject_key', 'key': key}]
    for i in range(shots):
        steps += [{'action': 'wait', 'seconds': game_step / slow}, {'action': 'capture_game', 'name': f'{tag}-{i:02d}'}]
    steps += [{'action': 'python_assert_number', 'expression': f'{m}.speed({tail_slow})', 'operator': 'eq', 'expected': 1}]
    for i in range(tail_shots):
        steps += [{'action': 'wait', 'seconds': tail_step / tail_slow}, {'action': 'capture_game', 'name': f'{tag}-t{i:02d}'}]
    return {'name': f'Film {tag}', 'dependencies': ['Tools/TestMotionFilm.py', 'Tools/TestDonorPunch.py'],
            'steps': steps, 'teardown': {'stop_pie': True}}
