# 보스 폴리싱 스펙 — 이동 끊김 · 충돌 구조 (2026-09-11)

> Codex용 문서. 1~3번은 **이미 적용됨**(Claude). 4~6번이 남은 작업이다.
> 증상: "모션 취하고 움직일 때 뚝 끊기면서 움직이는 느낌", "충돌이 조잡하다".

---

## 원칙 — 소울류 판정은 3층으로 나눈다

| 층 | 역할 | 형태 | 크런치 |
|---|---|---|---|
| **밀림 (Push)** | 서로 겹치지 않게 | 몸통 캡슐 **1개** | `CollisionCylinder` |
| **피격 (Hurtbox)** | 맞는 곳 | 부위별 도형, **막지 않음** | PhysicsAsset 부위 도형 |
| **공격 (Hitbox)** | 때리는 곳 | 뼈를 따라가는 구/캡슐 + 액티브 구간 | 손 소켓 스윕 |

**움직이는 팔다리가 플레이어를 막으면 안 된다.** 막는 건 몸통 캡슐뿐이다.
거대 보스일수록 캡슐을 **보기보다 작게** 잡아 다리 사이·옆으로 파고들 수 있게 한다.
FromSoft 게임은 공격 판정을 무기/뼈의 DummyPoly에 붙이고, 애니메이션 타임라인(TAE)에
켜지는 프레임 구간을, 공격 파라미터(AtkParam)에 반경을 따로 둔다.
우리 손 스윕 방식이 이 구조와 같다.

---

## 적용 완료

### 1. 즉시 정지 제거 → 감속 정지

`StopMovementImmediately`는 속도를 한 프레임에 0으로 만든다. 감속값을 무시하고,
블렌드스페이스가 Jog→Idle로 튄다. 공격 진입 경로에서 제거했다.

| 위치 | 변경 |
|---|---|
| `EvaluateUtility` | 즉시 정지 2개 삭제. `TryAttack`으로 바로 연결 |
| `UpdateUtilityMovement` | 체인 끝 즉시 정지 삭제 |
| `StopBossLocomotion` | 즉시 정지 삭제. `StopMovement` + `ConsumeMovementInputVector`만 남김 |
| `ExitCombat` | **유지** — 사망은 즉시 정지가 맞다 |

제동값:

| | BP 기본값 | 레벨 인스턴스 |
|---|---|---|
| `bUseSeparateBrakingFriction` | true | **false (설정 불가 — 아래 참고)** |
| `BrakingFriction` | 1.0 | 1.0 |
| `BrakingFrictionFactor` | 기본 2 | **0.25** |
| `BrakingDecelerationWalking` | 900 | 900 |

⚠ 인스턴스의 `bUseSeparateBrakingFriction`은 `set_properties`/`reset_properties`
모두 거부됐다. 그래서 인스턴스는 `GroundFriction 8 × BrakingFrictionFactor 0.25 = 2`로
같은 효과를 냈다. 에디터 디테일 패널에서 체크가 되면 체크하고 Factor를 기본값으로
돌려도 된다.

240cm/s에서 약 0.2초에 멈춘다 — 몽타주 블렌드인 0.25초와 맞물린다.

### 2. 부위 도형 `Pawn Block` → `Pawn Overlap`

이전 작업에서 PhysicsAsset 부위 도형 전체가 Pawn을 **막고** 있었다.
공격하는 팔이 플레이어를 밀어내 끼임·튕김이 생긴다.

`CharacterMesh0` 콜리전 응답 (BP 기본 + 레벨 인스턴스):

```
Vehicle     Ignore
Camera      Ignore
Pawn        Overlap   ← Block에서 변경
Visibility  Block     (유지)
ObjectType  Pawn / QueryOnly
```

밀림은 이제 몸통 캡슐만 담당한다. 부위 도형은 피격 확인용으로 남는다.

### 3. 회전 `RInterpTo` → `RInterpToConstant`

`RInterpTo`의 속도는 **배율**이다. 180 × 0.016 = 2.9 → 1로 잘려 매 프레임 스냅했다.
`RInterpToConstant`는 **초당 도**다.

- EventGraph Tick의 추적 회전 노드 교체 (Yaw 전용 구조는 유지)
- `TurnSpeed` 180 → **100 (초당 100도)**, BP 기본 + 인스턴스

