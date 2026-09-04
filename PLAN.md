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
- `InputMappingContext`의 `Triggers`(Tap/Hold 등)는 인스턴스 서브오브젝트라
  MCP로 새로 못 만든다 — 에디터에서 직접 추가해야 한다. 매핑 배열에 새
  항목을 추가할 때는, 기존 항목들의 트리거 참조(`InputTriggerTap_0` 등)를
  그대로 포함해서 배열 전체를 다시 써야 한다 — 일부만 바꾸면 "삽입 위치가
  모호하다"는 에러가 난다.
- Enhanced Input의 `Hold` 트리거를 쓸 때 `Started` 핀은 **누른 순간 즉시**
  발동한다 (Hold 시간을 채우기 전에도). 정말 "그 시간만큼 눌러야 발동"을
  원하면 `Triggered` 핀을 써야 한다. 다만 같은 키에 `Completed`/`Canceled`로
  상태를 원상복구하는 로직이 있으면 `Started`를 써도 결과적으로는 크게
  문제되지 않는다 (지금 Sprint 구현이 이 경우).
- 이벤트 그래프에서 노드를 코멘트 박스로 정리(드래그로 묶기)하다가
  실행선이 실수로 끊어질 수 있다 — `IA_LockOn → ToggleLockOn` 연결이 한 번
  이렇게 끊어졌었다. 정리 작업 후엔 `get_connected_subgraph`로 실행선이
  살아있는지 재확인하는 습관을 들일 것.
- 리터럴 값(Enum 드롭다운 등) 설정 실수는 컴파일 에러로 안 잡힌다 —
  `ToggleLockOn`의 `SetMovementMode` 노드가 `NewEnumerator1`(LockOn)이어야
  할 자리에 `NewEnumerator0`(Free)이 박혀 있던 버그가 실제 사례. 증상은
  "일부 로직(LockOnTarget)은 정상 작동하는데 최종 상태(MovementMode)만
  안 바뀜"처럼 헷갈리게 나타난다. PIE에서 이상하면 그래프 실행선뿐 아니라
  각 노드의 입력 핀 리터럴 값도 `get_node_infos`로 직접 확인할 것.
- MCP엔 "액터의 블루프린트 함수를 직접 호출"하는 툴이 없다 (Enhanced Input
  키 입력도 MCP로 주입 불가). PIE에서 함수 로직을 검증하려면, 그 함수가
  실제로 만들어내는 상태 변화를 `set_properties`로 동일하게 재현한 뒤
  Tick 기반 후속 로직(회전, 속도 등)이 맞게 반응하는지 관찰하는 방식으로
  우회한다 — 그래프 자체의 배선/값 정확성은 `get_connected_subgraph`/
  `get_node_infos`로 정적 검증한다.
- **`BlendSpace`(및 아마 `AnimBlueprint`의 AnimGraph 등 파생 캐시를 갖는
  애셋 전반)의 `sampleData`/`blendParameters` 같은 복합 프로퍼티는
  `ObjectTools.set_properties`로 직접 덮어쓰면 안 된다 — 절대 안전하지
  않음, 실제로 에디터가 크래시남.** 블렌드 스페이스는 그리드 보간용 내부
  캐시를 별도로 들고 있는데, 리플렉션으로 `sampleData`만 갈아끼우면 이
  캐시가 어긋나서 저장 시점에 `Array index out of bounds` 어써션으로 즉시
  크래시가 난다 (2026-09-01 실제 발생, `BS_Player_LockOn8Dir` 작업 중).
  다행히 크래시가 `save_assets` 시점에 나서 손상된 파일이 디스크에
  저장되지는 않았지만, 시도 자체가 위험하다. **블렌드 스페이스/애님
  블루프린트의 AnimGraph 내부 편집은 Enum 생성처럼 MCP가 못 하는 작업으로
  취급하고, 에디터 UI에서 직접 만들어야 한다.** (Blueprint의 EventGraph는
  일반 K2 그래프라 기존 방식대로 MCP로 편집 가능 — 위험한 건 AnimGraph/
  BlendSpace 전용 파생 데이터 쪽.)
- `AController.ControlRotation`은 리플렉션으로 읽을 수 없다 (protected,
  BlueprintReadWrite 아님) — `get_properties`로 직접 조회 불가. 카메라가
  실제로 어디를 보는지 확인하려면 `PlayerCameraManager` 액터의
  `get_actor_transform` 회전값을 대신 읽는다 (Pawn Control Rotation을
  쓰는 카메라 붐이면 이 값이 사실상 ControlRotation과 같다).
- **AnimGraph 작업 시 유용한 패턴들** (ABP_Player_Combat 작업에서 확인):
  - Enum 전용 블렌드 노드(`BlendPoses(내열거형)`)는 커스텀 Enum의 항목
    수만큼 자동으로 핀이 안 생기고 `add_node_pin`도 지원 안 함 — 대신
    **`부울로포즈블렌딩`(Blend Poses by bool)**을 쓰고 조건을 bool 변수로
    미리 계산해두는 게 훨씬 안전하다.
  - `부울로포즈블렌딩`의 `BlendPose_0`/`BlendPose_1`은 이름만 보면
    False/True 순서로 착각하기 쉬운데, **실제로는 `BlendPose_0` =
    `bActiveValue == true`, `BlendPose_1` = `false`** 다 (실제 PIE에서
    반대로 나와서 스왑하고서야 확인함). 헷갈리면 일단 연결하고 PIE로
    검증할 것.
  - 블렌드 스페이스/시퀀스를 재생하는 AnimGraph 노드는, 그 애셋이 그
    애님 블루프린트 안에서 이미 한 번이라도 쓰인 적 있어야
    `find_node_types`에 특화된 타입(`...플레이어'애셋이름'`)으로 뜬다.
    처음 쓰는 애셋이면 그 특화 타입은 아직 없다 — 대신 범용
    `애니메이션|시퀀스|시퀀스플레이어`(또는 블렌드스페이스플레이어)를
    만든 뒤, `ObjectTools.set_properties`로 그 노드의 `node.sequence`
    (또는 블렌드 스페이스 노드는 애셋 참조 프로퍼티)를 직접 지정하면
    된다 — 핀이 아니라 노드 자체의 프로퍼티라는 점에 주의.
- **RootMotion 애니메이션이 임포트 직후엔 "Enable Root Motion"이 기본
  꺼짐 상태다** (`AnimSequence.bEnableRootMotion`). `AnimInstance`의
  `RootMotionMode`(`RootMotionFromMontagesOnly` 등)를 맞게 설정해놔도,
  애셋 자체의 이 옵션이 꺼져 있으면 이동이 통째로 안 일어난다 — 증상은
  "몽타주는 재생되는데 캐릭터가 제자리에 멈춰있음"으로 나타나서 다른
  버그(카메라 추적, 입력 문제 등)로 오인하기 쉽다. RootMotion 세트를
  새로 가져올 때마다 이 프로퍼티부터 확인할 것 (`get_properties`로
  `bEnableRootMotion` 조회).
- **`+`/`-`/`*`/`/` 같은 산술 연산 노드(`K2Node_PromotableOperator`)는
  `find_node_types`에 아무 문맥 없이 검색하면 안 뜬다.** 대신
  `context_pins`에 이미 그래프에 있는 **아무 노드의 출력 핀**(꼭 연산과
  관련 없어도 됨, 액터 레퍼런스 핀도 통했음)을 하나 끼워서 검색하면
  `유틸리티|연산자|추가`/`빼기`/`곱하기`/`나누기` 형태로 나온다. 생성 직후
  타입은 `와일드카드`인데, `A`/`B` 핀에 실제 값(float, vector 등)을
  연결하는 순간 자동으로 `float+float`처럼 구체 타입으로 확정된다 —
  타입 확인은 연결 후 `get_node_infos`로.
- **`write_graph_dsl`(그래프를 텍스트 DSL로 한 번에 작성하는 도구)은
  이 프로젝트 환경에서 신뢰할 수 없었다** — 함수에 이미 있던
  `FunctionResult` 노드까지 지워버리고 본문은 채우지 못한 채 끝나는
  실패가 반복 재현됨 (2026-09-02, `ComputeDodgeTargetLocation`/
  `Test_Dsl` 두 번 다 같은 증상). 노드 단위로 `create_node`/`connect_pins`
  조합하는 기존 방식을 계속 쓸 것 — DSL은 당분간 시도하지 않는다.
