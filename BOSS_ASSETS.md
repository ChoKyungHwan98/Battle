# 보스 에셋 목록 — ParagonCrunch

> 2026-09-10: 실제 사용 몽타주 7종과 행동 카드 8종을 연결했다.
> 원본 Combo_01~04는 각각 단타이며, 새 3타는 Combo_01→Combo_02→Ability_Uppercut이다.
> 마지막은 Combo_03이 아니다. 최신 사용 범위는 [현재 수치](BOSS_UTILITY_TUNING.md)를 따른다.
> 아래 루트모션·미구현 표기는 초안 당시 기록이다.

보스 AI(HFSM + Utility AI + GOAP) 설계를 위한 사용 가능 에셋 정리.
작성 2026-09-07.

---

## 0. 먼저 알아야 할 것

**크런치는 자체 스켈레톤을 쓴다** — `Crunch_Skeleton`.
플레이어의 `SK_Mannequin`과 **호환되지 않는다.**

| | 플레이어 | 보스 |
|---|---|---|
| 스켈레톤 | `/Game/Characters/Mannequins/Meshes/SK_Mannequin` | `/Game/ParagonCrunch/.../Crunch_Skeleton` |
| 메시 | `SKM_Quinn_Simple` | `Crunch` |

→ **보스 전용 AnimBP를 새로 만들어야 한다.** 플레이어 `ABP_Player_Combat`은
재사용 불가. 대신 크런치 애니메이션은 리타게팅 없이 그대로 쓸 수 있다.

**루트모션은 전부 꺼져 있다** (`bEnableRootMotion = false`).
플레이어 구르기 때와 같은 함정이다. 전진하는 공격(대시 크로스 등)을
쓰려면 켜야 한다 — 애니메이션 자체에 루트 이동이 들어있는지는 켜보고
확인 필요.

**기본 경로**: `/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/`

---

## 1. 공격 — HFSM `Combat` 상태 / Utility AI 후보 행동

Utility AI가 점수를 매길 "행동 카드"들. 길이는 초 단위.

### 근접 단타 모션 (제자리)

| 애니메이션 | 길이 | 비고 |
|---|---|---|
| `Ability_Combo_01` | 0.933 | 왼손 휘두르기, 단타 |
| `Ability_Combo_02` | 0.933 | 오른손 휘두르기, 단타 |
| `Ability_Combo_03` | 0.933 | 왼손 어퍼컷, 단타 |
| `Ability_Combo_04` | 0.933 | 단타, 사용 미정 |

2026-09-09 사용자 정정: 이름이 Combo여도 각 애니메이션은 공격 1회다.
번호를 연속 공격 순서로 취급하지 않는다.

**속도 변형이 전부 준비되어 있다** — 같은 동작의 Fast / Slow 버전:

| 변형 | 길이 | 용도 |
|---|---|---|
| `Ability_Combo_01_Fast` | 0.533 | 빠른 변형, 현재 사용하지 않음 |
| `Ability_Combo_01` | 0.933 | 기본 |
| `Ability_Combo_01_Slow` | 1.233 | 임팩트는 기본과 같고 후딜이 긴 변형 |

> 플레이어 회피에 맞춰 같은 공격 속도를 몰래 높이지 않는다.
> Slow를 엇박이나 가드 브레이크로 취급하지 않는다. 가드 브레이크는
> 별도 예고를 가진 GutPunch의 역할이다. `_Additive`는 기본 포즈와 합성하는
> 변형이며 별도 공격 기술로 세지 않는다.

### 단발 기술

| 애니메이션 | 길이 | 성격 |
|---|---|---|
| `Ability_Hook` | 1.667 | 훅. 중간 예비동작 |
| `Ability_Hook_Empowered` | 2.0 | 강화 훅. 긴 예비동작 = 회피 타이밍 명확 |
| `Ability_Uppercut` | 2.0 | 보스가 점프하며 어퍼컷. 새 01→02→Uppercut 콤보의 마지막 타 |
| `Ability_GutPunch` | 1.2 | 복부 강타. 빠름 |
| `Ability_Attack_Air` | 0.933 | 공중 공격 |

### 이동기 (GOAP 다단 계획용)

| 애니메이션 | 길이 | 성격 |
|---|---|---|
| `Ability_DashingCross_Start` | 0.333 | 대시 시작 |
| `Ability_DashingCross` | 1.133 | 돌진 + 크로스 |
| `Ability_Dashing_Recovery` | 1.833 | 빗나갔을 때 후딜 |
| `Ability_Dashing_Recovery_Hit` | 2.367 | 맞췄을 때 후딜 |