무거운 보스가 느리게 도는 것이 정상이고, 옆으로 도는 플레이어에게 기회가 된다.

---

## 남은 작업 (Codex)

### 4. 대시 속도 연동

`DashingCross` 전진이 EventGraph의 `AddActorLocalOffset`(직접 위치 이동)이다.
몸은 이동하는데 CharacterMovement 속도는 0이라 블렌드스페이스가 제자리 모션을 틀고,
대시가 끝나는 순간 튄다.

- 방법 A: 대시 중 `Velocity`를 대시 속도로 설정하거나 `LaunchCharacter`
- 방법 B: 대시 중에는 AnimBP의 이동 블렌드 입력을 0으로 고정하고 전신 몽타주만
- 기존 조건 유지: 남은 이동량 제한, 캡슐 스윕, 0–650cm

### 5. 블렌드스페이스 보간

`BS_Boss_8Way` 모든 축 `InterpolationTime = 0`, `TargetWeightInterpolationSpeedPerSec = 0`.
ABP에서 입력을 `FInterpTo(6)`로 보간해 일부 가렸지만 원본은 비어 있다.

- 축 보간 0.2~0.3초 (에디터에서 설정 권장 — 블렌드스페이스 리플렉션 편집은
  이전에 에디터 크래시 이력 있음, `PLAN.md` 함정 노트)

### 6. 플레이어 공격 판정 → 손 기반

플레이어 공격이 아직 `ApplyRadialDamage`(몸 앞 고정 구)다. 보스처럼 손 소켓 스윕으로.
보스의 피격 대상은 부위 도형(Overlap)을 쓰면 된다. `BreakHitResult.HitBoneName`으로
부위 식별 가능.

---

## 정리 대상 (죽은 노드)

EventGraph에 실행 입력이 끊긴 노드 2개. 기능 영향 없음, 삭제 가능.

- `TransitionBossState` (Inactive → Ready, "BeginPlay — 보스전 즉시 활성화")
  — HFSM v1 잔재. 현재는 `BeginBossEncounter`의 Intro 흐름이 대체
- `UpdateUtilityMovement` 호출 — 어디서도 호출되지 않음. 현재 접근은
  `ChooseCombatAction`의 `MoveToActor`

## 검증 한계

MCP로 띄운 PIE는 창이 포커스되지 않으면 **3 FPS로 제한**된다. 감속 0.2초·회전
초당 100도 같은 체감 수치는 이 환경에서 측정이 무의미하다. **사람이 직접 플레이로
확인할 것.** 확인 항목:

- 접근 → 공격 전환 시 미끄러지듯 서는가
- 플레이어가 옆으로 돌 때 보스가 뚝뚝 꺾이지 않는가
- 공격하는 팔에 플레이어가 밀려나지 않는가
- 몸통 캡슐만으로 밀림이 충분한가 (파고들어 겹치지 않는가)

---

## 2차 적용 (2026-09-11) — 발 겹침 · 보스 크기 · 시점

### 증상
팔다리 `Pawn Overlap` 전환 후, 몸통 캡슐(반경 60×1.5=90)이 **보스의 벌어진
발 사이보다 작아서** 플레이어가 발 위에 겹쳐 서는 장면이 생겼다. "짜친다".

### 보스 크기 1.5 → 1.3
- 레벨 인스턴스 `relativeScale3D` 1.3, 배치 Z = −8 + 110×1.3 = **135**
- PIE 안착 Z 137.15 (바닥 간격 2.15, 정상)
- 실신장 약 340cm

### 밀림 캡슐 반경 60 → 105 (BP 기본 + 인스턴스)
- 월드 반경 105×1.3 ≈ **137cm**. 측면 캡처로 앞발·뒷발이 캡슐 원 안에 드는 것 확인
- 반경 상한은 반높이 110 (넘으면 캡슐이 구로 바뀜)
- 소울류 원칙(밀림 캡슐 하나)은 유지. 팔은 여전히 막지 않음
- 공격 자세에서 발이 더 벌어지면 발끝이 약간 나올 수 있다 — 플레이 확인

⚠ **공격 판정 반경은 월드 단위라 스케일을 따라 줄지 않는다.** 보스가 작아졌으므로
손 스윕 반경(현재 인스턴스 110, 휩쓸기 55)과 Utility 거리 조건(0–320 / 400–900 /
접근 260)은 플레이 후 재조정 대상이다.

