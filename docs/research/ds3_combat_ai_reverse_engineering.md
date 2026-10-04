# DS3 전투 AI 역설계 자료: Crunch에 사용할 수 있는 근거

조사일: 2026-10-04. 이 문서는 **공개된 역설계 자료에서 확인한 사실**과 **Battle의 기획 해석**을 분리한다. 추가로 이 PC의 DS3 설치본에서 군다의 실제 파라미터 행과 AI 바이트코드를 추출했다. 값·가중치·한계는 [군다 원본 AI 추출 기록](ds3_gundyr_original_ai_extract.md)에 정리했다.

## 먼저 읽을 결론

DS3에서 참고할 가치가 큰 것은 확인되지 않은 `몇 도/몇 초` 값을 베끼는 것보다 다음 데이터 연결이다.

`맵의 적 배치 → NPC/Think 파라미터 → 전투 AI의 조건·행동 가중치 → 애니메이션과 TAE 이벤트 → 실제 회전·이동·타격`

이 연결이 확인되면 Crunch의 설계도 같은 질문으로 검증할 수 있다: **어디에 있는가 → 왜 그 행동을 골랐는가 → 발과 몸이 어떻게 움직였는가 → 언제 타격·방향 고정이 일어났는가.** 이는 자료에서 영감을 받은 Battle의 설계 해석이며, DS3가 HFSM·Utility AI·GOAP라는 이름의 세 시스템을 사용했다는 주장은 아니다.

## 공개 자료에서 실제로 확인한 항목

| 자료 | 확인된 항목 | Crunch에 옮길 질문 | 증거 범위 |
| --- | --- | --- | --- |
| DS3 Paramdex `NPC_PARAM_ST` | `turnVellocity`, `hitHeight`, `hitRadius` 필드가 있다. | 기본 회전 능력과 몸/공격 형상을 별도로 측정할까? | **필드 정의**다. 군다의 실제 행 값은 [별도 추출 기록](ds3_gundyr_original_ai_extract.md)에 있다. |
| DS3 Paramdex `NPC_THINK_PARAM_ST` | `battleGoalId`, `nearDist`, `midDist`, `farDist`, `OutDist`, 시야각과 이동 관련 필드가 있다. | 거리 구간과 AI 스크립트 연결을 분리할까? | XML의 `= ...`는 정의의 기본값이다. 군다의 실제 행 값은 [별도 추출 기록](ds3_gundyr_original_ai_extract.md)에 있다. |
| DS3 Lua Compendium | `GetDist`, `IsInsideTarget`, `IsTargetGuard`, `GetRandam_Int`, `Approach_Act_Flex`, `SpaceCheck`, `SpaceCheckBeforeAct`, `SetCoolTime` 함수가 정리돼 있다. | 거리·각도·가드·뒤 공간을 후보 점수와 위치 행동에 넣을까? | DS3 함수 레퍼런스다. 특정 보스가 모두 사용했다는 증거는 아니다. |
| DS3 Lua Compendium `SetCoolTime` | 애니메이션 쿨다운 여부에 따라 행동 가중치를 바꾸며, 다른 행동이 모두 불가할 때를 위해 매우 낮은 가중치 `1`을 남기는 사용법이 설명돼 있다. | 최근 공격 반복을 낮추되 후보가 전부 사라지지 않게 할까? | 함수 사용법이다. Crunch의 점수나 군다의 실제 확률은 아니다. |
| Souls Modding 공통 AI 함수 목록 | `GOAL_COMMON_ApproachTarget`, `LeaveTarget`, `SidewayMove`, `Turn`, `AttackTunableSpin`, `NonspinningAttack`와 전·후·좌·우 각도 검사가 나와 있다. | 접근·턴·후퇴를 각각 행동으로, 공격별 방향 정렬을 속성으로 만들까? | 문서 자체가 **DS1을 위해 작성됐고 다른 게임과 호환성이 높다**고 밝힌다. DS3 특정 보스의 실행 기록은 아니다. |
| Souls Modding TAE 문서 | 애니메이션 시간대에 이벤트를 붙인다. Type 224는 해당 구간 동안 회전속도를 변경하고 끝나면 기본값으로 돌아간다고 설명한다. | 공격 시작~타격 사이의 회전 허용을 구간으로 측정할까? | 공개 문서는 이벤트 형식 설명이다. 군다 `3000`의 실제 Type 224 구간은 [설치본 추출 기록](ds3_gundyr_original_ai_extract.md)에 추가했다. 속도의 단위는 여전히 미확정이다. |
| 심판자 군다 분해 문서 | 군다 모델 ID는 `c5110`. `chrbnd`는 모델·물리 형상, `anibnd`는 애니메이션·TAE, `behbnd`는 저수준 애니메이션 제어. | 같은 모델이어도 파라미터와 스크립트 분기로 전투 성격이 달라짐을 어떻게 보여줄까? | 공개 문서에는 공격별 확률·회전값이 없다. 이번 설치본 추출에서는 `511000`·`511100`의 `battleGoalId`가 모두 `511000`으로 나와, **같은 진입 Goal의 내부 조건 분기**를 확인했다. |

### 정확히 구분할 용어

