"""Read what happened in the designer's own play sessions (plain Python, run outside the editor).

The boss Blueprint writes a [BATTLE_QA] row to the editor log for every state change, decision, strike, contact and
(about 5 times a second) a position sample, for both the boss and the player. This turns those rows into a summary:
where the player stood, what the boss did, how long it stood still after each attack, what hit and what was avoided.

    python Tools/PlayLog.py                 # the last session
    python Tools/PlayLog.py 2               # the last two sessions
    python Tools/PlayLog.py archive         # keep a copy of the log (the build script clears Saved/Logs)

Archived logs live in Saved/PlayLogs and are read as well.
"""
import collections
import glob
import math
import os
import re
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, 'Saved', 'Logs', 'Battle.log')
KEEP = os.path.join(ROOT, 'Saved', 'PlayLogs')
ATTACKS = {'0': '왼손', '1': '오른손', '2': '어퍼컷', '3': '휩쓸기', '4': '잽잽훅', '5': '가드 브레이크', '6': '슈퍼맨 펀치',
           '8': '점프 내려찍기', '9': '2연타', '10': '내려찍기'}
BANDS = [(200, '붙음'), (345, '단거리'), (650, '중거리'), (1000, '장거리'), (1e9, '초장거리')]


def archive():
    os.makedirs(KEEP, exist_ok=True)
    if not os.path.exists(LOG) or '[BATTLE_QA]' not in open(LOG, encoding='utf-8', errors='ignore').read():
        return None
    target = os.path.join(KEEP, time.strftime('Battle_%Y%m%d_%H%M%S.log', time.localtime(os.path.getmtime(LOG))))
    if not os.path.exists(target):
        shutil.copy2(LOG, target)
    return target


def rows_of(path):
    out = []
    for line in open(path, encoding='utf-8', errors='ignore'):
        if '[BATTLE_QA]' not in line:
            continue
        row = dict(kv.split('=', 1) for kv in line.split('[BATTLE_QA] ')[1].strip().split('|') if '=' in kv)
        row['_clock'] = line[1:20]
        out.append(row)
    return out


def sessions():
    """Every play session found, oldest first: (clock, map, rows)."""
    found = {}
    for path in sorted(glob.glob(os.path.join(KEEP, '*.log'))) + [LOG]:
        if not os.path.exists(path):
            continue
        rows = rows_of(path)
        starts = [i for i, r in enumerate(rows) if r.get('event') == 'session_start' and r.get('role') == 'boss']
        for a, b in zip(starts, starts[1:] + [len(rows)]):
            found[rows[a]['_clock']] = (rows[a]['_clock'], rows[a].get('map', ''), rows[a:b])
    return [found[k] for k in sorted(found)]


def position(row):
    m = re.match(r'X=([-\d.]+) Y=([-\d.]+)', row.get('pos', ''))
    return (float(m[1]), float(m[2])) if m else None


def band(distance):
    return next(name for limit, name in BANDS if distance < limit)


def is_test(rows):
    """Automated scenarios never move the player with input: its samples show no speed at all."""
    player = [r for r in rows if r.get('role') == 'player' and r.get('event') == 'sample']
    return not any(float(r.get('speed', 0) or 0) > 1 for r in player) and not any(r.get('event', '').startswith('dodge') for r in rows)


