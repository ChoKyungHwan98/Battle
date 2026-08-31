# 세키로식 HFSM 플레이어 전투 구조 계획

## 프로젝트 정보

- 엔진: **Unreal Engine 5.8.2**

## 알아둘 것 (함정 노트)

- **InputMappingContext의 키 매핑은 `defaultKeyMappings.mappings`에 넣어야
  한다 (UE 5.8.2 기준).** 예전 버전 문서/튜토리얼에 나오는 최상위
  `Mappings` 배열에 넣으면, 조회는 되는데(내가 쓴 값을 그대로 되읽으니까)
  실제 게임 입력 시스템은 그 자리를 안 읽어서 아무 반응이 없다. 에디터에서
  "디폴트 키 매핑: 0 맵 0엘리먼트"라고 뜨면 이 함정에 걸린 것 — 값이
  legacy `Mappings` 필드에만 들어가고 실제 UI/런타임이 보는
  `DefaultKeyMappings.Mappings`엔 안 들어간 상태다.
- Enum 애셋(`UserDefinedEnum`)은 MCP 도구로 생성이 안 된다 — 에디터에서
  직접 만들어야 한다 (블루프린트 → 열거형).

## 진행 상황 (2026-09-01 기준)

기반 공사 + 락온 토글까지 끝났다.

```
✔ 완료   BP_Player_Combat / BP_PlayerController_Combat / BP_BossArenaGameMode
✔ 완료   Lvl_Arena_01을 시작 맵으로 지정, PIE로 정상 스폰 확인
✔ 완료   IA_Dodge(Shift) / IA_LockOn(마우스 휠) / IMC_Player_Combat, 자동 등록
✔ 완료   E_PlayerMovementMode / E_ActionState Enum, BP_Player_Combat 변수로 추가
✔ 완료   ToggleLockOn 함수 — Free⇄LockOn 전환, BP_TrainingDummy를
         LockOnTarget으로 저장, PIE에서 실제 작동 확인함 (구현 순서 6번)
← 다음   락온 중 타겟 방향으로 캐릭터 회전 + 8방향 이동/애니메이션 연결
         (구현 순서 7번)
← 이후   더킹 → ABP_Player_Combat → 입력 버퍼/취소 구간
```

세부 히스토리(마이그레이션, 레거시 정리 등)는 git 커밋 로그 참고 — 여기엔
지금 상태와 다음 할 일만 남긴다.

## 핵심 목표

이 작업은 단순히 이동과 더킹을 연결하는 것이 아니라, 세키로·소울라이크의
전투 문법을 수용할 수 있는 HFSM 토대를 만드는 것이 목표다.

완성된 구조는 다음을 지원해야 한다.

- 자유 상태와 락온 상태 분리
- 락온 시 전투 자세 Idle
- 락온 기준 8방향 이동
- 이동 방향 기반 4방향 더킹
- 공격 중 방어·더킹 취소
- 애니메이션 후반부 취소 가능 구간
- 약간 일찍 입력해도 실행되는 입력 버퍼
- 공격·방어·더킹 우선순위
- 애니메이션과 판정의 분리

핵심 성공 기준은 "작동한다"뿐 아니라 다음 네 가지다.

- 상태가 명확하게 분리되어 있을 것
- 블루프린트가 스파게티처럼 연결되지 않을 것
- 새 기능을 추가해도 기존 기능을 뜯어고치지 않을 것
- 기획 의도와 노드 역할을 화면으로 설명할 수 있을 것

## HFSM 구조

단순한 하나의 거대한 상태 머신이 아니라, 상위 상태 안에 하위 상태를 넣는다.

**중요 결정**: `Dodge`/`Guard`/`Attack`은 락온 여부와 무관하게 항상 가능하다
(락온 안 해도 아무 방향으로나 공격 가능해야 함 — 확정 사항). 그래서
`CombatAction`은 `Free`와 `LockOn` 양쪽에 각각 존재하고, 실행되는 기능은
동일하되 재생되는 애니메이션만 다르다 (`Free`는 자유 모션, `LockOn`은 복싱
가드 기반 모션). `LockOn` 밑에만 두는 트리는 틀린 설계이니 참고하지 않는다.

```text
PlayerRoot
├─ Free
│  ├─ Idle
│  ├─ Move
│  └─ CombatAction
│     ├─ Dodge     (자유 모션)
│     ├─ Guard     (자유 모션)
│     └─ Attack    (자유 모션)
│
├─ LockOn
│  ├─ CombatIdle
│  ├─ CombatMove8Dir
│  └─ CombatAction
│     ├─ Dodge     (복싱 모션)
│     ├─ Guard     (복싱 모션)
│     └─ Attack    (복싱 모션)
│
└─ Global
   ├─ Hit
   └─ Dead
```