- **다른 블루프린트가 만든 커스텀 함수/변수는, 그 블루프린트 "밖"에서
  `create_node`로 노드를 못 만든다** (2026-09-03, `ANS_AttackCancelWindow`
  작업 중 발견). `find_node_types`엔 후보로 뜨는데 (예:
  `함수호출|SetCancelWindowOpen`) `create_node`를 부르면 "존재하지 않음"
  에러가 남 — **엔진 기본(C++) 함수는 문제없음** (예: `GetOwner`,
  `PlayAnimMontage`), **우리가 블루프린트로 만든 함수/변수만 이 문제가
  있음**. 같은 블루프린트 "안"에서는 전혀 문제없이 잘 만들어진다.
  다른 블루프린트에서 이 블루프린트의 상태를 읽거나 바꿔야 하면,
  "저쪽에서 이쪽으로 부르기"가 아니라 "이쪽에서 저쪽 상태를 물어보기"
  구조로 뒤집는 게 낫다 (예: 커스텀 노티파이 안에 로직을 넣는 대신,
  캐릭터 쪽에서 `WasAnimNotifyStateActiveInAnyState()`로 매 틱 물어보는
  방식으로 우회함).
- `find_node_types`의 `context_pins`는 **방향이 중요하다.** 힌트로 준
  핀이 `EGPD_Output`(출력)이면 "그 타입을 입력으로 받는" 노드 위주로
  뜨고(예: `Set...` 계열), `EGPD_Input`(입력)이면 "그 타입을 출력하는"
  노드 위주로 뜬다(예: `Get...` 계열). 변수 Getter를 찾고 싶은데
  `Set...`만 계속 나오면, 힌트 핀의 방향을 `EGPD_Input`으로 바꿔서
  다시 검색해볼 것.

## 진행 상황 (2026-09-01 기준)

기반 공사 + 락온 토글까지 끝났다.

```
✔ 완료   BP_Player_Combat / BP_PlayerController_Combat / BP_BossArenaGameMode
✔ 완료   Lvl_Arena_01을 시작 맵으로 지정, PIE로 정상 스폰 확인
✔ 완료   IA_Dodge(Shift) / IA_LockOn(마우스 휠) / IMC_Player_Combat, 자동 등록
✔ 완료   E_PlayerMovementMode / E_ActionState Enum, BP_Player_Combat 변수로 추가
✔ 완료   ToggleLockOn 함수 — Free⇄LockOn 전환, BP_TrainingDummy를
         LockOnTarget으로 저장 (구현 순서 6번)
✔ 완료   UpdateLockOnRotation — LockOn 중 매 틱 타겟 방향으로 부드럽게
         회전(RInterpTo), bOrientRotationToMovement Free↔LockOn 자동 전환.
         PIE 시뮬레이션으로 상태 전환·회전 각도·Sprint 병행·복귀까지 전부
         검증 완료 (2026-09-01)
✔ 완료   Dodge(B/L/R)·Trot(8방향) 애니메이션 임포트 + 우리 스켈레톤으로
         리타겟 완료 (`/Game/BossArena/Animations`)
✔ 완료   Sprint — IA_Sprint(Shift Hold, 0.25초) + IA_Dodge(Shift Tap,
         0.2초) 트리거 분리, bIsSprinting/SetSprinting으로 MaxWalkSpeed
         600↔900 전환, PIE에서 체감 속도 증가 확인함
✔ 완료   락온 중 카메라도 타겟 방향으로 같이 회전 — Controller의
         ControlRotation을 몸통과 같은 TargetYaw로 RInterpTo, Pitch는
         플레이어 마우스 조작 그대로 유지. PlayerCameraManager 회전값으로
         검증함 (2026-09-01)
✖ 실패→보류 BS_Player_LockOn8Dir(8방향 Trot 블렌드 스페이스)를
         set_properties로 직접 조립하려다 에디터 크래시 — "알아둘 것"
         참고. 에디터 UI에서 직접 만듦 (사용자가 축 세팅 + 8방향 샘플 배치)
✔ 완료   BS_Player_LockOn8Dir 완성 (에디터 UI로 제작, Direction -180~180
         8분할, AS_Trot-* 8개 + 후방 중복 샘플 총 9개)
✔ 완료   ABP_Player_Combat 생성 (ABP_Unarmed 복제) + AnimGraph 연결 —
         `부울로포즈블렌딩` 2단 구조: 바깥쪽은 MovementMode 기반
         Free/LockOn 분기, 안쪽은 LockOn일 때 ShouldMove 기반
         CombatIdle(AS_Idle)/CombatMove8Dir(BS_Player_LockOn8Dir) 분기.
         EventGraph에 bIsLockedOn 변수 추가(Character→BP_Player_Combat
         캐스트 후 MovementMode==LockOn 비교). 기존 Direction/GroundSpeed/
         ShouldMove 변수는 템플릿이 이미 계산해두던 것을 그대로 재사용.
         BP_Player_Combat의 AnimClass를 ABP_Unarmed→ABP_Player_Combat로
         교체. PIE에서 락온 Idle/Move 전환 확인함 (구현 순서 7번 완료,
         2026-09-01)
← 다음   방향 스냅샷 기반 더킹 구현 (구현 순서 8번)
← 이후   ActionState/CombatAction(Dodge→Locomotion 복귀) → Guard/Attack →
         입력 버퍼/취소 구간
```

세부 히스토리(마이그레이션, 레거시 정리 등)는 git 커밋 로그 참고 — 여기엔
지금 상태와 다음 할 일만 남긴다.

## 회피(Dodge) 상세 설계 (2026-09-02)

### 레퍼런스 분석 → 구현 방법

넥슨/네오플 "Project BBQ" 트레일러 후반 보스전 장면을 프레임 단위로
분석해서 뽑아낸 핵심 요소 3가지와, 그걸 우리 게임에 어떻게 반영했는지:

1. **잔상(고스트 실루엣) VFX** — 회피할 때 몸에서 하얀 잔상이 떨어져
   나가며 남는다. → **아직 미구현.** 지금은 이동 느낌부터 잡는 중이고,
   VFX는 이동이 확정된 뒤 나중에 붙일 항목 (파티클/포스트프로세스 작업,
   별도 단계로 분리).
2. **버스트성 순간이동** — 관성으로 미끄러지지 않고 "팟!" 하고 짧게
   끊어지듯 이동한다. → 처음엔 코드로 위치를 강제로 옮기는 방식
   (`VInterpConstantTo`)으로 만들었다가, 최종적으로 **애니메이션 자체에
   내장된 이동(RootMotion)**으로 전환했다 (아래 "이동 방식 결정" 참고).
3. **근접 회피(안 멀리 안 도망감)** — 상대 히트박스 옆으로 바짝 붙어서
   피한다. → 회피 거리를 짧게 유지하는 것으로 간접 반영 (RootMotion
   애니메이션 자체의 이동 거리가 짧은 편).

### 이동 방식 결정 — 최종: 코드 이동 (RootMotion은 폐기, 2026-09-03)

RootMotion으로 한 번 갔다가 **다시 코드 이동으로 되돌린다.** 이유는
레퍼런스 분석 결과와 직접 충돌하기 때문이다:

- 레퍼런스(Project BBQ)의 회피는 사실적인 발걸음 이동이 아니라, **정해진
  짧은 거리를 앞쪽에 몰아서 순간적으로 이동**하는 연출이다.
- RootMotion은 "모션 캡처 배우가 실제로 움직인 거리"에 이동량이 묶여
  있어서, **"몇 cm를 갈지"를 숫자로 정할 수가 없다.** 이건 설정 문제가
  아니라 RootMotion의 성격 그 자체다 (엔진의 `AnimRootMotionTranslationScale`
  도 이 프로젝트에선 읽기 전용이라 배율 조절 불가).
- 즉 RootMotion은 발 미끄러짐을 해결해주는 대신, 레퍼런스의 핵심 요소인
  "거리 조절 가능한 버스트 이동"을 포기하는 선택이었다 → 되돌린다.

**사용할 애니메이션은 다시 InPlace 세트**
(`/Game/BossArena/Animations/Dodge/A_INP_Dodge_01_*`).

#### 어색함을 없애는 방법 — 이동을 애니메이션 타임라인에 얹기

코드 이동의 예전 문제는 두 가지였다: (a) 마찰을 0으로 죽여서 생긴
스케이팅, (b) 이동이 0.06초 만에 끝나는데 애니메이션은 0.8초라
**도착해놓고 제자리에서 팔다리만 휘젓는** 어색함. 둘 다 "이동과
애니메이션이 서로 다른 시계로 돈다"는 같은 원인이다.

해결: 순간이동이 아니라, **애니메이션 앞부분 구간에 이동을 나눠서 배분**한다.

```
애니메이션 전체 (예: 0.8초)
├────────────────────┼───────────────┤
   이동 구간 (앞 60%)      나머지 (착지/정리)
   거리 전부 소화             이동 없음
   앞이 빠르고 뒤로 갈수록 감속
```

- "슉" 느낌 유지 — 이동이 앞쪽에 몰려 있고 초반이 제일 빠름
- 어색함 제거 — 이동이 애니메이션 안에서 끝나고, 뒷부분 동작이 "멈춰서는
  동작"과 맞물림
- 거리는 우리가 숫자로 지정 — 애니메이션에 묶이지 않음

#### 조절 가능한 값 (CombatTuning 카테고리, Instance Editable)

