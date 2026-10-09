"""Key 3 (uppercut), short version: gather, hold, then strike - the same read as keys 1 and 2.

The Paragon clip cocks the fist in 0.10s and is already rising at 0.15s, so the boss used to stand still for a 0.4s
telegraph and then hit almost at once: nothing in the body said "this is coming". Here the clip is only retimed:

    0.00 .. HOLD   the clip's first 0.145s (crouch, fist low) stretched over 0.42s: quick at first, slowing to a
                   tenth of the clip's speed, then accelerating into the punch. It never stops.
    HOLD ..        the clip from 0.145s on, unchanged

No pose is invented and nothing after the release changes. Every event of the attack moves PREFIX seconds later.
Run in the editor:  prepare() -> integrate()
"""
import json
import math
from pathlib import Path
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util

CLIP = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_03'
ANIM = common.ROOT + '/AS_Crunch_UppercutCharged'
MONTAGE = common.ROOT + '/AM_Crunch_UppercutCharged'
CARD = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Uppercut'
SOURCE_MONTAGE = '/Game/BossArena/Boss/Animations/AM_Boss_Combo_03'
FPS = 60
HOLD = .42                      # montage seconds at which the clip takes over at its own speed
RELEASE = .145                  # clip seconds reached at HOLD
PREFIX = HOLD - RELEASE         # how much later everything after the release happens
TELEGRAPH = .08                 # same short telegraph as keys 1 and 2: the windup is now in the body
# (montage seconds, clip seconds, clip speed). The first version reached the cocked pose and then froze for 0.24s:
# a held frame. A person gathering for a punch keeps sinking, slower and slower, and then goes. So the body never
# stops: it slows to about a tenth of the clip's speed in the middle and is back at full speed exactly at HOLD.
KEYS = [(0., 0., .6), (.20, .07, .12), (HOLD, RELEASE, 1.)]


def clip_time(t):
    if t >= HOLD:
        return t - PREFIX
    for (t0, c0, m0), (t1, c1, m1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            h = t1 - t0
            u = (t - t0) / h
            return ((2*u**3 - 3*u**2 + 1) * c0 + (u**3 - 2*u**2 + u) * h * m0
                    + (-2*u**3 + 3*u**2) * c1 + (u**3 - u**2) * h * m1)
    return t - PREFIX


def prepare():
    common.require_editor()
    clip = unreal.EditorAssetLibrary.load_asset(CLIP)
    length = clip.get_play_length()
    last = math.ceil((length + PREFIX) * FPS / 2) * 2
    anim = util.duplicate(CLIP, ANIM)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(anim)
    anim.modify()
    samples = [common.poses(CLIP, min(clip_time(f / FPS), length)) for f in range(last + 1)]
    controller = anim.get_editor_property('controller')
    controller.open_bracket('Retime the uppercut: gather, hold, strike', False)
    try:
        controller.set_frame_rate(unreal.FrameRate(FPS, 1), False)
        controller.set_number_of_frames(unreal.FrameNumber(last), False)
        for name in anim.get_editor_property('data_model_interface').get_bone_track_names():
            keys = [p[str(name)] for p in samples]
            assert controller.set_bone_track_keys(name, [k.translation for k in keys], [k.rotation for k in keys],
                [k.scale3d for k in keys], False), name
    finally:
        controller.close_bracket(False)
    common.save(anim)
    # The release must be continuous: the same pose just before and at HOLD, and the clip itself afterwards.
    after = common.poses(ANIM, HOLD + .2, True)['hand_l'].translation
    source = common.poses(CLIP, RELEASE + .2, True)['hand_l'].translation
    times = [clip_time(f / FPS) for f in range(int(HOLD * FPS) + 2)]
    report = {'length': last / FPS, 'prefix': PREFIX, 'after_release_error_cm': (after - source).length(),
              'slowest_speed': min((b - a) * FPS for a, b in zip(times, times[1:])),
              'release_speed': (clip_time(HOLD) - clip_time(HOLD - 1. / FPS)) * FPS}
    print('PREPARED', json.dumps(report))
    assert report['after_release_error_cm'] < .5 and report['slowest_speed'] > .05 and abs(report['release_speed'] - 1.) < .1, report
    return report


def integrate():
    common.require_editor()
    card = unreal.EditorAssetLibrary.load_asset(CARD)
    source = unreal.EditorAssetLibrary.load_asset(SOURCE_MONTAGE)
    path = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/crunch_uppercut_charge.json'
    before = {n: (list(card.get_editor_property(n)) if n in ('ImpactTimes', 'HitWindowEnds') else card.get_editor_property(n))
              for n in ['TelegraphSeconds', 'ImpactTimes', 'HitWindowEnds', 'TotalSeconds', 'PlayRate']}
    before['Montage'] = card.get_editor_property('Montage').get_path_name()
    if before['Montage'].split('.')[0] == MONTAGE and path.exists():       # running again: keep the true original
        before = json.loads(path.read_text(encoding='utf-8'))['original_card']
    montage = util.duplicate(SOURCE_MONTAGE, MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    track = tracks[0].get_editor_property('anim_track')
    segment = list(track.get_editor_property('anim_segments'))[0]
    duration = source.get_play_length() + PREFIX
    segment.set_editor_property('anim_reference', unreal.EditorAssetLibrary.load_asset(ANIM))
    segment.set_editor_property('anim_end_time', duration)
    segment.set_editor_property('anim_play_rate', 1.)
    segment.set_editor_property('cached_play_length', duration)
    track.set_editor_property('anim_segments', [segment]); tracks[0].set_editor_property('anim_track', track)
    montage.modify(); montage.set_editor_property('slot_anim_tracks', tracks)
    common.save(montage)
    assert unreal.AnimMontageService.set_segment_end_position(MONTAGE, 0, 0, duration)
    order = lambda items: sorted(items, key=lambda n: (str(n.notify_name), n.trigger_time))
    originals = order(unreal.AnimMontageService.list_notifies(SOURCE_MONTAGE))
    for n, o in zip(order(unreal.AnimMontageService.list_notifies(MONTAGE)), originals):
        assert unreal.AnimMontageService.set_notify_trigger_time(MONTAGE, n.notify_index, o.trigger_time + PREFIX), str(n.notify_name)
    common.save(montage)
    assert abs(montage.get_play_length() - duration) < .01, montage.get_play_length()
    rate = before['PlayRate']
    moved = PREFIX / rate + TELEGRAPH - before['TelegraphSeconds']      # real seconds from the start of the action
    card.modify()
    card.set_editor_property('Montage', montage)
    card.set_editor_property('TelegraphSeconds', TELEGRAPH)
    card.set_editor_property('ImpactTimes', [v + moved for v in before['ImpactTimes']])
    card.set_editor_property('HitWindowEnds', [v + PREFIX for v in before['HitWindowEnds']])
    card.set_editor_property('TotalSeconds', before['TotalSeconds'] + moved)
    common.save(card)
    report = {'original_card': before, 'montage': MONTAGE, 'telegraph': TELEGRAPH,
              'impact': list(card.get_editor_property('ImpactTimes')), 'hit_window_end': list(card.get_editor_property('HitWindowEnds')),
              'total': card.get_editor_property('TotalSeconds'),
              'notifies': [(str(n.notify_name), round(n.trigger_time, 3)) for n in unreal.AnimMontageService.list_notifies(MONTAGE)]}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('MODIFIED uppercut card', json.dumps(report, ensure_ascii=False))
    return report
