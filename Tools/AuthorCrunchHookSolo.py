"""MotionLab-only card that plays the jab-jab-hook's third hit (Ability_Hook) on its own, so its reach can be measured.

The hook exists in the game only as the last hit of the chain. This copies that segment (same clip, same 1.15x
rate, same strike window relative to the segment) into its own montage and card. The montage is duplicated from
the left punch so the strike notify is the single-hit class (ANS_PhysicalStrike_0) with its particle setup.
Requested in the lab with K (it rides the left-punch slot; see LabHookCardPath in BossCombatIntentComponent.cpp).
"""
import unreal
import CrunchControlRigAuthoring as common
import AuthorCrunchOriginalStep as util

ROOT = common.ROOT
ACTIONS = '/Game/BossArena/Boss/AI/Actions/'
CHAIN = '/Game/BossArena/Boss/Animations/AM_Boss_Jab_Jab_Hook_Matched'
LEFT_CARD = ACTIONS + 'DA_Attack_Left'
CHAIN_CARD = ACTIONS + 'DA_Attack_Combo'
MONTAGE = ROOT + '/AM_Crunch_HookSolo'
CARD = ACTIONS + 'DA_Lab_Hook'
DISPLAY = '훅 단독 (모션랩 K)'


def build():
    common.require_editor()
    service = unreal.AnimMontageService
    hook = list(service.list_anim_segments(CHAIN, 0))[-1]
    assert hook.anim_sequence_path.endswith('Ability_Hook'), hook.anim_sequence_path
    chain_notes = {str(n.notify_name): n for n in service.list_notifies(CHAIN) if n.trigger_time >= hook.start_time - .001}
    strike, particle = chain_notes['PhysicalStrike2'], chain_notes['ANS_BossScaledParticle']

    left_card = unreal.EditorAssetLibrary.load_asset(LEFT_CARD)
    montage = util.duplicate(left_card.get_editor_property('Montage').get_path_name(), MONTAGE)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(montage)
    tracks = list(montage.get_editor_property('slot_anim_tracks'))
    track = tracks[0].get_editor_property('anim_track')
    segment = list(track.get_editor_property('anim_segments'))[0]
    clip = unreal.EditorAssetLibrary.load_asset(hook.anim_sequence_path.split('.')[0])
    segment.set_editor_property('anim_reference', clip)
    segment.set_editor_property('anim_start_time', hook.anim_start_pos)
    segment.set_editor_property('anim_end_time', hook.anim_end_pos)
    segment.set_editor_property('anim_play_rate', hook.play_rate)
    segment.set_editor_property('cached_play_length', clip.get_play_length())
    track.set_editor_property('anim_segments', [segment]);tracks[0].set_editor_property('anim_track', track)
    montage.modify();montage.set_editor_property('slot_anim_tracks', tracks)
    common.save(montage)
    assert service.set_segment_end_position(MONTAGE, 0, 0, hook.anim_end_pos)
    unreal.AnimationLibrary.remove_animation_notify_events_by_name(montage, 'ANS_BossAttackStep')
    for n in service.list_notifies(MONTAGE):
        source = strike if str(n.notify_name) == 'PhysicalStrike0' else particle
        assert service.set_notify_trigger_time(MONTAGE, n.notify_index, source.trigger_time - hook.start_time)
        assert service.set_notify_duration(MONTAGE, n.notify_index, source.duration)
    common.save(montage)
    length = montage.get_play_length()
    assert abs(length - hook.duration) < .02, (length, hook.duration)

    chain_card = unreal.EditorAssetLibrary.load_asset(CHAIN_CARD)
    rate = chain_card.get_editor_property('PlayRate')
    telegraph = chain_card.get_editor_property('TelegraphSeconds')
    # Card times keep the chain's relation to its third strike: impact (real seconds) and window end (montage seconds).
    impact = telegraph + (list(chain_card.get_editor_property('ImpactTimes'))[2] - telegraph) - hook.start_time / rate
    window_end = list(chain_card.get_editor_property('HitWindowEnds'))[2] - hook.start_time
    card = unreal.EditorAssetLibrary.load_asset(CARD) if unreal.EditorAssetLibrary.does_asset_exist(CARD) \
        else util.duplicate(LEFT_CARD, CARD)
    card.modify()
    card.set_editor_property('Montage', montage)
    card.set_editor_property('DisplayName', DISPLAY)
    card.set_editor_property('PlayRate', rate)
    card.set_editor_property('TelegraphSeconds', telegraph)
    card.set_editor_property('ImpactTimes', [impact])
    card.set_editor_property('HitWindowEnds', [window_end])
    card.set_editor_property('TotalSeconds', telegraph + length / rate + .05)
    # The hook is thrown with the right hand; the left-punch card this was copied from sweeps the left one.
    sockets = list(chain_card.get_editor_property('HitSockets'))
    damages = list(chain_card.get_editor_property('HitDamages'))
    card.set_editor_property('HitSockets', [sockets[2]])
    card.set_editor_property('HitDamages', [damages[2]] if len(damages) > 2 else [65.])
    card.set_editor_property('Damage', damages[2] if len(damages) > 2 else 65.)
    card.set_editor_property('MinDistance', 0.)
    card.set_editor_property('MaxDistance', chain_card.get_editor_property('MaxDistance'))
    common.save(card)
    print('HOOK SOLO', MONTAGE, round(length, 3), 's; notifies',
        [(str(n.notify_name), round(n.trigger_time, 3), round(n.duration, 3)) for n in service.list_notifies(MONTAGE)],
        'impact', round(impact, 3), 'window end', round(window_end, 3))