| 변수 | 의미 | 초기값 |
|---|---|---|
| `DodgeDistance` | 총 이동 거리 (cm) | 350 |
| `DodgeMoveWindow` | 애니메이션 중 이동이 차지하는 비율 (0~1) | 0.6 |
| `DodgeMoveEase` | 초반 쏠림 강도 (클수록 앞에서 확 튀고 급감속) | 2.0 |
| `DodgeBurstRate` | 초반 재생 배속 | 3.0 |
| `DodgeBurstDuration` | 그 초반 구간 길이(초) | 0.08 |
| `DodgePlayRate` | 그 이후 재생 배속 | 1.5 |
| `DodgeCancelRatio` | 애니메이션 몇 %부터 공격/방어로 취소 가능한지 | 0.55 |

#### 레퍼런스 재현 범위 (정직하게)

이동 뼈대는 위 값들로 재현 가능하지만, 영상의 인상은 이동만으로 만들어진
게 아니다. **잔상(고스트) VFX, 히트스톱, 카메라 연출은 전부 별도 작업**이며
이번 범위 밖이다. "영상 같은 느낌"의 나머지 절반은 그 단계에서 붙는다.

### (폐기) 이전 시도 — RootMotion 채택

| | 코드로 위치를 직접 옮기기 (이전 방식) | 애니메이션 자체의 이동 사용 (RootMotion, 현재 방식) |
|---|---|---|
| 이동 거리/속도 | `DodgeDistance`/`DodgeSpeed` 변수로 코드가 계산 | 애니메이션 제작자가 이미 잡아놓은 궤적 그대로 사용 |
| 손이 가는 곳 | 매 프레임 `SetActorLocation` 직접 호출 | `PlaySlotAnimationAsDynamicMontage` 한 번 호출로 끝, 나머지는 엔진이 알아서 처리 |
| 장점 | 거리/속도를 숫자로 정밀 제어 가능 | 애니메이션과 발/몸 움직임이 항상 100% 일치 (미끄러짐 없음) |
| 단점 | 발이 미끄러지는 느낌("스케이팅") 튜닝이 까다로움 | 방향별 애니메이션 10개 전부 손봐야 하고, 거리 조절이 애니메이션 리타이밍 없인 어려움 |

이 표는 **판단 근거로만 남겨둔다.** 당시엔 "코드 이동 = 스케이팅 문제"로
보고 RootMotion으로 갔지만, 스케이팅은 마찰을 0으로 죽인 처리 방식의
문제였지 코드 이동 자체의 한계가 아니었다. RootMotion 시도에서 얻은
소득: **RootMotion 애니메이션은 임포트 시 "Enable Root Motion"이 기본 꺼짐**
이라는 함정을 발견함 (아래 "알아둘 것"에 기록). 지금은 InPlace 세트를
쓰므로 이 설정은 무관하다.

### 애니메이션 선택 로직 (쉬운 설명)

`TryEnterDodge()` 함수가 Shift를 누른 순간 하는 일은 딱 이거다:

1. **지금 이동 입력(WASD)과 카메라 방향을 합쳐서 "어느 쪽으로 피할지"
   방향 벡터를 만든다.** 아무 키도 안 누르고 있으면 "지금 보고 있는 방향의
   반대쪽(후방)"으로 기본값을 잡는다.
2. **그 방향이 캐릭터가 지금 보고 있는 정면 기준으로 몇 도인지 각도를
   잰다** (`CalculateDirection` — 8방향 이동 애니메이션 만들 때 쓴 것과
   똑같은 함수 재사용).
3. **그 각도를 8개 구간(0°/45°/90°/135°/180°, 좌우 포함) 중 가장 가까운
   칸에 집어넣어서, 미리 준비된 10개 애니메이션 중 하나를 고른다** —
   `SelectObject` 노드를 이진 트리처럼 엮어서 비교 후 하나씩 좁혀나가는
   방식.
4. 고른 애니메이션으로 몽타주를 재생하고, `ActionState`를 `Dodge`로 바꿔서
   재생 중엔 이동 입력이 안 먹히게 잠근다.

즉 "8방향 이동 애니메이션 고르는 로직"을 거의 그대로 재사용해서 "8방향
회피 애니메이션 고르는 로직"으로 다시 쓴 것 — 새로 만든 개념이 아니라
기존 패턴 재사용.

### 애니메이션 속도 조절 (2단계 배속 시스템)

RootMotion으로 바꾸면서 "이동 거리"는 더 이상 우리가 숫자로 정하는 게
아니라 애니메이션이 정한다. 대신 **"얼마나 빨리 재생할지"**는 여전히
우리가 조절 가능하고, 지금은 2단계로 나눠놨다:

```
Shift 입력
   │
   ├─ 0 ~ DodgeBurstDuration초 동안: DodgeBurstRate 배속으로 재생 (기본 3배속, "팍!")
   │
   └─ 그 이후 끝날 때까지: DodgePlayRate 배속으로 재생 (기본 1.5배속, 평소보다 살짝 빠름)
```

왜 이렇게 나눴냐면: 처음부터 끝까지 다 3배속이면 너무 방정맞고, 다
1.5배속이면 "팍!" 하는 느낌이 안 산다. **초반 임팩트만 확 튀게 하고
나머지는 자연스럽게** 재생하려고 두 단계로 나눴다 (레퍼런스 영상에서
받은 "슉 움직이고 모션이 출력되는" 인상을 재현하려는 목적).

재생속도를 두 단계로 나누면 "애니메이션이 실제로 끝나는 시점"도
달라지므로, 조작 불가 상태를 풀어주는 복귀 타이머(`OnDodgeRecoveryTimer`)
시간도 `DodgeBurstDuration + (전체길이 - DodgeBurstDuration×DodgeBurstRate) ÷ DodgePlayRate`
공식으로 다시 계산하도록 고쳤다 — 안 그러면 애니메이션은 끝났는데 계속
조작 안 되는 상태로 남거나, 반대로 애니메이션 끝나기 전에 조작권이
돌아와버린다.

**직접 조절하려면**: `BP_Player_Combat` 열고 좌측 변수 목록 →
**CombatTuning** 카테고리에서 `DodgeBurstRate`/`DodgeBurstDuration`/
`DodgePlayRate` 값을 디테일 패널에서 바로 수정 → 컴파일 → 저장. (유니티
인스펙터로 값 조절하던 것과 같은 방식 — Instance Editable 변수라 코드
안 건드리고 숫자만 바꾸면 됨.)

### 이동 "거리"는 지금 누가 정하나

RootMotion 전환 후로는 **거리 자체를 우리가 숫자로 정하지 않는다** — 각
방향 애니메이션 클립 안에 이미 박혀있는 이동 궤적을 그대로 따라간다.
거리를 바꾸고 싶으면 (a) 애니메이션 자체를 리타이밍하거나, (b) 굳이
코드로 배율을 걸고 싶으면 `MontageSetPlayRate`처럼 이동량에도 곱연산을
거는 방식을 추가로 만들어야 한다 (아직 없음, 필요해지면 그때 추가).

### 죽은 코드 정리 — 완료 (2026-09-02)

- **`EventGraph`의 `Branch(ActionState==Dodge) → VInterpConstantTo →
  SetActorLocation` 체인** (코드로 위치를 직접 밀어주던 옛날 방식) — 삭제
  완료. 부속 노드(`GetActorLocation`, `GetDodgeTargetLocation`,
  `GetDodgeSpeed`, `Self` 참조 등 EventGraph 쪽 사본) 전부 같이 제거.
- **`TryEnterDodge`의 목표지점 계산 체인**(`RotationFromXVector →
  MakeTransform → TransformLocation`, `GetActorLocation`,
  `GetDodgeDistance`) — RootMotion 전환 후 `DodgeTargetLocation`을 읽는
  곳이 없어져서 같이 죽은 코드였음. 삭제하고 `SetActionState(Dodge)`가
  바로 몽타주 재생 단계로 이어지게 실행선 재연결.
- **`DodgeDistance`/`DodgeSpeed`/`DodgeStartLocation`/`DodgeTargetLocation`
  변수 4개** — 전부 제거.
- `TryEnterDodge`/`EventGraph` 양쪽 다 `arrange_nodes`로 정돈함.

### Dash → Roll로 개명 (2026-09-03) — 완료, 모션은 후속 다듬기 필요

**정리하고 보니 "Dash"는 별도 능력이 아니라 "락온 안 했을 때(Free
모드) 회피 애니메이션이 달라지는 것"이었다.** 회피는 이미 락온 여부와
무관하게 항상 가능(위 "확정 사항" 참고)하고, 지금까지는 Free든
LockOn이든 똑같은 `A_INP_Dodge_01_*`(전투용, 복싱 자세) 10종 세트를
썼다. `A_INP_Dash_Idle*` 8종(평상시 이동 자세)은 계속 안 쓰이고
대기만 하고 있었음. 그래서 새 키/새 상태/새 함수 없이, **기존
`TryEnterDodge`의 애니메이션 선택 로직 맨 끝에 "지금 락온 중인가?"로
갈라주는 병합 지점 하나만 추가**했다.

