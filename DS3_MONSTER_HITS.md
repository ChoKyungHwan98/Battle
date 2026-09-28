# DS3 자료를 참고한 몬스터 판정·피격

## 무엇을 가져왔나

Souls Modding의 DS3 가이드와 DS3 Paramdex 정의를 확인했다. 공격 이벤트가 공격 데이터를 호출하고, 그 데이터가 판정 위치·반경·피격 등급을 갖는 구조를 Battle에 적용했다.

**DS3 특정 보스의 원본 수치를 복사한 것은 아니다.** 공개 정의에는 필드 이름과 형식이 있지만, 특정 보스의 전체 공격별 값·애니메이션 이벤트·부위별 경직 조건은 이 프로젝트에 제공되지 않았다. 현재 반경·피해·시간은 Battle의 Crunch와 SwordShield 모션에 맞춘 값이다.

| DS3에서 확인한 구조 | Battle 구현 |
|---|---|
| TAE 공격 이벤트 → BehaviorParam → AtkParam | 공격 데이터 에셋 → 몽타주·타격 시작/종료 → 접촉 검사 |
| `Hit#_DmyPoly1/2`, `Hit#_Radius` | 칼날 시작·끝, 팔꿈치·주먹과 반경 |
| `isShareHitList` | 한 타격에서 성공한 피해를 한 번만 처리. 양손도 기록 공유 |
| `damageLevel`, `AtkSuperArmor` | 공격의 `HitReactionLevel`을 HP 피해량과 분리 |
| NPC `superArmorDurability`, `isNoDamageMotion` | 기존 기획의 공격 중 경직 없음 유지. 공격 밖에서는 방향별 시각 반응 |

필드가 존재한다는 사실과 특정 적의 값·행동을 검증했다는 것은 구분해야 한다. Battle의 무적 중 접촉 기록 정책도 아래와 같이 명시한 프로젝트 규칙이다.

## 플레이어가 몬스터를 때릴 때

이전에는 몸 앞의 고정 구가 피해를 주었다. 이제 Sword 컴포넌트의 실제 변환에서 칼날 구간을 계산한다.

1. 공격 시작 시 이전 타격 기록과 판정 창을 초기화한다.
2. 기존 공격 타이머가 유효 시간의 시작을 알린다.
3. 칼날 구간, 이전 프레임의 칼끝, 이전 프레임의 칼 중간을 구형 스윕으로 검사한다.
4. 보스의 물리 에셋과 닿으면 `ApplyPointDamage`로 적중 위치·뼈 정보를 전달한다.
5. 같은 타격에서 중복 접촉은 피해를 추가하지 않는다.
6. 벽을 먼저 맞으면 그 타격의 판정 창을 닫는다. 다음 공격에서는 다시 검사한다.

현재 전장은 단일 보스이므로 타격별 성공 기록은 bool이다. 여러 적을 한 공격으로 맞히는 전투로 확장한다면 타격별 대상 Set으로 바꿔야 한다.

### 기획자가 조정할 값

| 값 | 현재 설정 | 의미 |
|---|---:|---|
| 칼날 구간 | 모델 로컬 Z 8~99cm | 실제 검 모델에 대응하는 구간 |
| `SwordTraceRadius` | 12cm | 얇은 날에 대한 접촉 허용 폭 |
| `AttackHitRatio` | 0.12 | 공격 길이 대비 판정 시작 비율 |
| `SwordActiveRatio` | 0.30 | 공격 길이 대비 판정 유지 비율 |

타이밍·반경은 DS3 원본 값이 아니다. 큰 반경으로 빈 공간을 때리게 만드는 대신 실제 칼날 위치를 사용한다.

프레임 측정에서 기존 0.36 시작은 실제 칼이 앞으로 나갔다가 돌아온 뒤에 열렸다. 시작을 0.12로 앞당겨 칼의 실제 접촉 프레임을 판정 창에 포함시켰다.

## 몬스터가 플레이어를 때릴 때

기존 공격별 타격 시점과 팔꿈치~주먹 검사, 이전 프레임 주먹 궤적을 유지한다. 접촉 검사는 Pawn만 찾던 방식에서 **몸과 환경을 함께 검사하는 스윕**으로 바뀌었다.

- 이동 캡슐: 캐릭터끼리 밀리지 않고 지형에 막히는 이동용 충돌.
- 스켈레탈 메시의 물리 에셋: 공격에 맞는 몸의 형상. 쿼리만 사용하며 래그돌을 켜지 않는다.
- 유효 시간: 준비·회복 동작에서는 공격 판정이 없다.
- 성공 기록: 한 번 피해를 주면 그 타격은 끝. 양손이 같은 타격에 각각 피해를 주지 않는다.
- 무적: 무적 중에는 피해·가드 브레이크를 적용하지 않고 성공 기록도 소비하지 않는다. 같은 유효 시간에 무적이 끝나고 여전히 닿아 있으면 맞을 수 있다.
- 벽: 스윕이 벽을 먼저 검출하면 그 접촉을 플레이어 피해로 처리하지 않는다.

몬스터 반경과 데이터 에셋의 기존 공격 시점은 보존했다. 원본 DS3 보스의 모든 판정을 재현했다는 의미는 아니다.

## 피격 반응

### 몬스터가 맞았을 때