### 시점 — `UpdateCameraFraming` (BP_Player_Combat, 신규 함수)

Tick 시퀀스 `then_3`에서 매 프레임 호출.

```
락온 여부 = IsValid(LockOnTarget)
암 길이    → FInterpToConstant(현재, 락온 ? CamLockArm : CamFreeArm, dt, 300/초)
소켓 Z    → FInterpToConstant(현재, 락온 ? CamLockOffsetZ : CamFreeOffsetZ, dt, 150/초)
카메라 랙  → 켬, 속도 10 (위치만. 회전 랙은 끔 — 락온 회전은 이미 보간 중)
```

| 변수 (카테고리 Camera) | 값 | 의미 |
|---|---|---|
| `CamFreeArm` | 400 | 자유 시점 거리 (기존값) |
| `CamLockArm` | 520 | 락온 시 뒤로 뺌 — 큰 보스가 화면을 덮지 않게 |
| `CamFreeOffsetZ` | 40 | 자유 시점 높이 |
| `CamLockOffsetZ` | 90 | 락온 시 올림 — 보스 전신과 플레이어를 같이 담음 |

PIE 확인: 자유 시점에서 암 400, 소켓 Z 40, 랙 켜짐·속도 10으로 수렴.
락온은 입력이 필요해 사람이 확인해야 한다.

기본값이 BeginPlay가 아니라 **변수**에 있으므로 디테일 패널에서 바로 조절 가능.
카메라 컴포넌트 템플릿(SCS)은 MCP로 접근이 안 돼서 런타임 보정 함수로 구현했다.

### 남은 선택지 (사용자 결정)
- **락온 피치 자동 조정** — 지금 락온 중 상하 각도는 마우스 그대로. 소울류는 보스가
  가까울수록 카메라가 살짝 내려다본다. 넣으면 조작감이 바뀌므로 결정 필요

---

## 3차 적용 (2026-09-11) — 속도 · 크기 복귀 · 락온 피치 · 판정

### 보스 크기 1.3 → 1.5 복귀 (사용자 요청)
배치 Z = −8 + 110×1.5 = **157**. 캡슐 반경 105 유지 (월드 약 157cm).

### 공격 전체 감속 — PlayRate 0.75 → 0.6
`/Game/BossArena/Boss/AI/Actions/DA_Attack_*` 7종 모두.
타이밍은 초 단위로 저장돼 있어 **몽타주 배속만 바꾸면 판정이 어긋난다.** 같이 환산했다.

```
배율 k = 0.75 / 0.6 = 1.25
impactTimes  = telegraph + (기존 − telegraph) × k     (예고 시간은 애니메이션과 무관하므로 제외)
totalSeconds = telegraph + (기존 − telegraph) × k
activeSeconds = 기존 × k
```

| 행동 | 첫 타격 | 전체 |
|---|---|---|
| 왼손 | 0.300 → 0.375 | 1.244 → 1.555 |
| 오른손 | 0.267 → 0.334 | 1.244 → 1.555 |
| 어퍼컷 | 0.711 → 0.889 | 1.661 → 2.076 |
| 휩쓸기 | 0.667 → 0.834 | 2.667 → 3.334 (판정창 0.65 → 0.812) |
| 3타 | 0.65/1.861/3.08 → 0.725/2.239/3.763 | 5.506 → 6.795 |
| 가드 브레이크 | 1.306 → 1.495 | 2.256 → 2.683 |
| 슈퍼맨 펀치 | 0.933 → 1.166 | 1.983 → 2.479 |

### 락온 피치 자동 (BP_Player_Combat.UpdateLockOnRotation)
기존: 락온 중 피치 = 현재 컨트롤 피치(마우스 그대로).
변경: 피치 = `Clamp(보스를 바라보는 피치, LockOnPitchMin, LockOnPitchMax)` → 기존 RInterpTo(10)로 부드럽게.

| 변수 (Camera) | 값 |
|---|---|
| `LockOnPitchMin` | −20 |
| `LockOnPitchMax` | 8 |

락온 중에는 마우스 상하 입력이 덮어써진다 (소울류 동작과 같음).

### 판정 — 보스가 플레이어를 못 맞히던 문제