- 기존 로직(8~10방향 각도 비교로 알맞은 애니메이션 하나 고르는
  이진 트리, "애니메이션 선택 로직" 문단 참고)은 전혀 안 건드림 —
  이미 "완벽하다"고 확인받은 회피 기능이라 손대는 대신 **옆에 나란히
  같은 모양의 새 트리를 하나 더 만들어서** Dash용 8개 애니메이션 중
  하나를 고르게 함. 각도 비교값(22.5°/67.5°/112.5°/157.5°)과 좌우
  판정은 기존 트리가 이미 계산해둔 값을 그대로 재사용(다시 계산 안
  함) — 순수 함수라 여러 곳에서 결과를 나눠 써도 안전함.
  - Dodge 세트는 정면(0°)/후면(180°)도 좌우로 갈라진 10개짜리라
    Dash(8개, 정면·후면은 좌우 구분 없이 단일 애셋)와 트리 모양이
    살짝 다름 — 정면·후면 지점만 즉시 리터럴 값을 쓰고 나머지
    45°/90°/135° 구간은 기존과 똑같이 좌우 분기.
  - 마지막에 `SelectObject(조건=MovementMode==Free, A=Dash트리 결과,
    B=기존 Dodge트리 결과)` 노드 하나로 병합해서, 몽타주 재생 직전
    최종 애니메이션 자리에 끼워넣음. "락온 중인가?" 판정도 이미
    `TryEnterDodge`에 있던 걸 재사용(새로 안 만듦).
- 거리/타이밍/재생속도 등 나머지 전부(`DodgeDistance`,
  `DodgeMoveWindow`, `DodgeBurstRate` 등)는 Free든 LockOn이든
  동일하게 적용됨 — Dash만의 별도 수치는 없음. **손맛이 달라야 하면
  (예: Dash는 더 멀리/빠르게) 나중에 이 지점에 `MovementMode`별
  분기를 추가로 얹으면 됨** — 지금은 "다른 애니메이션 세트를 쓴다"만
  구현.
- 컴파일 확인, 에러 없음, 저장 완료.
- **버그 발견 및 수정 (2026-09-03)**: 첫 버전은 Dash/Dodge가 정반대로
  나왔음 — "락온 안 했을 때 Dash가 안 나오고 Dodge와 바뀜" 리포트.
  원인: 재사용한 기존 체크(`EnumEquality_1`)의 리터럴 값을 다시 읽지
  않고 기억에 의존해서 `NewEnumerator0`(Free)라고 착각했는데, 실제
  값은 `NewEnumerator1`(LockOn)이었음 — 즉 이 조건은 "Free인가"가
  아니라 "LockOn인가"였음. 이 조건 자체는 다른 곳(방향 계산 폴백
  로직)에서도 쓰이고 있어서 값을 바꾸지 않고, 병합 노드의 A/B 입력만
  서로 바꿔서 수정(A=Dodge/LockOn용, B=Dash/Free용). 컴파일 확인,
  저장 완료, PIE 재시작함.
- **버그 2(진짜 원인) 발견 및 수정 (2026-09-03)**: 위 수정 후에도
  "락온 안 했을 때 Dash가 아예 안 나오고 캐릭터가 멈춰있음(애니메이션
  자체가 없음)" 리포트. 진단용 `PrintString`을 캐스트 실패 분기에
  심어서 확인했지만 안 뜸 — 즉 `TryEnterDodge` 함수 자체가 호출도
  안 되고 있었음. 함수 맨 앞의 진입 조건(`IfThenElse_0`)을 다시 보니
  `ActionState==Locomotion` **AND** `MovementMode==LockOn`으로
  되어 있었음 — **이건 Dash 작업으로 새로 생긴 버그가 아니라
  원래부터 있던 버그**. "회피는 락온 여부와 무관하게 항상 가능하다"는
  확정 사항과 반대로, 실제 코드는 **락온 중일 때만 회피 진입이
  가능**했던 것. 이 세션의 모든 이전 회피 테스트가 우연히 다 락온한
  상태에서 이루어져서 지금까지 안 걸렸던 것으로 보임 — Dash 작업이
  처음으로 "락온 안 한 상태에서 회피" 경로를 실제로 실행시키면서
  드러남. `MovementMode==LockOn` 조건을 진입 조건에서 완전히 제거하고
  `ActionState==Locomotion` 하나만 보게 수정(`TryEnterAttack`과
  동일한 패턴). `EnumEquality_1`(MovementMode==LockOn) 자체는 안
  지우고 그대로 둠 — Dash/Dodge 애니메이션 선택 병합 노드에서 계속
  사용 중.
  - **교훈**: 캐스트 실패 등 "실행이 안 됨" 계열 증상을 디버깅할 땐
    문제로 의심되는 지점만 보지 말고, 함수의 진입 조건부터 다시
    확인할 것 — 이번에도 진단 PrintString이 "여기까지도 안 왔다"는
    걸 알려줘서 훨씬 앞부분(함수 진입 게이트)을 다시 보게 된 것이
    결정적이었음.
- **애니메이션 세트 교체 및 명칭 확정 (2026-09-03)**: 위 버그들
  고치고 나서 Dash 자체는 작동했지만, 사용자가 `A_INP_Dash_Idle*`
  모션이 어색하다고 판단 — `/Game/Roll_Dodge_Dash_Set/SourceFiles/
  fbx/InPlace/Mannequin/Roll/A_INP_Roll_Idle*` 세트(같은 8방향
  네이밍 패턴, 스켈레톤 일치 확인함)로 교체. 트리 구조(비교 로직,
  임계값)는 전혀 안 건드리고 8개 리프 노드의 애셋 경로만 교체.
  이후 사용자가 이 애셋들을 `/Game/BossArena/Animations/Roll/`로
  직접 옮겨서(원본 `Roll_Dodge_Dash_Set/SourceFiles/...` 위치의
  파일은 사라짐 — 리다이렉터 없는 순수 이동으로 보임), 블루프린트의
  8개 리프 참조를 새 경로로 다시 갱신함. **명칭도 이제부터 "Dash"가
  아니라 "Roll"로 부른다** — Free 모드 회피의 정식 이름.
  - **아직 남은 것 (보류, 다음에)**: 구르기(Roll) 동작 자체가
    "자연스럽지 않다"는 피드백 있음 — 어느 부분이 어색한지 아직
    구체화 안 함. 지금은 넘어가고 나중에 다시 다룸.

## 공격(Attack) 1타 + 취소 구간/입력 버퍼 계획 (2026-09-03)

### 사용할 애니메이션 — **사용자 리타게팅 필요 (블로커)**

| 용도 | 원본 | 비고 |
|---|---|---|
| 1타 (좌) | `/Game/UAF_H2HCombat/Animations/H2HCombo/LeftHand/AM_Jab-L` (`AS_Jab-L`) | 길이 0.48초, RootMotion 켜져 있음 (지를 때 살짝 전진) |
| 2타 (우, 나중에) | `/Game/UAF_H2HCombat/Animations/H2HCombo/RightHand/AM_Cross-R` (`AS_Cross-R`) | 좌-우 콤보용 |

**문제**: 이 애셋들은 `/Game/UAF_H2HCombat/Demo/Characters/Mannequins/Meshes/SK_Mannequin`
에 물려 있고, 우리 캐릭터는 `/Game/Characters/Mannequins/Meshes/SK_Mannequin`
이다 (이름만 같고 다른 애셋).

**처리 방법**: 우리 스켈레톤으로 **리타게팅해서 `/Game/BossArena/Animations/Attack/`
에 배치** — 이 작업은 사용자가 직접 한다 (아래 "확정 사항"의 우회 금지 규칙
참고). 리타게팅 전엔 공격 구현 착수 불가.

공격은 InPlace가 아니라 **RootMotion 켜진 원본을 그대로 쓰는 게 맞다** —
주먹 지를 때의 짧은 전진은 오히려 자연스럽고, 회피처럼 거리를 숫자로
조절할 이유가 없다. (회피=코드 이동, 공격=RootMotion으로 서로 다른 방식을
쓰는 것이 의도된 설계다.)

### 취소 구간 + 입력 버퍼 — 구현 방식 변경

원래 계획(위 "세키로식 취소 구조")은 `Anim Notify State`로 취소 구간을
표시하는 방식이었다. **회피에 한해서는 타이머 기반으로 대체한다**:

- 이유: 회피는 이미 타이머 기반(`OnDodgeRecoveryTimer`)으로 복귀를
  관리하고 있어서, 타이머 하나를 더 거는 게 훨씬 단순하고 애니메이션
  에셋을 건드릴 필요가 없다.
- `DodgeCancelRatio`(기본 0.55) 시점에 타이머가 발동해서 "이제 취소 가능"
  플래그를 켠다 → 이때 예약된 입력이 있으면 즉시 소비.
- **공격 콤보(좌→우)처럼 타이밍이 정밀해야 하는 구간은 원래 계획대로
  Anim Notify State를 쓴다.** 즉 두 방식을 병행한다.

