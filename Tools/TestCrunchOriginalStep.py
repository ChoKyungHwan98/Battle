"""MotionLab v3 connection check. Does not assert artistic quality or 550cm reach."""
import json
from pathlib import Path
import unreal
import TestDonorPunch as fixture


def begin(distance=550):
    result = fixture.begin(distance)
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0],1.)
    return result


def montage_ok():
    return int(any(s['montage']=='AM_Crunch_LeftSwing_OriginalStep' for s in fixture.SAMPLES))


def finish():
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
        fixture.OBSERVER=None
    report={'montage_verified':bool(montage_ok()),'root_travel_cm':fixture.travel(),
        'damage':fixture.damage(),'quality_approved':False,'samples':fixture.SAMPLES}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_original_step_v3_pie.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ORIGINAL_STEP_V3', {k:v for k,v in report.items() if k!='samples'},'REPORT',str(path))
    return 1


def scenario():
    module="__import__('TestCrunchOriginalStep')"
    return {'name':'Crunch original-preserving step v3: lab playback and travel',
        'dependencies':['Tools/AuthorCrunchOriginalStep.py','Tools/TestCrunchOriginalStep.py',
            'Content/BossArena/Boss/Authoring/AS_Crunch_LeftSwing_OriginalStep.uasset',
            'Content/BossArena/Boss/Authoring/AM_Crunch_LeftSwing_OriginalStep.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset'],
        'steps':[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
            {'action':'wait','seconds':.5},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'inject_key','key':'L'},{'action':'wait','seconds':.15},
            {'action':'python_assert_number','expression':module+'.begin()','operator':'eq','expected':1},
            {'action':'inject_key','key':'One'},{'action':'wait','seconds':3.5},
            {'action':'python_assert_number','expression':module+'.finish()','operator':'eq','expected':1},
            {'action':'python_assert_number','expression':module+'.montage_ok()','operator':'eq','expected':1},
            {'action':'python_assert_number','expression':"__import__('TestDonorPunch').travel()",
                'operator':'eq','expected':205,'tolerance':3}],
        'teardown':{'stop_pie':True}}