- `GOAL_COMMON_Turn`의 **Goal**은 DS3 AI의 하위 행동 이름이다. Battle에서 말하는 **GOAP 계획 알고리즘**을 DS3가 사용했다는 뜻이 아니다.
- `SpinTime`/`SpinAngle`은 공통 함수 자료에서 **공격 행동 전에 목표 방향을 맞출 시간·각도**로 설명한다. 이것만으로 타격 중 `0.2초 추적` 같은 값을 입증할 수 없다. 애니메이션 도중 회전 변화는 TAE나 실제 게임 데이터를 따로 확인해야 한다.
- 공유 대화에 나온 `잽 30°/0.2초`, `휩쓸기 15°/0.3초` 같은 숫자는 **Crunch 기획 예시**다. DS3 추출값으로 인용하지 않는다.
- 인터넷 검색에서 발견되는 `NPCs_vs_DS3/zz_AIvsDS3_Gundyr_battle.lua`는 파일 첫머리에 `custom gundyr battle goal for testing`이라고 적힌 **커스텀 대전 AI**다. 원본 군다의 행동 표로 사용하지 않는다.

## Crunch에 적용할 수 있는 설계 실험

| DS3에서 확인한 구조 | Battle의 현재 상태 | 다음 실험 |
| --- | --- | --- |
| 거리·각도 조건으로 행동을 분리할 수 있다. | GOAP에 `FaceTarget`, `DirectApproach`, 좌·우 `Orbit`가 있다. `FaceTarget`은 이미 즉시 180° 회전이 아니다. | 뒤쪽 90°/180°에서 턴 클립과 실제 Yaw를 동기화하고 발 미끄러짐을 촬영한다. |
| 행동 후보에 쿨다운과 공간 조건을 적용할 수 있다. | Utility가 공격 후보를 점수화하고 가중 추첨한다. 밀착 후퇴는 아직 없다. | `너무 가까움 + 뒤 공간 있음`일 때만 뒤걸음 후보를 열고 접근↔후퇴 반복을 막는다. |
| 기본 회전과 공격 중 방향 허용을 별개로 볼 수 있다. | HFSM에서 준비·타격·후딜을 구분한다. | 각 공격의 준비 초반 Yaw 변화, Commit 시점, 타격 중 Yaw 변화를 실제 PIE로 기록한다. |
| 애니메이션 시간대의 타격 이벤트가 중요하다. | Crunch 타격은 몽타주와 손 접촉 추적을 사용한다. | 손 소켓의 접촉 프레임과 판정 열린 구간을 함께 기록한다. |

우선순위는 **턴 발동작 → 공격별 방향 약속 측정 → 밀착 뒤걸음 → Utility 선택 기록**이다. GOAP 행동을 무작정 늘리기 전에 화면에서 각 행동이 읽히는지부터 합격시킨다.

## 원작 수치 조사 현황

`511000/511100` 행과 실제 `511000_battle.lua` → `Gunda_battle.lua`/`Gunda_HU_battle.lua` 연결을 추출해 [행·행동 가중치·턴·공격 후 움직임을 기록했다](ds3_gundyr_original_ai_extract.md). 따라서 앞서 공개 정의만 보고 비워 둔 숫자 일부는 이제 출처와 함께 제시할 수 있다.

`c5110.anibnd`의 TAE에서 공격 `3000`의 Type 224 회전 관련 이벤트 구간까지 확인했다. 남은 검증은 `m40_00_00_00`의 NPC 배치를 원본 맵에서 직접 대조하고, 이 이벤트와 실제 플레이의 회전·타격 프레임을 맞추는 것이다. 특히 `turnVellocity=70`의 단위와 `GOAL_COMMON_Turn`의 각도 인자만으로 실제 회전 속도를 단정하지 않는다.

## 출처

- [SoulsMods Paramdex: DS3 NPC_PARAM_ST](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/NPC_PARAM_ST.xml)
- [SoulsMods Paramdex: DS3 NPC_THINK_PARAM_ST](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/NPC_THINK_PARAM_ST.xml)
- [DS3 Lua Compendium](https://docs.google.com/spreadsheets/d/1_tvSopHY_A_s70a_VO9xzX78fN7ig1oKJihuDjWDB-g/edit?gid=1578583932)
- [Souls Modding: Lua AI Common Function Repository](https://www.soulsmodding.com/doku.php?id=common-refmat:lua_ai_common_function_repository)
- [Souls Modding: TAE](https://www.soulsmodding.com/doku.php?id=format:tae)
- [Souls Modding: Anatomy of a Boss Fight: Iudex Gundyr](https://www.soulsmodding.com/doku.php?id=tutorial:boss-iudex-gundyr)
- [Souls Modding: DS3 moveset/AI extraction guide](https://www.soulsmodding.com/doku.php?id=tutorial:modding-movesets-the-muffin-knowledge-compenium-ds3)
- [DSLuaDecompiler project](https://github.com/katalash/DSLuaDecompiler)
- [NPCs_vs_DS3 custom script: 바닐라 근거로 사용하지 않는 예](https://github.com/TuriansNotBad/NPCs_vs_DS3/blob/master/zz_AIvsDS3_Gundyr_battle.lua)
