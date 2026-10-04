"""PIE regression for Crunch's limited tracking, chain re-aim, and recovery lock."""
import json
import math

import unreal
import TestSoulsHits as fixture


observer = None
samples = []
phase_times = {}
start_time = 0.0
active_moved = False
link_moved = False
recovery_moved = False


def _angle_delta(before, after):
    return (after - before + 180.0) % 360.0 - 180.0


def _place_target(angle_degrees):
    boss = fixture.boss()
    player = fixture.player()
    angle = math.radians(angle_degrees)
    delta = unreal.Vector(-250.0 * math.cos(angle), -250.0 * math.sin(angle), 0.0)
    boss_half = boss.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    player_half = player.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
    player.set_actor_location(boss.get_actor_location() + delta + unreal.Vector(0, 0, player_half - boss_half), False, False)


def begin():
    global observer, samples, phase_times, start_time
    global active_moved, link_moved, recovery_moved
    fixture.setup(250)
    boss = fixture.boss()
    unreal.GameplayStatics.set_global_time_dilation(fixture.world(), 0.5)
    samples = []
    phase_times = {}
    active_moved = link_moved = recovery_moved = False
    start_time = unreal.GameplayStatics.get_time_seconds(fixture.world())

    def tick(_delta):
        global active_moved, link_moved, recovery_moved
        b = fixture.boss()
        phase = b.get_editor_property('BossState').export_text()
        t = unreal.GameplayStatics.get_time_seconds(fixture.world()) - start_time
        if 'Attack.Active' in phase and not active_moved:
            _place_target(25)
            active_moved = True
            phase_times['active'] = t
        elif 'Attack.Link' in phase and not link_moved:
            _place_target(60)
            link_moved = True
            phase_times['link'] = t
        elif 'Attack.Recovery' in phase and not recovery_moved:
            _place_target(-70)
            recovery_moved = True
            phase_times['recovery'] = t
        samples.append((round(t, 3), phase, round(b.get_actor_rotation().yaw, 3),
                        bool(b.get_editor_property('bCanTurn')),
                        int(b.get_editor_property('HitIndex'))))

    observer = unreal.register_slate_post_tick_callback(tick)
    boss.call_method('RequestCombatAction', (4,))
    boss.set_actor_tick_enabled(True)
    return int(boss.get_editor_property('SelectedSlot') == 4)


def finish():
    global observer
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    active = [s for s in samples if 'Attack.Active' in s[1] and s[0] < phase_times.get('link', 0)]
    link = [s for s in samples if 'Attack.Link' in s[1] and
            phase_times.get('link', 1e9) <= s[0] < phase_times.get('link', 1e9) + 0.8]
    recovery = [s for s in samples if 'Attack.Recovery' in s[1] and
                phase_times.get('recovery', 1e9) <= s[0] < phase_times.get('recovery', 1e9) + 0.3]
    active_yaw = abs(_angle_delta(active[0][2], active[-1][2])) if len(active) > 1 else -1
    link_yaw = abs(_angle_delta(link[0][2], link[-1][2])) if len(link) > 1 else -1
    recovery_yaw = abs(_angle_delta(recovery[0][2], recovery[-1][2])) if len(recovery) > 1 else -1
    report = {'phase_times': phase_times, 'sample_count': len(samples),
              'active_yaw': active_yaw, 'link_yaw': link_yaw,
              'recovery_yaw': recovery_yaw,
              'active_can_turn': any(s[3] for s in active),
              'link_can_turn': any(s[3] for s in link),
              'recovery_can_turn': any(s[3] for s in recovery)}
    path = unreal.Paths.project_saved_dir() + 'VibeUE/boss-reaim.json'
    with open(path, 'w', encoding='utf-8') as out:
        json.dump({'report': report, 'samples': samples}, out, ensure_ascii=False, indent=2)
    print('REAIM_REPORT', json.dumps(report, ensure_ascii=False), 'PATH', path)
    return int(1 <= active_yaw <= 20 and 12 <= link_yaw <= 85 and
               recovery_yaw <= 1 and report['active_can_turn'] and
               report['link_can_turn'] and not report['recovery_can_turn'])


def scenario():
    module = "__import__('TestBossReaim')"
    return {'name': 'Crunch re-aims between combo hits, tracks slightly on contact, and holds recovery',
            'steps': [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20},
                      {'action': 'python_assert_number', 'expression': f'{module}.begin()',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'wait', 'seconds': 17.0},
                      {'action': 'python_assert_number', 'expression': f'{module}.finish()',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'assert_log', 'not_contains': 'LogScript: Warning'}],
            'teardown': {'stop_pie': True}}