def report(session):
    clock, level, rows = session
    boss = [r for r in rows if r.get('role') == 'boss']
    player = [r for r in rows if r.get('role') == 'player']
    if not boss:
        return
    length = float(boss[-1]['t']) - float(boss[0]['t'])
    print('=' * 78)
    print('세션 %s (UTC) · %s · %.0f초%s' % (clock, level, length, ' · 자동 시험으로 보임' if is_test(rows) else ''))

    # 거리: 같은 시각의 보스·플레이어 표본
    where = {r['t']: position(r) for r in player if r.get('event') == 'sample'}
    share = collections.Counter(); distances = []
    for r in boss:
        if r.get('event') != 'sample':
            continue
        a, b = position(r), where.get(r['t'])
        if a and b:
            d = math.dist(a, b); distances.append(d); share[band(d)] += 1
    if distances:
        total = sum(share.values())
        print('거리  ' + ' · '.join('%s %d%%' % (name, round(100 * share[name] / total)) for _, name in BANDS if share[name])
              + '  (중앙값 %dcm, 최대 %dcm)' % (sorted(distances)[len(distances) // 2], max(distances)))

    # 보스가 한 일
    state_time = collections.Counter(); prev = None
    for r in boss:
        if r.get('event') == 'state':
            if prev: state_time[prev[0]] += float(r['t']) - prev[1]
            prev = (r.get('state', '').replace('Boss.Combat.', ''), float(r['t']))
    if state_time:
        total = sum(state_time.values())
        print('보스 시간  ' + ' · '.join('%s %d%%' % (k, round(100 * v / total)) for k, v in state_time.most_common(7)))

    attacks = []            # one dict per attack
    current = None
    for r in boss:
        e = r.get('event')
        if e == 'attack_accepted':
            current = {'t': float(r['t']), 'id': r.get('started_action_id', ''), 'montage': r.get('started_montage', ''),
                       'distance': float(r.get('start_distance', 0) or 0), 'strikes': 0, 'contacts': 0, 'recovery': None, 'end': None}
            attacks.append(current)
        elif current and e == 'strike_begin': current['strikes'] += 1
        elif current and e == 'contact_submitted': current['contacts'] += 1
        elif current and e == 'state':
            state = r.get('state', '')
            if state.endswith('Recovery') and current['recovery'] is None: current['recovery'] = float(r['t'])
            if state.endswith('Ready') and current['recovery'] is not None and current['end'] is None: current['end'] = float(r['t'])
    if attacks:
        print('보스 공격 %d회 (분당 %.1f회)' % (len(attacks), 60 * len(attacks) / max(1., length)))
        by = collections.defaultdict(list)
        for a in attacks: by[a['id']].append(a)
        for key, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
            versions = collections.Counter('먼 쪽' if 'RunInFar' in a['montage'] else '가까운 쪽' if 'RunIn' in a['montage'] else '제자리' for a in items)
            recover = [a['end'] - a['recovery'] for a in items if a['end'] and a['recovery']]
            print('  %-10s %2d회 · 접촉 %d/%d타 · 시작 거리 %d~%dcm · %s%s' % (
                ATTACKS.get(key, key), len(items), sum(a['contacts'] for a in items), sum(a['strikes'] for a in items),
                min(a['distance'] for a in items), max(a['distance'] for a in items),
                ' / '.join('%s %d' % kv for kv in versions.most_common()),
                ' · 후딜 평균 %.1f초' % (sum(recover) / len(recover)) if recover else ''))
        gaps = [b['t'] - a['end'] for a, b in zip(attacks, attacks[1:]) if a['end']]
        recover = [a['end'] - a['recovery'] for a in attacks if a['end'] and a['recovery']]
        if recover:
            print('후딜(마지막 타 뒤 다시 고를 때까지) 평균 %.1f초, 가장 긴 것 %.1f초' % (sum(recover) / len(recover), max(recover)))
        if gaps:
            print('후딜이 끝나고 다음 공격까지 평균 %.1f초' % (sum(gaps) / len(gaps)))
        beats = [b['t'] - a['t'] for a, b in zip(attacks, attacks[1:])]
        if beats:
            print('공격 시작에서 다음 공격 시작까지 평균 %.1f초' % (sum(beats) / len(beats)))

    count = collections.Counter(r.get('event') for r in boss)
    moves = {'발놀림(빠지기)': count['footwork_space'], '발놀림(각)': count['footwork_angle'], '발놀림(조이기)': count['footwork_press'],
             '연계': count['chain'], '도발': count['taunt_far'], '웃기': count['taunt_down'], '뒤쪽 대응': count['rear_response'], '후딜 일찍 끝냄': count['recovery_flank_exit'],
             '턴': count['turn_synced'], '움찔': count['flinch'], '접근 선택': sum(1 for r in boss if r.get('event') == 'choice' and '접근' in r.get('choice', ''))}
    print('보스 그 밖  ' + ' · '.join('%s %d' % kv for kv in moves.items() if kv[1]))

    # 플레이어가 한 일
    pcount = collections.Counter(r.get('event') for r in player)
    health = [float(r['hp']) for r in player if r.get('hp') not in (None, '')]
    boss_health = [float(r['hp']) for r in boss if r.get('hp') not in (None, '')]
    taken = sum(max(0., a - b) for a, b in zip(health, health[1:]))
    dealt = sum(max(0., a - b) for a, b in zip(boss_health, boss_health[1:]))
    print('가드  막음 %d · 저스트 가드 %d' % (count['guard_block'], count['just_guard']))
    print('플레이어  회피 %d회 · 가드 %d회 · 받은 피해 %d · 준 피해 %d · 마지막 체력 %d (보스 %d)' % (
        pcount['dodge_accepted'], pcount['guard_begin'], taken, dealt, health[-1] if health else -1, boss_health[-1] if boss_health else -1))
    speeds = [float(r.get('speed', 0) or 0) for r in player if r.get('event') == 'sample']
    if speeds:
        print('플레이어 이동  움직인 시간 %d%%' % round(100 * sum(1 for s in speeds if s > 50) / len(speeds)))


if __name__ == '__main__':
    argument = sys.argv[1] if len(sys.argv) > 1 else '1'
    if argument == 'archive':
        print(archive())
    else:
        found = sessions()
        if '--all' not in sys.argv:
            found = [s for s in found if not is_test(s[2])] or found
        for session in found[-int(argument):]:
            report(session)
