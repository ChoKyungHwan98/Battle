"""MotionLab contact measurements for the separate October 8 punch candidates."""
import unreal
import json
from pathlib import Path
import TestDonorPunch as fixture

RESULTS=[]
KEY=1
OBSERVER=None

def sample(dt):
    fixture.sample(dt)
    _,boss,_=fixture.actors()
    mesh=boss.get_component_by_class(unreal.SkeletalMeshComponent)
    fixture.SAMPLES[-1]['hand_r']=mesh.get_socket_location('hand_r').to_tuple()
    fixture.SAMPLES[-1]['full_body']=mesh.get_anim_instance().get_curve_value('FullBody')

def begin(distance,key):
    global KEY,OBSERVER
    KEY=key
    fixture.begin(distance)
    unreal.unregister_slate_post_tick_callback(fixture.OBSERVER)
    fixture.OBSERVER=None
    OBSERVER=unreal.register_slate_post_tick_callback(sample)
    world,_,_=fixture.actors()
    unreal.GameplayStatics.set_global_time_dilation(world,1)
    return 1

def finish(distance):
    global OBSERVER
    if OBSERVER is not None:
        unreal.unregister_slate_post_tick_callback(OBSERVER)
        OBSERVER=None
    name='AM_Crunch_StepThroughReach90_LeftSwing' if KEY==1 else 'AM_Crunch_RightCrossPolished'
    samples=fixture.SAMPLES
    contact=[s for s in samples if s['hp']<fixture.START_HEALTH]
    played=any(s['montage']==name for s in samples)
    result={'key':KEY,'distance_cm':distance,'damage':fixture.damage(),
        'travel_cm':fixture.travel(),'played_expected_montage':played,
        'first_damage_seconds':contact[0]['t'] if contact else None,
        'full_body_active':any(s['open'] and s['full_body']>.99 for s in samples),
        'sample_count':len(samples),'samples':samples}
    RESULTS.append(result)
    path=Path(unreal.Paths.project_saved_dir())/'VibeUE/Reports/crunch_punch_contact_20261008.json'
    path.write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CONTACT',json.dumps({k:v for k,v in result.items() if k!='samples'}))
    return int(played and result['full_body_active'])

def damage():
    return fixture.damage()

def scenario(cases=None):
    module="__import__('TestCrunchPunchPolish')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
           {'action':'wait','seconds':.8},{'action':'inject_key','key':'L'},
           {'action':'wait','seconds':.15},{'action':'inject_key','key':'L'},
           {'action':'wait','seconds':.15}]
    if cases is None:
        cases=[(1,400,110),(1,425,110),(1,450,110),(1,460,0),(1,475,0),
               (2,350,110),(2,400,0),(2,420,0)]
    for case in cases:
        key,distance=case[:2]
        steps.extend([{'action':'python_assert_number','expression':f'{module}.begin({distance},{key})','operator':'eq','expected':1},
            {'action':'inject_key','key':'One' if key==1 else 'Two'},
            {'action':'wait','seconds':4.8},
            {'action':'python_assert_number','expression':f'{module}.finish({distance})','operator':'eq','expected':1}])
        if len(case)>2:
            steps.append({'action':'python_assert_number','expression':f'{module}.damage()',
                          'operator':'eq','expected':case[2],'tolerance':.01})
    return {'name':'Left reach and right punch runtime contact, October 8',
        'dependencies':['Tools/TestCrunchPunchPolish.py','Tools/TuneCrunchLeftReach.py','Tools/PolishCrunchRightPunch.py',
            'Content/BossArena/Boss/Authoring/AS_Crunch_StepThroughReach90_LeftSwing.uasset',
            'Content/BossArena/Boss/Authoring/AS_Crunch_RightCrossPolished.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.uasset',
            'Content/BossArena/Boss/AI/Actions/DA_Lab_Right_RightFootStep.uasset'],
        'steps':steps,'teardown':{'stop_pie':True}}