입력 버퍼 자체(0.1~0.15초, 최근 입력 1개, 우선순위 덮어쓰기)는 위
"입력 버퍼" 섹션의 설계를 그대로 따른다.

### 작업 순서

1. ✔ 완료 (2026-09-03) 회피 이동 방식 되돌리기 + 위 조절값 구현. 버그 2개
   잡고 해결:
   - Tick 로직이 "회피 중이면 이동 / 아니면 카메라" 양자택일 구조였음 →
     회피 중엔 카메라 추적이 통째로 멈췄다가 끝나고 갑자기 따라잡으면서
     끊기는 현상 발생. `Sequence` 노드로 바꿔서 카메라는 항상 매 틱 실행,
     이동만 조건부로 분리.
   - `TryEnterDodge`에서 `SetDodgeMoveDuration`이 `CastToAnimSequence`
     캐스팅 **전에** 그 결과(재생 길이)를 읽으려고 해서 None 접근
     런타임 에러 발생 + 이동시간이 0에 가깝게 잘못 계산됨 → 순간 이동처럼
     "뚝" 끊기는 진짜 원인이었음. 실행 순서를 캐스팅 → 이동시간 계산으로
     교정.
   - 확인된 사용자 리타게팅: `AM_Jab-L`/`AS_Cross-R` 둘 다 원본 폴더에서
     바로 리타게팅 완료 확인함 (Skeleton = 우리 프로젝트 SK_Mannequin).
2. ✔ 완료 (2026-09-03) 공격 1타 (`AM_Jab-L`). `TryEnterAttack()` 함수 생성:
   - `ActionState==Locomotion`일 때만 진입 허용
   - `ActionState=Attack`으로 바꾸고 `PlayAnimMontage(AM_Jab-L)` 재생
     (이미 완성된 몽타주 에셋이라 Dodge처럼 `PlaySlotAnimationAsDynamicMontage`
     + 캐스팅 안 거치고 바로 재생 — 훨씬 단순함)
   - `PlayAnimMontage`가 재생 길이를 직접 반환해주므로 그 값으로 타이머
     설정 → `OnAttackRecoveryTimer`에서 `ActionState=Locomotion` 복귀
   - 입력: 좌클릭(`LeftMouseButton`) → `IA_Attack` 신규 생성,
     `IMC_Player_Combat`에 매핑 추가
   - `Move()` 함수가 이미 `ActionState==Locomotion`일 때만 이동 입력을
     받게 되어 있어서, 공격 중 이동 잠금은 추가 작업 없이 자동으로 적용됨
   - Attack 애니메이션엔 RootMotion이 켜져 있어(지를 때 살짝 전진) 코드로
     따로 안 건드림 — Dodge와 달리 이동 방식이 다르다는 점 명시
3. 취소 구간 + 입력 버퍼 → 회피 → 공격 연결 테스트
4. ✔ 완료 (2026-09-03) 공격 2타(`AM_Cross-R`) 추가해서 좌-우 콤보. 순서를
   앞당겨서 3번보다 먼저 완료함:
   - `AttackComboIndex`(0=1타/1=2타), `bAttackQueued`(다음 입력 예약),
     `AttackPlayRate`(재생 배속, 기본 1.4배속) 변수 추가
   - `TryEnterAttack()`: `Locomotion` 상태면 1타(`Jab-L`)로 새로 진입;
     이미 `Attack` 상태면(1타 재생 중) 그냥 `bAttackQueued=true`로 예약만
     해두고 끝
   - `OnAttackRecoveryTimer`: 1타가 끝나는 시점에 예약(`bAttackQueued`)이
     있고 아직 2타를 안 냈으면(`AttackComboIndex==0`) → 2타(`Cross-R`)
     재생, 콤보 인덱스를 1로 올리고 새 타이머 설정. 예약이 없거나 이미
     2타까지 다 냈으면 → `Locomotion`으로 복귀하고 상태 초기화
   - **주의**: 이건 "1타가 끝나는 순간에 예약된 입력을 소비"하는 방식이라
     3번(진짜 애니메이션 중간 취소 구간)과는 다르다 — 1타 재생 도중
     아무 때나 클릭하면 예약되고, 반드시 1타가 자연스럽게 끝난 뒤에만
     2타가 나간다. 더 타이트한 손맛(공격 후반부에만 예약 인정 등)을
     원하면 3번 작업에서 이 로직 위에 취소 구간을 얹어야 함.
   - **버그 발견 및 수정 (2026-09-03)**: "콤보가 제대로 안 나간다"는
     리포트 확인 중 발견. `PlayAnimMontage`가 반환하는 값은 재생속도가
     적용되지 않은 **몽타주 원본 길이**인데, 이 값을 그대로
     `SetTimerByFunctionName`의 `Time`에 넣고 있었음. `AttackPlayRate`가
     1.4배속이라 실제 애니메이션은 원본 길이보다 1.4배 빨리 끝나는데
     타이머는 원본 길이만큼 기다렸다가 발동 → 1타가 화면상으론 이미
     끝났는데 다음 판정(2타 전환 또는 Locomotion 복귀)이 늦게 발동하는
     "멈칫하는" 버그였음. Dodge 시스템에서 이미 한 번 겪었던 것과 같은
     종류의 실수(재생속도 보정 누락). `TryEnterAttack`과
     `OnAttackRecoveryTimer` 양쪽에 `float/float` 나누기 노드를 추가해서
     `Time = PlayAnimMontage 반환값 / AttackPlayRate`로 수정함.
   - **버그 2 발견 및 수정 (2026-09-03)**: 위 수정 후에도 "여전히 안 고쳐짐"
     리포트. 그래프를 처음부터 끝까지 노드 하나하나 다시 읽어서 두 개를
     더 찾음.
     (a) `OnAttackRecoveryTimer`의 "콤보 인덱스==0인가?" 비교 노드
     (`Equal(Integer)`)의 B 입력값이 `0`이 아니라 완전히 빈 문자열로
     설정되어 있었음 → 이 비교가 항상 거짓으로 나와서 2타(`Cross-R`)로
     넘어가는 분기를 절대 못 탐. `0`으로 명시적으로 설정해서 수정.
     (b) `IA_Attack` 입력 노드가 `Triggered` 핀에 연결되어 있었는데,
     `IA_Attack`엔 트리거가 하나도 없어서(빈 배열) Enhanced Input
     기본 동작상 `Triggered`는 **버튼을 누르고 있는 동안 매 프레임마다**
     계속 발동함. 즉 클릭 한 번(물리적으로 몇 프레임은 눌려있음)만으로도
     `bAttackQueued`가 자동으로 true가 되어, 두 번 클릭 안 해도 1타 뒤에
     2타가 자동으로 이어져버리는 상태였음 — "L 클릭, R 클릭"이라는
     의도한 콤보 조작감이 아니었음. `Triggered` 대신 누르는 순간 딱
     한 번만 발동하는 `Started` 핀으로 연결 변경해서 수정.
   - 세 가지(재생속도, 빈 정수 비교값, Triggered 프레임반복) 모두 함께
     걸려있었던 복합 버그였음.
   - **버그 3 발견 및 수정 (2026-09-03)**: 위 세 개를 다 고친 뒤에도
     "1타가 안 나가고 2타만 나감" 리포트. 원인은 블루프린트 로직이 아니라
     **몽타주 에셋의 블렌드 타임**이었음. `AM_Jab-L`은 원본 길이 0.48초에
     `BlendIn=0.25초`인데, `AttackPlayRate=1.4`를 적용한 실제 재생시간은
     약 0.35초 — 그중 72%가 블렌드 인 구간이라 완전히 자리잡은 포즈가
     나오기도 전에 다음 몽타주(`Cross-R`)로 블렌드 아웃되어 사실상 안
     보였던 것. `Cross-R`은 원본 0.82초로 더 길어서 블렌드 인 비중이
     작아 정상적으로 보였음. `AM_Jab-L`의 `BlendIn`을 0.25→0.05초,
     `BlendOut`을 0.25→0.08초로 줄여서 수정. **교훈**: 애니메이션
     재생속도(`PlayRate`)를 올릴 때는 블루프린트 타이머 계산뿐 아니라
     몽타주 자체의 BlendIn/BlendOut 시간도 실제 재생시간 대비 너무 크지
     않은지 같이 확인해야 함.
5. (재번호) 취소 구간 + 입력 버퍼 정교화 — 아래 "취소구간(Cancel
   Window) 상세 설계" 참고. **아직 착수 전, 사용자 확인 대기중.**

### 취소구간(Cancel Window) 상세 설계 — 착수 전 (2026-09-03)