**원인은 2차 적용에서 넓힌 밀림 캡슐(반경 105)이다.** 플레이어가 보스 중심에서
최소 약 191cm 떨어지게 됐는데, 보스는 여전히 260cm에서 멈춰 공격했고
판정은 **주먹 구 하나**라 거기서 닿지 않았다. 상단 촬영으로 스케일 1.5에서
임팩트 순간 주먹이 몸 중심에서 전방으로 약 110~150cm만 나오는 것을 확인했다.

수정 두 가지:

1. **판정을 주먹 → 팔뚝 전체로.** 스윕 시작점을 "직전 프레임 주먹 위치"에서
   **아래팔 소켓**으로 바꿨다. 매 프레임 `lowerarm → hand` 구간을 구로 쓸어서
   **팔뚝 캡슐**이 된다. 소울류 거대 보스의 무기/팔 판정과 같은 형태.
   - 메인: `AttackSocket`(hand_l/hand_r) 이름에서 `hand` → `lowerarm` 치환해 소켓 결정
   - 양손 공격(`TraceOtherHand`): `lowerarm_r → hand_r`
   - 반경은 기존 `AttackHitRadius`(인스턴스 110, 휩쓸기 55) 그대로
   - 직전 프레임 스윕을 뺐지만 반경 55~110이면 60fps에서 터널링 여지는 작다
2. **공격 거리 당김.**
   - `UtilityStopDistance` 260 → **210** (BP 기본 + 인스턴스)
   - 근접 공격 6종 `maxDistance` 320 → **280**
   - 접근 카드 `minDistance` 280 → **230**
   - 슈퍼맨 펀치(400–900)는 그대로

### 확인 필요 (사람)
- 보스가 실제로 맞히는지, 너무 잘 맞히는지 (반경 110은 팔뚝 캡슐로는 클 수 있다)
- 0.6 배속이 무게감 있게 느껴지는지, 반격 창이 과하게 길어지지 않았는지
- 락온 피치 범위 −20~8이 보스 전신을 담는지

---

## 4차 적용 (2026-09-11) — 락온 피치 원복 · 회피 판정 완화

### 락온 피치 자동 — **원복** (사용자 판단: 이전이 더 낫다)
`UpdateLockOnRotation`의 Pitch 입력을 다시 **현재 컨트롤 피치(마우스)** 로 연결했다.
Clamp 노드와 `LockOnPitchMin` / `LockOnPitchMax` 변수는 삭제했다.
락온 시 거리·높이 보정(`UpdateCameraFraming`, 520 / +90)은 유지한다.

### 회피 무적 시간 0.48 → 0.58초
`BP_Player_Combat.IFrameDuration`. 약 17프레임(30fps 기준).
- 이력: DS3 미들롤 0.433 → Codex 0.48 → **0.58**
- 이유: 보스 판정이 팔뚝 전체(반경 110)로 넓어졌고, 배속 0.6으로 판정 창도
  0.15 → 0.188초로 길어졌다. 판정은 후해지고 회피는 그대로면 체감상 회피가 박해진다.
- 쿨다운 0.25, 스태미나 13은 그대로
- 너무 후하면(구르기만 반복해도 다 피해짐) 0.5 정도로 되돌릴 것

---

## 5차 적용 (2026-09-11) — 늦은 회피 유예 · 무적 단축 · 잔상 1개

### 문제
무적을 0.58초로 늘리자 회피가 길게 느껴졌다. 그런데 실제 불만은 무적 길이가 아니라
**"모션을 보고 누르면 버튼보다 판정이 먼저 들어온다"** 는 반응 지연이었다.

### 해법 — 피격 유예 (Late Dodge Grace)
맞는 순간 바로 피해를 넣지 않고 **0.15초 보류**한다. 그 사이에 회피가 시작되면
피격을 취소하고 **퍼펙트 회피로 처리**한다. 무적 시간을 늘리지 않고 반응 여유만 준다.

```
AnyDamage
 ├ bInvincible → OnPerfectDodge                      (기존: 무적 중 접촉)
 └ else → PendingDamage = Damage, bHitPending = true
          SetTimer("ApplyPendingDamage", LateDodgeGrace)

ApplyPendingDamage (커스텀 이벤트)
 └ bHitPending? → false → 기존 체력 감소 · 사망 체인 (피해값은 PendingDamage)

TryEnterDodge (무적 켜고 OnIFrameEnd 타이머 예약 직후)
 └ bHitPending? → ClearTimer("ApplyPendingDamage") → false → OnPerfectDodge
```

