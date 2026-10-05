"""Read observational Battle QA records; standard library, no Unreal dependency.

Usage: python Tools/ReadCombatQA.py [--log Saved/Logs/Battle.log] [--session N]
N is one-based; omission selects the latest recorded play session.
"""
import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = '[BATTLE_QA] '


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def vector(value):
    matches = re.findall(r'([XYZ])\s*=\s*([-+\d.eE]+)', value or '')
    axes = {key: float(val) for key, val in matches}
    return tuple(axes[key] for key in 'XYZ') if len(axes) == 3 else None


def parse_lines(lines):
    records = []
    for line_number, line in enumerate(lines, 1):
        if MARKER not in line:
            continue
        prefix, payload = line.split(MARKER, 1)
        record = {'line': line_number, 'log_prefix': prefix.strip()}
        for field in payload.strip().split('|'):
            if '=' in field:
                key, value = field.split('=', 1)
                record[key.strip()] = value.strip()
        if record.get('v') == '1' and record.get('role') in {'boss', 'player', 'candidate'}:
            records.append(record)
    return records


def split_sessions(records):
    sessions, current = [], []
    for record in records:
        if record.get('event') == 'session_start' and record['role'] == 'boss':
            if current:
                sessions.append(current)
            current = []
        current.append(record)
    if current:
        sessions.append(current)
    return sessions


def summarize(records):
    boss = [r for r in records if r['role'] == 'boss']
    player = [r for r in records if r['role'] == 'player']
    choices = [r for r in boss if r.get('event') == 'choice']
    samples = [r for r in boss if r.get('event') == 'sample']
    candidates = [r for r in records if r['role'] == 'candidate']
    starts = [r for r in boss if r.get('event') == 'state'
              and r.get('state', '').endswith('.Windup')]
    # Selection text can remain from a previous action in manual/phase requests.
    # New execution snapshots are authoritative; old logs can only identify a slot.
    def execution_name(r):
        return r.get('started_name') or ('slot ' + r.get('slot', '?') + ' (legacy)')
    events = Counter(r.get('event', 'candidate') for r in boss if r.get('event') != 'sample')
    # State time is sampled and capped at one second per interval. Gaps are never
    # counted as proof that an actor stayed in a state while paused/unrecorded.
    sampled_state_seconds = Counter()
    for before, after in zip(samples, samples[1:]):
        if before.get('boss') != after.get('boss'):
            continue
        t0, t1 = number(before.get('t')), number(after.get('t'))
        if t0 is not None and t1 is not None and 0 <= t1-t0 <= 1:
            sampled_state_seconds[before.get('state', '?')] += t1-t0
    health_drops, previous_hp = [], {}
    for r in player:
        hp = number(r.get('hp')); actor = r.get('boss', '')
        if hp is None:
            continue
        previous = previous_hp.get(actor)
        if previous is not None and hp < previous:
            health_drops.append({'t':r.get('t'), 'amount':round(previous-hp, 3),
                                 'event':r.get('event'), 'line':r['line']})
        previous_hp[actor] = hp
    streak, longest, previous_choice = 0, 0, None
    for r in choices:
        label = r.get('choice', r.get('slot','?'))
        streak = streak + 1 if label == previous_choice else 1
        previous_choice = label
        longest = max(streak, longest)
    # Rows are emitted boss then player for the same call. Pair only exact
    # actor/game-time/event keys; decision_distance is deliberately not live.
    boss_rows = {(r.get('boss'),r.get('t'),r.get('event')):r for r in boss}
    live_distances = []
    for r in player:
        peer = boss_rows.get((r.get('boss'),r.get('t'),r.get('event')))
        a, b = vector(peer.get('pos')) if peer else None, vector(r.get('pos'))
        if a is not None and b is not None:
            r['live_distance_2d_cm'] = round(math.hypot(a[0]-b[0],a[1]-b[1]), 2)
            live_distances.append(r['live_distance_2d_cm'])
    times = [number(r.get('t')) for r in records]
    times = [t for t in times if t is not None]
    return {
        'rows':len(records), 'map': next((r.get('map') for r in boss if r.get('map')), '?'),
        'has_start_marker':any(r.get('event')=='session_start' for r in boss),
        'first_game_time':min(times) if times else None,
        'last_game_time':max(times) if times else None,
        'choices':dict(Counter(r.get('choice',r.get('slot','?')) for r in choices)),
        'longest_identical_choice_streak':longest, 'events':dict(events),
        'actual_attack_starts_by_slot':dict(Counter(r.get('slot','?') for r in starts)),
        'actual_attack_starts_by_pattern':dict(Counter(execution_name(r) for r in starts)),
        'actual_attack_starts_by_source':dict(Counter(r.get('started_source','legacy_unknown') for r in starts)),
        'attack_rejections':dict(Counter(r.get('start_reason','?') for r in boss
                                       if r.get('event') == 'attack_rejected')),
        'accepted_attack_requests':sum(r.get('event') == 'attack_accepted' for r in boss),
        'sampled_state_seconds':{k:round(v,2) for k,v in sampled_state_seconds.items()},
        'candidate_rows':len(candidates),
        'zero_score_reasons':dict(Counter(r.get('reason','?') for r in candidates
                                       if number(r.get('score')) == 0)),
        'player_health_drops':health_drops,
        'player_hp_lost_observed':round(sum(d['amount'] for d in health_drops),3),
        'player_dodge_rows':[r for r in player if r.get('event')=='dodge_accepted'],
        'player_refund_rows':[r for r in player if r.get('event')=='stamina_refund'],
        'min_live_distance_cm':min(live_distances) if live_distances else None,
        'max_live_distance_cm':max(live_distances) if live_distances else None,
    }