실제 구현은 이 그림을 두 층으로 나눠서 반영한다.

- **게임플레이 층 (`BP_Player_Combat`)**: `E_PlayerMovementMode`(Free/LockOn),
  `E_ActionState`(Locomotion/Dodge/Guard/Attack/Hit/Dead) 두 Enum 변수만
  있으면 이 트리 전체가 표현된다. `ActionState`는 `MovementMode`와 완전히
  독립이다 — 즉 게이팅 규칙("Guard/Attack은 락온 중에만") 없이 어디서든
  전이 가능하다.
- **애니메이션 층 (`ABP_Player_Combat`)**: 위 그림 그대로 중첩 State
  Machine으로 그린다. `Free` 갈래 State Machine 하나, `LockOn` 갈래 State
  Machine 하나. 같은 `ActionState`라도 소속된 갈래(`MovementMode`)에 따라
  다른 애니메이션 세트를 재생한다.

피격과 사망은 모든 상태에서 우선 처리되는 전역 상태로 둔다 (표는 위 트리의
`Global` 참고).

## 상태와 규칙의 분리

상태는 "현재 무엇을 하고 있는가"를 나타낸다.

```text
현재 상태 = Attack
```

규칙은 "현재 상태에서 무엇을 허용하는가"를 나타낸다.

```text
Attack 중
├─ 초반: 취소 불가
├─ 후반: Guard 취소 가능
├─ 후반: Dodge 취소 가능
└─ 입력 버퍼 허용
```

따라서 `Attack → Guard`, `Attack → Dodge`는 별도의 거대한 상태를 만드는 것이
아니라 공격 상태의 전이 규칙으로 관리한다.

## 세키로식 취소 구조

공격 애니메이션 타임라인에 구간을 둔다.

```text
공격 애니메이션
1F──────10F──────20F──────30F
   준비      타격       회수

1~14F   취소 불가
15~30F  Guard 취소 가능
15~30F  Dodge 취소 가능
```

이 구간은 나중에 애니메이션의 `Anim Notify State`로 표시한다.

- `ANS_GuardCancelWindow`
- `ANS_DodgeCancelWindow`
- `ANS_HitWindow`

블루프린트는 Notify State가 열려 있는지만 확인하고, 프레임 숫자를 직접
계산하지 않는다.

## 입력 버퍼

입력 버퍼는 "지금 실행할 수 없는 입력을 잠시 예약하는 기능"이다.

```text
공격 중 13F
→ Guard 입력
→ Guard 예약

14F 이후 취소 구간 시작
→ 저장된 Guard 실행
```

초기값은 다음으로 고정한다.

- 버퍼 시간: 0.1초
- 저장 입력: 가장 최근 입력 하나
- 새 입력이 들어오면 이전 예약 덮어쓰기
- Dodge와 Guard가 동시에 들어오면 우선순위 테이블 사용

초기 우선순위:

```text
Hit/Dead > Dodge > Guard > Attack > Locomotion
```

### 구현 방식 (11단계에서 실제로 만들 때 이대로)

타임스탬프 계산 대신 **타이머로 자동 만료**시키는 방식을 쓴다 — 뺄셈 계산이
없어서 블루프린트로 짜기 쉽고 버그가 덜 난다.

`BP_Player_Combat`에 추가할 것:

```
변수
├─ bHasBufferedInput   (Boolean)
├─ BufferedAction      (E_ActionState)
└─ BufferTimerHandle   (Timer Handle)

함수
├─ BufferInput(DesiredAction)
│  1. BufferedAction = DesiredAction, bHasBufferedInput = true
│  2. 기존 BufferTimerHandle 있으면 Clear (새 입력이 이전 예약 덮어씀)
│  3. SetTimerByEvent(BufferTimerHandle, ClearBuffer, 0.1초, 반복 안 함)
│
├─ ClearBuffer()                          ← 타이머가 0.1초 뒤 자동 호출
│  bHasBufferedInput = false
│
└─ TryConsumeBufferedInput(AllowedAction) → bool
   1. bHasBufferedInput == false 면 false 리턴
   2. BufferedAction != AllowedAction 면 false 리턴
   3. 둘 다 통과하면: 타이머 Clear, bHasBufferedInput = false,
      실제 전이 함수(TryEnterDodge 등) 호출, true 리턴
```

**연결 지점**: `TryEnterDodge()`/`TryEnterGuard()` 같은 전이 함수가 "지금은
못 들어감"(취소 불가 구간)이라고 판단하면, 그냥 무시하지 않고
`BufferInput(Dodge)`를 호출한다. 반대로 `ANS_DodgeCancelWindow` 같은 Notify
State가 열리는 시점(`Play Montage`의 `On Notify Begin` 델리게이트로 감지)에
`TryConsumeBufferedInput(Dodge)`를 호출해서, 예약해둔 입력이 있으면 그 즉시
실행한다.

