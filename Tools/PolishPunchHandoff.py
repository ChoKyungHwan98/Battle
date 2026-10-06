"""Shorten the idle hold before ordinary punches, preserving animation timing.

Run through Unreal MCP with PIE stopped. No gameplay verification is performed.
Only action-relative timestamps shift; montage-local notifies and foot curves stay intact.
"""
import json
from pathlib import Path
import unreal
import vibeue

ROOT = '/Game/BossArena/Boss/AI/Actions/DA_Attack_'
HOLD = 0.08


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    cards = [unreal.EditorAssetLibrary.load_asset(ROOT + side) for side in ['Left', 'Right']]
    assert all(cards)
    # Never save over an unrelated unsaved edit to either shared action card.
    dirty = {p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    assert not any(a.get_path_name().split('.')[0] in dirty for a in cards), dirty
    planned = []
    for card in cards:
        before = {p: card.get_editor_property(p) for p in
                  ['TelegraphSeconds', 'TotalSeconds', 'PlayRate', 'ImpactTimes', 'HitWindowEnds']}
        before['ImpactTimes'] = list(before['ImpactTimes'])
        before['HitWindowEnds'] = list(before['HitWindowEnds'])
        old = float(before['TelegraphSeconds'])
        assert abs(old - .25) < 1e-5 or abs(old - HOLD) < 1e-5, (card, old)
        delta = HOLD - old
        planned.append((card, before, delta))
    journal = json.loads(unreal.WorkflowService.start_run(
        'Ordinary punch locomotion handoff', json.dumps({'PIE': False, 'hold_seconds': HOLD})))
    assert journal['success'], journal
    run_id = journal['runId']
    report = {'gameplay_verified': False, 'attacks': []}
    try:
        for card, before, delta in planned:
            montage = card.get_editor_property('Montage')
            card.modify()
            card.set_editor_property('TelegraphSeconds', HOLD)
            card.set_editor_property('ImpactTimes', [t + delta for t in before['ImpactTimes']])
            card.set_editor_property('TotalSeconds', before['TotalSeconds'] + delta)
            after = {p: card.get_editor_property(p) for p in before}
            after['ImpactTimes'] = list(after['ImpactTimes'])
            after['HitWindowEnds'] = list(after['HitWindowEnds'])
            assert after['PlayRate'] == before['PlayRate']
            assert after['HitWindowEnds'] == before['HitWindowEnds']
            assert card.get_editor_property('Montage') == montage
            for old_t, new_t in zip(before['ImpactTimes'], after['ImpactTimes']):
                assert abs((old_t-before['TelegraphSeconds'])-(new_t-HOLD)) < 1e-5
            assert abs((before['TotalSeconds']-before['TelegraphSeconds'])-
                       (after['TotalSeconds']-HOLD)) < 1e-5
            assert unreal.EditorAssetLibrary.save_loaded_asset(card, False)
            print('MODIFIED', card.get_path_name(), 'hold', before['TelegraphSeconds'], '->', HOLD)
            report['attacks'].append({'asset': card.get_path_name(), 'before': before, 'after': after})
        path = Path(unreal.Paths.project_saved_dir()).resolve()/'VibeUE/Reports/crunch_punch_handoff_20261006.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('VERIFIED action-relative timing offsets; montage speed/contact windows unchanged', str(path))
        unreal.WorkflowService.finish_run(run_id, 'succeeded', str(path))
        print('JOURNAL', run_id, 'succeeded')
    except Exception as error:
        unreal.WorkflowService.finish_run(run_id, 'failed', str(error))
        raise


if __name__ == '__main__':
    apply()
