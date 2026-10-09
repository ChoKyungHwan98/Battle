"""Verify the v9 (stays advanced) montage in PIE: planted windup, one right step on the punch beat."""
import json
from pathlib import Path
import unreal
import TestDonorPunch as fixture
import TestCrunchMirroredLower as shared

MONTAGE='AM_Crunch_StepThroughAdvance_LeftSwing'


def begin():
    shared.MONTAGE=MONTAGE
    return shared.begin()


def rows():
    return [s for s in fixture.SAMPLES if s['montage']==MONTAGE]


def foot_travel(row,name):
    # Boss faces -X in the fixture; measure along its facing, relative to the first sample.
    return rows()[0][name][0]-row[name][0]


def windup_right_foot_travel():
    """The rear foot must not walk forward before the punch starts (v6 did)."""
    return max((abs(foot_travel(s,'foot_r')) for s in rows() if s['montage_time']<.16),default=999.)


def right_foot_landing_time():
    """Montage time at which the right foot has finished its forward flight."""
    final=max(foot_travel(s,'foot_r') for s in rows() if s['montage_time']<.6)
    return min((s['montage_time'] for s in rows() if foot_travel(s,'foot_r')>final-5.),default=999.)


def right_foot_step():
    return max((foot_travel(s,'foot_r') for s in rows() if s['montage_time']<.6),default=0.)


def support_drift():
    # The ankle swings about 6cm (animation space) as the rear heel lifts over planted toes.
    points=[unreal.Vector(*s['foot_l']) for s in rows() if .10<s['montage_time']<1.10]
    return max(((p-points[0]).length() for p in points),default=999.)


def final_forward_cm():
    """Boss displacement toward the player once the action is over (v5-v8 returned to 0)."""
    return fixture.START_LOCATION[0]-fixture.SAMPLES[-1]['boss'][0]


def finish():
    if fixture.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(fixture.OBSERVER);fixture.OBSERVER=None
    report={'played':bool(rows()),'first_physical_window_seconds':shared.first_window(),
        'windup_right_foot_travel_cm':windup_right_foot_travel(),
        'right_foot_landing_montage_seconds':right_foot_landing_time(),
        'right_foot_step_cm':right_foot_step(),'support_ankle_drift_cm':support_drift(),
        'capsule_max_displacement_cm':fixture.travel(),'final_forward_cm':final_forward_cm(),'damage':fixture.damage(),
        'walking_override_frames':shared.locomotion_override_frames(),
        'moving_full_body_frames':shared.moving_full_body_frames(),
        'quality_approved':False,'range_verified':False,'samples':fixture.SAMPLES}
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_step_through_v9_pie.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RUNTIME',json.dumps({k:v for k,v in report.items() if k!='samples'}),'REPORT',str(path))
    return 1


def scenario():
    m="__import__('TestCrunchStepThroughAdvance')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},{'action':'wait','seconds':.5}]
    for _ in range(3):steps += [{'action':'inject_key','key':'L'},{'action':'wait','seconds':.15}]
    steps += [{'action':'python_assert_number','expression':m+'.begin()','operator':'eq','expected':1},
        {'action':'inject_key','key':'One'},{'action':'wait','seconds':3.2},
        {'action':'python_assert_number','expression':m+'.finish()','operator':'eq','expected':1}]
    for expr,op,value in [('shared.played()','eq',1),('shared.first_window()','gt',.4),('shared.first_window()','lt',.75),
            ('shared.locomotion_override_frames()','eq',0),('shared.moving_full_body_frames()','gt',0),
            ('windup_right_foot_travel()','lt',8.),('right_foot_landing_time()','gt',.33),
            ('right_foot_landing_time()','lt',.45),('right_foot_step()','gt',150.),('support_drift()','lt',12.),('final_forward_cm()','gt',55.)]:
        steps.append({'action':'python_assert_number','expression':m+'.'+expr,'operator':op,'expected':value})
    return {'name':'Crunch v9 advance: planted windup, single right step on the punch beat',
        'dependencies':['Tools/TestCrunchStepThroughAdvance.py','Tools/TestCrunchMirroredLower.py','Tools/TestDonorPunch.py',
            'Content/BossArena/Boss/Animation/ABP_Boss_Crunch.uasset',
            'Content/BossArena/Boss/Authoring/AS_Crunch_StepThroughAdvance_LeftSwing.uasset',
            'Content/BossArena/Boss/Authoring/AM_Crunch_StepThroughAdvance_LeftSwing.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset'],
        'steps':steps,'teardown':{'stop_pie':True}}