### 상황별 결과 (위 메커니즘이 자동으로 만들어내는 결과, 검증용)

```
공격 애니메이션
1F────────14F────────────30F
   취소 불가       취소 가능

경우 1) 5F에 Guard 입력
  → 예약(BufferInput) 되지만 0.1초 타이머가 14F 도달 전에 만료
  → 자동으로 취소됨. 공격 그대로 진행 (너무 일찍 누르면 씹힘 — 정상 동작)

경우 2) 13F에 Guard 입력 (취소 구간 열리기 직전)
  → 예약, 1프레임 뒤 14F에 취소 구간 열림 → 아직 0.1초 안 지남
  → TryConsumeBufferedInput 성공 → 즉시 Attack → Guard 전환
  → 세키로에서 "공격 끝무렵에 방어 누르면 들어가는" 그 현상

경우 3) 20F에 Guard 입력 (취소 구간 이미 열린 상태)
  → 버퍼 필요 없이 TryEnterGuard()에서 바로 즉시 전환

경우 4) Guard 예약 중에 Dodge가 새로 입력됨
  → BufferedAction이 Dodge로 덮어써짐, Guard는 버려짐
  → 완전히 동시(같은 프레임)면 우선순위표(Dodge > Guard)로 Dodge 승리
```

이 방식의 장점: `BP_Player_Combat`은 "지금이 몇 프레임째냐"를 전혀 몰라도
된다 — Notify State가 열렸다는 신호만 받으면 됨 (계획 상단의 "블루프린트는
프레임 숫자를 직접 계산하지 않는다" 원칙과 일치).

## 자산 구조

**폴더 규칙**: 플레이어 관련 새 에셋은 전부 `/Game/BossArena/Player/` 아래
역할별 하위 폴더에 넣는다. 특히 블루프린트는 예외 없이
`/Game/BossArena/Player/Blueprints/`에만 넣는다 — 다른 곳에 만들지 않는다.
(Enum → `Enums/`, 애니메이션 → `Animation/`, 입력 → `Input/`, 튜닝값 →
`Data/`, 디버그 위젯 → `Debug/`.) 이렇게 해두면 콘텐츠 브라우저에서
`/Game/BossArena/Player/` 한 곳만 열면 전부 보인다.

```text
/Game/BossArena/Player
├─ Blueprints
│  ├─ BP_Player_Combat            ✔ 완료
│  ├─ BP_PlayerController_Combat  ✔ 완료
│  └─ BP_BossArenaGameMode        ✔ 완료
│
├─ Enums
│  ├─ E_PlayerMovementMode               ✔ 생성됨 (항목 채우는 중)
│  └─ E_ActionState                ✔ 생성됨 (항목 채우는 중)
│
├─ Animation
│  ├─ ABP_Player_Combat            ← 아직
│  ├─ BlendSpaces
│  │  ├─ BS_Player_FreeMove        ← 아직
│  │  └─ BS_Player_LockOn8Dir      ← 아직
│  ├─ Montages
│  │  ├─ AM_Player_Dodge_F/_B/_L/_R  ← 아직, 애니메이션 소스 필요
│  └─ Notifies                     ← 아직
│
├─ Input
│  ├─ IA_Dodge                     ✔ 완료 (Left Shift)
│  ├─ IA_LockOn                    ✔ 완료 (Middle Mouse Button)
│  └─ IMC_Player_Combat            ✔ 완료
│
├─ Data
│  └─ DA_PlayerCombatTuning        ← 아직
│
└─ Debug                           ← 아직
```

`BP_Player_Combat`은 게임플레이 상태·입력·판정을 담당한다.
`ABP_Player_Combat`은 상태값을 받아 포즈와 애니메이션만 출력한다.

## 구현 순서

1. ~~기존 `BP_Player`와 `ABP_Player_HFSM`을 `Assets/Legacy`로 격리~~ —
   **N/A (Battle 프로젝트엔 해당 레거시가 없음)**
2. `BP_Player_Combat` 생성 — ✔ 완료
3. `BP_PlayerController_Combat` 생성 — ✔ 완료
4. 새 게임 모드에 새 플레이어 연결 — ✔ 완료
5. 이동·락온·더킹 입력 연결 — ✔ 완료 (IA/IMC 생성·매핑·자동등록까지)
6. `PlayerRoot → Free/LockOn` HFSM 구성 — ✔ 완료 (Enum 변수 + ToggleLockOn,
   PIE 검증함)
7. 락온 전투 Idle과 8방향 이동 연결 — ← 다음 순서
8. 방향 스냅샷 기반 더킹 구현
9. `Locomotion → Dodge → Locomotion` 복귀 검증
10. `CombatAction` 하위에 Guard·Attack 상태 추가 (Free/LockOn 양쪽)
11. 입력 버퍼 추가
12. Anim Notify State 기반 취소 구간 추가
13. 공격 중 Guard/Dodge 취소 검증

## 1차 완료 기준

첫 번째 기능 목표는 이동·락온·더킹이지만, 그래프 구조는 처음부터 다음
확장을 수용해야 한다.

- 자유 이동 Idle/Move
- 락온 CombatIdle/CombatMove
- 방향별 Dodge
- 더킹 종료 후 자동 복귀
- 추후 공격 중 더킹 취소
- 추후 공격 후반부 방어 취소
- 추후 패링 판정과 히트 판정

즉, 1차 기능은 단순하지만 구조는 최종 전투 시스템을 고려해 설계한다.

## 테스트 기준

- 맵 실행 시 `BP_Player_Combat`만 생성되는가 (템플릿 캐릭터 중복 스폰 없음)
- 락온하지 않으면 일반 Idle
- 락온하면 전투 자세(복싱 가드) Idle
- 락온 상태에서 입력 방향에 맞는 8방향 이동
- 이동 후 Shift를 눌러도 마지막 이동 방향으로 고정되지 않음
- 입력이 없을 때 Shift는 후방 더킹
- 더킹 애니메이션이 반드시 `Locomotion → Dodge → Locomotion`으로 종료
- 더킹 중 이동 입력 차단
- Dodge/Guard/Attack이 락온 여부와 무관하게 전부 가능한가 (애니메이션만
  다르게 재생되는가)
- 공격 전반부에는 취소 불가
- 공격 후반부에는 Guard/Dodge 취소 가능
- 취소 구간 직전에 입력해도 0.1초 버퍼 후 실행
- Guard와 Dodge가 충돌하면 정의된 우선순위대로 실행
- 기존 레거시 블루프린트를 참조하지 않음
- 모든 상태·전이·취소 규칙에 한국어 주석이 있음
- 블루프린트 컴파일 오류가 없는가

## 최종 영상 흐름

```text
자유 이동
→ 락온
→ 전투 자세
→ 8방향 이동
→ 방향별 더킹
→ 방어
→ 공격
→ 공격 중 취소
→ 입력 버퍼 실행
```

## 최종 산출물

- 새 플레이어 캐릭터 블루프린트
- 새 플레이어 컨트롤러
- 새 애니메이션 블루프린트
- 이동·락온·더킹 HFSM
- 방어·공격 상태 확장 구조
- 입력 버퍼
- Anim Notify State 취소 구간
- 한국어 주석
- 레거시와 분리된 폴더 구조
- 기능별 테스트 체크리스트
- 포트폴리오 촬영용 실행 장면

## 확정 사항 (변경 시 이 문서를 갱신)

- 이동 물리·카메라는 UE5 3인칭 템플릿 것을 재사용한다. 처음부터 새로
  만들지 않는다.
- 새 기준 플레이어는 `BP_Player_Combat` (`/Game/BossArena/Player`)이다.
- 새 구조는 HFSM이어야 한다 (위 "HFSM 구조" 참고).
- `Dodge`/`Guard`/`Attack`은 락온 여부와 무관하게 항상 가능하다. 락온은
  애니메이션 세트와 공격 방향(타겟 자동 조준 여부)만 바꾼다. "Guard/Attack은
  락온 중에만"이라는 규칙은 명시적으로 폐기했다.
- 세키로식 입력 버퍼(0.1초, 최근 입력 1개, 우선순위 기반 덮어쓰기)와 공격
  후반부 취소를 지원한다.
- 상태와 전이 규칙을 분리한다 (`ActionState` = 무엇을 하는가,
  Notify State/함수 내부 조건 = 언제 전이가 허용되는가).
- 애니메이션은 게임플레이 로직과 분리한다 (`BP_Player_Combat`은 상태만
  결정, `ABP_Player_Combat`은 그 상태를 구독해서 포즈만 출력).
- 1차 구현 범위는 이동·락온·더킹이다. 방어·공격·패링은 같은 토대 위에
  확장한다.
- `LevelPrototyping`은 아레나 지오메트리가 직접 참조하므로 삭제하지 않고
  유지한다.
- `Lvl_ThirdPerson` 데모 맵과 그 전용 자산은 삭제했고, 시작 맵은
  `Lvl_Arena_01`이다.
- 상태 변수는 Enum 하나로 통일한다 (bool 여러 개 + byte 여러 개 동시 사용
  금지).
- 한 이벤트 그래프에 모든 상태 로직을 몰아넣지 않는다 — 상태별 함수/커스텀
  이벤트로 분리한다.
- 플레이스홀더 자산은 검증 전에 영구 배선하지 않는다 (이동+애니메이션부터
  눈으로 확인 후 다음 단계).
- 깔끔한 체크포인트마다 git 커밋한다.
