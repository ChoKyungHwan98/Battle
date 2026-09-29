"""PIE checks for montage notify controlled attack phases."""
import unreal


def phase_scenario():
    t="__import__('TestSwordShield')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(seconds): steps.append({'action':'wait','seconds':seconds})
    def key(name,event): steps.append({'action':'inject_key','key':name,'event':event})
    def check(expression,expected=1):
        steps.append({'action':'python_assert_number','expression':expression,
                      'expected':expected,'operator':'eq','tolerance':0})
    def flag(name): return f'int({t}.player().get_editor_property("{name}"))'
    check(f'int({t}.setup())');wait(1.1)
    check(f'{t}.state()',5)
    key('LeftMouseButton','down');wait(.04);key('LeftMouseButton','up')
    wait(.08)
    check(f'{t}.state()',4)
    steps.append({'action':'python_assert_number',
                  'expression':f'{t}.player().get_editor_property("CurrentAttackDuration")',
                  'expected':0,'operator':'eq','tolerance':10})
    check(flag('bSwordWindowOpen'),0)
    check(flag('bAttackRollWindowOpen'),0)
    check(flag('bComboWindowOpen'),0)
    wait(.15)
    check(flag('bSwordWindowOpen'))
    wait(.25)
    check(flag('bSwordWindowOpen'),0)
    wait(.14)
    check(flag('bAttackRollWindowOpen'))
    wait(.1)
    check(f'{t}.state()',5)
    wait(.31)
    check(f'{t}.state()',5)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Four attack phases emitted by animation montage notifies',
            'steps':steps,'teardown':{'stop_pie':True}}