**쉬운 설명**: 지금은 공격/회피 애니메이션이 "완전히 다 끝나야만" 다음
동작을 받아준다 (문이 끝에서 딱 한 번만 열림). 이걸 "애니메이션이
어느 정도(예: 60%) 진행되면 아직 안 끝났어도 다음 동작을 미리 받아준다"
로 바꾸는 작업 — 문이 중간에 한 번 더 열리게 만드는 것. 2026-09-03에
확인된 "Dodge→공격", "공격→공격" 체이닝 딜레이가 이걸로 해결될 걸로
예상하지만, 아직 착수 전이라 확정은 아님(원인 미확정 상태로 보류
중이었던 항목, 아래 "아직 안 끝난 것" 참고).

옛날에 미리 써둔 "세키로식 취소 구조"/"입력 버퍼" 섹션(이 문서 하단)의
설계를 그대로 따르되, 지금 실제로 만들어진 `TryEnterAttack`/
`OnAttackRecoveryTimer`/`AttackComboIndex`/`bAttackQueued`와 연결한
구체 버전이 아래 내용이다.

**구현 방식: Anim Notify State** (`SEKIRO_COMBAT_RESEARCH.md` 14절
참고, 위 "리서치 문서 반영" 참고). 타이머로 몇 초 지났는지 계산하는
대신, 애니메이션 자체에 구간 표시를 심고 블루프린트는 "지금 그 표시가
켜져 있나?"만 확인한다.

**작업이 두 단계로 나뉜다 — 한쪽은 내가, 한쪽은 사용자가:**

1. **`ANS_AttackCancelWindow` 클래스 생성** — `UAnimNotifyState`를
   부모로 하는 새 블루프린트 클래스. MCP `create` 툴로 가능해 보임 —
   내가 진행 가능.
2. **그 표시를 실제 공격/회피 애니메이션 타임라인 위에 드래그해서
   찍기** (`AM_Jab-L`, `AM_Cross-R`, 회피 몽타주 10개 등, 후반부 구간에)
   — 이건 애니메이션 에디터(Persona) UI 안에서 하는 작업이고, MCP
   툴셋 전체를 확인했지만 몽타주/노티파이 편집 툴이 없음. **Enum 생성,
   BlendSpace 조립 때와 같은 종류의 "에디터 UI 전용" 작업으로 보임 —
   사용자가 직접 해야 할 가능성이 높다 (우회 안 함, 확정되면 여기 기록).**

**블루프린트 쪽 변경 계획 (2번이 끝난 뒤 진행):**

- `BP_Player_Combat`에 bool 변수 `bCanCancelCurrentAction` 추가
- 몽타주 재생 시 Notify State의 시작/끝 이벤트를 바인딩해서, 구간이
  열리면 true, 닫히면 false로 설정
- `TryEnterAttack()`/`TryEnterDodge()`의 진입 조건에 `ActionState==
  Locomotion`뿐 아니라 `bCanCancelCurrentAction==true`도 추가 (둘 중
  하나만 참이면 진입 허용)
- 지금 있는 `AttackComboIndex`/`bAttackQueued` 예약 로직은 그대로
  유지 — 취소구간은 "언제부터 그 예약을 받아줄지"를 앞당겨주는
  역할만 추가하는 것이고, 새로 뜯어고치는 게 아니다
- `OnAttackRecoveryTimer`가 완전히 끝났을 때 `Locomotion`으로 복귀하는
  기존 로직은 안 건드림 — 취소구간이 안 열린 채로 애니메이션이 끝까지
  가면 지금과 동일하게 동작

**착수 순서 (사용자 승인 후 진행):**
1. ✔ 완료 (2026-09-03) `ANS_AttackCancelWindow` 클래스 생성 (나)
2. **대기중** — 애니메이션들에 구간 배치 (사용자, 에디터 UI). 이거 없으면
   지금 연결해둔 로직은 항상 "닫혀있음"으로 동작함(구간을 아직 아무
   데도 안 찍었으니까).
3. ✔ 완료 (2026-09-03) 블루프린트 연결 (나). 계획과 실제 구현이 조금
   달라졌음 — 아래 참고.
4. ✔ 완료 (2026-09-03) 사용자가 `AM_Attack1_1`(17~28프레임, 60fps
   기준 0.48초 애니메이션의 58.6% 지점부터)과 `AM_Attack1_2`(29~48
   프레임, 0.82초 애니메이션의 59.2% 지점부터)에
   `ANS_AttackCancelWindow`를 직접 배치·저장. PIE 테스트 결과 딜레이
   체감 개선 확인.

**콤보 트리거 방식 변경 (2026-09-03)**: 취소구간이 정상 작동하는 걸
확인한 뒤, 사용자가 "좌클릭 두 번이 아니라 **한 번 클릭에 1타→2타가
자동으로 이어졌으면 좋겠다**"고 요청 — 원래 계획(1타 재생 중 다시
클릭해야 2타 예약)에서 "누르면 항상 2타까지 자동 콤보"로 단순화.
`TryEnterAttack()`의 `Locomotion`→`Attack` 진입 분기에서
`AttackComboIndex=0` 설정 직후 `bAttackQueued=true`를 **자동으로**
같이 설정하도록 노드 하나 추가(`SetAttackQueued(true)`를 `SetAttackComboIndex`와
`SetActionState(Attack)` 사이에 끼워넣음). 그 결과:
- 좌클릭 1번 → 1타 재생 → 취소구간 열리면 자동으로 2타까지 이어짐
  (별도 클릭 불필요)
- 2타 재생 중 또 클릭하면 여전히 예약은 되지만, 2타가 끝나는 시점엔
  `AttackComboIndex==0` 체크에 걸려 자동으로 `Locomotion` 복귀 —
  기존 "2타 콤보 상한" 설계는 그대로 유지(3타로 안 늘어남).
- 기존 "1타 재생 중 클릭하면 예약" 로직(`else` 분기)은 안 건드림 —
  이제는 사실상 무의미(이미 true라서)하지만 놔둬도 무해함.

**콤보 속도 추가 조정 — "따닥" 손맛 (2026-09-03)**: 자동 콤보로 바꾼
뒤에도 "너무 느리다, 복싱 잽잽처럼 빨랐으면"이라는 피드백. 원인:
1타→2타 전환이 **1타 취소구간이 열리는 시점(58.6%)이 아니라 1타
애니메이션이 완전히 다 끝나는 시점(100%, 재생속도 적용 후 약
0.35초)**에 걸려있었음 — 취소구간은 지금까지 "새 콤보 진입/재입력
허용" 조건에만 관여했지, 1타→2타 전환 타이머 자체와는 무관했음.

**수정**: 새 튜닝 변수 `AttackChainRatio`(float, `CombatTuning`
카테고리, 인스턴스 편집 가능, 기본값 **0.6** — 1타 취소구간 시작
지점인 58.6%와 맞춤) 추가. `TryEnterAttack()`에서 1타 타이머 시간을
계산할 때 `(PlayAnimMontage 반환값 ÷ AttackPlayRate) × AttackChainRatio`로
바꿔서, 1타가 다 끝나기 전에(취소구간이 열리자마자) 2타가 바로
나가도록 함. 컴파일/저장 확인.

**추가로 빠르게 하고 싶으면**: `BP_Player_Combat` 디테일 패널에서
`AttackChainRatio`를 더 낮추면(예: 0.5) 2타가 더 일찍 나가고,
`AttackPlayRate`(현재 1.4)를 올리면 전체 재생 자체가 더 빨라짐 —
둘 다 코드 안 건드리고 바로 조절 가능.

**3번 실제 구현 (계획 대비 변경점, 실제로 해보며 알게 된 것)**:

- **원래 계획한 "OnNotifyBegin/End 델리게이트 바인딩" 대신 "매 틱 폴링"
  방식으로 바꿈.** 이유: 커스텀 노티파이 클래스(`ANS_AttackCancelWindow`)
  안에서 다른 블루프린트(`BP_Player_Combat`)의 변수/함수를 직접
  호출하는 노드를 MCP로 생성하려고 하면 계속 "존재하지 않음" 에러가
  남 — `find_node_types`에는 후보로 뜨는데 `create_node`가 실제로는
  못 만듦. 엔진 기본 함수(예: `GetOwner`)는 문제없이 되는데, 우리가
  만든 블루프린트 함수/변수를 **다른 블루프린트 그래프 안에서** 만드는
  것만 안 됨 — 이 MCP 도구의 한계로 보임 (같은 블루프린트 안에서는
  전혀 문제없이 잘 됨). 그래서 `ANS_AttackCancelWindow`는 그냥 빈
  "이름표" 클래스로만 남겨두고, 대신 `AnimInstance`에 있는
  `WasAnimNotifyStateActiveInAnyState(클래스)` 함수를 매 틱마다 물어보는
  방식으로 바꿨음 — "지금 이 구간이 열려있나?"를 직접 질문하는
  방식이라 델리게이트 바인딩보다 오히려 더 단순함.
- 실제로 만든 것: `BP_Player_Combat`에 `bCanCancelCurrentAction`(bool)
  변수와 `SetCancelWindowOpen(bOpen)` 함수 추가. `Event Tick`의
  `Sequence`에 세 번째 분기를 새로 달아서, 매 틱
  `GetMesh→GetAnimInstance→WasAnimNotifyStateActiveInAnyState
  (ANS_AttackCancelWindow)`의 결과를 `SetCancelWindowOpen`으로 저장.