def markdown(summary, records, source, session, total):
    lines = ['# Battle 플레이 QA', '', f'- 원본: `{source}`',
             f'- 세션: {session}/{total} · 맵: {summary["map"]}',
             f'- 게임 시간: {summary["first_game_time"]} ~ {summary["last_game_time"]}초',
             f'- 기록: {summary["rows"]}행 · 후보 평가: {summary["candidate_rows"]}행', '',
             '이 기록은 플레이 중의 판단과 수치입니다. 화면에서 발이 자연스럽게 디뎌지는지, '
             '이펙트가 충분히 보이는지는 영상으로 확인해야 합니다.', '', '## 선택과 실행', '']
    for label, count in summary['choices'].items():
        lines.append(f'- {label}: {count}번 선택')
    lines += [f'- 같은 선택의 최장 연속: {summary["longest_identical_choice_streak"]}회',
              '- 실제 공격 준비 진입(슬롯별): '+json.dumps(summary['actual_attack_starts_by_slot'],ensure_ascii=False),
              '- 실제 시작한 패턴: '+json.dumps(summary['actual_attack_starts_by_pattern'],ensure_ascii=False),
              '- 공격 시작 경로: '+json.dumps(summary['actual_attack_starts_by_source'],ensure_ascii=False),
              '- 시작 거부 사유: '+json.dumps(summary['attack_rejections'],ensure_ascii=False),
              '', '## 판정과 회피', '',
              f'- 팔 접촉 전달: {summary["events"].get("contact_submitted",0)}회',
              f'- 관찰한 플레이어 HP 감소: {summary["player_hp_lost_observed"]}',
              f'- 회피 허용: {len(summary["player_dodge_rows"])}회',
              f'- 스태미나 반환 실행: {len(summary["player_refund_rows"])}회', '',
              '접촉 전달만으로 피해를 확정하지 않습니다. 가드나 지연 피해 처리가 있을 수 있습니다. '
              '회피 허용 이벤트는 스태미나 지불 직전이며, 이후 상태와 이동은 표본으로 확인합니다. '
              '반환 이벤트는 스태미나를 돌려준 직후입니다.', '', '## 표본에서 관찰한 상태 시간', '']
    for state, seconds in summary['sampled_state_seconds'].items():
        lines.append(f'- {state}: 약 {seconds}초')
    lines += ['', '기본 표본 간격은 0.2초입니다. 짧은 무적 구간이나 정확한 접촉 프레임은 '
              '표본만으로 확정할 수 없습니다. 장시간 멈춘 구간은 상태 시간에서 제외합니다.', '',
              '## 점수가 0인 후보의 이유', '']
    for reason,count in summary['zero_score_reasons'].items():
        lines.append(f'- {reason}: {count}행')
    lines += ['', '## 이벤트 시간표', '',
              '| 게임 초 | 이벤트 | 보스 상태 | 선택 | 판정 |',
              '|---:|---|---|---|---|']
    for r in records:
        if r['role'] != 'boss' or r.get('event') == 'sample':
            continue
        cells = [r.get('t','?'),r.get('event','?'),r.get('state','?'),r.get('choice','?'),
                 f'타격 {r.get("strike","?")} / 열림 {r.get("strike_open","?")}']
        lines.append('| '+' | '.join(c.replace('|','/').replace('\n',' ') for c in cells)+' |')
    if not summary['has_start_marker']:
        lines += ['', '주의: 시작 표식이 없어 일부만 기록된 세션일 수 있습니다.']
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path)
    parser.add_argument('--session', type=int)
    parser.add_argument('--output', type=Path, default=ROOT/'Saved'/'QA')
    args = parser.parse_args()
    files = list((ROOT/'Saved'/'Logs').glob('*.log')) if args.log is None else [args.log]
    if not files:
        print('로그 파일이 없습니다. 먼저 에디터에서 직접 플레이해 주세요.');return 0
    source = max(files,key=lambda path:path.stat().st_mtime)
    records = parse_lines(source.read_text(encoding='utf-8-sig',errors='replace').splitlines())
    sessions = split_sessions(records)
    if not sessions:
        print(f'QA 플레이 기록 없음: {source}\n기능 추가 후 아직 기록된 플레이가 없습니다.');return 0
    index = args.session or len(sessions)
    if not 1 <= index <= len(sessions):
        parser.error(f'세션 번호는 1~{len(sessions)}입니다.')
    selected = sessions[index-1];summary = summarize(selected)
    args.output.mkdir(parents=True,exist_ok=True)
    base = args.output/'combat-qa-latest'
    base.with_suffix('.json').write_text(json.dumps({'source':str(source),'session':index,
        'total_sessions':len(sessions),'summary':summary,'records':selected},ensure_ascii=False,indent=2),encoding='utf-8')
    fields = sorted(set().union(*(r.keys() for r in selected)))
    with base.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(selected)
    base.with_suffix('.md').write_text(markdown(summary,selected,source,index,len(sessions)),encoding='utf-8')
    print(f'QA 세션 {index}/{len(sessions)}: {summary["rows"]}행\n요약: {base.with_suffix(".md")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
