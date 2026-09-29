"""Timed actual-input checks; no screenshot stalls during combo measurement."""
import unreal
import json
import time
import TestSoulsHits as H
import TestSwordShield as T
import TestDS3CameraFraming as C

observer = None
records = []
origin_time = 0
key_held = False


def setup(distance=300):
    stop_observing()
    H.start = None
    assert H.setup(distance)
    # Keep original gameplay stamina and hit stop enabled.
    return True


def lock():
    p = T.player()
    if not p.get_editor_property('LockOnTarget'):
        p.call_method('ToggleLockOn')
    return bool(p.get_editor_property('LockOnTarget'))


def observe(drive_combo=False):
    global observer, origin_time, key_held
    records.clear()
    origin_time = time.perf_counter()
    key_held = False
    queued_starts = set()
    def tick(delta):
        global key_held
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
            stop_observing()
            return
        p = T.player()
        a = p.mesh.get_anim_instance()
        m = a.get_current_active_montage()
        records.append({'wall': round(time.perf_counter()-origin_time, 4),
            'game': round(unreal.GameplayStatics.get_time_seconds(H.world()), 4),
            'start': round(p.get_editor_property('AttackStartTime'), 4),
            'montage': m.get_name() if m else '',
            'position': round(a.montage_get_position(m), 4) if m else 0,
            'state': T.state(), 'window': bool(p.get_editor_property('bSwordWindowOpen')),
            'hp': H.boss().get_editor_property('CurrentHealth'),
            'dilation': unreal.GameplayStatics.get_global_time_dilation(H.world())})
        if key_held:
            unreal.InputService.inject_key('LeftMouseButton', 'up')
            key_held = False
        elif drive_combo and T.state() == 4 and len(p.get_editor_property('PendingCombo')) > 0:
            start = p.get_editor_property('AttackStartTime')
            age = unreal.GameplayStatics.get_time_seconds(H.world())-start
            if age >= .08 and start not in queued_starts:
                # Real mapped key presses, scheduled on ticks relative to each
                # actual attack start rather than scenario step overhead.
                unreal.InputService.inject_key('LeftMouseButton', 'down')
                key_held = True
                queued_starts.add(start)
    observer = unreal.register_slate_post_tick_callback(tick)
    return True


def stop_observing():
    global observer, key_held
    if observer is not None:
        unreal.unregister_slate_post_tick_callback(observer)
        observer = None
    if key_held and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
        unreal.InputService.inject_key('LeftMouseButton', 'up')
    key_held = False
    return True


def result(contact=False):
    stop_observing()
    strikes=[]
    for r in records:
        if r['state'] == 4 and 'AM_Sword_Attack_' in r['montage']:
            if not strikes or r['start'] != strikes[-1]['start']:
                strikes.append(r)
    damage_changes=[]
    for previous, current in zip(records, records[1:]):
        if current['hp'] < previous['hp']:
            damage_changes.append({'wall': current['wall'], 'damage': previous['hp']-current['hp']})
    recovery = next((r['wall'] for r in records if len(strikes) == 4
                     and r['wall'] > strikes[-1]['wall'] and r['state'] == 5), None)
    intervals = [round(b['wall']-a['wall'], 3) for a,b in zip(strikes,strikes[1:])]
    out={'contact':contact,'strikes':[{k:r[k] for k in ['wall','start','montage']} for r in strikes],
         'intervals':intervals,'recovery':recovery,'damage':damage_changes,'samples':records}
    path=unreal.Paths.project_saved_dir()+f'VibeUE/combo-readability-{int(contact)}.json'
    with open(path,'w',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print('COMBO',strikes and [r['montage'] for r in strikes],intervals,'recovery',recovery,
          'damage',damage_changes,'saved',path)
    return int(len(strikes)==4 and [r['montage'] for r in strikes]==
        [f'AM_Sword_Attack_{i}' for i in range(1,5)] and recovery is not None and
        recovery-strikes[0]['wall'] < (2.5 if contact else 2.2) and
        all(v < (.6 if contact else .51) for v in intervals) and
        (not contact or len(damage_changes)==4))


def combo_scenario(contact=False):
    Q="__import__('TestCombatReadability')"; B="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def check(expression, expected=1):
        steps.append({'action':'python_assert_number','expression':expression,'expected':expected,'operator':'eq'})
    def wait(s):steps.append({'action':'wait','seconds':s})
    def tap():
        steps.extend([{'action':'inject_key','key':'LeftMouseButton','event':'down'},
                      {'action':'wait','seconds':.03},
                      {'action':'inject_key','key':'LeftMouseButton','event':'up'}])
    check(f'int({Q}.setup({280 if contact else 1000}))');wait(1.1)
    check(f'int({Q}.lock())');wait(.8)
    check(f'{B}.state()',5);check(f'int({Q}.observe(True))')
    tap();wait(2.5);check(f'{B}.state()',5)
    check(f'{Q}.result({contact!r})')
    check(f'int(__import__("unreal").GameplayStatics.get_global_time_dilation({B}.world())==1)')
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':f'Faster four-hit combo actual input {"with real contact" if contact else "without contact"}',
            'steps':steps,'teardown':{'stop_pie':True},
            'dependencies':['Tools/TestCombatReadability.py',
              'Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset',
              'Content/BossArena/Boss/Blueprints/BP_Boss_Crunch.uasset',
              'Content/BossArena/Maps/Lvl_Arena_01.umap']+
              [f'Content/BossArena/Player/Animation/SwordShield/Montages/AM_Sword_Attack_{i}.uasset' for i in range(1,5)]}


