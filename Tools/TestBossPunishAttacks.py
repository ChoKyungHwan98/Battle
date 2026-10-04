"""Use real mapped attack keys during the boss combo's recovery."""
import json

import unreal
import TestSoulsHits as fixture
import TestCombatReadability as player_combo


observer = None
records = []
started = False
key_held = False


def begin():
    global observer, records, started, key_held
    fixture.setup(450)
    boss = fixture.boss()
    player = fixture.player()
    records = []
    started = False
    key_held = False
    player_combo.observe(True)

    def tick(_delta):
        global started, key_held
        if not fixture.world():
            return
        phase = boss.get_editor_property('BossState').export_text()
        if not started and 'Attack.Recovery' in phase:
            boss_half = boss.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
            player_half = player.get_component_by_class(unreal.CapsuleComponent).get_scaled_capsule_half_height()
            player.set_actor_location(boss.get_actor_location() + boss.get_actor_forward_vector()*190 +
                                      unreal.Vector(0, 0, player_half-boss_half), False, False)
            player.set_actor_rotation(unreal.Rotator(yaw=boss.get_actor_rotation().yaw+180), False)
            player.get_controller().set_control_rotation(unreal.Rotator(yaw=boss.get_actor_rotation().yaw+180))
            unreal.InputService.inject_key('LeftMouseButton', 'down')
            key_held = True
            started = True
        elif key_held:
            unreal.InputService.inject_key('LeftMouseButton', 'up')
            key_held = False
        records.append({'t': round(unreal.GameplayStatics.get_time_seconds(fixture.world()), 3),
                        'boss_phase': phase,
                        'boss_hp': boss.get_editor_property('CurrentHealth'),
                        'player_state': player.get_editor_property('ActionState').value,
                        'player_attack_start': player.get_editor_property('AttackStartTime')})

    observer = unreal.register_slate_post_tick_callback(tick)
    boss.call_method('RequestCombatAction', (4,))
    boss.set_actor_tick_enabled(True)
    return int(boss.get_editor_property('ActiveAction') == boss.get_editor_property('Actions')[4])


def finish():
    global observer, key_held
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    if key_held:
        unreal.InputService.inject_key('LeftMouseButton', 'up')
        key_held = False
    player_combo.stop_observing()
    attack_starts = []
    damage = []
    for before, after in zip(records, records[1:]):
        if after['player_attack_start'] != before['player_attack_start'] and after['player_state'] == 4:
            attack_starts.append(after['t'])
        if after['boss_hp'] < before['boss_hp']:
            damage.append({'t': after['t'], 'amount': before['boss_hp']-after['boss_hp'],
                           'boss_phase': after['boss_phase']})
    first_ready = next((r['t'] for r in records if started and 'Boss.Combat.Ready' in r['boss_phase']
                        and r['t'] > attack_starts[0]), None) if attack_starts else None
    before_ready = [hit for hit in damage if first_ready is not None and hit['t'] < first_ready]
    result = {'started': started, 'attack_starts': attack_starts, 'damage': damage,
              'ready_after_recovery': first_ready, 'hits_before_ready': len(before_ready),
              'boss_hp_final': fixture.boss().get_editor_property('CurrentHealth')}
    path = unreal.Paths.project_saved_dir() + 'VibeUE/boss-punish-attacks.json'
    with open(path, 'w', encoding='utf-8') as output:
        json.dump({'result': result, 'records': records}, output, indent=2)
    print('PUNISH_ATTACKS', json.dumps(result), 'PATH', path)
    return int(started and len(attack_starts) >= 3 and len(before_ready) >= 3)


def scenario():
    module = "__import__('TestBossPunishAttacks')"
    return {'name': 'Actual mapped player attacks punish a missed Crunch three-hit combo',
            'steps': [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20},
                      {'action': 'python_assert_number', 'expression': f'{module}.begin()',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'wait', 'seconds': 11},
                      {'action': 'python_assert_number', 'expression': f'{module}.finish()',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'assert_log', 'not_contains': 'LogScript: Warning'}],
            'teardown': {'stop_pie': True}}