| 변수 | 값 | 카테고리 |
|---|---|---|
| `LateDodgeGrace` | 0.15 | CombatTuning |
| `PendingDamage` | 런타임 | CombatState |
| `bHitPending` | 런타임 | CombatState |
| `IFrameDuration` | 0.58 → **0.40** | CombatTuning |

- 유예 중 회피는 쿨다운·스태미나·공중 검사를 **그대로 통과해야** 한다 (기존 게이트 유지)
- 부작용: 피격 시 체력바가 0.15초 늦게 준다. 피격 리액션이 생기면 그 시작도 이 타이머 뒤로
- 가드 브레이크(`ReceiveBossGuardBreak`)는 보스 쪽에서 피해 전에 즉시 처리되므로 유예 대상이 아니다

### 잔상 3개 → 1개
EventGraph의 `SetTimer("SpawnGhost2")`, `SetTimer("SpawnGhost3")` 노드를 삭제했다.
퍼펙트 회피 시 회피 시작 위치에 잔상 하나만 남는다 (색·지속 0.45초·투명도 그대로).
`SpawnGhost2` / `SpawnGhost3` 이벤트 노드는 호출자가 없는 채로 남아 있다 — 정리 대상.

---

## 6차 적용 (2026-09-11) — 회피(Shift) 감속 · 거리 단축

### 원인 — 초반 가속 구간이 회피 전체를 덮고 있었다
회피 몽타주는 `DodgeBurstRate`로 시작해 `DodgeBurstDuration` 뒤 `OnDodgeBurstEnd`에서
`DodgePlayRate`로 바뀐다. 기존 값이 **2배속을 0.9초** 유지해서, 회피 모션 대부분이
2배속으로 재생되고 있었다. `DodgePlayRate`를 바꿔도 체감이 거의 없던 이유다.

| 변수 | 이전 | 변경 |
|---|---|---|
| `DodgeBurstRate` | 2.0 | **1.4** (시작 순간만 살짝 튀게) |
| `DodgeBurstDuration` | 0.9 | **0.1** (원 설계 0.08초 수준) |
| `DodgePlayRate` | 1.2 | **0.95** (나머지 구간) |
| `DodgeDistance` | 280 | **220** (락온 회피 이동량) |

락온 회피 이동 시간은 `Max(BurstDuration + (길이 − ...)/PlayRate, 0.05) × DodgeMoveWindow`로
배속을 따라가므로, 느려진 모션과 이동이 같이 늘어난다.

### 한계 — 자유 시점 구르기 거리
자유 시점 Roll은 **루트모션**이라 이동 거리가 애니메이션에 들어 있다.
배속은 같이 느려지지만 거리는 그대로다. 줄이려면 루트모션 스케일
(`AnimRootMotionTranslationScale`)을 조절해야 하는데, UE 5.8에는 Blueprint 설정 노드가
없고 CDO 프로퍼티도 MCP로 읽기/쓰기가 안 된다 (`PLAN.md` 기록). C++ 한 줄 또는
구르기 애니메이션 교체가 필요하다.

---

## 7차 적용 (2026-09-11) — 이동 속도 · 락온 회피 후딜

### 이동 속도
| | 이전 | 변경 |
|---|---|---|
| 기본 걷기 (`BaseWalkSpeed`, CMC `MaxWalkSpeed`) | 600 | **450** |
| 달리기 (`SetSprinting` SelectFloat A) | 900 | **650** |
| 달리기 해제 (`SetSprinting` SelectFloat B) | 600 | **450** |
| 가드 중 (`BlockWalkSpeed`) | 220 | 220 (유지) |

`SetSprinting`의 900/600은 변수가 아니라 **리터럴**이다. `BaseWalkSpeed`와 따로 놀 수 있으니
나중에 `SprintWalkSpeed` 변수로 빼는 것을 권장.
락온 8방향 블렌드스페이스 재생 속도가 600 기준이면 발 미끄러짐이 생길 수 있다 — 플레이 확인.

