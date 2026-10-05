"""Prepare a separate two-hit pattern through Unreal MCP, without running PIE.

New cards start disabled and outside the live action array. IntegrateBossTwoHit
connects link eligibility, candidate evaluation and cooldown storage before enabling.
Never overwrite an existing edited draft on re-run: verify it instead.
"""
import json
from pathlib import Path
import unreal
import vibeue

ROOT = '/Game/BossArena/Boss/Animations/'
SOURCE = ROOT + 'AM_Boss_Jab_Jab_Hook_Matched'
MONTAGE = ROOT + 'AM_Boss_Left_Right'
SOURCE_CARD = '/Game/BossArena/Boss/AI/Actions/DA_Attack_Combo'
CARD = '/Game/BossArena/Boss/AI/Actions/DA_Attack_LeftRight'
RECOVERY = '/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Ability_Combo_02_Recovery'
M = unreal.AnimMontageService
E = unreal.EditorAssetLibrary


def segments(path):
    return [(s.anim_sequence_path, s.start_time, s.duration, s.anim_start_pos,
             s.anim_end_pos, s.play_rate) for s in M.list_anim_segments(path, 0)]


def notifies(path):
    return [(n.notify_name, n.trigger_time, n.duration, n.notify_class)
            for n in M.list_notifies(path)]


def prepare():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    source_segments, source_notifies = segments(SOURCE), notifies(SOURCE)
    assert len(source_segments) == 6 and len(source_notifies) == 9
    source_card = E.load_asset(SOURCE_CARD)
    source_impacts = list(source_card.get_editor_property('ImpactTimes'))
    source_ends = list(source_card.get_editor_property('HitWindowEnds'))
    if not E.does_asset_exist(MONTAGE):
        assert M.duplicate_montage(SOURCE, ROOT.rstrip('/'), 'AM_Boss_Left_Right')
        print('CREATED', MONTAGE)
        for i in [8, 7, 6]:
            assert M.remove_notify(MONTAGE, i)
            print('REMOVED draft third-hit notify', i)
        for i in [5, 4]:
            assert M.remove_anim_segment(MONTAGE, 0, i)
            print('REMOVED draft third-hit segment', i)
        tail_start = source_segments[3][1] + source_segments[3][2]
        index = M.add_anim_segment(MONTAGE, 0, RECOVERY, tail_start, 2.4)
        assert index == 4
        assert M.set_segment_end_position(MONTAGE, 0, index, 1.8)
        print('ADDED right recovery', MONTAGE, tail_start)
        assert E.save_asset(MONTAGE)
    if not E.does_asset_exist(CARD):
        card = E.duplicate_asset(SOURCE_CARD, CARD)
        assert card
        print('CREATED', CARD)
        values = {'ActionId': 9, 'DisplayName': '왼손 → 오른손 2연타',
                  'BaseWeight': 20.0, 'CooldownSeconds': 4.0, 'ObservationRule': 0,
                  'bEnabled': False, 'Montage': E.load_asset(MONTAGE),
                  'ImpactTimes': source_impacts[:2], 'HitWindowEnds': source_ends[:2],
                  'HitSockets': ['hand_l', 'hand_r'], 'HitDamages': [40.0, 40.0],
                  'TotalSeconds': M.get_montage_length(MONTAGE) / .75 + .25}
        for key, value in values.items():
            card.set_editor_property(key, value)
            print('MODIFIED', CARD, key)
        assert E.save_loaded_asset(card)
    card = E.load_asset(CARD)
    actual_segments, actual_notifies = segments(MONTAGE), notifies(MONTAGE)
    sections = list(M.list_sections(MONTAGE))
    abort = next((s for s in sections if s.section_name == 'AbortLeftRecovery'), None)
    assert len(actual_segments) == (6 if abort else 5) and len(actual_notifies) == 6
    assert actual_segments[:4] == source_segments[:4], 'First two strikes and join must remain unchanged'
    assert actual_notifies == source_notifies[:6], 'First two hand, step and FX timings must remain unchanged'
    assert segments(SOURCE) == source_segments and notifies(SOURCE) == source_notifies
    assert list(source_card.get_editor_property('ImpactTimes')) == source_impacts
    assert list(card.get_editor_property('ImpactTimes')) == source_impacts[:2]
    assert list(card.get_editor_property('HitWindowEnds')) == source_ends[:2]
    assert len(card.get_editor_property('HitSockets')) == len(card.get_editor_property('HitDamages')) == 2
    boss = unreal.get_default_object(E.load_asset('/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch').generated_class())
    integrated = card in boss.get_editor_property('Actions')
    assert bool(card.get_editor_property('bEnabled')) == integrated
    if integrated:
        assert abort and all(s.next_section_name == 'None' for s in sections)
        assert len(boss.get_editor_property('CooldownUntil')) >= len(boss.get_editor_property('Actions'))
    total = card.get_editor_property('TotalSeconds')
    final_recovery = total - source_impacts[1] - card.get_editor_property('ActiveSeconds')
    assert .6 <= final_recovery < 1.0
    assert all(n[1] + n[2] <= M.get_montage_length(MONTAGE) for n in actual_notifies)
    normal_end = abort.start_time if abort else M.get_montage_length(MONTAGE)
    assert abs(total - (normal_end / .75 + .25)) < .001
    report = {'status': 'integrated' if integrated else 'prepared_not_integrated', 'pie_run': False,
              'montage': MONTAGE, 'card': CARD, 'total_seconds': total,
              'final_recovery_timer_seconds': final_recovery,
              'segments': actual_segments, 'notifies': actual_notifies,
              'checks': ['first two source strikes preserved', 'first six notifies preserved',
                         'third strike removed only from duplicate', 'two damage entries',
                         'source pattern unchanged', 'enabled flag matches live membership',
                         'final recovery between 0.6 and 1.0 seconds'],
              'remaining': ['user gameplay evaluation'] if integrated else
                           ['link eligibility', 'Utility and cooldown array integration', 'MotionLab request and HUD', 'user gameplay evaluation']}
    path = Path(unreal.Paths.project_dir()) / 'Saved/VibeUE/Reports/crunch_two_hit_prepared.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('VERIFIED', report['status'], str(path), 'final recovery', final_recovery)
    return report
