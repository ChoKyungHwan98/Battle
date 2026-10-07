"""Verify the v6 montage, original strike tempo and visible runtime stepping."""
import json
from pathlib import Path
import unreal
import TestDonorPunch as fixture

MONTAGE='AM_Crunch_MirroredLower_LeftSwing'


def sample(delta):
    fixture.sample(delta)
    w,b,p=fixture.actors()
    row=fixture.SAMPLES[-1]
    row['attack_elapsed']=unreal.GameplayStatics.get_time_seconds(w)-b.get_editor_property('AttackStartedAt')
    anim=b.get_component_by_class(unreal.SkeletalMeshComponent).get_anim_instance()
    row['full_body']=bool(anim.get_editor_property('FullBody'))
    row['accelerating']=bool(anim.get_editor_property('IsAccelerating'))


def begin():
    fixture.begin(400)
    unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
    fixture.OBSERVER=unreal.register_slate_post_tick_callback(sample)
    unreal.GameplayStatics.set_global_time_dilation(fixture.actors()[0],1.)
    return 1


def rows():
    return [s for s in fixture.SAMPLES if s['montage']==MONTAGE]


def played():
    return int(bool(rows()))


def first_window():
    return min((s['attack_elapsed'] for s in rows() if s['open']),default=999.)


def locomotion_override_frames():
    return sum(s['accelerating'] and not s['full_body'] for s in rows() if s['montage_time']>.1)


def moving_full_body_frames():
    return sum(s['accelerating'] and s['full_body'] for s in rows() if s['montage_time']>.1)


def support_drift():
    points=[unreal.Vector(*s['foot_l']) for s in rows() if .15<s['montage_time']<1.10]
    return max(((p-points[0]).length() for p in points),default=999.)


def right_lift():
    points=[s['foot_r'][2] for s in rows() if .06<s['montage_time']<.6]
    return max(points)-min(points) if points else 0.


def finish():
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER);fixture.OBSERVER=None
    report={'played':bool(played()),'first_physical_window_seconds':first_window(),
        'support_drift_cm':support_drift(),'right_foot_lift_cm':right_lift(),
        'capsule_max_displacement_cm':fixture.travel(),
        'walking_override_frames':locomotion_override_frames(),
        'quality_approved':False,'range_verified':False,'samples':fixture.SAMPLES}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_mirrored_lower_v6_pie.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RUNTIME',json.dumps({k:v for k,v in report.items() if k!='samples'}),'REPORT',str(path))
    return 1


def scenario():
    m="__import__('TestCrunchMirroredLower')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},{'action':'wait','seconds':.5}]
    for _ in range(3):steps += [{'action':'inject_key','key':'L'},{'action':'wait','seconds':.15}]
    steps += [{'action':'python_assert_number','expression':m+'.begin()','operator':'eq','expected':1},
        {'action':'inject_key','key':'One'},{'action':'wait','seconds':3.2},
        {'action':'python_assert_number','expression':m+'.finish()','operator':'eq','expected':1},
        {'action':'capture_game','name':'v6_runtime_after_attack'}]
    for expr,op,value in [('played()','eq',1),('first_window()','gt',.4),('first_window()','lt',.75),
            ('locomotion_override_frames()','eq',0),('moving_full_body_frames()','gt',0),
            ('support_drift()','lt',5.),('right_lift()','gt',10.)]:
        steps.append({'action':'python_assert_number','expression':m+'.'+expr,'operator':op,'expected':value})
    return {'name':'Crunch v6: mirrored original foot motion and original punch tempo',
        'dependencies':['Tools/TestCrunchMirroredLower.py','Tools/TestDonorPunch.py',
            'Content/BossArena/Boss/Animation/ABP_Boss_Crunch.uasset',
            'Content/BossArena/Boss/Authoring/AS_Crunch_MirroredLower_LeftSwing.uasset',
            'Content/BossArena/Boss/Authoring/AM_Crunch_MirroredLower_LeftSwing.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset'],
        'steps':steps,'teardown':{'stop_pie':True}}