- `TryEnterAttack()`의 진입 조건을 `ActionState==Locomotion`
  **OR** `bCanCancelCurrentAction==true`로 바꿨음(`ORBoolean` 노드로
  연결). 즉 지금은 **공격 1타→1타 재시작** 케이스에만 해당(같은
  `ANS_AttackCancelWindow`를 검사하니까). **Dodge→공격 전환의 딜레이는
  아직 이걸로 해결 안 됨** — 도지 몽타주엔 이 표시가 안 붙을 거라서.
  이건 별도 판단이 필요한 다음 단계로 남겨둠(도지도 같은 표시를 쓸지,
  `ANS_DodgeCancelWindow`를 따로 만들지는 2번 배치 결과 보고 결정).
- 컴파일 확인, 에러 없음, 저장 완료.

### 잔여 코드 정리 — 완료 (2026-09-03)

"스파게티/잉여 코드 있는지 확인해달라"는 요청으로 EventGraph 전체를
다시 훑어서 실제로 찾음: 이 프로젝트가 언리얼 기본 "3인칭 템플릿"에서
시작해서, **모바일 터치스크린 입력용 노드**가 그대로 남아있었음
(`PrimaryThumbstickEvent`/`SecondaryThumbstickEvent`/`TouchJumpStart`/
`TouchJumpEnd` 등 4개 + 그걸로 Move/Aim을 한 번 더 호출하던 중복 노드
2개). PC 전용 프로젝트라 터치 이벤트는 절대 발동할 일이 없는 완전한
죽은 코드였음 — 전부 삭제. `Jump`/`StopJumping` 자체는 남겨둠(진짜
키보드/게임패드 Jump 입력으로도 연결되어 있어서 죽은 코드 아님, 터치
쪽 연결만 같이 삭제됨). 컴파일 확인, 에러 없음, 저장 완료.

### 아직 안 끝난 것

- **콤보/회피 체이닝 시 딜레이 — 원인 분석 완료 (2026-09-03), 해결은
  취소구간 작업에 위임**: 1타는 정상적으로 보이고 2타로도 이어지지만,
  (a) Dodge 종료 → 공격 시작, (b) 공격 1타 종료 → 공격 1타 재시작
  사이에 "자연스럽게 안 이어지고 딜레이가 있다"는 리포트.

  **분석 방법**: 사용자가 준 PIE 녹화 영상(`Battle - 언리얼 에디터
  2026-09-03 22-46-37.mp4`)을 ffmpeg로 30fps까지 쪼개서 프레임 단위로
  확인 + 실제 코드 수식으로 잠금 시간을 역산.

  **결론 — 애니메이션 문제가 아니라 입력 판정 구조 문제**:
  - 영상 확인 결과 구르기 애니메이션 자체는 약 0.4~0.6초 안에 매끄럽게
    끝남. 중간에 멈추거나 프레임이 끊기는 곳 없음 — 재생 자체는
    정상.
  - 코드의 복귀 타이머 공식으로 역산하면: 구르기 시작 시점부터
    `DodgeBurstDuration(0.08) + (원본길이(≈0.93) -
    DodgeBurstDuration×DodgeBurstRate(3.0)) ÷ DodgePlayRate(1.5)
    ≈ 0.54초` 동안 다음 입력이 원천적으로 안 받아들여짐. 이 자체는
    다른 액션게임 대비 유별나게 긴 시간은 아님.
  - **진짜 문제는 "몇 초냐"가 아니라 그 0.54초 동안 눌린 입력이
    예약도 안 되고 그냥 버려진다는 것.** 애니메이션은 시각적으로 거의
    끝나 보이는데 코드상 잠금은 아직 안 풀린 "화면과 판정의 어긋남"
    구간이 있어서, 그 사이에 누르면 그냥 씹힘 — 이게 "딜레이"로
    느껴지는 정체.
  - **결론: 새로 팔 문제가 아니라, 지금 진행 중인 취소구간(Cancel
    Window) + 입력 버퍼 작업이 곧 이 문제의 정답.** 별도 조사/구현
    불필요.
- **구르기(Roll) 내부 포즈 전환이 단계적으로 튀어 보임 (2026-09-03
  확인, 원인 미확정, 보류 — Roll 모션 다듬기 항목에 통합)**: 시작/끝
  타이밍 문제(위 항목)와는 별개로, **구르기 동작 도중** 포즈와 포즈
  사이 변화량이 너무 커서 회전·무게중심 이동이 연속적이지 않고
  계단식으로 튀어 보인다는 피드백. 다크소울3 참고 영상 대비 우리
  쪽은 회전/무게중심 전환이 매끄럽게 이어지지 않음.
  - 이건 애니메이션 자체(`A_INP_Roll_*`)의 내부 키프레임 문제로
    추정됨 — 아직 구체적으로 진단 안 함. **후보 원인**:
    (a) 원본 애셋이 RootMotion 버전(`A_Roll_*`, 실제 발/무게중심
    이동 포함)과 InPlace 버전(`A_INP_Roll_*`, 제자리 재생용으로
    가공됨)이 따로 있는데, InPlace로 가공하는 과정에서 회전/무게중심
    관련 키프레임이 성기게 남았을 가능성.
    (b) 우리가 쓰는 방식(코드로 위치만 이동시키고 애니메이션은 제자리
    재생)이 "몸이 실제로 회전하며 이동하는" 감각과 "캐릭터가 밀려나는
    이동"이 서로 다른 시계로 돌고 있어서, 포즈 전환은 애니메이션
    자체의 키프레임 타이밍을 그대로 따르는데 위치 이동은 별도의
    이징 커브를 따르다 보니 둘이 안 맞아서 튀어 보이는 것일 수 있음
    (Dodge 설계 문서의 "이동과 애니메이션이 서로 다른 시계로 돈다"는
    문제의 변주일 가능성).
  - 다음에 다룰 때 확인할 것: Persona 에디터에서 `A_INP_Roll_IdleFwd`
    등을 프레임 단위로 스크럽하면서 실제 키프레임 밀도/회전량을
    직접 확인. 필요하면 RootMotion 버전(`A_Roll_*`)의 회전/이동
    곡선과 비교.
- **방금 만든 2단계 배속 시스템(`DodgeBurstRate`/`DodgeBurstDuration`)을
  PIE에서 아직 실제로 테스트 안 함.** RootMotion이 방향별로 제대로
  움직이는지, 배속 전환이 자연스러운지 확인 필요.
- 잔상(고스트) VFX — 손 안 댐.
- 구현 순서 8번(방향 스냅샷 기반 더킹) 자체는 사실상 이번 회피 작업으로
  완료됐다고 볼 수 있음 — 다음 단계인 9번(`Locomotion → Dodge →
  Locomotion` 복귀 검증)부터 마저 검증 필요.

### 리서치 문서 반영 (`SEKIRO_COMBAT_RESEARCH.md`, 2026-09-03 검토)

사용자가 ChatGPT로 정리한 세키로 전투 리서치 문서를 검토한 결과.

**반영 (우리 아키텍처에 실제로 쓸 것)**
- **Anim Notify State 구조** (문서 14절): `ANS_AttackHitbox`,
  `ANS_IFrame`, `ANS_CancelWindow`, `ANS_InputBuffer` 등 — 지금 타이머
  기반(`SetTimerByFunctionName`)으로 구현된 취소 구간을, 애니메이션
  자체에 박힌 Notify State 구간으로 바꾸는 게 맞다는 확신을 줌. 바로
  위 5번 작업의 구체적 구현 방법으로 채택.
- **Raw Root Motion vs Effective Movement 구분** (문서 9절): RootMotion
  원본 이동량과 TAE 배율 적용 후 실제 이동량이 다르다는 개념 —
  우리가 Dodge를 RootMotion에서 코드 기반으로 되돌린 결정(정확한 수치
  튜닝이 필요해서)이 옳았다는 근거로 확인됨. 추가 작업 불필요, 기록만.
- **AttackType별 Evade Mask** (문서 3절): 회피를 `bInvincible=true`
  단순 온오프가 아니라 공격 속성(Normal/Thrust/Sweep 등)별로 판정을
  분리하는 구조 — 나중에 적 공격/피격 시스템 만들 때 참고할 설계
  패턴으로 기록. 지금은 적 공격 자체가 없어서 당장 할 일은 없음.
- **Guard Spam Penalty** (문서 5.2절): 연속 가드 입력마다 판정 윈도우가
  줄어들다가 성공 시 리셋되는 패턴 — 나중에 Guard/Deflect 시스템 만들
  때 참고. 지금은 Guard 자체가 없어서 당장 할 일은 없음.
- **HFSM 구조** (문서 15절) — 우리 `E_ActionState`(Dead/Hit/Dodge/Guard
  /Attack/Locomotion) 설계가 큰 틀에서 합리적이라는 확인 정도. 구조
  변경 불필요.
