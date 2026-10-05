"""Synthetic parser tests only. Does not launch or test the game."""
import unittest
from ReadCombatQA import parse_lines, split_sessions, summarize


def row(**fields):
    fields = {'v':'1', 'boss':'Crunch_0', 't':'0', **fields}
    return '[BATTLE_QA] ' + '|'.join(f'{k}={v}' for k,v in fields.items())


class QAReaderTests(unittest.TestCase):
    def test_intent_abort_is_separate_from_contact_and_arrival(self):
        records = parse_lines([
            row(role='boss', event='intent_aborted', intent_reason='timeout', intent_elapsed=2.03, intent_serial=1),
            row(role='boss', event='intent_arrived', intent_elapsed=.8, intent_serial=2),
            row(role='boss', event='intent_aborted', intent_reason='blocked', intent_elapsed=2.8, intent_serial=3)])
        result = summarize(records)
        self.assertEqual(result['intent_aborts'], {'timeout':1, 'blocked':1})
        self.assertEqual(result['intent_arrivals'], 1)
        self.assertEqual([r['serial'] for r in result['intent_duration_overruns']], ['3'])
        self.assertEqual(result['player_hp_lost_observed'], 0)

    def test_manual_execution_does_not_inherit_stale_choice(self):
        records = parse_lines([
            row(role='boss', event='attack_accepted', slot=8, choice='바디펀치',
                started_name='점프 내려찍기', started_source='manual'),
            row(role='boss', event='state', state='Boss.Combat.Attack.Windup',
                slot=8, choice='바디펀치', started_name='점프 내려찍기', started_source='manual')])
        summary = summarize(records)
        self.assertEqual(summary['actual_attack_starts_by_pattern'], {'점프 내려찍기': 1})
        self.assertEqual(summary['actual_attack_starts_by_source'], {'manual': 1})
        self.assertEqual(summary['accepted_attack_requests'], 1)

    def test_rejected_request_is_not_an_attack(self):
        records = parse_lines([row(role='boss', event='attack_rejected',
                                   start_reason='distance', started_name='이전 공격')])
        summary = summarize(records)
        self.assertEqual(summary['actual_attack_starts_by_pattern'], {})
        self.assertEqual(summary['attack_rejections'], {'distance': 1})

    def test_legacy_names_are_not_treated_as_execution_evidence(self):
        records = parse_lines([row(role='boss', event='state',
                                   state='Boss.Combat.Attack.Windup', slot=8, choice='바디펀치')])
        self.assertEqual(summarize(records)['actual_attack_starts_by_pattern'], {'slot 8 (legacy)': 1})

    def test_sessions_separate_on_boss_start_only(self):
        records = parse_lines([row(role='boss',event='session_start'),
                               row(role='player',event='session_start'),
                               row(role='boss',event='sample',t=10),
                               row(role='boss',event='session_start')])
        self.assertEqual([len(s) for s in split_sessions(records)], [3,1])

    def test_contact_and_choice_are_not_damage_or_attack_execution(self):
        records = parse_lines([row(role='boss',event='choice',choice='접근'),
                               row(role='boss',event='contact_submitted'),
                               row(role='player',event='sample',hp=100),
                               row(role='player',event='sample',hp=100,t=.2)])
        result = summarize(records)
        self.assertEqual(result['events']['contact_submitted'],1)
        self.assertEqual(result['actual_attack_starts_by_slot'],{})
        self.assertEqual(result['player_hp_lost_observed'],0)

    def test_hp_reset_does_not_count_as_damage(self):
        records=parse_lines([row(role='player',event='sample',hp=100),
                             row(role='player',event='player_damage',hp=80,t=.1),
                             row(role='player',event='sample',hp=100,t=.2),
                             row(role='player',event='player_damage',hp=70,t=.3)])
        self.assertEqual(summarize(records)['player_hp_lost_observed'],50)

    def test_sample_gaps_and_actual_distance(self):
        records=parse_lines([row(role='boss',event='sample',state='Ready',pos='X=0 Y=0 Z=200'),
                             row(role='player',event='sample',pos='X=300 Y=400 Z=92'),
                             row(role='boss',event='sample',state='Ready',t=.2),
                             row(role='boss',event='sample',state='Ready',t=10)])
        result=summarize(records)
        self.assertEqual(result['sampled_state_seconds']['Ready'],.2)
        self.assertEqual(result['min_live_distance_cm'],500)


if __name__=='__main__':
    unittest.main()
