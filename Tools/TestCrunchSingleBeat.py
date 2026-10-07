"""Runtime connection/tempo check only; artistic QA belongs to the user."""
import json
from pathlib import Path
import unreal
import TestDonorPunch as fixture


def sample(delta):
    fixture.sample(delta)
    w,b,p=fixture.actors()
    fixture.SAMPLES[-1]['attack_elapsed']=unreal.GameplayStatics.get_time_seconds(w)-b.get_editor_property('AttackStartedAt')
    anim=b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance()
    fixture.SAMPLES[-1]['full_body']=bool(anim.get_editor_property('FullBody'))
    fixture.SAMPLES[-1]['accelerating']=bool(anim.get_editor_property('IsAccelerating'))


def begin():
    fixture.begin(400)
    unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
    fixture.OBSERVER=unreal.register_slate_post_tick_callback(sample)
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0],1.)
    return 1


def played():
    return int(any(s['montage']=='AM_Crunch_RightStep_SingleBeat' for s in fixture.SAMPLES))


def first_window():
    return min((s['attack_elapsed'] for s in fixture.SAMPLES
        if s['montage']=='AM_Crunch_RightStep_SingleBeat' and s['open']),default=999.)


def locomotion_override_frames():
    return sum(1 for s in fixture.SAMPLES
        if s['montage']=='AM_Crunch_RightStep_SingleBeat' and s['montage_time']>.1
        and s['accelerating'] and not s['full_body'])


def moving_full_body_frames():
    return sum(1 for s in fixture.SAMPLES
        if s['montage']=='AM_Crunch_RightStep_SingleBeat' and s['montage_time']>.1
        and s['accelerating'] and s['full_body'])


def finish():
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER);fixture.OBSERVER=None
    report={'played':bool(played()),'first_physical_window_seconds':first_window(),
        'quality_approved':False,'samples':fixture.SAMPLES}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_single_beat_v5_pie.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('TEMPO',played(),first_window(),'REPORT',str(path))
    return 1


def scenario():
    m="__import__('TestCrunchSingleBeat')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},{'action':'wait','seconds':.5}]
    for _ in range(3):steps += [{'action':'inject_key','key':'L'},{'action':'wait','seconds':.15}]
    steps += [{'action':'python_assert_number','expression':m+'.begin()','operator':'eq','expected':1},
        {'action':'inject_key','key':'One'},{'action':'wait','seconds':3.2},
        {'action':'python_assert_number','expression':m+'.finish()','operator':'eq','expected':1},
        {'action':'python_assert_number','expression':m+'.played()','operator':'eq','expected':1},
        {'action':'python_assert_number','expression':m+'.first_window()','operator':'gt','expected':.4},
        {'action':'python_assert_number','expression':m+'.first_window()','operator':'lt','expected':.75},
        {'action':'python_assert_number','expression':m+'.locomotion_override_frames()','operator':'eq','expected':0},
        {'action':'python_assert_number','expression':m+'.moving_full_body_frames()','operator':'gt','expected':0}]
    return {'name':'Crunch single-beat v5: actual montage and original tempo',
        'dependencies':['Tools/TestCrunchSingleBeat.py',
            'Tools/TestDonorPunch.py',
            'Content/BossArena/Boss/Animation/ABP_Boss_Crunch.uasset',
            'Content/BossArena/Boss/Authoring/AS_Crunch_RightStep_SingleBeat.uasset',
            'Content/BossArena/Boss/Authoring/AM_Crunch_RightStep_SingleBeat.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset'],
        'steps':steps,'teardown':{'stop_pie':True}}