- **공격 Hitbox 구현 방법 — Socket Sweep** (문서 13절): 검/주먹의
  시작-끝 소켓 사이를 매 틱 Sphere/Capsule 트레이스로 스윕하는 방식.
  지금은 공격에 타격 판정 자체가 없음(애니메이션만 재생) — **나중에
  데미지 시스템 만들 때 쓸 구현 방법**으로 기록. 당장 할 일 없음.
- **공격 데이터 구조 — Data Asset** (문서 16절): `DA_Attack`처럼
  Damage/PostureDamage/AttackType/HitRadius/Knockback 등을 데이터
  애셋으로 분리하는 구조. **나중에 데미지 시스템 만들 때 쓸 설계
  패턴**으로 기록. 당장 할 일 없음.
- **Sprint 방향전환 — Brake Angle** (문서 8절): 스프린트 중 반대
  방향으로 급하게 꺾으면 감속→턴 애니메이션→재가속하는 처리. 지금
  스프린트는 방향 전환 시 그냥 즉시 도는 상태 — **나중에 스프린트
  손맛 다듬을 때 참고**할 아이디어로 기록. 당장 할 일 없음(급하지
  않음).

**버림 (우리 프로젝트에 안 맞음)**
- 세키로 원본 애니메이션 ID(`a000_213300` 등), 정확한 수치(Forward
  Step I-Frame 0.30초, Deflect 0.20초, Walk→Run 0.90 등) — 이건 다른
  게임(세키로)의 다른 캐릭터/리그 기준 수치이고, 문서 자체도 "모딩
  역분석 추정치, 확정 아님"이라고 명시함. 우리는 `UAF_H2HCombat`/
  `Roll_Dodge_Dash_Set` 등 완전히 다른 에셋을 쓰고 있어서 숫자를 그대로
  가져오는 건 의미 없음 — 문서 18절이 스스로도 경고하는 "Sekiro
  Reference를 그대로 복제하지 말 것" 원칙과 같은 맥락.
- Jump 회피 판정(문서 4절) — 우리는 Jump 시스템 자체가 없음.
- Sprint Guard(문서 6절) — Guard 시스템 자체가 없음.
- 세키로 공격 애니메이션 ID(문서 12절) — 우리 것 아님.
- **Walk→Run 입력 임계값/Hysteresis** (문서 7절): 아날로그 스틱
  기울기(0.75/0.90/0.70)를 기준으로 한 판정 — 우리는 아날로그 이동
  입력 자체가 없고 키보드(WASD, 이동은 항상 최대치) + Shift 홀드로
  Sprint on/off만 하는 완전히 다른 입력 구조라서 해당 없음.
- Step 계측 대상 목록(문서 11절), 다음 조사 우선순위(문서 19절), 참고
  자료 링크(문서 20절) — 세키로 원본 애니메이션을 실측하기 위한
  방법론/일정으로, 우리 애셋에는 적용 대상이 없음.

**검토 결과**: 문서 20개 절 전부 대조 완료. 채택 6개 / 미래 참고용
3개(Hitbox, Data Asset, Sprint Brake) / 버림 6개(우리 애셋과 무관한
수치·ID·방법론). 빠진 항목 없음 확인 (2026-09-03 재검증).

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
│  │  ├─ Walk    (기본)
│  │  └─ Sprint  (Shift 홀드)
│  └─ CombatAction
│     ├─ Dodge     (자유 모션)
│     ├─ Guard     (자유 모션)
│     └─ Attack    (자유 모션)
│
├─ LockOn
│  ├─ CombatIdle
│  ├─ CombatMove8Dir
│  │  ├─ Trot    (기본)
│  │  └─ Sprint  (Shift 홀드)
│  └─ CombatAction
│     ├─ Dodge     (복싱 모션)
│     ├─ Guard     (복싱 모션)
│     └─ Attack    (복싱 모션)
│
└─ Global
   ├─ Hit
   └─ Dead
```

`Move`/`CombatMove8Dir` 밑의 `Walk`·`Sprint`(`Trot`·`Sprint`)는 **그림
표현일 뿐, 별도 `ActionState` 값이 아니다** — 아래 "세 번째 독립 축"
참고.

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

### 세 번째 독립 축 — Sprint

`bIsSprinting`(Boolean)은 `ActionState`에 넣지 않는다. "지금 뭘 하는가"가
아니라 "얼마나 빠르게 움직이는가"라서, `MovementMode`/`ActionState`와
마찬가지로 완전히 독립된 축으로 둔다. `Free`/`LockOn` 어디서든 켜질 수
있다 (락온 중에도 달리기 가능 — 확정 사항).

```text
Shift 키 하나를 두 입력으로 분리
├─ Tap  (0.2초 이내 뗌) → IA_Dodge  → ActionState = Dodge
└─ Hold (0.2초 이상 유지) → IA_Sprint → bIsSprinting = true (뗄 때까지)
```

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
│  ├─ ABP_Player_Combat            ✔ 완료 (ABP_Unarmed 복제 + AnimGraph 연결)
│  ├─ BlendSpaces
│  │  ├─ BS_Player_FreeMove        ← 아직 (Free는 템플릿 BS_Idle_Walk_Run 그대로 사용 중)
│  │  └─ BS_Player_LockOn8Dir      ✔ 완료 (Direction -180~180, 8분할)
│  ├─ Montages
│  │  ├─ AM_Player_Dodge_B/_L/_R   ← 아직 조립 전, 원본 준비됨 (F 없음)
│  └─ Notifies                     ← 아직
│
├─ Input
│  ├─ IA_Dodge                     ✔ 완료 (Left Shift, Tap 0.2초)
│  ├─ IA_Sprint                    ✔ 완료 (Left Shift, Hold 0.25초)
│  ├─ IA_LockOn                    ✔ 완료 (Middle Mouse Button)
│  └─ IMC_Player_Combat            ✔ 완료
│
├─ Data
│  └─ DA_PlayerCombatTuning        ← 아직
│
└─ Debug                           ← 아직
```

**원본 애니메이션 소스**는 `/Game/BossArena/Animations`에 있다 (Player 폴더
밖 — 사용자가 임포트한 원본 팩 위치, 위 규칙의 예외로 둔다).

```text
/Game/BossArena/Animations
├─ Dodge/   AM_Dodge-B/L/R, AS_Dodge-B/L/R   (우리 스켈레톤으로 리타겟 완료)
└─ Trot/    AS_Trot-F/FL/FR/R/BR/B/BL/L      (8방향, 리타겟 완료)
```

여기서 `BS_Player_LockOn8Dir`, `AM_Player_Dodge_*` 몽타주를 조립해서
`Player/Animation/`에 최종본을 만든다.

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
7. 락온 전투 Idle과 8방향 이동 연결 + Sprint(Shift Tap/Hold 분리) — ✔
   완료 (BS_Player_LockOn8Dir + ABP_Player_Combat)
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
- **Sprint(달리기)는 Free/LockOn 양쪽에서 전부 가능하다** (확정, 락온 중에도
  달릴 수 있어야 함). `ActionState`엔 안 넣고 `bIsSprinting`(Boolean)으로
  독립 관리한다. `Shift`를 짧게 탭하면 `Dodge`, 길게 홀드하면 `Sprint` —
  같은 물리 키를 Tap/Hold 트리거로 구분해서 쓴다 (구현 순서 7번에서 같이
  작업).
- 마켓플레이스에서 임포트한 애니메이션은 스켈레톤이 달라도(본 이름이
  같으면) 언리얼 버전 차이와 무관하게 "리타겟 스켈레톤"으로 바로 쓸 수
  있다. Dodge(B/L/R)·Trot(8방향) 완료. Dodge Forward, Sprint 전용
  애니메이션은 아직 없음 — 필요해지면 그때 다시 다룬다.
- **애셋 파이프라인 작업(리타게팅, FBX 임포트 설정, 스켈레톤 지정, Enum·
  BlendSpace 생성, AnimGraph 편집)은 사용자가 직접 한다.** 막히면
  우회하지 말고 **필요한 작업(원본 경로 / 대상 스켈레톤 / 배치 폴더)을
  명확히 보고하고 대기**한다. 편법으로 돌아가서 "일단 돌아가게" 만드는
  것은 막힌 상태로 두는 것보다 나쁜 결과다 — 실제 파이프라인 단계를
  숨기게 되고, 이 프로젝트는 그 구조를 설명할 수 있어야 하는 포트폴리오다.
  (2026-09-02 실제 사례: 공격 애니메이션 스켈레톤 불일치를 보고하지 않고
  `CompatibleSkeletons`에 등록해서 우회 → 되돌림.)
- **작업한 내용은 매번 사용자에게 보고한다.** 어떤 노드/변수를 왜
  추가·삭제·변경했는지 쉬운 한국어로 그때그때 알린다 — 나중에 요약만
  던지면 구조를 따라올 수 없고, 면접에서 설명할 수 없게 된다.