> **GOAP가 필요한 이유가 여기 있다.** 대시 크로스는
> `Start → Dash → Recovery`가 한 묶음이고, "거리가 멀다 → 붙어야 한다 →
> 대시로 붙는다 → 콤보로 잇는다"처럼 **여러 스텝의 계획**이 필요하다.
> 단발 공격과 달리 Utility 점수 하나로 표현하기 어렵다.

### 후딜 (공격 후 빈틈 = 플레이어의 반격 창)

| 애니메이션 | 길이 |
|---|---|
| `Ability_Combo_01_Recovery` | 1.467 |
| `Ability_Combo_02_Recovery` | 1.8 |

---

## 2. 피격 · 경직 — HFSM `Stagger` / `Hit` 상태

| 애니메이션 | 길이 | 용도 |
|---|---|---|
| `HitReact_Front` | 0.967 | 정면 피격 |
| `HitReact_Back` | 1.2 | 후면 피격 |
| `HitReact_Left` | 0.9 | 좌측 피격 |
| `HitReact_Right` | 1.2 | 우측 피격 |
| `Knockback_Front` | 2.033 | 넉백 (강공격) |
| `Knockback_Back` | 2.033 | 넉백 |
| `Stunned_Start` | 1.167 | 체간 붕괴 진입 |
| `Stunned_Loop` | 2.167 | 체간 붕괴 유지 (= 처형 기회) |
| `Death_A` | 1.667 | 사망 |

> **4방향 피격이 다 있다** → 맞은 방향을 계산해서 골라 재생하면
> 타격감이 크게 올라간다.
> `Stunned_Start` + `Stunned_Loop`는 **세키로의 체간 시스템**을 그대로
> 만들 수 있는 구성이다. HFSM에서 이 상태는 **다른 모든 상태를
> 무조건 끊는 최우선 전이**로 두면 된다.

---

## 3. 이동 · 대기 — HFSM `Idle` / `Approach` / `Reposition`

### 대기

| 애니메이션 | 길이 | 비고 |
|---|---|---|
| `Idle_Combat` | 9.167 | 전투 대기 (길다, 루프용) |
| `Idle_Combat_Var1` | 5.9 | 변형 |
| `Idle_Pose` | — | 단일 포즈 |
| `Idle_AmbientNoise` | — | 비전투 |
| `Step_InPlace` | 5.0 | 제자리 스텝 (거리 조절용) |

### 이동 (8방향 + 시작/정지/피벗 완비)

```
Jog_Fwd / Bwd / Left / Right                    기본 4방향
Jog_*_Start / _Stop / _Pivot                    가감속·방향전환
Jog_Fwd_Circle_Left / Right                     선회 (보스가 플레이어 주위를 돌 때)
Jog_Bwd_Circle_Left / Right
Jog_FwdToBwd_Spin_cw / ccw                      급반전
Jog_*_UpHill / _DownHill                        경사
Sprint_Fwd                                      돌진 접근
Travelmode_*                                    비전투 이동
```

> **`Circle_Left` / `Circle_Right`가 있다는 게 중요하다.** 보스가
> 플레이어 주위를 빙 도는 "간보기" 행동을 만들 수 있고, 이건
> Utility AI에서 **"지금은 공격 점수가 다 낮다 → 선회"** 라는
> 결과를 눈에 보이게 만든다.

### 회전

| 애니메이션 | 길이 |
|---|---|
| `Idle_90_Turn_Left` / `Right` | 1.467 |
| `Idle_180_Turn_Left` / `Right` | 2.5 |

### 점프

현재 점프 내려찍기 몽타주: `Jump_Start`(0.359초) → `Jump_Apex`(1.481초) → `Jump_PreLand`(0.556초) → `Jump_Land`(1.7초) → `Stunned_Start` → `Stunned_Loop`. 착지는 시작 약 2.396초다. 원본 `Ability_Attack_Air`는 이 점프 연속 동작과 양 끝 자세가 맞지 않아 몽타주에서 제외했다. 원본 시퀀스 자체는 유지한다.

### 블렌드스페이스 (기성품 9개)

`Blendspaces/` — `JogFwdSlopeLean`, `JogBwdSlopeLean`, `JogLeftSlopeLean`,
`JogRightSlopeLean`, `Sprint*SlopeLean` 4종, `StepInPlace`

### 에임 오프셋

`AimOffsets/` — `Crunch_AO_Blendspace` + 상하좌우 9방향 포즈 15개.
**보스가 항상 플레이어를 바라보게 하는 데 쓴다.**

---

## 4. 이펙트 (Cascade ParticleSystem)

`/Game/ParagonCrunch/FX/Particles/Abilities/`

