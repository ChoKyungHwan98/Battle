"""Observe the real MotionLab number-key attacks, with no asset or timing edits."""
import json
import unreal

observer = None
records = []
samples = []


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def boss():
    return next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
                if a.get_class().get_name() == 'BP_Boss_Crunch_C')


def particles():
    found = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor):
        for component in actor.get_components_by_class(unreal.ParticleSystemComponent):
            template = component.get_editor_property('template')
            if template and 'ParagonCrunch/FX' in template.get_path_name():
                found.append({'asset': template.get_name(), 'active': component.is_active(),
                              'socket': str(component.get_attach_socket_name()),
                              'location': list(component.get_world_location().to_tuple())})
    return found


def stop():
    global observer
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None


def begin(key='Four', pause_position=-1, distance_key='X'):
    """Pause at a live montage frame for a stall-free screenshot, if requested."""
    global observer, records
    stop()
    records = []
    unreal.GameplayStatics.set_game_paused(world(), False)
    unreal.InputService.inject_key('R')
    unreal.InputService.inject_key(distance_key)
    state = {'requested': False, 'ticks': 0}

    def tick(_delta):
        if not world():
            stop()
            return
        state['ticks'] += 1
        if not state['requested']:
            if state['ticks'] >= 3:
                unreal.InputService.inject_key(key)
                state['requested'] = True
            return
        actor = boss()
        anim = actor.get_editor_property('Mesh').get_anim_instance()
        montage = actor.get_editor_property('AttackMontage')
        position = anim.montage_get_position(montage) if montage else 0
        record = {'t': unreal.GameplayStatics.get_time_seconds(world()),
                  'position': position, 'hit': actor.get_editor_property('bPhysicalStrikeHit'),
                  'fx': particles()}
        records.append(record)
        if pause_position >= 0 and position >= pause_position:
            unreal.GameplayStatics.set_game_paused(world(), True)
            print('FX_FRAME', json.dumps(record))
            stop()

    observer = unreal.register_slate_post_tick_callback(tick)
    return 1


def result(label):
    stop()
    assets = sorted({p['asset'] for r in records for p in r['fx'] if p['active']})
    summary = {'label': label, 'frames': len(records), 'assets_seen': assets,
               'contact_observed': any(r['hit'] for r in records),
               'remaining_active': [p['asset'] for p in particles() if p['active']]}
    samples.append(summary)
    path = unreal.Paths.project_saved_dir() + 'VibeUE/boss-attack-fx.json'
    with open(path, 'w', encoding='utf-8') as output:
        json.dump({'samples': samples, 'latest_records': records}, output, indent=2)
    print('FX_RESULT', json.dumps(summary), 'PATH', path)
    return summary


def suite():
    """Real key input, hit/miss separation, and end-of-action cleanup assertions."""
    global observer, samples
    stop()
    samples = []
    unreal.GameplayStatics.set_game_paused(world(), False)
    cases = [('One', 'X', 5.5, 'P_Crunch_Primary_Impact'),
             ('Two', 'X', 5.5, 'P_Crunch_Primary_Impact'),
             ('Four', 'X', 5.5, 'P_Crunch_Hook_Enemy_Impact'),
             ('Six', 'X', 5.5, 'P_Crunch_GutPunch_Impact'),
             ('Seven', 'B', 5.5, 'P_Crunch_Cross_Enemy_Impact'),
             ('Nine', 'B', 9.5, 'P_Crunch_Uppercut_Impact'),
             ('Five', 'X', 11.5, 'P_Crunch_Primary_Impact'),
             ('One', 'B', 5.5, None)]
    state = {'case': -1, 'start': 0, 'prepare': True, 'requested': False,
             'seen': set(), 'hit': False, 'ticks': 0}

    def tick(_delta):
        if not world():
            stop()
            return
        now = unreal.GameplayStatics.get_time_seconds(world())
        if state['prepare']:
            state['case'] += 1
            if state['case'] == len(cases):
                stop()
                print('FX_SUITE_DONE', json.dumps(samples))
                with open(unreal.Paths.project_saved_dir() + 'VibeUE/boss-attack-fx-suite.json',
                          'w', encoding='utf-8') as out:
                    json.dump(samples, out, indent=2)
                return
            unreal.InputService.inject_key('R')
            unreal.InputService.inject_key(cases[state['case']][1])
            state.update(prepare=False, requested=False, start=now, seen=set(), hit=False, ticks=0)
            return
        state['ticks'] += 1
        # Allow the reset and any earlier player reaction to finish before the next request.
        if not state['requested']:
            if now - state['start'] > 4:
                unreal.InputService.inject_key(cases[state['case']][0])
                state.update(requested=True, start=now)
            return
        state['seen'].update(p['asset'] for p in particles() if p['active'])
        state['hit'] |= boss().get_editor_property('bPhysicalStrikeHit')
        if now - state['start'] >= cases[state['case']][2]:
            key, distance, _, expected = cases[state['case']]
            active = [p['asset'] for p in particles() if p['active']]
            impacts = {p for p in state['seen'] if 'Impact' in p}
            ok = expected in state['seen'] if expected else not impacts and not state['hit']
            samples.append({'key': key, 'distance_key': distance, 'seen': sorted(state['seen']),
                            'contact': state['hit'], 'remaining_active': active,
                            'passed': bool(ok and not active)})
            print('FX_CASE', json.dumps(samples[-1]))
            state['prepare'] = True

    observer = unreal.register_slate_post_tick_callback(tick)
    return 1


def passed():
    return int(len(samples) == 8 and all(s['passed'] for s in samples))
