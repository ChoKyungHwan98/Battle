"""Real contact assertions for the 510cm MotionLab lunges, with no OS input."""
import json
from pathlib import Path
import unreal
import TestCrunchPunchPolish as shared
import TestDonorPunch as fixture

RESULTS=[]
begin=shared.begin
damage=shared.damage

def finish(key,distance):
    if shared.OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(shared.OBSERVER)
        shared.OBSERVER=None
    expected='AM_Crunch_LeftSwing510' if key==1 else 'AM_Crunch_RightCross510'
    samples=fixture.SAMPLES
    result={'key':key,'distance_cm':distance,'damage':fixture.damage(),
        'travel_cm':fixture.travel(),'played_expected_montage':any(s['montage']==expected for s in samples),
        'full_body_active':any(s['open'] and s['full_body']>.99 for s in samples),
        'sample_count':len(samples),'samples':samples}
    RESULTS.append(result)
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_510_contact_20261008.json'
    path.write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CONTACT_510',json.dumps({k:v for k,v in result.items() if k!='samples'}))
    return int(result['played_expected_montage'] and result['full_body_active'])

def scenario(cases=None):
    module="__import__('TestCrunch510Punches')"
    if cases is None:
        cases=[(1,400),(1,510,110),(1,530),(2,400),(2,510,110),(2,530)]
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
        {'action':'wait','seconds':.8},{'action':'inject_key','key':'L'},
        {'action':'wait','seconds':.15},{'action':'inject_key','key':'L'},
        {'action':'wait','seconds':.15}]
    for case in cases:
        key,distance=case[:2]
        steps.extend([{'action':'python_assert_number','expression':f'{module}.begin({distance},{key})','operator':'eq','expected':1},
            {'action':'inject_key','key':'One' if key==1 else 'Two'},
            {'action':'wait','seconds':4.8},
            {'action':'python_assert_number','expression':f'{module}.finish({key},{distance})','operator':'eq','expected':1}])
        if len(case)>2:
            steps.append({'action':'python_assert_number','expression':f'{module}.damage()',
                'operator':'eq','expected':case[2],'tolerance':.01})
    return {'name':'Crunch 1/2 510cm physical hand contacts',
        'dependencies':['Tools/AuthorCrunch510Punches.py','Tools/TestCrunch510Punches.py',
            'Content/BossArena/Boss/Authoring/AS_Crunch_LeftSwing510.uasset',
            'Content/BossArena/Boss/Authoring/AS_Crunch_RightCross510.uasset'],
        'steps':steps,'teardown':{'stop_pie':True}}
