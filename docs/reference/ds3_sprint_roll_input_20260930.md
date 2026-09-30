# Space Sprint/Roll 재조사 — 2026-09-30

## 근거 구분

| 등급 | 확인 결과 |
|---|---|
| A — 설치본 직접 확인 | Steam DS3 `Data3`의 `/action/script/common_define.hks`(SHA-256 `f0d006a8aa714dda955a4430cdda81265af9a5c07438e84746af9ea883293c7a`)를 [DSLuaDecompiler](https://github.com/katalash/DSLuaDecompiler)로 읽으면 `ACTION_ARM_SP_MOVE=5`, `ACTION_ARM_BACKSTEP=12`, `ACTION_ARM_ROLLING=13`이다. `/action/script/c0000.hks`(SHA-256 `ef9d2020546b8f88023e0cb4c04fd3523117bc4c34483469dda2302a47a965b2`)에는 `env(1106, ACTION_ARM_ROLLING)`과 `env(1106, ACTION_ARM_BACKSTEP)`의 별도 요청 경로가 있다. |
| A — 설치본 범위 | 같은 `c0000.hks`의 `Move_Update()`는 `SetMoveWeightIndex()`와 `ChangeWaistTwist()`를 호출한다. `env(1108, ACTION_ARM_SP_MOVE)`는 확인한 디컴파일에서 사다리 이동에 등장한다. 제시된 `>100` Dash 전환이나 락온 `abs(g_MoveAngle)<25` 식은 여기서 확인되지 않았다. 이는 해당 식이 DS3 어디에도 없다는 증명이 아니다. 디컴파일 정확도와 입력 처리의 다른 계층을 고려해야 한다. |
| A — Behavior/TAE 범위 | 설치본 `c0000.behbnd`(SHA-256 `b3d129213946108043689542e6c813082e78e524912006c4e51a3ad19815cb49`, BND4)에서 Dash·Rolling·BackStep 노드 이름을 확인했다. `c0000-a00.tae`(SHA-256 `9f8b4742c77dd5a0f4858e5cb65c968e8c45b1bf808fdae2ed717c90be63a92d`)의 수치 이벤트는 `Tools/ReadDS3Events.py`로 읽었다. 이 자료만으로 입력 홀드 임계값이나 ±25° 조건을 연결할 수 없다. |
| B — 공개 역공학 | 공개 정리 HKS와 [HKS 명령 설명](https://github.com/vawser/ER-Documentation/blob/main/Info%20-%20HKS.txt)도 ActionRequest 1106, ActionDuration 1108 및 Roll/Backstep의 구별을 뒷받침한다. 조사한 공개 `c0000.hks`에도 제시된 `MoveUpdate >100ms`, `g_MoveAngle <25` 식은 없었다. 공개 코드는 디컴파일 후 수정된 자료이므로 원본 증거로 취급하지 않는다. |
| C — Battle 보정 | 최초 시도한 0.10초 기준에서는 락온 중 130ms 입력이 구르기로 들어가지 않았다. 현재는 Space 탭 `<0.18초`, 이동 중 Space 홀드 `>=0.18초`, 이동 입력 크기 제곱 `>0.01`로 조정했다. **0.18초와 ±25°를 DS3 원본값이라고 부르지 않는다.** |

원본 추출 기록은 `Saved/VibeUE/ReferenceReader/selected-members.json`에 있고, 로컬 디컴파일 결과는 같은 폴더의 `common_define-installed.dec.lua`, `c0000-installed.dec.lua`에 남겨 두었다. 게임 원본 파일과 디컴파일 결과는 Git에 추가하지 않았다.

## Battle 적용

- `IMC_Player_Combat`: IA_Dodge Space에 Tap `<0.18초`, IA_Sprint Space에 Hold `>=0.18초`를 설정했다. UE 5.8 `InputTriggerTap`의 Release 판정과 `InputTriggerHold`의 Triggered 판정을 사용한다.
- `BP_Player_Combat`: 탭 Release 시 이동 입력이 있으면 기존 방향 구르기, 없으면 무동작이다. 달리기는 홀드와 이동 입력이 모두 있을 때 시작하고 Space Release 시 끝난다.
- 정지 탭의 임시 백스텝 경로는 제거했다. Backstep 클립의 Root Motion도 이전 설정으로 되돌렸다. 기존 백스텝은 회복 이벤트가 없어 행동 상태가 회피에 고정되는 결함이 있었다.
- 달리기가 `LockOnTarget`을 비우지 않게 했다. 수동 락온 토글은 달리기 중에도 허용한다.
- 롤·백스텝 모션과 락온 중 측면 Dash의 실제 DS3 등가성은 증명되지 않았다. 확인되지 않은 ±25° 제한은 적용하지 않았다.

## PIE 검증

`Tools/TestDS3SprintRoll.py`의 재현 시나리오 결과:

| 시나리오 | 결과 |
|---|---|
| 정지 짧은 탭 | 행동 상태 유지, 0.7초 뒤에도 이동 가능 — `20260930T041111Z-FCE31683` |
| 락온 중 130ms 탭 | 구르기 상태, 약 232cm 이동, 락온 대상 유지 — `20260930T041127Z-937ABB93` |
| 락온 구르기 회복 | 회복 후 이동 속도 450cm/s — `20260930T041239Z-15C1B5A2` |
| 락온 중 이동 홀드·Release | 달리기 시작·종료, 전 과정 `LockOnTarget` 유지 — `20260930T041346Z-70C7E389` |
| 정지 상태 Space 홀드 | 달리기·백스텝 진입 없음, Release 후 행동 상태 유지 — `20260930T041445Z-87D0C5E5` |
| 비락온 이동 짧은 탭 | 방향 구르기 진입, 백스텝·달리기 없음 — `20260930T041503Z-32D83C1B` |

각 시나리오에서 Blueprint 런타임 경고를 검사했다. 이 검증은 Battle 동작 검증이며 DS3 원본과 동일한 입력 타이밍을 입증하는 시험은 아니다.

첫 구현은 `Tools/ApplyDS3SprintRoll.py`, 정지 백스텝 제거와 탭 시간 수정은 `Tools/FixSpaceRollNoBackstep.py`로 재현할 수 있다. 두 스크립트 모두 각각의 적용 전 상태를 전제로 하는 일회성 마이그레이션이다.
