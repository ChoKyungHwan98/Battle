"""Preserve Kubold source poses and join at their matching continuation poses.

This is a Battle timing profile for the user's 1:28-1:33 reference, not DS3 data.
Run only with PIE stopped. Source bone keys, camera, inputs and boss stay intact.
"""
import json
import os
import unreal

PLAYER = '/Game/BossArena/Player/Blueprints/BP_Player_Combat'
MONTAGE = '/Game/BossArena/Player/Animation/SwordShield/Montages/AM_Sword_Attack_'
JOINS = [.55, 22/60, 32/60, 1.22]
CLOSES = [.50, .35, .50, .52]


def apply():
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
    editor = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    cdo = unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(PLAYER))
    before = {'AttackPlayRate': cdo.get_editor_property('AttackPlayRate'), 'montages': []}
    for i in range(1, 5):
        path = MONTAGE+str(i)
        before['montages'].append({'path': path,
            'segment': unreal.AnimMontageService.list_anim_segments(path, 0)[0].export_text(),
            'notifies': [n.export_text() for n in unreal.AnimMontageService.list_notifies(path)],
            'blend': unreal.AnimMontageService.get_blend_settings(path).export_text()})
    out = os.path.join(unreal.Paths.project_saved_dir(), 'VibeUE', 'reference-sword-before.json')
    if not os.path.exists(out):
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(before, f, indent=2)
    for i in range(1, 5):
        path = MONTAGE+str(i)
        editor.close_all_editors_for_asset(unreal.load_asset(path))
        source = unreal.AnimMontageService.list_anim_segments(path, 0)[0].anim_sequence_path
        length = unreal.load_asset(source).get_play_length()
        assert unreal.AnimMontageService.set_segment_end_position(path, 0, 0, length)
        assert unreal.AnimMontageService.set_segment_play_rate(path, 0, 0, 1.)
        times = {'AN_SwordHitClose': CLOSES[i-1], 'AN_AttackComboQueue': JOINS[i-1],
                 'AN_AttackRecovery': length-.04}
        for n in unreal.AnimMontageService.list_notifies(path):
            if n.notify_name in times:
                assert unreal.AnimMontageService.set_notify_trigger_time(path, n.notify_index, times[n.notify_name])
        assert unreal.AnimMontageService.set_blend_in(path, .04)
        assert unreal.AnimMontageService.set_blend_out(path, .08)
        assert unreal.EditorAssetLibrary.save_asset(path)
        print('MODIFIED:', path, 'full source', length, 'join', JOINS[i-1])
    assert unreal.BlueprintService.set_variable_default_value(PLAYER, 'AttackPlayRate', '1.0')
    result = unreal.BlueprintService.compile_blueprint(PLAYER)
    assert result.success and result.num_errors == 0, str(result)
    assert unreal.EditorAssetLibrary.save_asset(PLAYER)
    print('MODIFIED:', PLAYER, 'AttackPlayRate=1.0; compile errors=0')
    for i in range(1, 5):
        path = MONTAGE+str(i)
        info = unreal.AnimMontageService.list_anim_segments(path, 0)[0]
        assert abs(info.anim_end_pos-1.3) < .001 and abs(info.play_rate-1) < .001
        print('VERIFIED:', i, [(n.notify_name, round(n.trigger_time,4))
                              for n in unreal.AnimMontageService.list_notifies(path)])
    return True
