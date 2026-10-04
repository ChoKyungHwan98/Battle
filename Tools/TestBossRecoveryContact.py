"""Probe whether a missed combo can damage a target after Recovery begins."""
import json

import unreal
import TestSoulsHits as fixture


observer = None
result = {}


def begin():
    global observer, result
    fixture.setup(450)
    boss = fixture.boss()
    player = fixture.player()
    result = {'entered_recovery': False, 'health_before': player.get_editor_property('CurrentHealth')}

    def tick(_delta):
        if not fixture.world():
            return
        phase = boss.get_editor_property('BossState').export_text()
        if 'Attack.Recovery' in phase and not result['entered_recovery']:
            mesh = boss.get_component_by_class(unreal.SkeletalMeshComponent)
            socket = boss.get_editor_property('PhysicalStrikeSocket')
            hand = mesh.get_socket_location(socket)
            result.update(entered_recovery=True,
                          strike_already_hit=bool(boss.get_editor_property('bPhysicalStrikeHit')),
                          strike_window_open=bool(boss.get_editor_property('bPhysicalStrikeOpen')),
                          health_at_entry=player.get_editor_property('CurrentHealth'),
                          hand=hand.to_tuple())
            player.set_actor_location(hand+unreal.Vector(0, 0, -15), False, False)

    observer = unreal.register_slate_post_tick_callback(tick)
    boss.call_method('RequestCombatAction', (4,))
    boss.set_actor_tick_enabled(True)
    return int(boss.get_editor_property('ActiveAction') == boss.get_editor_property('Actions')[4])


def finish():
    global observer
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    result['health_after'] = fixture.player().get_editor_property('CurrentHealth')
    result['damage_after_recovery_started'] = (result.get('health_at_entry', result['health_before'])-
                                                result['health_after'])
    path = unreal.Paths.project_saved_dir() + 'VibeUE/boss-recovery-contact.json'
    with open(path, 'w', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print('RECOVERY_CONTACT', json.dumps(result), 'PATH', path)
    return int(result['entered_recovery'] and not result['strike_already_hit'] and
               not result['strike_window_open'] and
               result['damage_after_recovery_started'] == 0)


def scenario():
    module = "__import__('TestBossRecoveryContact')"
    return {'name': 'Probe missed final combo hit entering physical hand during Recovery',
            'steps': [{'action': 'start_pie'}, {'action': 'wait_for_pie', 'timeout_seconds': 20},
                      {'action': 'python_assert_number', 'expression': f'{module}.begin()',
                       'expected': 1, 'operator': 'eq'},
                      {'action': 'wait', 'seconds': 10},
                      {'action': 'python_assert_number', 'expression': f'{module}.finish()',
                       'expected': 1, 'operator': 'eq'}],
            'teardown': {'stop_pie': True}}