| 이펙트 | 용도 |
|---|---|
| `P_Crunch_Primary_Impact` | 기본 히트 (**플레이어가 이미 사용 중**) |
| `P_Crunch_Cross_Enemy_Impact` | 크로스 피격 |
| `P_Crunch_Hook_Enemy_Impact` | 훅 피격 |
| `P_Crunch_Uppercut_Impact` | 어퍼컷 피격 |
| `P_Crunch_GutPunch_Impact` | 복부 강타 피격 |
| `P_Crunch_Hook_3D_Trail` | 주먹 궤적 |
| `P_Crunch_UpperCut_3D_Trail` | 주먹 궤적 |
| `P_Crunch_Fist_Fire_Cross/Hook/UpperCut` | 주먹 화염 (강화 상태 표현) |
| `P_Crunch_Cross_Jets` / `Hook_Jets` / `Gutpunch_Jets` / `UpperCut_Jets` | 제트 분사 |
| `P_Crunch_JetFX_Stage_1` / `_2` | 단계별 제트 (**페이즈 2 시각 신호로 적합**) |
| `P_Crunch_Heat_Distortion` | 열 왜곡 |
| `P_Crunch_Cross_AmpedFLames` / `Cross_Fires` | 화염 |
| `P_Crunch_Cross_DirtTrail` | 지면 먼지 |
| `P_LevelStart_Fist_Slam` / `_LR` | 지면 강타 (등장 연출) |

> `Fist_Fire_*`와 `JetFX_Stage_1/2`가 있다는 건 **페이즈 전환을
> 시각적으로 표현할 수단이 이미 있다는 뜻이다.**
> 페이즈 1은 이펙트 없음 → 페이즈 2에서 주먹에 불 + 제트 점화.

---

## 5. 사운드

`Characters/Heroes/Crunch/Sounds/SoundCues/` — 146개 큐

전투 관련: `Crunch_Effort_Attack`, `Crunch_Effort_Ability_Primary`,
`Crunch_Effort_Ability_E_Uppercut`, `Crunch_Effort_Ability_RMB_Dash`,
`Crunch_Effort_Ability_RMB_Punch`, `Crunch_Effort_Ability_Ultimate`,
`Crunch_Effort_Block`, `Crunch_Effort_BreathingLowHealth`,
`Crunch_Death`, `Crunch_Effort_Death`, `Crunch_Effort_Frustration`

> `BreathingLowHealth`는 **페이즈 2 진입의 청각 신호**로 그대로 쓸 수 있다.

---

## 6. 메시 · 머티리얼

| 애셋 | 경로 |
|---|---|
| 스켈레탈 메시 | `Characters/Heroes/Crunch/Meshes/Crunch` |
| 스켈레톤 | `Characters/Heroes/Crunch/Meshes/Crunch_Skeleton` |
| 스킨 | `Skins/Teir_1/BlackGold`, `Valentine`, `Tier_3/BlackSite`, `CrashSite` |

---

## 7. AI 3계층에 대한 에셋 매핑 제안

에셋만 놓고 봤을 때 세 기법을 이렇게 나누면 각각이 **화면에서
구분되어 보인다** (홀로그램 패널에 띄웠을 때 의미가 명확).

### HFSM — 하드 제약 / 페이즈

```
Root
├─ Inactive        (Idle_AmbientNoise)
├─ Combat
│   ├─ Phase1      기본 속도 콤보
│   └─ Phase2      Combo_*_Fast + 주먹 화염 + JetFX_Stage_2
├─ Stagger         Stunned_Start → Stunned_Loop     ← 최우선, 무조건 끊음
├─ HitReact        HitReact_4방향 / Knockback
└─ Dead            Death_A
```
"무엇을 **할 수 없는가**"를 담당. 경직 중엔 어떤 계획도 무효.

### Utility AI — Combat 안에서 "지금 무엇을?"

점수 입력: 거리 / 각도 / 내 체력 / 플레이어 스태미나 / 각 기술 쿨다운 /
플레이어의 최근 행동(구르기 빈도, 가드 빈도)

| 행동 | 후보 애니메이션 | 높게 평가되는 상황 |
|---|---|---|
| 근접 콤보 | `Ability_Combo_01~04` | 가깝고 정면 |
| 빠른 콤보 | `Ability_Combo_*_Fast` | 플레이어가 구르기로 계속 회피 |
| 느린 강공격 | `Ability_Combo_*_Slow`, `Hook_Empowered` | 플레이어가 가드만 함 |
| 점프 어퍼컷 | `Ability_Uppercut` | 회피를 자주 한 상대에게 선택하는 3타 콤보의 마지막 모션 |
| 선회 | `Jog_*_Circle_*` | 모든 공격 점수가 낮음 (간보기) |
| 후퇴 | `Jog_Bwd` | 내 체력 낮음 + 플레이어 근접 |