### 락온 회피 후딜 (TryEnterDodge / OnDodgeRecoveryTimer)
기존: 회피 몽타주 **전체 길이**가 끝나야 Locomotion으로 복귀. 6차에서 배속을 낮춰 후딜이 더 길어졌다.

- 복귀 타이머 시간 = `기존 계산값 × DodgeRecoveryRatio` (Lerp(0, X, Ratio)로 곱셈)
- `DodgeRecoveryRatio` = **0.7** (CombatTuning) — 모션의 70% 지점에서 조작 복귀
- 복귀 시 `Montage_Stop(ActiveDodgeMontage, 0.2)` — 남은 회피 모션을 0.2초 블렌드아웃.
  안 하면 조작은 풀렸는데 회피 모션이 계속 재생돼 미끄러진다
- 쿨다운(0.25)은 복귀 시점부터 카운트 (기존 유지)
- 락온 이동 시간 계산(× DodgeMoveWindow 0.6)은 이 비율과 무관 — 이동은 이미 60% 지점에서 끝난다

---

## 8차 (2026-09-11) — 락온 회피 밀착 끼임 · 테스트 몽타주 · 판정 가시화

### 락온 회피가 보스에 붙으면 막히던 문제 — 슬라이드 추가
락온 회피 이동은 Tick의 `SetActorLocation(목표, sweep=true)`다. 보스 캡슐에 막히면 그 자리에서 멈췄다
(W+D+Shift로 보스 우측 앞으로 파고들 때 재현). 막혔을 때 **남은 이동을 벽면을 따라 미끄러지게** 했다.

```
SetActorLocation(목표, sweep)
 └ SweepHitResult.bBlockingHit?
     → 법선 N을 수평으로 평탄화 (Z=0, Normalize)   ← 보스 캡슐 하단 곡면에서 바닥으로 밀리지 않게
     → SetActorLocation(ProjectPointOntoPlane(목표, 충돌 위치, N), sweep)
```
`ProjectPointOntoPlane`이 "충돌면을 지나는 평면 위로 목표를 투영"하므로 뺄셈·덧셈 노드 없이 슬라이드가 된다.

### MM_Attack_01/02 테스트 — 보류 (에디터 작업 필요)
`AM_Attack1_1/1_2`를 복제해 세그먼트만 `MM_Attack_01/02`로 바꿨으나 **몽타주 길이(SequenceLength)가
원본 값(0.44 / 0.74초)으로 남았다.** MM 애니메이션은 1.0초라 절반에서 잘린다. 길이는 에디터 편집 이벤트에서만
재계산되고 MCP로는 쓸 수 없다.
- `AttackMontages`는 **원본(AM_Attack1_1~4)으로 되돌려 둠**
- 남은 사본 `AM_Test_MM_Attack_01/02`는 쓰지 말 것
- 필요 작업: 콘텐츠 브라우저에서 `MM_Attack_01`/`02` 우클릭 → 애니메이션 몽타주 생성 → 배열 0·1번에 지정
  (슬롯은 `DefaultSlot`. 원본 1·2타 되돌릴 경로는 `/Game/BossArena/Animations/Attack/AM_Attack1_1`, `_2`)

### 판정 가시화
영상 확인 결과 주황 디버그 구가 **주먹 위치에만** 그려지고 있었다. 3차에서 실제 판정은 팔뚝 전체로
바꿨으므로 화면과 실제 판정이 달랐다 ("판정이 애매하다"의 한 원인).
- 주먹 구(`DrawDebugSphere`) 삭제
- 두 판정 트레이스(`EventGraph` 메인, `TraceOtherHand`)의 `DrawDebugType = ForOneFrame` — 판정 창이
  열려 있는 동안 **실제로 검사하는 팔뚝 캡슐**을 그대로 그린다 (빨강=빗나감, 초록=적중)
- 주의: 이 표시는 `bShowHitDebug`와 무관하게 판정 창 동안 항상 그려진다. 영상 촬영 전 `None`으로

### "맞는다는 느낌이 없다" — 남은 원인 (미적용, 사용자 결정)
1. **히트스톱 없음** — 적중 순간 0.05~0.08초 정지가 없다
2. **보스 피격 반응 없음** — 경직은 설계상 제외지만, 번쩍임·작은 흔들림·소리도 없다
3. **플레이어 공격은 여전히 몸 앞 고정 구(`ApplyRadialDamage`)** — 주먹이 닿는 위치와 무관 (2번 남은 작업 6)
4. 피격 시 카메라 흔들림 없음