- 앞·뒤·왼쪽·오른쪽에 있는 공격자 위치로 `HitReact_Front/Back/Left/Right`를 선택한다.
- 전투 대기·접근 상태에서 상체 반응을 재생한다.
- 공격 중에는 공격 몽타주와 HFSM 진행을 유지한다. 일반 공격으로 보스가 계속 끊기는 구조를 만들지 않았다.
- 사망은 기존 `CheckBossDeath` 흐름이 처리한다.

### 플레이어가 몬스터에게 맞았을 때

`BP_BossActionDefinition`의 새 `HitReactionLevel`을 공격 데이터에서 읽는다.

| 프로젝트 값 | 반응 | 기본 패턴 |
|---:|---|---|
| 0 | 기존 방향별 일반 피격 | 왼손·오른손·휩쓸기·잽→잽→훅 |
| 1 | 넘어짐·일어나기 | 어퍼컷·가드 브레이크·대시 |

**0/1은 Battle의 편의 코드이며 DS3 `damageLevel` 번호를 그대로 쓴 값이 아니다.** 가드 성공 시에는 기존 방패 막기 모션을 사용한다. 공격 데이터가 없는 외부 피해에만 기존 피해량 기준 넘어짐 판정을 보조 규칙으로 사용한다.

예를 들어 일반 공격을 160 피해로 테스트해도 넘어짐 등급으로 바뀌지 않고, 넘어짐 등급 공격을 10 피해로 테스트해도 넘어짐 반응을 재생한다.

## 구현을 읽는 순서

- 플레이어: `StartComboStep` → `DoAttackHitCheck` → Tick의 `TraceSwordWindow` → `ResolveSwordContact`.
- 몬스터: `OpenActionImpact` → Tick의 스윕 및 `TraceOtherHand` → `CloseActionImpact`.
- 몬스터 피격: `AnyDamage` → 체력·사망 확인 → Ready 상태에서 `PlayDirectionalHitReaction`.
- 플레이어 피격: `AnyDamage` → 공격 데이터의 `HitReactionLevel` → `PlayShieldReaction`.
- `RequestCombatAction(ActionIndex)`: 기획 검증용 개별 패턴 요청. Ready이며 유효한 인덱스일 때만 기존 `BeginCombatAction`을 호출한다. 자동 Utility 선택에는 연결하지 않았다.

백업: `/Game/BossArena/Backup/*_PreSoulsHit_20260929`. 수정 전 플레이어·보스·공격 정의와 각 데이터 에셋을 보관했다.

## 출처

- [Souls Modding: DS3 moveset guide](https://soulsmodding.com/doku.php?id=tutorial:modding-movesets-the-muffin-knowledge-compenium-ds3)
- [Paramdex: DS3 ATK_PARAM_ST](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/ATK_PARAM_ST.xml)
- [Paramdex: DS3 NPC_PARAM_ST](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/NPC_PARAM_ST.xml)
- [Souls Modding: TAE](https://soulsmodding.com/doku.php?id=format:tae)

## 검증 기록

2026-09-29, UE 5.8.3, `Lvl_Arena_01`에서 총 **97개 검사 통과**. 플레이어·보스·공격 정의 블루프린트는 컴파일 후 `BS_UP_TO_DATE`를 확인했고, 실행 중 `LogScript: Warning`이 없는 것도 검사했다.

| 시나리오 ID | 검사 | 결과 |
|---|---|---|
| `20260928T154948Z-5AFCC614` | 실제 LMB 공격 250cm에서 12 피해 / 650cm에서 0, 한 타격 중복 피해 방지, 실제 네 방향 피격 클립, 무적 중 0 피해·기록 미소비, 종료 후 왼손 데이터 피해 110을 한 번만 적용 | 38/38 |
| `20260928T154817Z-5CD916B6` | 벽 접촉 우선 처리, 일반 등급 160 피해에서 넘어지지 않음, 강한 등급 10 피해에서 넘어짐, 맞아도 보스 공격 몽타주 유지, 사망·판정 종료 | 24/24 |
| `20260928T155022Z-3FC98938` | Space 즉시 구르기·320cm 이동, 길게 누르면 달리기, F 점프, 마우스 4타 연계, 방패 가드·막기, 방향별 피격·넘어짐·일어나기 | 35/35 |

캡처는 `Saved/VibeUE/Scenarios/<ID>-<장면>.png`에 저장했다. 실제 화면을 열어 검 자세, 네 방향 반응 캡처, 공격 유지, 벽 검사, 넘어짐을 확인했다. 방향 검사는 화면뿐 아니라 재생된 `HitReact_Front/Back/Left/Right` 클립 이름과 각도도 확인한다.

테스트 범위: 단일 Crunch와 현재 검 모델을 대상으로 한 격리된 PIE 검사다. 벽 검사는 실제 벽 HitResult를 먼저 처리하고 이후 몸체 접촉을 거절하는 규칙을 확인한다. 모든 지형·모든 패턴의 판정 형상을 전수 검증한 결과는 아니다. 무적 검사는 겹친 위치를 유지하여 무적 종료 전후를 비교한다. 테스트용 체력 2000, 위치 이동, 보스 AI 정지는 PIE에서만 사용한다.

`Tools/TestSoulsHits.py`는 재현용 검사이고, `Tools/PolishSoulsHits.py`는 이번 에셋 수정 과정을 기록한 도구다. 후자를 다시 실행하면 기획 조정값이 기본값으로 돌아갈 수 있으므로 반복 테스트에는 검사 도구를 사용한다.