### GOAP — 다단 계획

| 목표 | 계획 예시 |
|---|---|
| `CloseDistance` | `Sprint_Fwd` → `DashingCross_Start` → `DashingCross` → `Combo_01` |
| `PunishWhiff` | 플레이어 공격 회피(`Jog_Bwd`) → `Combo_01_Fast` |
| `CreateSpace` | `Jog_FwdToBwd_Spin` → `Jog_Bwd` → 회복 |

---

## 8. 홀로그램 디버그 패널 (우측 상단) — 표시 항목 제안

포트폴리오의 핵심. **"왜 이 행동을 골랐는가"가 화면에 그대로 보여야 한다.**

```
┌─ BOSS AI ────────────────────────────┐
│ HFSM   Combat > Phase2               │  ← 현재 상태 경로
│                                       │
│ UTILITY                               │  ← 실시간 막대그래프
│   Combo_Fast     ████████░░  0.82     │
│   Uppercut       █████░░░░░  0.51     │
│   Circle_Left    ███░░░░░░░  0.30     │
│   Retreat        █░░░░░░░░░  0.12     │
│                                       │
│ GOAP   Goal: CloseDistance            │  ← 현재 계획 큐
│   [1] Sprint      ✔                   │
│   [2] DashCross   ▶                   │
│   [3] Combo_01    ·                   │
│                                       │
│ 거리 4.2m │ 각도 12° │ HP 61%          │  ← 점수 입력값
└───────────────────────────────────────┘
```

입력값까지 같이 띄우는 게 중요하다. 점수만 보이면 "왜 저 점수가
나왔는지" 알 수 없다.

---

## 9. 확인이 필요한 것 (에셋 관련)

1. **루트모션** — 전부 꺼져 있다. `Ability_DashingCross`에 실제 루트
   이동이 들어있는지 켜보고 확인 필요. 없으면 코드로 밀어야 한다.
2. **몽타주** — `Ability_Combo_01_Montage` 등 일부만 몽타주가 있다.
   나머지는 시퀀스라 몽타주를 새로 만들거나
   `PlaySlotAnimationAsDynamicMontage`로 재생해야 한다.
3. **AnimNotify** — 파라곤 원본 애니메이션에 히트 노티파이가 붙어 있는지
   미확인. 없으면 플레이어처럼 타이머 방식으로 간다.
4. **`Crunch_Extents` / `Crunch_ShadowCyl`** — 콜리전/그림자용 보조 메시.
   히트박스 크기 잡을 때 참고 가능.


---

## ⚠ ParagonCrunch를 다시 받으면 해야 할 것 (2026-09-08)

`ParagonCrunch`는 2GB라 `.gitignore`에 넣었다. Fab에서 다시 받으면
아래 수정이 사라지므로 **매번 다시 해야 한다.**

### 1. `CrunchPlayerCharacter` 컴파일 에러

```
CrunchPlayerCharacter'에서 "ResetOrientationAndPosition" 함수를 찾을 수 없습니다
```

파라곤에 딸려온 **언리얼 3인칭 템플릿 캐릭터**(우리는 안 씀)에 VR 노드가
들어 있는데, UE 5.8에서 그 함수가 없어졌다. PIE를 켤 때마다 경고창이 뜬다.

**해결**: `CrunchPlayerCharacter`의 EventGraph에서 두 노드 삭제
- `Reset Orientation and Position` (CallFunction)
- `InputAction ResetVR` (이벤트)

남는 경고(`InputAxis MoveForward`, `Turn`, `Jump` 등)는 구식 입력 시스템을
참조해서 나는 것으로, **에러가 아니라 무시해도 된다.**

### 2. 보스가 참조하는 것

우리 `ABP_Boss_Crunch`는 파라곤 원본 `Crunch_AnimBlueprint`의 복제본이고,
`CastToCrunchPlayerCharacter` 노드를 그대로 갖고 있다. 그래서
`CrunchPlayerCharacter`를 **지우면 안 된다** (지우려면 그 캐스트들을 먼저
제거해야 함). 캐스트는 실패해도 조용히 넘어가므로 동작에는 문제없다.

우리 보스가 실제로 쓰는 것:
```
/Game/ParagonCrunch/Characters/Heroes/Crunch/Meshes/Crunch          메시
/Game/ParagonCrunch/Characters/Heroes/Crunch/Meshes/Crunch_Skeleton 스켈레톤
/Game/ParagonCrunch/Characters/Heroes/Crunch/Crunch_AnimBlueprint   AnimBP 원본
/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/*           애니메이션
/Game/ParagonCrunch/FX/Particles/Abilities/*                        이펙트
```
