"""PIE check that an eligible roll reservation survives a later attack press."""
import unreal
import TestSwordShield as T


def begin():
    p = T.player()
    p.call_method('TryEnterDodge')
    return int(T.state() == 2)


def queue_both():
    p = T.player()
    p.call_method('TryEnterDodge')
    roll = bool(p.get_editor_property('bDodgeBuffered'))
    p.call_method('TryEnterAttack')
    result = (roll, bool(p.get_editor_property('bDodgeBuffered')),
              bool(p.get_editor_property('bAttackBuffered')), T.state())
    print('INPUT_PRIORITY', result)
    return int(result == (True, True, False, 2))


def scenario():
    q = "__import__('TestDS3InputPriority')"
    def check(expr, expected=1):
        return {'action': 'python_assert_number', 'expression': expr,
                'expected': expected, 'operator': 'eq'}
    return {'name': 'Dodge request wins over subsequent attack while rolling',
            'steps': [{'action': 'start_pie'},
                      {'action': 'wait_for_pie', 'timeout_seconds': 20},
                      check("int(__import__('TestSwordShield').setup())"),
                      {'action': 'wait', 'seconds': .65},
                      check(f'{q}.begin()'), {'action': 'wait', 'seconds': .37},
                      check(f'{q}.queue_both()'),
                      {'action': 'wait', 'seconds': .43},
                      check("__import__('TestSwordShield').state()", 2),
                      {'action': 'wait', 'seconds': 1.0},
                      check("int(not __import__('TestSwordShield').player().get_editor_property('bAttackBuffered'))")],
            'teardown': {'stop_pie': True}}
