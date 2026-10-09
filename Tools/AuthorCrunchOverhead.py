"""New attack: right-hand overhead smash (오른손 내려찍기), from the unused Paragon clip Ability_Combo_04.

The clip is the 4th hit of Crunch's own combo: the right fist goes up over the head (0.10s) and comes down (0.30s).
It starts from the 3rd hit's end pose, not from idle, so a lead-in is authored the same way as the mid-range uppercut
(AuthorCrunchRunIn.prepare_lead): PREFIX seconds from the idle stance into the clip, with the raise stretched over the
whole lead-in. The boss lifts the fist slowly and brings it down at the clip's own speed. A tail settles back to idle.

Run in the editor:  build()
"""
import json
from pathlib import Path
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util
import AuthorCrunchRunIn as lead

CLIP = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_04'
ANIM = common.ROOT + '/AS_Crunch_OverheadSmash'
MONTAGE = common.ROOT + '/AM_Crunch_OverheadSmash'
TEMPLATE_MONTAGE = common.ROOT + '/AM_Crunch_UppercutCharged'      # same slot, blend settings and notify classes
ACTIONS = '/Game/BossArena/Boss/AI/Actions/'
CARD = ACTIONS + 'DA_Attack_Overhead'
PREFIX, TAIL = .45, .40
STRIKE = (.14, .33)            # clip seconds the fist is coming down
ACTION_ID = 10
lead.CONFIG[20] = dict(source=ANIM, clip=CLIP, prefix=PREFIX, tail=TAIL, stem='OverheadSmash')


def build(weight=16., damage=140., cooldown=6., min_distance=165., max_distance=285.):
    common.require_editor()
    lead.prepare_lead(20)
    anim = unreal.EditorAssetLibrary.load_asset(ANIM)
    length = anim.get_play_length()
    montage = util.duplicate(TEMPLATE_MONTAGE, MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    track = tracks[0].get_editor_property('anim_track')
    segment = list(track.get_editor_property('anim_segments'))[0]
    segment.set_editor_property('anim_reference', anim)
    segment.set_editor_property('anim_end_time', length)
    segment.set_editor_property('anim_play_rate', 1.)
    segment.set_editor_property('cached_play_length', length)
    track.set_editor_property('anim_segments', [segment]); tracks[0].set_editor_property('anim_track', track)
    montage.modify(); montage.set_editor_property('slot_anim_tracks', tracks)
    common.save(montage)
    assert unreal.AnimMontageService.set_segment_end_position(MONTAGE, 0, 0, length)
    service = unreal.AnimMontageService
    # Keep only what this attack needs: its strike window and the combo bookkeeping events. The uppercut's fist
    # flame and the old "step" push do not belong here.
    for name in ('ANS_BossScaledParticle', 'ANS_BossAttackStep'):
        for n in sorted(service.list_notifies(MONTAGE), key=lambda n: -n.notify_index):
            if str(n.notify_name) == name:
                assert service.remove_notify(MONTAGE, n.notify_index)
    begin, end = PREFIX + STRIKE[0], PREFIX + STRIKE[1]
    for n in service.list_notifies(MONTAGE):
        name = str(n.notify_name)
        if name == 'PhysicalStrike0':
            assert service.set_notify_trigger_time(MONTAGE, n.notify_index, begin)
            assert service.set_notify_duration(MONTAGE, n.notify_index, end - begin)
        elif name == 'SaveAttack':
            assert service.set_notify_trigger_time(MONTAGE, n.notify_index, end + .30)
        elif name == 'ResetCombo':
            assert service.set_notify_trigger_time(MONTAGE, n.notify_index, min(length - .05, end + .60))
    common.save(montage)
    assert abs(montage.get_play_length() - length) < .01, montage.get_play_length()
    if unreal.EditorAssetLibrary.does_asset_exist(CARD):
        card = unreal.EditorAssetLibrary.load_asset(CARD)
    else:
        card = util.duplicate(ACTIONS + 'DA_Attack_Uppercut', CARD)
    right = unreal.EditorAssetLibrary.load_asset(ACTIONS + 'DA_Attack_Right')
    rate, telegraph = .75, .08
    card.modify()
    for name, value in [('ActionId', ACTION_ID), ('DisplayName', '오른손 내려찍기'), ('BaseWeight', weight), ('MinDistance', min_distance),
            ('MaxDistance', max_distance), ('CooldownSeconds', cooldown), ('ObservationRule', 0), ('Montage', montage),
            ('TelegraphSeconds', telegraph), ('PlayRate', rate), ('HitSockets', right.get_editor_property('HitSockets')),
            ('HitDamages', [damage]), ('ImpactTimes', [telegraph + (begin + .08) / rate]), ('HitWindowEnds', [end]),
            ('TotalSeconds', telegraph + length / rate + .35), ('bEnabled', True)]:
        card.set_editor_property(name, value)
    common.save(card)
    report = {'animation': ANIM, 'montage': MONTAGE, 'card': CARD, 'length': length, 'strike_window': [begin, end],
              'impact_seconds': list(card.get_editor_property('ImpactTimes')), 'total_seconds': card.get_editor_property('TotalSeconds'),
              'notifies': [(str(n.notify_name), round(n.trigger_time, 3), round(n.duration, 3)) for n in service.list_notifies(MONTAGE)]}
    path = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/Reports/crunch_overhead.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BUILT overhead smash', json.dumps(report, ensure_ascii=False))
    return report