### MM_Attack 테스트 적용 (사용자가 몽타주 생성 후)
`AttackMontages`:
```
[0] /Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01_Montage   (길이 1.0, DefaultSlot)
[1] /Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_02_Montage   (길이 1.0, DefaultSlot)
[2] /Game/BossArena/Animations/Attack/AM_Attack1_3   (원본 유지)
[3] /Game/BossArena/Animations/Attack/AM_Attack1_4   (원본 유지)
```
**되돌리기**: [0] `AM_Attack1_1`, [1] `AM_Attack1_2`.
타이밍은 비율 기반(`AttackHitRatio` 0.35, `ComboWindowRatio` 0.55, `AttackPlayRate` 1.4)이라 길이가
0.44→1.0으로 늘어난 만큼 1·2타가 느리고 판정도 늦게 나온다. 테스트 후 판단.

---

## 9차 (2026-09-11) — 1·2타 롤백 · 보스 1.8 · 히트스톱 · 흔들림 · 경직 모션

### 롤백
`AttackMontages` [0]`AM_Attack1_1`, [1]`AM_Attack1_2` 로 복귀. `MM_Attack_01/02_Montage`는 남아 있으나 미사용.

### 보스 스케일 1.5 → 1.8
배치 Z = −8 + 110×1.8 = **190**. 캡슐 반경 105 유지(월드 약 189cm, 발 커버).
커진 만큼 **공격 거리도 1.2배**: 멈춤 거리 210→**250**, 근접 6종 최대 280→**330**, 접근 시작 230→**275**.
(스케일만 올리면 3차 때처럼 밀림 캡슐 때문에 주먹이 안 닿는다.)

### 히트스톱 (BP_Player_Combat — `StartHitStop` / `EndHitStop`)
```
StartHitStop: SetGlobalTimeDilation(HitStopDilation)
              ClientStartCameraShake(BP_CamShake_Hit)
              SetTimer("EndHitStop", HitStopDuration × HitStopDilation)   ← 타이머도 느려진 시간으로 흐르므로 곱해 준다
EndHitStop:   SetGlobalTimeDilation(1.0)
```
| 변수 (HitFeel) | 값 |
|---|---|
| `HitStopDilation` | 0.05 |
| `HitStopDuration` | 0.07초 (실시간) |

호출 지점:
- **플레이어가 보스를 맞힘** — `DoAttackHitCheck`의 피격 이펙트 스폰 직후
- **플레이어가 맞음** — `ApplyPendingDamage`에서 피격이 확정된 뒤 (늦은 회피 유예 0.15초를 넘긴 경우만).
  유예 중 회피로 취소된 공격에는 히트스톱이 걸리지 않는다

### 카메라 흔들림 `BP_CamShake_Hit` (LegacyCameraShake, 아주 약하게)
지속 0.18초, 블렌드 인 0.02 / 아웃 0.1, 회전 진동 Pitch 0.45°@28Hz · Yaw 0.3°@22Hz, 위치·FOV 진동 없음.
히트스톱 중에는 멈춰 있다가 풀리는 순간 흔들린다.

### 경직 모션
| 대상 | 애니메이션 | 조건 |
|---|---|---|
| 플레이어 피격 | `/Game/FightAnimations_FBX/A_HitBody_F_IP` (제자리, 0.5초) | 피격 확정 시, `DefaultSlot`, 블렌드 0.05/0.15 |
| 보스 피격 | `ParagonCrunch/.../HitReact_Front` | **`Boss.Combat.Ready`일 때만**, `UpperBody` 슬롯, 1.3배속 |

보스는 공격 중(Windup/Active/Recovery)에는 반응하지 않는다 — "보스는 경직으로 공격이 끊기지 않는다"는
기존 설계 유지. 대기·접근 중에 맞을 때만 상체가 움찔한다.

남은 점: 플레이어 경직은 모션만 재생하고 `ActionState`를 Hit로 바꾸지 않는다 → 경직 중에도 공격·회피 입력이
들어간다. 방향별(뒤·좌·우) 모션(`A_HitBody_L/R_IP`, `A_Hit_Back_IP`)도 아직 미사용.