def visual_scenario():
    Q="__import__('TestCombatReadability')";F="__import__('TestDS3CameraFraming')";B="__import__('TestSwordShield')"
    return {'name':'Read actual sword hit shape and clean locked camera frame',
      'steps':[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
        {'action':'python_assert_number','expression':f'int({Q}.setup(300))','expected':1,'operator':'eq'},
        {'action':'wait','seconds':1.1},
        {'action':'python_assert_number','expression':f'int({Q}.lock())','expected':1,'operator':'eq'},
        {'action':'wait','seconds':1},
        {'action':'python_assert_number','expression':f'int({F}.record("clean-lock-300"))','expected':1,'operator':'eq'},
        {'action':'capture_game','name':'clean-near-lock-frame'},
        {'action':'wait','seconds':.3},
        {'action':'inject_key','key':'LeftMouseButton','event':'down'},
        {'action':'wait','seconds':.03},
        {'action':'inject_key','key':'LeftMouseButton','event':'up'},
        {'action':'wait','seconds':.2},
        {'action':'python_assert_number','expression':f'int({B}.player().get_editor_property("bSwordWindowOpen"))','expected':1,'operator':'eq'},
        {'action':'capture_game','name':'blue-sword-active-sweep'},
        {'action':'wait','seconds':1},
        {'action':'python_assert_number','expression':f'int({B}.player().get_editor_property("bSwordWindowOpen"))','expected':0,'operator':'eq'},
        {'action':'capture_game','name':'attack-window-closed-no-trace'},
        {'action':'python_assert_number','expression':f'int({F}.place(600))','expected':1,'operator':'eq'},
        {'action':'wait','seconds':1},
        {'action':'python_assert_number','expression':f'int({F}.record("clean-lock-600"))','expected':1,'operator':'eq'},
        {'action':'capture_game','name':'clean-mid-lock-frame'},
        {'action':'python_assert_number','expression':f'int({F}.unlock())','expected':1,'operator':'eq'},
        {'action':'wait','seconds':1},
        {'action':'python_assert_number','expression':f'int({F}.record("clean-free-600"))','expected':1,'operator':'eq'},
        {'action':'capture_game','name':'clean-free-frame'},
        {'action':'python_assert_number','expression':f'int({F}.save())','expected':1,'operator':'eq'},
        {'action':'assert_log','not_contains':'LogScript: Warning'}],
      'teardown':{'stop_pie':True}}


def begin_boss_attack(index=0):
    b = H.boss()
    b.call_method('RequestCombatAction', (index,))
    b.set_actor_tick_enabled(True)
    return b.get_editor_property('ActiveAction') == b.get_editor_property('Actions')[index]


def slow(value):
    unreal.SystemLibrary.execute_console_command(H.world(), f'slomo {value}')
    return True


def boss_visual_scenario(distance=285):
    Q="__import__('TestCombatReadability')";HITS="__import__('TestSoulsHits')"
    # The left swing's existing mesh sweep also reaches the 360cm fixture.
    contact = distance <= 360
    def check(expr, value=1):
        return {'action':'python_assert_number','expression':expr,'expected':value,'operator':'eq'}
    return {'name':f'Visible actual Crunch left swing {"contact" if contact else "miss"}',
      'steps':[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
        check(f'int({Q}.setup({distance}))'),{'action':'wait','seconds':1.1},
        check(f'int({Q}.lock())'),{'action':'wait','seconds':.8},
        check(f'int({Q}.begin_boss_attack())'),{'action':'wait','seconds':.98},
        check(f'int({Q}.slow(.05))'),
        check(f'int({HITS}.boss().get_editor_property("bHitWindowOpen"))'),
        {'action':'capture_game','name':f'orange-crunch-sweep-{distance}'},
        check(f'int({Q}.slow(1))'),{'action':'wait','seconds':.5},
        check(f'{HITS}.player().get_editor_property("CurrentHealth")',1890 if contact else 2000),
        check(f'int({HITS}.boss().get_editor_property("bShowHitDebug"))',0),
        {'action':'assert_log','not_contains':'LogScript: Warning'}],
      'teardown':{'stop_pie':True},
      'dependencies':['Tools/TestCombatReadability.py',
         'Content/BossArena/Player/Blueprints/BP_Player_Combat.uasset',
         'Content/BossArena/Boss/Blueprints/BP_Boss_Crunch.uasset',
         'Content/BossArena/Boss/AI/Actions/DA_Attack_Left.uasset',
         'Content/BossArena/Maps/Lvl_Arena_01.umap']}


def cancel_guard_scenario():
    Q="__import__('TestCombatReadability')";B="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(s):steps.append({'action':'wait','seconds':s})
    def key(k,event):steps.append({'action':'inject_key','key':k,'event':event})
    def check(expr,expected=1):
        steps.append({'action':'python_assert_number','expression':expr,'expected':expected,'operator':'eq'})
    check(f'int({Q}.setup(1000))');wait(1.1)
    key('LeftMouseButton','down');wait(.03);key('LeftMouseButton','up');wait(.1)
    check(f'{B}.state()',4)
    key('SpaceBar','down');wait(.03);key('SpaceBar','up');wait(.27)
    check(f'{B}.state()',2);wait(.25)
    check(f'{B}.state()',2);wait(.6);check(f'{B}.state()',5)
    key('LeftMouseButton','down');wait(.03);key('LeftMouseButton','up')
    key('RightMouseButton','down');wait(.8)
    check(f'{B}.state()',3)
    key('RightMouseButton','up');wait(.2);check(f'{B}.state()',5)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Faster attacks keep buffered roll and held guard recovery',
            'steps':steps,'teardown':{'stop_pie':True}}
