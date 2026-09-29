"""Transient PIE observations for Kubold's R/RL/RLL/RLLR chain.

No timing captures inside a measured run. Samples use the actual montage clock.
"""
import json
import unreal
import TestSwordShield as T
import TestSoulsHits as H

handle = None
samples = []
mode = ''
index = 0
started = 0
done = False
origin = None
pressed = set()
montages = []


def prepare(kind='geometry'):
    global montages
    if kind in ['geometry', 'contact_chain']:
        H.setup(205)
        if kind == 'contact_chain':
            # The horizontal second slash can pass between Crunch's leg hurtboxes
            # head-on. Offset the transient target 45cm so its leg intersects the
            # visible blade; leave all production collision shapes unchanged.
            H.boss().set_actor_location(H.boss().get_actor_location()+unreal.Vector(0,45,0),False,False)
    else:
        T.setup()
    montages = list(T.player().get_editor_property('AttackMontages'))
    return 1


def begin(kind='geometry'):
    global handle, samples, mode, index, started, done, origin, pressed
    stop()
    mode, index, done, pressed, samples = kind, 0, False, set(), []
    p = T.player()
    if kind == 'geometry':
        p.set_editor_property('AttackPlayRate', 1.)
        p.set_editor_property('AttackMontages', [montages[0]])
    origin = p.get_actor_location()
    started = unreal.GameplayStatics.get_time_seconds(T.world())
    p.call_method('TryEnterAttack')
    handle = unreal.register_slate_post_tick_callback(tick)
    return 1


def tick(delta):
    global index, done
    if not T.world() or done:
        return
    p, anim = T.player(), T.player().mesh.get_anim_instance()
    now = unreal.GameplayStatics.get_time_seconds(T.world())
    if now - started > 8:
        done = True
        return
    m = anim.get_current_active_montage()
    if m and 'AM_Sword_Attack_' in m.get_name():
        number = int(m.get_name().rsplit('_', 1)[1])
        pos = anim.montage_get_position(m)
        sword = next(c for c in p.get_components_by_class(unreal.StaticMeshComponent)
                     if c.get_name() == 'Sword')
        tr = sword.get_world_transform()
        base = tr.transform_location(unreal.Vector(0, 0, 8))
        tip = tr.transform_location(unreal.Vector(0, 0, 99))
        contact = None
        if mode in ['geometry', 'contact_chain']:
            contact = unreal.SystemLibrary.sphere_trace_single(T.world(), base, tip, 12,
                unreal.TraceTypeQuery.ECC_VISIBILITY, False, [p], unreal.DrawDebugTrace.NONE, False)
        samples.append({'t': now-started, 'number': number, 'pos': pos, 'state': T.state(),
            'window': p.get_editor_property('bSwordWindowOpen'),
            'combo': p.get_editor_property('bComboWindowOpen'),
            'hit': p.get_editor_property('bSwordHasHit'), 'contact': contact is not None,
            'hp': H.boss().get_editor_property('CurrentHealth') if mode == 'contact_chain' else None,
            'location': p.get_actor_location().to_tuple(), 'base': base.to_tuple(), 'tip': tip.to_tuple()})
        # Physical injection goes through the existing LMB input binding once per hit.
        if mode in ['chain', 'contact_chain'] and number < 4 and pos >= .20 and number not in pressed:
            unreal.InputService.inject_key('LeftMouseButton', 'down')
            pressed.add(number)
        elif mode in ['chain', 'contact_chain'] and number in pressed:
            unreal.InputService.inject_key('LeftMouseButton', 'up')
    elif T.state() == 5:
        if mode == 'geometry' and index < 3:
            index += 1
            p.set_actor_location(origin, False, False)
            p.character_movement.stop_movement_immediately()
            p.set_editor_property('AttackMontages', [montages[index]])
            p.call_method('TryEnterAttack')
        else:
            done = True


def stop():
    global handle
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    return 1


def report():
    stop()
    summary = []
    for number in range(1, 5):
        rows = [s for s in samples if s['number'] == number]
        contacts = [s['pos'] for s in rows if s['contact']]
        summary.append({'number': number, 'samples': len(rows),
            'first': rows[0]['t'] if rows else None,
            'last_pose_time': rows[-1]['pos'] if rows else None,
            'contacts': [min(contacts), max(contacts)] if contacts else [],
            'travel': (unreal.Vector(*rows[-1]['location']) - unreal.Vector(*rows[0]['location'])).length() if rows else 0})
    path = unreal.Paths.project_saved_dir()+'VibeUE/reference-sword-'+mode+'.json'
    passed = done and all(s['samples'] > 0 for s in summary) and T.state() == 5
    if mode in ['chain', 'contact_chain']:
        numbers = [s['number'] for s in samples]
        passed = passed and numbers == sorted(numbers) and all(s['state'] == 4 for s in samples)
        for n, join in enumerate([.55, 22/60, 32/60], 1):
            passed = passed and abs(summary[n-1]['last_pose_time'] - join) < .04
        if mode == 'contact_chain':
            for n in range(1, 5):
                rows = [s for s in samples if s['number'] == n]
                drops = sum(rows[i]['hp'] < rows[i-1]['hp'] for i in range(1, len(rows)))
                summary[n-1]['hp_drops'] = drops
                summary[n-1]['confirmed_hit'] = any(s['hit'] for s in rows)
                passed = passed and drops == 1 and summary[n-1]['confirmed_hit']
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'mode': mode, 'done': done, 'passed': passed, 'summary': summary, 'samples': samples}, f, indent=2)
    print('REFERENCE_SWORD', json.dumps({'passed': passed, 'done': done, 'summary': summary, 'path': path}))
    return int(passed)


def pose(number, position=.30):
    """Pause after blend-in solely for visual inspection; never used for timing."""
    global handle
    stop()
    p = T.player()
    p.mesh.get_anim_instance().montage_stop(0.)
    p.call_method('OnAttackRecoveryTimer')
    p.set_actor_tick_enabled(True)
    p.character_movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
    p.get_controller().set_control_rotation(unreal.Rotator(yaw=65, pitch=-10))
    p.set_editor_property('AttackMontages', [montages[number-1]])
    p.call_method('TryEnterAttack')
    def pause(delta):
        global handle
        a = p.mesh.get_anim_instance()
        m = a.get_current_active_montage()
        if m and a.montage_get_position(m) >= position:
            a.montage_pause(m)
            p.set_actor_tick_enabled(False)
            p.character_movement.stop_movement_immediately()
            p.character_movement.disable_movement()
            unreal.unregister_slate_post_tick_callback(handle)
            handle = None
    handle = unreal.register_slate_post_tick_callback(pause)
    return 1
