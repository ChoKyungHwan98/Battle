"""Observe montage-local event times at 30/60/120fps, including a local freeze."""
import json
import unreal
import TestSwordShield as T

handle=None
samples=[]
fps=60
kind=''
reports=[]


def setup(rate):
    global fps
    fps=rate
    T.setup()
    unreal.SystemLibrary.execute_console_command(T.world(),'t.MaxFPS '+str(rate))
    return 1


def begin(action):
    global handle,samples,kind
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle)
    samples=[];kind=action;p=T.player()
    p.call_method('TryEnterDodge' if action=='roll' else 'TryEnterAttack')
    def tick(dt):
        if not T.world():return
        p=T.player();a=p.mesh.get_anim_instance()
        m=p.get_editor_property('ActiveDodgeMontage' if kind=='roll' else 'ActiveAttackMontage')
        samples.append({'t':unreal.GameplayStatics.get_time_seconds(T.world()),'pos':a.montage_get_position(m),
            'state':T.state(),'inv':p.get_editor_property('bInvincible'),
            'hit':p.get_editor_property('bSwordWindowOpen'),'combo':p.get_editor_property('bComboWindowOpen'),
            'cancel':p.get_editor_property('bAttackRollWindowOpen'),'dilation':p.custom_time_dilation,
            'world':unreal.GameplayStatics.get_global_time_dilation(T.world()),
            'travel':(p.get_actor_location()-p.get_editor_property('DodgeMoveStartLocation')).length()})
    handle=unreal.register_slate_post_tick_callback(tick)
    return int(T.state()==(2 if kind=='roll' else 4))


def freeze():
    T.player().call_method('StartHitStop')
    return 1


def finish():
    global handle
    if handle is not None:unreal.unregister_slate_post_tick_callback(handle);handle=None
    tolerance=1/fps*(1/.7 if kind=='roll' else 1.4)+.003
    ok=bool(samples) and all(s['world']==1 for s in samples) and T.state()==5 and T.player().custom_time_dilation==1
    metrics={}
    if kind=='roll':
        end=next((s['pos'] for s in samples if s['state']==2 and not s['inv']),None)
        metrics={'iframe_end_pose_seconds':end,'distance':samples[-1]['travel']}
        ok=ok and end is not None and abs(end-.43333333333333335/.7)<=tolerance and abs(metrics['distance']-320)<12
    else:
        for label,target in [('hit',.25),('cancel',.60),('combo',.62)]:
            value=next((s['pos'] for s in samples if s[label]),None);metrics[label]=value
            ok=ok and value is not None and abs(value-target)<=tolerance
        metrics['frozen_frames']=sum(s['dilation']<.001 for s in samples)
        ok=ok and metrics['frozen_frames']>0
    reports.append({'fps':fps,'action':kind,'passed':bool(ok),'metrics':metrics,'samples':samples})
    with open(unreal.Paths.project_saved_dir()+'VibeUE/approved-timeline-evidence.json','w') as f:json.dump(reports,f,indent=2)
    print('TIMELINE',fps,kind,ok,metrics)
    return int(ok)


def scenario():
    q="__import__('TestApprovedTimeline')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(e):steps.append({'action':'python_assert_number','expression':e,'expected':1,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    for rate in [30,60,120]:
        check(f'{q}.setup({rate})');wait(.8);check(f'{q}.begin("roll")');wait(1.0);check(f'{q}.finish()')
        wait(.3);check(f'{q}.begin("attack")');wait(.12);check(f'{q}.freeze()');wait(1.0);check(f'{q}.finish()')
    check('int(__import__("unreal").SystemLibrary.execute_console_command(__import__("TestSwordShield").world(),"t.MaxFPS 0") is None)')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Animation events remain aligned across FPS and scoped hit stop','steps':steps,'teardown':{'stop_pie':True}}
