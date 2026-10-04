"""Measure real boss strike/recovery boundaries in PIE without editing assets."""
import json

import unreal
import TestSoulsHits as fixture


observer = None
samples = []
action_index = -1
started_at = 0.0


def begin(index=0, distance=250):
    global observer, samples, action_index, started_at
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    fixture.setup(distance)
    action_index = index
    samples = []
    boss = fixture.boss()
    player = fixture.player()
    started_at = unreal.GameplayStatics.get_time_seconds(fixture.world())

    def tick(_delta):
        world = fixture.world()
        if not world:
            return
        phase = boss.get_editor_property('BossState').export_text()
        mesh = boss.get_component_by_class(unreal.SkeletalMeshComponent)
        montage = mesh.get_anim_instance().get_current_active_montage()
        socket = str(boss.get_editor_property('PhysicalStrikeSocket'))
        hand = mesh.get_socket_location(socket) if socket and socket != 'None' else None
        center = player.get_actor_location()
        capsule = player.get_component_by_class(unreal.CapsuleComponent)
        if hand:
            dx, dy, dz = hand.x-center.x, hand.y-center.y, hand.z-center.z
            radial = max(0, (dx*dx+dy*dy)**0.5-capsule.get_scaled_capsule_radius())
            vertical = max(0, abs(dz)-capsule.get_scaled_capsule_half_height())
            hand_gap = round((radial*radial+vertical*vertical)**0.5, 2)
        else:
            hand_gap = None
        samples.append({
            't': round(unreal.GameplayStatics.get_time_seconds(world) - started_at, 4),
            'phase': phase,
            'window': bool(boss.get_editor_property('bPhysicalStrikeOpen')),
            'hit': bool(boss.get_editor_property('bPhysicalStrikeHit')),
            'can_turn': bool(boss.get_editor_property('bCanTurn')),
            'boss_xy': [round(boss.get_actor_location().x, 2), round(boss.get_actor_location().y, 2)],
            'player_hp': round(player.get_editor_property('CurrentHealth'), 2),
            'montage': montage.get_name() if montage else '',
            'montage_position': round(mesh.get_anim_instance().montage_get_position(montage), 4)
                                if montage else None,
            'strike_socket': socket,
            'hand_gap_cm': hand_gap,
        })

    observer = unreal.register_slate_post_tick_callback(tick)
    boss.call_method('RequestCombatAction', (index,))
    boss.set_actor_tick_enabled(True)
    return int(boss.get_editor_property('ActiveAction') == boss.get_editor_property('Actions')[index])


def finish():
    global observer
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    active = [s for s in samples if 'Attack.Active' in s['phase']]
    recovery = [s for s in samples if 'Attack.Recovery' in s['phase']]
    if not recovery:
        print('PUNISH_INCOMPLETE', action_index, len(samples))
        return 0
    recovery_start = recovery[0]['t']
    later_ready = next((s['t'] for s in samples if s['t'] > recovery_start and
                        'Boss.Combat.Ready' in s['phase']), None)
    last_open = max((s['t'] for s in samples if s['window']), default=None)
    last_active = max((s['t'] for s in active), default=None)
    first_recovery_xy = recovery[0]['boss_xy']
    last_recovery_xy = recovery[-1]['boss_xy']
    movement = round(sum((b-a)**2 for a, b in zip(first_recovery_xy, last_recovery_xy))**0.5, 2)
    report = {
        'action_index': action_index,
        'sample_count': len(samples),
        'last_hit_window_open': last_open,
        'last_active_sample': last_active,
        'recovery_start': recovery_start,
        'ready_after_recovery': later_ready,
        'recovery_duration': round(later_ready-recovery_start, 3) if later_ready else None,
        'safe_time_after_hit_window': round(later_ready-last_open, 3) if later_ready and last_open else None,
        'boss_recovery_movement_cm': movement,
        'turned_during_recovery': any(s['can_turn'] for s in recovery),
        'strike_open_during_recovery': any(s['window'] for s in recovery),
        'player_damage': round(samples[0]['player_hp']-samples[-1]['player_hp'], 2),
    }
    path = unreal.Paths.project_saved_dir() + f'VibeUE/boss-punish-window-{action_index}.json'
    with open(path, 'w', encoding='utf-8') as output:
        json.dump({'report': report, 'samples': samples}, output, ensure_ascii=False, indent=2)
    print('PUNISH_WINDOW', json.dumps(report, ensure_ascii=False), 'PATH', path)
    return int(later_ready is not None and last_open is not None and
               report['safe_time_after_hit_window'] >= 0.6 and
               last_open < recovery_start and movement <= 2 and
               not report['turned_during_recovery'] and
               not report['strike_open_during_recovery'])


def scenario(index=0, distance=250, wait_seconds=6):
    module = "__import__('TestBossPunishWindow')"
    return {
        'name': f'Crunch action {index} physical hit window and guaranteed recovery',
        'steps': [
            {'action': 'start_pie'},
            {'action': 'wait_for_pie', 'timeout_seconds': 20},
            {'action': 'python_assert_number', 'expression': f'{module}.begin({index},{distance})',
             'expected': 1, 'operator': 'eq'},
            {'action': 'wait', 'seconds': wait_seconds},
            {'action': 'python_assert_number', 'expression': f'{module}.finish()',
             'expected': 1, 'operator': 'eq'},
            {'action': 'assert_log', 'not_contains': 'LogScript: Warning'},
        ],
        'teardown': {'stop_pie': True},
        'dependencies': ['Tools/TestBossPunishWindow.py',
                         'Content/BossArena/Boss/Blueprints/BP_Boss_Crunch.uasset',
                         'Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset'],
    }
