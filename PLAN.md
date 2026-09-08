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

## 진행 상황 (2026-09-07 기준)

전투 코어(락온 / 회피 / 4타 콤보 + 입력 버퍼)까지 구현 완료. 남은 건
가드·히트박스·연출.

```
[기반]
✔ BP_Player_Combat / BP_PlayerController_Combat / BP_BossArenaGameMode
✔ Lvl_Arena_01 시작 맵 지정, PIE 스폰 확인
✔ IA_Move / IA_Look / IA_Sprint / IA_Dodge / IA_LockOn / IA_Attack + IMC
✔ E_PlayerMovementMode / E_ActionState

[이동 · 락온]
✔ ToggleLockOn — Free⇄LockOn 전환, BP_TrainingDummy를 타겟으로 저장
✔ UpdateLockOnRotation — 몸통 RInterpTo, bOrientRotationToMovement 자동 전환
✔ 락온 카메라 동조 — ControlRotation Yaw 추종, Pitch는 마우스 유지
✔ Sprint — Shift Hold(0.25초)/Tap(0.2초) 트리거 분리, 600↔900
✔ BS_Player_LockOn8Dir (에디터 UI 제작) + ABP_Player_Combat 2단 블렌드

[회피]
✔ Dodge (락온용) — A_INP_Dodge_01_* 10종, InPlace + 코드 이동
✔ Roll (Free용) — A_Roll_Idle* 8방향, RootMotion (2026-09-07 전환)
✔ 2단계 배속 — DodgeBurstRate(초반 3배) → DodgePlayRate
✔ 방향 판정 트리 — CalculateDirection 각도 → 8방향 Select 체인
✔ 회피 쿨타임 — DodgeCooldown, 복귀 시점부터 카운트 (2026-09-07)

[공격]
✔ 4타 콤보 — AttackMontages 배열 소비 방식, 좌클릭 1회 = 1타
✔ 세키로식 입력 버퍼 — bAttackBuffered / bComboWindowOpen,
  콤보 창(ComboWindowRatio 0.55) 이전 입력도 버퍼링 후 자동 발동
✔ OnComboWindowOpen / OnAttackRecoveryTimer 타이머 체계

[상태 제약]
✔ 공중(점프 중) 회피·공격 차단 — IsFalling 게이트 (2026-09-07)

[전투 판정]
✔ 히트박스 · 데미지 — ApplyRadialDamage 구체 판정, 몽타주 진행률 기준
✔ BP_TrainingDummy 체력 / 피격 / 자동 리셋
✔ 플레이어 체력 + 피격 처리

[가드]
✔ 가드(Block) — AS_Block, 홀드 방식, 데미지 감쇄
✖ IMC_Player_Combat에 IA_Block 키 바인딩 필요 (에디터에서 직접)

[체력 · 스태미나 · UI]
✔ 플레이어 체력 320 / 스태미나 120 (DS3·세키로 수치 기반)
✔ 스태미나 소모(회피 13 / 공격 18) · 지연 후 선형 재생(45/초)
✔ WBP_PlayerHUD — 좌하단 체력/스태미나 바 + 9-slice 프레임 + 지연 데미지 바
✔ 공격 히트 이펙트 (ParagonCrunch 임팩트)
✔ 플레이어 사망 처리 (체력 0 → Dead → 입력 차단)

✔ 무적 프레임 0.433초 (DS3 미들롤 13프레임)
✔ 퍼펙트 회피 판정 + 잔상(고스트) VFX 3연속
✔ 가드 중 하체 로코모션 (상체만 블렌딩)

[남은 것]
← 보스 AI (HFSM + Utility AI + GOAP) + 홀로그램 디버그 패널  ★ 포트폴리오 메인
← 패링(가드 초반 프레임 = 퍼펙트 가드)
← 히트스톱 · 피격 리액션 애니메이션
← 방향 스냅샷 기반 더킹
← 잔상(고스트) VFX, 카메라 연출
← 보스 AI (공격이 있어야 가드/체력이 실제로 검증됨)
```

4타 전부 스켈레톤 리타게팅 완료 확인 (2026-09-07). 다만 `AM_Attack1_2`/
`AM_Attack1_3` 몽타주는 BossArena의 `AS_Attack1_2`/`_3`이 아니라 UAF 원본
(`AS_Cross-R` / `AS_Hook-L`)을 참조한다. 원본도 우리 스켈레톤으로
리타게팅돼 있어 재생에는 문제 없지만, BossArena 쪽 사본 2개는 아무도
참조하지 않는 상태다 — 정리 대상.

### (이력) 2026-09-01 시점 체크리스트

기반 공사 + 락온 토글까지 끝났던 시점의 기록.

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

### Roll을 RootMotion 세트로 전환 (2026-09-07)

"구르기가 딱딱 끊긴다"는 피드백의 원인 중 하나가 **InPlace 애니메이션 +
코드 이동**이라는 이원 구조였다 (포즈와 위치가 서로 다른 곡선으로 움직여서
발이 미끄러짐). 이를 없애기 위해 Free 모드 회피(Roll) 8방향을
**RootMotion 세트로 교체**했다.

| | 이전 | 현재 |
|---|---|---|
| 애셋 | `A_INP_Roll_Idle*` (InPlace) | `A_Roll_Idle*` (RootMotion) |
| 위치 이동 | Tick의 `SetActorLocation` (`DodgeDistance` 350cm) | 애니메이션에 구워진 루트 이동 |
| 발 미끄러짐 | 있음 | 없음 |
| 거리 조절 | 숫자로 자유롭게 | **불가 (아래 참고)** |

**작업 내역**
1. `/Game/Roll_Dodge_Dash_Set/SourceFiles/fbx/RootMotion/Mannequin/Roll/`의
   8개를 `/Game/BossArena/Animations/Roll/`로 이동. 스켈레톤은 이미
   프로젝트 것(`/Game/Characters/Mannequins/Meshes/SK_Mannequin`)이라
   리타게팅 불필요했음.
2. 8개 전부 `bEnableRootMotion = true`로 설정 (임포트 직후 기본 꺼짐 —
   위 "알아둘 것"에 기록된 함정. 이번에도 그대로 재현됨).
3. `TryEnterDodge`의 Roll 8개 리프 노드 애셋 경로만 교체. 방향 판정
   트리(각도 임계값, Select 체인)는 손대지 않음.
4. **코드 이동 차단**: `SetDodgeMoveDuration` 앞에
   `SelectFloat(A=기존계산값, B=0.0, bPickA=EnumEquality_1)`을 삽입.
   `EnumEquality_1`은 "MovementMode == LockOn" 판정으로, Roll 트리와
   Dodge 트리를 고르는 데 이미 쓰이던 노드를 재사용한 것.
   - LockOn(Dodge, InPlace) → 기존 코드 이동 그대로
   - Free(Roll, RootMotion) → `DodgeMoveDuration = 0` → Tick의
     `DodgeMoveElapsed < DodgeMoveDuration`이 항상 false → 코드 이동 없음
   - 이걸 안 하면 루트모션과 코드 이동이 **동시에** 적용돼 두 배로 날아간다.
5. `RootMotionMode`는 `ABP_Player_Combat`에 이미
   `RootMotionFromMontagesOnly`로 설정돼 있었고,
   `PlaySlotAnimationAsDynamicMontage`는 실제 몽타주를 만들므로 그대로 동작.

**RootMotion 이동 거리 실측 (원본 FBX의 root 본 트랜슬레이션 커브 파싱)**

| 애니메이션 | 수평 이동 |
|---|---|
| `A_Roll_IdleFwd` | 459.5 cm |
| `A_Roll_IdleFwdLt_45` / `Rt_45` | 459.4 / 459.5 cm |
| `A_Roll_IdleFwdLt_90` / `Rt_90` | 460.1 cm |
| `A_Roll_IdleBwd` | 427.7 cm |
| `A_Roll_IdleBwdLt_135` / `Rt_135` | 427.5 cm |

8방향이 거의 균일하다 (427~460cm, 전부 1.0초). 기존 코드 이동값
`DodgeDistance = 350cm`보다 **약 31% 더 멀다.**

**이동 거리를 줄일 수 없는 이유 (확정)**

UE 5.8 블루프린트에는 `SetAnimRootMotionTranslationScale` 노드가 **없다.**
- `find_node_types`로 `RootMotion` / `AnimRootMotion` / `TranslationScale`
  전부 검색 → `애니메이션|GetAnimRootMotionTranslationScale` (게터)만 존재.
- `ACharacter::AnimRootMotionTranslationScale` 프로퍼티도 CDO에서
  읽기/쓰기 모두 실패 (`could not be read` / `could not be set`).
- 이 프로젝트 PLAN의 2026-09-03 기록("읽기 전용이라 배율 조절 불가")이
  맞았다는 게 재확인됨.

남은 방법은 **애셋에 직접 굽는 것** 하나뿐이다:
`AnimationModifier` → `GetController` + `OpenBracket` →
`GetDataModelInterface` → `GetBoneTrackByName("root")` →
포지션 키 배열을 배율로 스케일 → `SetBoneTrackKeys` → `CloseBracket`.
(필요한 노드가 전부 존재하는 것은 확인함.)

**단, 이 방법은 트레이드오프가 있다.** 루트 키를 0.7배로 줄이면 포즈는
"460cm 굴렀다"고 말하는데 실제로는 322cm만 가므로, **RootMotion으로
없앴던 발 미끄러짐이 30%만큼 그대로 되돌아온다.** 즉 거리를 줄이는 순간
RootMotion 전환의 이득 일부를 반납하는 셈. 그래서 먼저 100%(460cm)로
체감해보고 결정하는 것이 맞다.

**남은 것**
- `A_INP_Roll_Idle*` 8개는 이제 아무 데서도 참조되지 않는다 (롤백 대비로
  일단 남겨둠). 확정되면 삭제.
- 거리 축소가 필요하다고 결론나면 위 AnimationModifier를 만든다.
  적용은 콘텐츠 브라우저에서 수동이며, **두 번 적용하면 0.49배로 겹친다**는
  점을 주의.

### 상태 제약 — 공중 차단 + 회피 쿨타임 (2026-09-07)

#### 1. 점프 중 회피·공격 차단

캐릭터가 공중에 떠 있는 동안(점프, 낙하, 턱에서 걸어나감 전부 포함)
회피와 공격이 나가지 않도록 함수 진입부에 게이트를 달았다.

판정은 `GetCharacterMovement → IsFalling`. `IsFalling`은 점프해서
올라가는 중과 떨어지는 중을 모두 true로 잡으므로 "발이 땅에 안 닿아
있으면 못 한다"는 의도와 정확히 맞는다.

- **`TryEnterAttack`**: `FunctionEntry → Branch(IsFalling)`
  - `then`(공중) → 아무 데도 안 감 = 공격 취소
  - `else`(지상) → 기존 `IfThenElse_0`(ActionState 판정)로 그대로 이어짐
- **`TryEnterDodge`**: 같은 방식 + 쿨타임 판정까지 2단
  ```
  FunctionEntry
    → Branch(IsFalling)          then=차단 / else↓
      → Branch(bDodgeOnCooldown) then=차단 / else↓
        → 기존 IfThenElse_0 → SetActionState(Dodge) → ...
  ```

`Not`/`And` 노드를 쓰지 않고 **Branch의 `else` 핀을 통과 경로로** 쓴 이유:
이 프로젝트의 MCP 도구로는 프로모터블 연산자 노드(`Not`, `And` 등) 생성이
막혀 있다 (아래 "MCP 제약" 참고). Branch 두 개를 세로로 잇는 게
노드 수도 같고 그래프에서 읽기도 더 쉽다.

#### 2. 회피 쿨타임

연타로 구르기를 도배하는 걸 막는다.

| 변수 | 카테고리 | 의미 | 초기값 |
|---|---|---|---|
| `DodgeCooldown` | CombatTuning (Instance Editable) | 회피가 끝난 뒤 다시 회피 가능해지기까지 (초) | 0.25 |
| `bDodgeOnCooldown` | Combat State | 지금 쿨타임 중인지 | false |

**카운트 시작 지점을 "회피 시작"이 아니라 "회피 복귀"로 잡았다.**
회피 재생 시간은 `DodgePlayRate`/`DodgeBurstRate`를 만질 때마다 달라지는데,
시작 기준으로 잡으면 쿨타임 값이 재생 시간보다 짧아지는 순간 아무 효과도
없어진다. 복귀 기준이면 `DodgeCooldown`이 그대로 "구르고 나서 쉬는 시간"이라
배속을 어떻게 바꾸든 의미가 변하지 않는다.

흐름:
```
OnDodgeRecoveryTimer (기존)
  → SetActionState(Locomotion)      (기존)
  → SetbDodgeOnCooldown(true)       (신규)
  → SetTimerByFunctionName("OnDodgeCooldownEnd", DodgeCooldown)  (신규)

OnDodgeCooldownEnd (신규 커스텀 이벤트)
  → SetbDodgeOnCooldown(false)
```

튜닝은 디테일 패널의 CombatTuning에서 `DodgeCooldown` 숫자만 바꾸면 된다.
0으로 두면 쿨타임 없음(이전 동작)과 같다.

## 히트박스 · 데미지 (2026-09-07)

### 판정 방식 — 구체 하나, 타이머로 발동

무기가 없는 맨손 전투라 무기 궤적 트레이스 대신 **캐릭터 앞쪽에 구체를
하나 띄우고 그 안의 액터에게 데미지**를 준다. `ApplyRadialDamage` 노드
하나가 구체 오버랩 + `TakeDamage` 호출까지 다 해준다.

발동 시점은 **몽타주 진행률 기준 타이머**다. AnimNotify를 쓰지 않는 이유:
이 프로젝트는 이미 콤보 창(`OnComboWindowOpen`)과 복귀(`OnAttackRecoveryTimer`)를
전부 `SetTimerByFunctionName`으로 처리하고 있어서, 판정만 노티파이로 가면
타이밍 관리가 두 군데로 쪼개진다. 4개 몽타주에 노티파이를 일일이 찍는
수작업도 없어진다.

```
StartComboStep
  → PlayAnimMontage
  → SetTimer("OnComboWindowOpen",   길이/배속 × ComboWindowRatio)   기존
  → SetTimer("OnAttackRecoveryTimer", 길이/배속)                     기존
  → SetTimer("OnAttackHitCheck",     길이/배속 × AttackHitRatio)     신규
```

`OnAttackHitCheck` → `DoAttackHitCheck()`:

```
Branch(ActionState == Attack)        ← 회피 등으로 취소됐으면 판정 무효
  → ApplyRadialDamage(
       BaseDamage  = AttackDamage,
       Origin      = TransformLocation(액터 트랜스폼, (AttackHitRange,0,0)),
       DamageRadius= AttackHitRadius,
       DamageCauser= self, InstigatedByController = GetController,
       bDoFullDamage = true)
  → Branch(bShowHitDebug) → DrawDebugSphere (판정 구체를 눈으로 확인)
```

`Origin`을 `위치 + 앞방향×거리`로 계산하지 않고 **`TransformLocation`으로
로컬 오프셋을 월드로 변환**했다. MCP로는 `vector+vector` / `vector*float`
같은 프로모터블 연산자 노드를 만들 수 없어서인데, 결과적으로 노드 3개가
1개로 줄어 더 깔끔하다.

| 변수 (CombatTuning) | 의미 | 초기값 |
|---|---|---|
| `AttackDamage` | 한 대 데미지 | 12 |
| `AttackHitRange` | 캐릭터 앞 판정 중심까지 거리 (cm) | 130 |
| `AttackHitRadius` | 판정 구 반지름 (cm) | 85 |
| `AttackHitRatio` | 애니메이션 몇 % 지점에서 판정할지 | 0.35 |
| `bShowHitDebug` | 판정 구체를 화면에 그릴지 | true |

### 체력 처리 — 뺄셈 노드 없이 빼기

MCP로 `float-float` 노드를 만들 수 없어서 이렇게 우회했다:

```
새체력 = Clamp( Lerp(현재체력, 0, SafeDivide(데미지, 현재체력)), 0, 최대체력 )
```

`Lerp(A,B,t) = A + (B-A)·t` 이므로 `B=0`, `t=데미지/현재체력`을 넣으면
정확히 `현재체력 - 데미지`가 된다. `SafeDivide`라 현재체력이 0이어도
0으로 나누기 사고가 안 난다.

- **BP_TrainingDummy**: `MaxHealth` 200 / `CurrentHealth`.
  `BeginPlay`에서 초기화, `Event AnyDamage`에서 차감 후 화면에 HP 출력,
  0이 되면 "DUMMY DOWN" 출력 후 2초 뒤 `ResetDummy`로 체력 복구
  (테스트를 계속 하려면 죽고 끝나는 것보다 리셋이 낫다).
  메시는 `/Engine/BasicShapes/Cylinder`라 기본 콜리전이 있어 그대로 맞는다.
- **BP_Player_Combat**: `MaxHealth` 100 / `CurrentHealth`. 아직 플레이어를
  때리는 것이 없어서 검증은 보스 AI가 생긴 뒤에 가능하다.

## 가드(Block) (2026-09-07)

`/Game/BossArena/Animations/AS_Block` (3.92초, 우리 스켈레톤) 사용.
**홀드 방식** — 누르고 있는 동안 막고, 떼면 풀린다.

```
IA_Block Started   → TryEnterBlock()
IA_Block Completed → ExitBlock()
```

`TryEnterBlock`
```
Branch(IsFalling)                  then=차단
  else → Branch(ActionState == Locomotion)   then↓
    → ActionState = Guard
    → PlaySlotAnimationAsDynamicMontage(AS_Block, 'DefaultSlot',
         BlendIn 0.15 / BlendOut 0.25, LoopCount 999)
    → ActiveBlockMontage = 반환된 몽타주
```

`ExitBlock`
```
Branch(ActionState == Guard)       ← 구르기 등으로 이미 상태가 바뀌었으면 아무것도 안 함
  → MontageStop(ActiveBlockMontage, BlendOut 0.25)
  → ActionState = Locomotion
```

애님 그래프(`ABP_Player_Combat`)는 **건드리지 않았다.** 회피·공격과 똑같이
`DefaultSlot` 몽타주로 재생한다. 예전에 애님 그래프에 `LayeredBoneBlend`를
넣었다가 공격이 통째로 죽은 사고가 있어서, 상태 추가는 전부 몽타주 슬롯
방식으로 통일한다.

### 데미지 감쇄

`Event AnyDamage`에서:
```
받는데미지 = SelectFloat(
    A = Lerp(0, 원래데미지, BlockDamageMultiplier),   ← 가드 중
    B = 원래데미지,                                    ← 평상시
    bPickA = (ActionState == Guard))
```
`Lerp(0, X, m) = X·m`이다 — 여기도 곱하기 노드를 못 만들어서 쓴 우회.

| 변수 (CombatTuning) | 의미 | 초기값 |
|---|---|---|
| `MaxHealth` | 플레이어 최대 체력 | 100 |
| `BlockDamageMultiplier` | 가드 중 받는 데미지 배율 | 0.2 |

**한계 (의도적으로 안 넣음)**
- **방향 판정 없음** — 지금은 뒤에서 맞아도 막힌다. 정면 각도 체크는
  공격해오는 상대가 생긴 뒤에 붙이는 게 맞다.
- **패링 없음** — 가드 진입 직후 몇 프레임을 퍼펙트 가드로 치는 건
  다음 단계.
- **스태미나/포이즈 없음.**

### 남은 수동 작업 (에디터에서 직접)

`IA_Block`은 만들어서 블루프린트에 다 연결해놨지만, **`IMC_Player_Combat`에
키 바인딩만 사용자가 직접 넣어야 한다** (우클릭 권장).
MCP로 `Mappings`를 읽으면 2개만 나오는데 저장된 애셋에는 4개가 들어 있다 —
읽기 결과가 실제와 달라서, 그대로 덮어쓰면 기존 공격/스프린트 바인딩이
날아간다. 그래서 자동화하지 않았다.

## 체력 · 스태미나 수치 근거 (2026-09-07)

레퍼런스 게임의 실제 수치를 찾아서 맞췄다.

| 출처 | 수치 |
|---|---|
| 세키로 | 기본 체력 320, 체력력 1당 +80 (최대 1120). 스태미나 바 자체가 없고 체간(Posture)이 그 자리를 대신함 |
| 다크소울3 | 스태미나 지구력 11에서 95, 40에서 소프트캡 160, 최대 170. 재생 45/초. 무기 약공격 17.5~19.5 소모 |

세키로엔 스태미나가 없고 다크소울엔 체간이 없어서, **체력은 세키로의
기본값(320), 스태미나는 다크소울3 초반 캐릭터 수준(120)**으로 잡았다.
소모값은 다크소울3의 약공격 17.5~19.5를 반올림해서 공격 18,
회피는 그보다 살짝 비싸게 22로 뒀다 (회피를 남발하지 못하게).

| 변수 (CombatTuning) | 값 | 근거 |
|---|---|---|
| `MaxHealth` | 320 | 세키로 기본 체력 |
| `MaxStamina` | 120 | 다크소울3 초반 지구력 구간 |
| `StaminaRegenRate` | 45 | 다크소울3 표준 재생 45/초 |
| `StaminaRegenDelay` | 0.6 | 소모 직후 재생이 바로 안 붙게 |
| `AttackStaminaCost` | 18 | 다크소울3 직검 약공격 17.5 (검증됨) |
| `DodgeStaminaCost` | 13 | 아래 "구르기 비용 조사" 참고 |

#### 구르기 비용 조사 (2026-09-07) — 검증된 것과 아닌 것을 구분

**검증된 수치**
| 항목 | 값 | 출처 |
|---|---|---|
| 스태미나 재생 | 45/초 (장비하중 69.9% 초과 시 37/초) | DS3 위키 · 메커니즘 치트시트 |
| 스태미나 총량 | 지구력 11에서 95, 40에서 소프트캡 160, 최대 170 | DS3 위키 |
| 직검 1H R1 소모 | 브로드소드 17.5 / 다크소드 19.5 | 유저 실측 (총량 118에서 6타 후 1 남음 방식) |
| "1포인트만 있어도 행동은 나감" | 사양 | 메커니즘 치트시트 |

**검증 못 한 것 — 구르기 비용**
데이터마이닝된 정확한 수치가 공개 자료에 없다. 확인 가능한 것은 두 가지뿐:
- 커뮤니티 실측 추정 "**총 스태미나의 약 10%**"
- 구르기가 **약공격보다 확실히 싸다** — 스팀 토론에서 "구르기 비용이
  너무 낮다, R1 공격과 비슷해야 한다"는 불만이 반복적으로 제기됨

즉 DS3에서 구르기는 공격보다 싸고, 그게 롤 스팸을 조장한다는 게
**알려진 밸런스 결함**이다.

**우리 선택: 13 (DS3 충실)**
총량 120의 약 10% + "공격보다 싸다"는 두 조건을 모두 만족한다.
포트폴리오에서는 "레퍼런스를 그대로 맞췄고, 그 레퍼런스의 알려진 결함도
파악하고 있다"고 설명할 수 있는 쪽이 낫다고 판단했다.

**대안 (롤 스팸을 막고 싶다면): 20**
공격(18)보다 살짝 비싸게 만들어 "구르기는 공짜가 아니다"를 만드는 값.
DS3와는 다른 선택이지만 세키로/블러드본 쪽 설계 철학에 가깝다.
`DodgeStaminaCost` 하나만 바꾸면 되므로 언제든 전환 가능.

### 구현

- **재생**: Tick에서 `FInterpToConstant(현재, 최대, DeltaTime, 재생속도)`.
  이름 그대로 초당 일정량이라 "45/초"가 그대로 들어간다.
- **재생 지연**: 타이머 방식. 스태미나를 쓰면 `bStaminaRegenBlocked = true` +
  `SetTimer("OnStaminaRegenResume", 0.6)`. 같은 함수명으로 타이머를 다시
  걸면 기존 타이머가 갱신되므로, 연타하면 지연도 계속 밀린다.
- **소모**: `SpendStamina(Cost)` 함수. 체력과 같은
  `Clamp(Lerp(현재,0,SafeDivide(Cost,현재)),0,최대)` 우회를 쓴다.
- **판정**: `HasStamina(Cost)` 함수 —
  `InRange(Value=Cost, Min=0, Max=현재스태미나)`.
  `>=` 노드를 만들 수 없어서 InRange로 대체했다 (Cost가 0~현재 사이면
  충분하다는 뜻이라 의미가 같다).
- **게이트**: `TryEnterDodge` / `TryEnterAttack`의 공중 판정 다음에
  `HasStamina` 분기를 넣었다. 소모는 실제 발동 지점
  (`SetActionState(Dodge)` 직후 / `StartComboStep` 진입)에서 한다 —
  콤보 4타면 4번 소모된다.

## HUD — WBP_PlayerHUD (2026-09-07)

`/Game/BossArena/UI/WBP_PlayerHUD`. 좌하단에 체력(빨강) / 스태미나(초록)
프로그레스 바 2개.

- 앵커 좌하단(0,1), 정렬(0,1), 왼쪽 40px
- 체력 바: 아래에서 74px, 300×26 / 스태미나 바: 40px, 300×18
- `Event Tick` → `GetOwningPlayerPawn` → `Cast To BP_Player_Combat` →
  `HealthBar.SetPercent(SafeDivide(CurrentHealth, MaxHealth))` →
  `StaminaBar.SetPercent(SafeDivide(CurrentStamina, MaxStamina))`
- `BP_Player_Combat`의 BeginPlay에서 `CreateWidget` → `AddToViewport`

바인딩(Binding) 대신 Tick에서 갱신하는 이유: 바인딩은 매 프레임 도는 건
같은데 그래프가 위젯 안에 숨어서 디버깅이 어렵다. Tick 한 줄이 더 읽기 쉽다.

## 공격 이펙트 · 사거리 (2026-09-07)

### 사거리 축소

주먹인데 사거리가 길다는 피드백 → `AttackHitRange` 130 → **70**,
`AttackHitRadius` 85 → **50**. 판정 구체가 캐릭터 중심에서 앞으로 70cm,
반지름 50cm이므로 최대 도달거리 120cm. 사람 팔 뻗은 길이에 가깝다.
`bShowHitDebug`로 구체가 보이니 더미 앞에 서서 눈으로 맞추면 된다.

### 이펙트 — 프로젝트에 이미 있는 것을 씀

`/Game/ParagonCrunch/FX/Particles/Abilities/` — Paragon의 **크런치**가
복싱 캐릭터라 맨손 격투 이펙트가 통째로 들어있다. 새로 받을 필요가 없었다.

| 에셋 | 용도 |
|---|---|
| `P_Crunch_Primary_Impact` | 기본 펀치 히트 (현재 연결됨) |
| `P_Crunch_Cross_Enemy_Impact` | 2타(크로스)용 |
| `P_Crunch_Hook_Enemy_Impact` | 3타(훅)용 |
| `P_Crunch_Uppercut_Impact` / `GutPunch_Impact` | 4타용 |
| `P_Crunch_Hook_3D_Trail` / `UpperCut_3D_Trail` | 주먹 궤적 트레일 |

전부 Cascade(`ParticleSystem`)라 `SpawnEmitterAtLocation`으로 재생한다.

연결 방식: `ApplyRadialDamage`의 반환값(뭔가 맞았는지)이 true일 때만
`HitImpactFX`를 판정 구체 위치에 스폰한다. **허공을 치면 안 나온다.**
`HitImpactFX`는 CombatTuning의 인스턴스 편집 가능 변수라 디테일 패널에서
다른 이펙트로 바꿔 끼울 수 있다.

무료 대안(더 필요할 때): Epic이 Fab에 올린 **Niagara Examples Pack**
(50종 이상, UE5.7용, 무료) — 임팩트·스파크·트레일·히트 디졸브 포함.

## 가드 중 이동 (2026-09-07)

`Move` 함수가 `ActionState == Locomotion`일 때만 이동 입력을 받고 있어서
가드 중엔 움직일 수 없었다. `Locomotion` 분기의 `else`에 `Guard` 판정
분기를 하나 더 달아, 둘 중 하나면 같은 `AddMovementInput` 체인으로
들어가게 했다 (`Or` 노드를 못 만들어서 분기 2단으로 처리).

이동 속도는 `TryEnterBlock`에서 `MaxWalkSpeed = BlockWalkSpeed(220)`,
`ExitBlock`에서 `BaseWalkSpeed(600)`로 복구한다.

### 아직 남은 것 — 상체만 블록

지금 `AS_Block`은 `DefaultSlot`에 전신으로 재생되므로, **가드하며 걸으면
다리가 안 움직이고 미끄러진다.** 제대로 하려면 애님 그래프에
`LayeredBoneBlend`를 넣어 `spine_01` 위쪽만 블록 포즈로 덮고 하체는
로코모션을 유지해야 한다.

```
StateMachine → Slot 'DefaultSlot' ─┬─→ LayeredBoneBlend ─→ ControlRig → Root
                                   │      Base ←┘
                                   └─→ Slot 'UpperBody' ─→ Blend Pose 0
                                          (BlendDepth: spine_01 = 0)
```

**주의**: 예전에 이 작업을 하다 공격이 통째로 죽은 적이 있다.
원인은 `BlendDepth`를 `-1`로 준 것 — 음수는 해당 본 가지를 블렌드에서
**빼버리기** 때문에 상체가 통째로 0 가중치가 됐다. 반드시 `0`을 써야 한다
(0 = 해당 본과 그 자식 전부 100% 가중치).

## 회피 성공 VFX — 설계 (2026-09-07)

### 무엇을 "성공"으로 볼 것인가

지금 회피는 무적 프레임(i-frame) 개념이 없다. 그래서 먼저 정의가 필요하다:

```
회피 시작 → PerfectDodgeWindow(예: 앞 0.2초) 동안 bInvincible = true
          → 이 구간에 피격 판정이 들어오면 "퍼펙트 회피"
```

`Event AnyDamage`에서 `bInvincible`이면 데미지를 0으로 만들고
`OnPerfectDodge` 이벤트를 쏘는 구조. **보스 공격이 있어야 검증된다.**

### 잔상(고스트) 표현 방법 3가지

| 방법 | 방식 | 장단점 |
|---|---|---|
| **A. PoseableMesh 스냅샷** | 회피 순간 `PoseableMeshComponent`를 3~4개 스폰해 현재 포즈를 복사(`CopyPoseFromSkeletalComponent`)하고, 반투명 머티리얼로 점점 사라지게 함 | 진짜 "잔상"처럼 보임. 블루프린트만으로 가능. 캐릭터 1명이면 성능 문제 없음 |
| **B. 머티리얼 디졸브** | 캐릭터 머티리얼에 프레넬/디졸브 파라미터를 넣고 회피 중 값을 애니메이션 | 가장 가벼움. 하지만 "잔상"이 아니라 "번쩍임"에 가까움 |
| **C. Niagara 메시 리본** | Niagara에서 스켈레탈 메시를 샘플링해 파티클로 뿌림 | 가장 화려하지만 Niagara 작업량이 큼 |

**추천은 A.** 세키로/데빌메이크라이류의 잔상이 정확히 이 방식이고,
블루프린트만으로 끝나며, 값(개수/간격/지속시간/색)을 전부 노출할 수 있어
포트폴리오에서 설명하기도 좋다.

구현 스케치:
```
OnPerfectDodge
  → ForLoop(0 ~ GhostCount-1)
      → SpawnPoseableMesh(현재 위치/회전)
      → CopyPoseFromSkeletalComponent(플레이어 메시)
      → SetMaterial(M_Ghost, 시작 알파 = GhostAlpha)
      → SetTimer(소멸, GhostLife)
      → Delay(GhostInterval)   ← 이 부분은 타이머 체인으로
```
+ 화면 연출로 `P_Crunch_Heat_Distortion`(이미 프로젝트에 있음)을
같이 터뜨리면 "슉" 하는 느낌이 산다.

**순서상 보스 AI가 먼저다.** 맞을 일이 없으면 회피 성공을 판정할 수 없다.

## 무적 프레임 · 퍼펙트 회피 · 잔상 VFX (구현 완료, 2026-09-07)

### 무적 프레임 — DS3 미들롤 기준

다크소울3 미들롤의 무적 프레임은 **13프레임 = 0.433초**이고 롤 시작
즉시 발동한다(지연 없음). 장비 무게 시스템은 넣지 않기로 했으므로
미들롤 하나로 고정했다.

| 변수 (CombatTuning) | 값 |
|---|---|
| `IFrameDuration` | 0.433 |

우리 구르기 전체 길이는 배속 적용 후 약 0.71초이므로 앞 61% 구간이
무적이다. DS3도 롤 전체 대비 절반 남짓이라 체감이 비슷하다.

흐름: `TryEnterDodge`의 `SpendStamina` 직후
`bInvincible = true` → `SetTimer("OnIFrameEnd", IFrameDuration)` →
`OnIFrameEnd`에서 `false`.

### 퍼펙트 회피 = 무적 중 피격

`Event AnyDamage` 맨 앞에 `Branch(bInvincible)`을 넣었다.

- **true** → 데미지 처리를 통째로 건너뛰고 `OnPerfectDodge` 호출
- **false** → 기존 데미지 계산

별도의 "퍼펙트 판정 창"을 따로 두지 않은 이유: 무적 프레임 중에 실제로
공격이 지나갔다는 것 자체가 "성공적으로 피했다"는 뜻이라, 판정을 하나 더
만들면 값만 늘고 의미가 겹친다.

### 디버그 — 상시 퍼펙트 회피

지금은 플레이어를 때리는 것이 없어서 잔상을 볼 방법이 없다. 그래서
`bDebugAlwaysPerfectDodge` (Debug 카테고리, Instance Editable, **기본 true**)를
넣었다. 켜져 있으면 `TryEnterDodge`가 무적 타이머를 건 직후 무조건
`OnPerfectDodge`를 호출해서, **구를 때마다 잔상이 나온다.**

보스가 생겨서 실제 피격으로 검증되면 이 값을 false로 끄면 된다.
끄더라도 `AnyDamage`의 무적 판정 경로는 그대로 살아 있다.

### 잔상 VFX

**`M_DodgeGhost`** (`/Game/BossArena/Materials/Base/`)
- Unlit + Translucent + TwoSided
- `GhostColor` (VectorParameter, 기본 청록) → EmissiveColor
- `GhostOpacity` (ScalarParameter, 기본 0.6) → Opacity

**`BP_DodgeGhost`** (`/Game/BossArena/Blueprints/`)
- `InitGhost` 커스텀 이벤트:
  1. `AddComponentByClass(PoseableMeshComponent)` → 캐스팅 → `GhostMesh`
     (MCP로는 블루프린트에 컴포넌트를 미리 추가할 수 없어서 런타임 생성)
  2. `GetPlayerCharacter(0) → GetMesh` 로 플레이어 메시를 찾고,
     `SetSkinnedAssetAndUpdate` + `CopyPoseFromSkeletalComponent`로
     **그 순간의 포즈를 그대로 복사**
  3. `CreateDynamicMaterialInstance(0, GhostMaterial)`
  4. `SetLifeSpan(GhostLife)`
- `Tick`: `SetScalarParameterValueOnMaterials("GhostOpacity",
  Lerp(0, GhostAlpha, SafeDivide(GetLifeSpan(), GhostLife)))`
  → 남은 수명에 비례해 서서히 사라진다.
  `GetLifeSpan()`이 **남은 시간**을 돌려주는 걸 이용한 것이라 별도
  타이머 변수가 필요 없다.

| 변수 (BP_DodgeGhost, Ghost) | 값 |
|---|---|
| `GhostLife` | 0.45초 |
| `GhostAlpha` | 0.6 |
| `GhostMaterial` | `M_DodgeGhost` |

**스폰 (BP_Player_Combat)**
`SpawnDodgeGhost()` 함수 — 플레이어 **메시의 월드 트랜스폼**에 스폰한다
(액터 트랜스폼이 아니라 메시 기준이어야 -90 오프셋/회전이 맞는다).

```
OnPerfectDodge → SpawnDodgeGhost() → SetTimer("SpawnGhost2", 0.06)
SpawnGhost2    → SpawnDodgeGhost() → SetTimer("SpawnGhost3", 0.06)
SpawnGhost3    → SpawnDodgeGhost()
```

0.06초 간격으로 3개를 남겨서 회피 궤적을 따라 잔상이 늘어선다.
루프 대신 이벤트 3개를 체인으로 건 이유는 MCP로 `Delay` 노드를 만들 수
없기 때문이다 (타이머는 만들 수 있다).

**남은 것**: `SKM_Quinn_Simple`의 머티리얼 슬롯이 2개 이상이면 0번만
고스트 머티리얼로 바뀐다. PIE에서 보고 이상하면 슬롯을 추가로 덮으면 된다.

## 가드 상체 블렌딩 (완료, 2026-09-07)

애님 그래프에 **이미 레이어 구조가 있었다.**

```
StateMachine(MainStates) → Slot 'DefaultSlot' → SaveCachedPose 'BasePose'
                                                       ├→ LayeredBoneBlend.BasePose
                                                       └→ Slot 'AttackUpperBody' → BlendPoses_0
                                                                LayeredBoneBlend → ControlRig → Root
```

본 필터도 `spine_01 / BlendDepth 1`로 정상이었다 (예전 사고의 원인이던
`-1`이 아님). `AttackUpperBody` 슬롯에 아무것도 재생되지 않아서 그동안
아무 일도 안 하고 있었던 것.

**그래서 고친 건 핀 값 하나다** — `TryEnterBlock`의
`PlaySlotAnimationAsDynamicMontage` 슬롯 이름을
`DefaultSlot` → `AttackUpperBody`.

이제 가드 중에도 하체는 로코모션이 돌아 걸어다닐 수 있다. 공격·회피는
그대로 `DefaultSlot`(전신)이라 영향 없다.

(슬롯 이름이 `AttackUpperBody`인데 실제로는 블록이 쓴다 — 이름을 바꾸면
애님 그래프 노드와 몽타주를 같이 고쳐야 해서 그대로 뒀다.)

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

---

## 공격 콤보 재설계 — 4타 + 세키로식 입력 버퍼 (2026-09-06)

### 최종 스코프
**공격은 4타까지만 구현한다.** 그 이상은 만들지 않는다. 5타 이상이
필요해지면 그때 다시 논의한다.

### 폐기한 것
- **"좌클릭 1번에 1타+2타 연속(잽잽)"** 방향 폐기. 몽타주 두 개를 하나로
  합치거나 타이머로 자동 연결하는 방식은 전부 버린다. **한 번 클릭 =
  한 타**가 기본이다.
- **취소 구간 노티파이(`ANS_AttackCancelWindow`) 기반 판정 폐기.**
  `WasAnimNotifyStateActiveInAnyState`는 이름 그대로 **스테이트 머신의
  State에서 발생한 노티파이**를 조회하는 함수라, 몽타주 슬롯에 찍은
  노티파이는 잡히지 않는다. 그래서 `bCanCancelCurrentAction`이 한 번도
  true가 되지 않았고 2타가 영영 안 나갔다. 컴파일 에러도 런타임 에러도
  안 뜨기 때문에 겉보기엔 멀쩡해 보인다 — **이 함수를 몽타주 노티파이
  판정에 쓰지 말 것.**
  (그 전까지 "콤보가 된다"고 확인했던 건 취소 구간이 아니라
  `bAttackQueued`+타이머로 돌던 예약 방식이었다. 취소 구간 경로는 사실상
  한 번도 검증된 적이 없었다.)

### 현재 구조
데이터 주도 방식이라 **몽타주만 배열에 끼우면 4타까지 그대로 작동한다.**

**변수**
| 변수 | 타입 | 역할 |
|---|---|---|
| `AttackMontages` | AnimMontage 배열 (인스턴스 편집 가능) | 콤보 순서대로 넣는다. 넣은 개수만큼 콤보가 늘어남 (최대 4개) |
| `PendingCombo` | AnimMontage 배열 (내부) | 콤보 시작 시 `AttackMontages`를 복사해 쓰는 작업 큐. 한 타 나갈 때마다 앞에서 하나씩 제거 |
| `bComboWindowOpen` | bool | 다음 타로 넘어갈 수 있는 구간인지 |
| `bAttackBuffered` | bool | 세키로식 선입력 버퍼 |
| `ComboWindowRatio` | float (기본 0.55) | 현재 타의 몇 % 지점부터 다음 타를 받을지 |
| `AttackPlayRate` | float (기본 1.4) | 공격 몽타주 재생 배속 |

**흐름**
```
TryEnterAttack (좌클릭 1회 = 1회 호출)
├─ ActionState == Locomotion ?
│   YES → PendingCombo = AttackMontages   (큐 채우기)
│         ActionState = Attack
│         StartComboStep()
└─ NO → ActionState == Attack ?
        YES → bComboWindowOpen ?
              YES → StartComboStep()          (즉시 다음 타)
              NO  → bAttackBuffered = true    (선입력 저장 = 세키로 버퍼)
        NO  → 무시 (회피 중 등)

StartComboStep()  [공용 함수]
   bAttackBuffered = false
   bComboWindowOpen = false
   PlayAnimMontage( PendingCombo[0], AttackPlayRate )
   PendingCombo에서 0번 제거
   SetTimer(OnComboWindowOpen,     실재생시간 × ComboWindowRatio)
   SetTimer(OnAttackRecoveryTimer, 실재생시간)
      * 실재생시간 = 몽타주 길이 ÷ AttackPlayRate

OnComboWindowOpen
   PendingCombo에 아직 남은 타가 있으면
      bComboWindowOpen = true
      bAttackBuffered 였다면 → StartComboStep()   (버퍼 소진)

OnAttackRecoveryTimer
   ActionState = Locomotion
   bAttackBuffered = false
   bComboWindowOpen = false
```

**세키로식 조작감의 핵심**: 다음 타가 아직 안 열린 시점에 눌러도 입력이
씹히지 않고 `bAttackBuffered`에 저장됐다가, 창이 열리는 순간 자동으로
발동한다. 플레이어는 리듬만 맞추면 되고 프레임을 맞출 필요가 없다.
콤보 길이는 `PendingCombo`가 비면 자연히 끝나므로 별도 카운터가 없다.

### 알아둘 것 (MCP 제약)
- **승격 연산자(promotable operator) 노드는 `create_node`로 만들 수 없다.**
  `+`, `-`, `==`(int), `<`, `float*float`, `float/float` 전부 해당.
  `find_node_types`에도 안 잡힌다. 우회 수단:
  | 필요한 연산 | 대신 쓸 노드 |
  |---|---|
  | `A / B` | `수학\|플로트\|SafeDivide` |
  | `A * ratio` | `수학\|플로트\|Lerp(0, A, ratio)` |
  | 인덱스 유효성 | `유틸리티\|배열\|IsValidIndex` |
  | 카운터 증가 | 배열에서 `RemoveIndex(0)`으로 소진시키는 방식으로 대체 |
- **불리언 변수의 `b` 접두사는 노드 type_id에서 빠진다.**
  `bComboReady` → `Variables|CombatState|GetComboReady`.
- **순수(pure) 노드 재평가 함정**: 배열 `Get`은 순수 노드라 소비 시점에
  평가된다. `Get[0]` 결과를 쓰는 노드보다 `RemoveIndex(0)`를 먼저 실행하면
  엉뚱한 원소를 읽는다. **재생 → 제거** 순서를 지킬 것.


## 플레이어 최종 점검 (2026-09-07) — 보스 작업 전 마감

보스 AI로 넘어가기 전에 플레이어 쪽을 전수 점검했다. 그래프별로 고아 노드
(연결이 하나도 없거나 실행 핀이 끊긴 노드)를 전부 스캔했다.

### 발견하고 고친 것

**① `SpendStamina`가 통째로 끊겨 있었다 (심각)**
`FunctionEntry`부터 `SetCurrentStamina`까지 연결이 전부 사라져 있었다.
결과적으로 **스태미나가 한 번도 줄어들지 않았고**, `HasStamina` 게이트도
항상 통과했다. 재연결로 수정.

원인은 MCP 특유의 함정이다 — **노드에 파라미터를 추가하거나 클래스를
지정하면 언리얼이 그 노드를 재생성하면서 기존 연결을 버린다.** 같은 이유로
`BP_DodgeGhost`의 `AddComponentByClass`도 캐스트 연결이 끊겼었다.
**앞으로 MCP로 노드를 만든 뒤에는 반드시 `get_node_infos`로 연결을
다시 확인해야 한다.** 컴파일은 통과하기 때문에 눈치채기 어렵다.

**② 고아 노드 11개 제거**
- `TryEnterDodge` 7개 — 예전 세션의 SelectObject/EnumLiteral 잔재 +
  무적 프레임 배선 1차 시도가 남긴 중복 세트
- `EventGraph` 3개, `SpawnDodgeGhost` 1개

**③ 죽은 변수 `StaminaRegenTimer` 제거**
타이머 방식으로 바꾸면서 안 쓰게 된 변수. `LastMoveInput`은 카테고리가
비어 있어서 `Combat State`로 옮김.

**④ 플레이어 사망 처리 추가**
체력이 0이 돼도 아무 일이 없었다.
`AnyDamage` → 체력 반영 → `NearlyEqual(체력, 0)` → `ActionState = Dead`
→ "YOU DIED" 출력 → `DisableInput`.
사망 애니메이션은 에셋이 없어 넣지 않았다. 상태와 입력 차단만 되어 있으므로
몽타주만 끼우면 된다.

### 검증 결과 — `TryEnterDodge` 최종 실행 순서

```
FunctionEntry
 → Branch(ActionState == Dodge)      차단: 구르는 중 재입력
 → Branch(IsFalling)                 차단: 공중
 → Branch(bDodgeOnCooldown)          차단: 쿨타임
 → HasStamina(DodgeStaminaCost)
 → Branch(스태미나 충분?)             차단: 부족
 → SetActionState(Dodge)
 → SpendStamina(13)
 → bInvincible = true → SetTimer(OnIFrameEnd, 0.433)
 → Branch(bDebugAlwaysPerfectDodge)  → OnPerfectDodge (디버그용)
 → 이동 시작지점/방향 세팅 → 몽타주 재생 → 복귀 타이머
```

11개 그래프 전부 고아 노드 0개로 정리 완료.

## HUD 폴리싱 (2026-09-07)

### 사용 에셋 — Kenney Fantasy UI Borders (CC0)

`/Game/BossArena/UI/Textures/`
| 애셋 | 원본 | 용도 |
|---|---|---|
| `T_UI_Panel` | `Panel/panel-001.png` | 바 뒤 어두운 패널 |
| `T_UI_Frame` | `Transparent center/panel-transparent-center-001.png` | 장식 테두리 (가운데 투명) |

둘 다 48×48이라 **9-slice 마진 1/3 (16px)** 로 잡았다. 텍스처 설정은
`LODGroup=UI`, `CompressionSettings=EditorIcon`(UI용 무압축), `SRGB` 켬.

**중요 — 왜 바마다 프레임을 두르지 않았나**: 9-slice 마진이 16px이면 위젯의
최소 높이가 32px이다. 스태미나 바는 12px이라 프레임을 개별로 두르면
모서리가 뭉개진다. 그래서 **바 두 개를 감싸는 패널 하나(404×92)** 에만
프레임을 씌웠다. 결과적으로 소울류 HUD 배치에도 더 가깝다.

### 레이어 구성 (zOrder 순)

```
0  PanelBG        404×92  T_UI_Panel, 거의 검정 82%
1  HealthDelayBar 360×20  옅은 베이지 — 지연 데미지 바
2  HealthBar      360×20  진홍, 배경 투명(아래 지연 바가 비치도록)
2  StaminaBar     300×12  올리브
3  PanelFrame     404×92  T_UI_Frame, 황동색 틴트
```

### 지연 데미지 바

맞으면 빨간 바는 즉시 줄고, 그 아래 베이지 바가 뒤따라 내려온다.

```
Tick: DelayPercent = FInterpToConstant(DelayPercent, 체력비율, DeltaTime, DelaySpeed)
      HealthDelayBar.SetPercent(DelayPercent)
```
`DelaySpeed` 0.45 (초당 45%씩 따라감, Instance Editable).
`HealthBar`의 배경을 알파 0으로 만들어야 아래 바가 보인다.

### 게이지가 안 움직였던 원인

`CreateWidget`의 `OwningPlayer`가 비어 있었다. 그러면 위젯의
`GetOwningPlayerPawn`이 null을 반환하고 **캐스트가 조용히 실패**한다
(실패해도 로그가 안 남는다). 두 군데를 고쳤다:
- `CreateWidget`에 `GetPlayerController(0)` 연결
- 위젯도 `GetOwningPlayerPawn` → `GetPlayerCharacter(0)`으로 교체

### 아직 안 한 폴리싱 (에셋 불필요, 요청 시 가능)
- 스태미나 소진 시 붉게 깜빡임
- 스태미나 가득 차면 페이드아웃 (다크소울 방식)
- 숫자 표시 / 아이콘

---

## 보스 히트박스 재설계 — 범위 판정에서 소켓 추적 판정으로 (2026-09-08)

### 왜 바꿨나

기존 보스 공격 판정은 `ApplyRadialDamage`였다. **액터 중심에서 앞으로
150cm 떨어진 고정 지점에 반지름 110cm 구를 한 번 띄우는** 방식이다.
문제가 셋이다.

1. **애니메이션과 무관하다.** 주먹이 어디 있든 판정은 항상 몸 앞
   같은 자리에 뜬다. 왼손을 뻗든 오른손을 뻗든 똑같다.
2. **한 프레임만 검사한다.** 타이머가 울린 그 순간에 플레이어가
   구 밖에 있으면 그 뒤 프레임에 정통으로 맞아도 판정이 없다.
   반대로 그 한 순간만 걸치면 스치기만 해도 맞는다.
3. **크기가 과하다.** 반지름 110 + 전방 150 오프셋이면 실질 판정
   범위가 몸 앞 260cm다. 보스를 1.7배로 키우면 더 심해진다.

**"공격당하는 판정을 범위로 잡는 게 맞느냐"** — 맞지 않다.
상용 액션 게임은 무기/주먹 본에 히트박스를 붙이고, 액티브 프레임
동안 그 히트박스를 매 프레임 검사한다. 그 구조로 바꿨다.

### 새 구조

```
TryAttack
  bHasHitThisAttack = false      ← 이번 공격에서 아직 안 맞췄다
  몽타주 재생
  타이머: OnAttackCommit (WindupTime)     — 회전 금지
  타이머: OnAttackHit    (WindupTime)     — 액티브 프레임 시작
  타이머: OnAttackEnd    (AttackTotalTime)

OnAttackHit        bHitWindowOpen = true
                   타이머: OnHitWindowClose (ActiveTime)
OnHitWindowClose   bHitWindowOpen = false

Tick
  └ (회전 처리 후)
    Branch(bHitWindowOpen)
      └ Branch(bHasHitThisAttack) → else
          ├ Branch(bShowHitDebug) → DrawDebugSphere(주먹 위치, 반경, 0.05초)
          └ SphereOverlapActors(
                SpherePos      = GetSocketLocation(Mesh, AttackSocket),
                SphereRadius   = AttackHitRadius,
                ObjectTypes    = [Pawn],
                ActorClassFilter = BP_Player_Combat_C)
              └ Branch(맞았나)
                  → ApplyDamage(OutActors[0], AttackDamage, ...)
                  → bHasHitThisAttack = true
```

**핵심 세 가지**

- **소켓 추적** — 판정 구가 `AttackSocket`(현재 `hand_l`) 본을 따라간다.
  주먹이 움직이면 판정도 같이 움직인다. 공격마다 소켓을 바꿔 끼우면
  된다 (어퍼컷은 `hand_l`, 리버블로는 `hand_r`…).
- **액티브 윈도우** — `WindupTime`부터 `ActiveTime` 동안 **매 프레임**
  검사한다. 한 순간 스냅샷이 아니다. 다크소울/세키로의 액티브 프레임
  개념과 같다.
- **1회 히트 보장** — `bHasHitThisAttack`으로 한 공격당 한 번만
  데미지가 들어간다. 매 프레임 검사인데 이게 없으면 9프레임 동안
  9번 맞는다.

| 변수 | 의미 | 값 |
|---|---|---|
| `AttackSocket` | 판정을 붙일 본 이름 | `hand_l` |
| `AttackHitRadius` | 판정 구 반지름 (월드 cm) | 85 |
| `ActiveTime` | 액티브 프레임 길이 | 0.15초 |
| `bHitWindowOpen` | 지금 판정 중인가 | 런타임 |
| `bHasHitThisAttack` | 이번 공격에서 맞췄나 | 런타임 |

`bShowHitDebug`를 켜두면 액티브 프레임 동안 **주먹을 따라다니는
디버그 구**가 보인다. 포트폴리오 영상에서 판정을 보여주기에도 좋다.

### 아직 안 바꾼 것

플레이어 공격은 여전히 `ApplyRadialDamage`다. 같은 구조로 바꿀 수
있지만 지금은 체감 문제가 보고되지 않아 보류했다.

---

## 보스 배치 수정 (2026-09-08)

- **떠 있던 문제** — 아레나 바닥이 `z = -8`인데 액터 z가 170으로
  고정돼 있었다. 캡슐 반높이 110 × 스케일 1.45 = 159.5이므로
  캡슐 바닥이 z=10.5, 즉 **18.5cm 떠 있었다.**
  스케일을 1.7로 올리면서 z를 **179**(= -8 + 110×1.7)로 다시 계산했다.
- **스케일 1.45 → 1.7.** 크런치 메시 높이는 260cm이므로 실제 신장은
  442cm. 플레이어(약 180cm)의 2.5배.
- **카메라 관통** — 보스 캡슐과 메시가 **Camera 채널을 Ignore**
  하도록 되어 있었는데, **레벨 인스턴스의 오버라이드가 블루프린트
  기본값을 덮고 있어서 실제로는 적용되지 않았다.** 인스턴스 값을
  블루프린트와 같게 다시 맞췄다.
  - 캡슐: ObjectType `Pawn` / QueryAndPhysics / Visibility·Camera Ignore
  - 메시: ObjectType `Pawn` / QueryOnly / Pawn·Vehicle·Visibility·Camera Ignore

  카메라 스프링암은 Camera 채널로 충돌 검사를 한다. 보스가 이 채널을
  막고 있으면 보스 몸에 스프링암이 걸려 카메라가 **플레이어 안쪽으로
  빨려 들어간다.** 소울류 보스가 전부 이 처리를 해 두는 이유다.

---

## 피격 판정 방식 — 조사와 개선 (2026-09-08)

### 상용 액션 게임이 쓰는 방식

조사한 내용을 정리하면 판정 방식은 크게 세 층위다.

**1) 형태 — 무엇으로 검사하는가**

가장 흔한 실수는 **고정된 박스/구를 한 번 띄우는 것**이다. 빠른 공격은
그 사이를 통과해 버리고(터널링), 반대로 무기가 스치기만 해도 잡힌다.
검이라면 **칼끝이 지난 궤적을 따라 캡슐/구를 쓸어서(sweep)** 검사하는
것이 가장 정확하다. 프레임 사이 이동 거리가 판정 크기보다 클 때 놓치는
히트를 sweep이 잡아준다. 저프레임이나 빠른 휘두름에서 특히 그렇다.

**2) 시점 — 언제 켜고 끄는가**

> "히트박스는 타이머가 아니라 **애니메이션 이벤트**를 기준으로
> 켜지고 꺼져야 한다."

우리는 지금 타이머(`WindupTime`, `ActiveTime`)를 쓴다. 공격이 하나일
때는 문제없지만, Utility AI가 6~8개 공격 중에서 고르기 시작하면
공격마다 액티브 프레임이 달라서 **공격마다 숫자를 따로 관리**해야 한다.

**3) 대상 — 무엇을 맞히는가**

FPS의 헤드샷이 그렇듯, 정교한 게임은 **부위별 허트박스**(머리·몸통·팔·
다리)를 두고 배율을 다르게 준다. 소울라이크는 여기에 더해 **보스 판정은
후하게, 플레이어 판정은 박하게** 잡는 것으로 알려져 있다.

### 우리가 지금 한 것 — 스윕 판정으로 교체

`SphereOverlapActors`(한 지점의 구 검사) → **`SphereTraceForObjects`
(직전 프레임 주먹 위치 → 현재 주먹 위치를 잇는 구 스윕)**.

```
OnAttackHit
  bHitWindowOpen = true
  PrevHitLocation = 주먹 소켓 위치       ← 시작점 시딩
  타이머: OnHitWindowClose (ActiveTime)

Tick (윈도우 동안, 아직 안 맞췄으면)
  cur = GetSocketLocation(Mesh, AttackSocket)
  SphereTraceForObjects(Start=PrevHitLocation, End=cur,
                        Radius=AttackHitRadius, ObjectTypes=[Pawn],
                        bIgnoreSelf=true)
  PrevHitLocation = cur                  ← 매 프레임 갱신
  맞았으면 → HitActor를 BP_Player_Combat으로 캐스트 → ApplyDamage
          → bHasHitThisAttack = true
```

**왜 이게 나은가.** 크런치의 주먹은 2배 스케일에서 한 프레임에
수십 cm를 움직인다. 지점 검사는 그 사이를 그냥 지나칠 수 있다.
스윕은 **주먹이 지나간 경로 전체**를 판정한다. 스치는 판정도,
빠져나가는 판정도 없어진다.

`BreakHitResult`가 `HitBoneName`을 준다. 나중에 부위별 배율을
넣고 싶으면 여기서 바로 읽으면 된다.

### 아직 안 한 것 — 왜 지금은 안 하는가

**AnimNotifyState로 판정 창을 옮기는 것.** 이론적으로 맞는 방향인데
우리 사정에서 두 가지가 걸린다.

1. **ParagonCrunch 콘텐츠는 git에 안 올라간다** (2GB, LFS 무료 한도
   초과로 `.gitignore` 처리). 노티파이를 파라곤 애니메이션 타임라인에
   찍으면 **그 데이터가 버전 관리 밖에 남는다.** 포트폴리오로서 치명적이다.
2. **AI가 그 데이터를 읽어야 한다.** Utility AI는 "이 공격은 후딜이
   기니까 플레이어가 반격하기 쉽다"를 점수로 계산해야 한다. 타이밍이
   애니메이션 안에 숨어 있으면 AI가 못 읽는다.

그래서 방향은 **노티파이가 아니라 커밋되는 데이터 테이블**이다.
공격이 여러 개가 되는 시점에 `WindupTime`/`ActiveTime`/`AttackSocket`/
`Recovery`를 공격별 구조체로 묶어 DataTable로 뺀다. AI 설계와 판정
타이밍이 같은 데이터를 본다.

**부위별 허트박스**도 보류. 지금 플레이어는 캡슐 하나가 허트박스다.
소울라이크에 부위 판정이 꼭 필요하지는 않고, 넣는다면 보스 쪽
약점(등·머리)에 넣는 게 연출상 낫다. 필요해지면 그때.

### 출처
- Epic 포럼: 트레이스 기반 근접 판정 접근
- Pudgy Cat: 히트박스/허트박스 구조와 프레임 데이터
- itch.io 개발 로그: 캡슐 캐스팅으로 빠른 휘두름 판정 개선

---

## 보스 공중 부양 — 원인은 루트 모션 (2026-09-08)

캡슐과 바닥은 정확히 맞아 있었다(에디터에서 측정 확인). 문제는
**공격 애니메이션이 재생될 때만** 몸이 기울며 뜬다는 것이었다.

파라곤 크런치의 어빌리티 애니메이션은 **루트 트랙에 전진 런지가
들어 있는** 상태로 제작됐다. 그런데 `bEnableRootMotion`이 전부
**꺼져 있었다.** 루트 모션이 꺼져 있으면 루트 트랙이 캡슐을 밀지
못하고 **메시에 그대로 적용**된다. 결과적으로 캡슐은 제자리인데
몸만 앞으로 기울며 떠오른다.

`Ability_Combo_01~04`의 `bEnableRootMotion`을 켰다.
ABP는 이미 `RootMotionFromMontagesOnly`라 동적 몽타주에서
루트 모션이 추출된다.

**부수 효과 (의도한 것)**: 이제 보스가 공격할 때 실제로 한 발
전진한다. 커밋 이후 회전이 잠기므로 전진 방향도 커밋 시점에 고정된다.
거리 압박이 생기는 셈이라 전투 설계상 오히려 맞다.

**주의**: 이 플래그 변경은 ParagonCrunch 폴더 안이라 **git에 커밋되지
않는다.** 다른 PC에서 클론하면 다시 켜줘야 한다.

### 스케일 2.0

`z = -8 + 110 × 2.0 = 212`. 크런치 실신장 520cm.

---

## 공중 부양 — 실측으로 원인 좁히기 (2026-09-08, 정정)

### 앞서 말한 "루트 모션 때문" 은 틀렸다

PIE를 띄워 보스 액터의 좌표를 실제로 읽어봤다.

```
z = 214.15   (14회 샘플, 공격 중/후 전부 동일)
x, y = 0, -1200  (한 번도 안 움직임)
MovementMode = MOVE_Walking
```

- 캡슐 바닥 = 214.15 − (110 × 2.0) = **−5.85**
- 아레나 바닥 = **−8**
- 차이 2.15cm = 언리얼 CharacterMovement의 `MAX_FLOOR_DIST` 기본값

**캡슐은 정확히 땅에 붙어 있다.** 그리고 공격 중에도 액터가 전혀
움직이지 않는다 → **`Ability_Combo_01`에는 루트 모션이 아예 없다.**
(루트 트랙이 안 움직이는 애니메이션이다.)

그러므로 "루트 트랙의 런지가 메시에 적용돼서 뜬다"는 앞선 설명은
사실이 아니다. 취소한다.

**남는 가능성은 하나다: 액터는 제자리인데 스켈레톤(메시)이 위로
올라간다.** 공격 애니메이션 안에서 루트 본 또는 골반이 올라가는 것.

### 그래서 한 것

**1. 동적 슬롯 몽타주 → 진짜 몽타주 에셋**

`PlaySlotAnimationAsDynamicMontage`는 런타임에 몽타주를 만들어
쓰는 방식이라 루트 모션 설정과 **루트 락(Root Lock)** 이 제대로
걸리지 않는다. 파라곤이 이미 `Ability_Combo_01_Montage`를 갖고 있고
슬롯도 우리와 같은 `UpperBody`였다.

```
/Game/BossArena/Boss/Animations/AM_Boss_Combo_01   ← 복제본 (우리 폴더)
BP_Boss_Crunch.AttackMontage (AnimMontage)         ← 새 변수
TryAttack:  PlaySlotAnimationAsDynamicMontage → PlayAnimMontage
```

**우리 폴더에 복제한 이유**: ParagonCrunch는 `.gitignore` 대상이라
그 안에서 뭘 고쳐도 버전 관리에 안 들어간다. 몽타주를 우리 폴더로
가져오면 슬롯·재생 설정·나중에 붙일 노티파이가 **커밋된다.**

이제 `bEnableRootMotion` + `RootMotionRootLock = RefPose`가 실제로
동작한다. 루트 본이 레퍼런스 포즈로 고정되므로, 애니메이션이 루트를
들어올리고 있었다면 그 오프셋이 제거된다.

**2. 캡슐/메시 분리를 눈으로 볼 수 있는 디버그**

`bShowHitDebug`가 켜져 있으면 Tick마다:

| 색 | 무엇 |
|---|---|
| 청록 캡슐 | 실제 콜리전 캡슐 (액터 위치·스케일 반영) |
| 자홍 구 | 메시의 `Root` 소켓 위치 |

**둘이 벌어지면 메시가 캡슐을 떠난 것이고, 둘이 같이 떠 있으면
액터 자체가 뜬 것이다.** 다음 테스트에서 어느 쪽인지 한눈에 나온다.
추측을 더 쌓지 않기 위한 계측 장치다.

### 실측으로 확인 — 발은 땅에 붙어 있다

디버그를 붙인 뒤 PIE에서 소켓 높이를 로그로 뽑았다.
바닥은 `z = -8`, 보스 스케일 2.0.

| 소켓 | 표본 | 범위 |
|---|---|---|
| `Foot_L` | 61 | **-10.3 ~ +10.8** |
| `Chest` | 253 | **271 ~ 314** |

- 왼발은 바닥(-8) 주변에서만 움직인다. **뜨지 않는다.**
- 가슴이 271~314에 있으므로 **스켈레톤이 제대로 포즈를 잡고 있다.**
  (스켈레톤이 뭉개졌다면 모든 본이 루트 높이인 -6 근처로 나온다.
   발 높이만 보면 이 둘을 구분할 수 없어서 가슴을 같이 쟀다.)
- 이 표본들은 `bIsAttacking`이 켜진 구간을 포함한다.

동적 슬롯 몽타주 → 진짜 몽타주 에셋 교체로 해결된 것으로 본다.
`PlaySlotAnimationAsDynamicMontage`는 루트 락을 적용하지 않는다.

### 부작용 하나 — 에디터 뷰포트에서 메시가 뭉개짐

PIE를 여러 번 켰다 끄는 과정에서 **에디터 월드의** 보스 메시가
모든 본이 루트로 뭉친 상태로 표시되는 일이 있었다. PIE 안에서는
정상이었다(위 소켓 수치가 증거). 에디터 표시만의 문제다.

복구 방법: 메시 컴포넌트의 `AnimationMode`를 `AnimationSingleNode`로
바꿨다가 `AnimationBlueprint`로 되돌리면 애님 인스턴스가 재초기화된다.

### 남은 것 — 런지가 없다

`Ability_Combo_01`은 루트 모션이 없는데(실측: 공격 중 액터가 1cm도
안 움직임), 애니메이션 자체는 **앞으로 파고드는 동작**이다.
파라곤은 이 전진을 애니메이션이 아니라 **어빌리티 코드**로 처리했다.

그래서 지금은 보스가 제자리에서 몸만 앞으로 기울인다. "떠 보인다"는
인상의 상당 부분이 여기서 온다고 본다. 해결은 **우리가 직접 전진을
넣는 것**이다 — 커밋 전까지 전방으로 `AttackLungeDistance`만큼
밀어주면 애니메이션과 이동이 맞는다. 거리 압박이라는 설계 의도와도
맞는다. 아직 넣지 않았다.

---

## 공격 런지 (2026-09-08)

### 왜 넣는가

`Ability_Combo_01`은 **앞으로 파고들며 치는 동작**인데 루트 모션이
없다(실측: 공격 중 액터 이동 0). 파라곤은 이 전진을 **어빌리티 코드**로
처리했다. 우리가 그 코드를 안 넣으면 보스는 앞발을 못 박은 채 상체만
기울이고 뒷다리는 허공에 뜬다 — "떠 보인다"의 실체가 이것이다.

발바닥 소켓(`Foot_L`) 높이를 3,010회 측정한 결과 공격 중 최대 **+93**
(바닥 -8 기준 101 위, 보스 키의 19%). 큰 스텝을 밟는데 몸이 안 나간다.

### 구조

```
TryAttack        → bHasHitThisAttack = false
                 → bLungeActive = true
                 → PlayAnimMontage

Tick (런지 중)    → step = (AttackLungeDistance / WindupTime) × DeltaTime
                 → AddActorLocalOffset( (step, 0, 0), sweep = true )

OnAttackCommit   → bCanTurn = false        ← 회전 금지
                 → bLungeActive = false    ← 전진 정지
OnAttackEnd      → bLungeActive = false    (안전망)
```

**커밋 시점에 회전과 전진이 같이 멈춘다.** 이미 정한 "커밋 이후에는
방향을 못 바꾼다"는 규칙이 이동에도 그대로 적용된다. 플레이어가
윈드업을 보고 옆으로 빠지면 보스는 빈 곳으로 파고든다.

`AddActorLocalOffset`은 액터 로컬 +X(정면)로 민다. 방향 벡터를
따로 만들 필요가 없다. `sweep=true`라 벽이나 플레이어를 뚫지 않는다.

| 변수 | 값 | 비고 |
|---|---|---|
| `AttackLungeDistance` | 120 | **Instance Editable** — 레벨에서 보스 선택 후 바로 조절 |
| `WindupTime` | 0.30 | 이 시간 동안 전진 → 속도 400 uu/s |
| `bLungeActive` | 런타임 | |

### CharacterMovement를 안 쓴 이유

처음에 `AddMovementInput` + `MaxWalkSpeed` 방식으로 만들었는데
보스가 전혀 안 움직였다. 원인은 `CharacterMovementComponent`가
**컨트롤러 없는 폰의 입력을 소비하지 않기** 때문이다
(`bRunPhysicsWithNoController` 기본 false). AIController를 붙이고
플래그를 켜도 안 됐다.

지금 필요한 건 "애니메이션에 맞춘 정해진 거리 이동"이지 "가감속이
있는 이동"이 아니다. 루트 모션의 대체물이므로 직접 오프셋이 맞다.
**Approach/Circle/Retreat 같은 진짜 이동을 붙일 때 CMC로 간다.**

### 계측 함정 — 에디터 백그라운드 3 FPS

MCP로 PIE를 띄워놓고 창을 포커스하지 않으면 에디터가
**틱 레이트를 3 FPS로 제한**한다(`Use Less CPU when in Background`).
로그: `Bringing World ... up for play (max tick rate 3)`.

이 상태에서 이동 거리를 재면 완전히 틀린 값이 나온다. 실제로
`step` 로그가 **133.3/프레임**으로 찍혔다 — `400 × DeltaTime`에서
DeltaTime이 0.333이라는 뜻이다. 윈드업 0.3초가 한 프레임도 안 되니
런지가 사실상 1프레임 만에 끝난다.

**이동 관련 수치는 반드시 포커스된 창에서 사람이 확인해야 한다.**

### 부수 변경

- `AutoPossessAI = PlacedInWorldOrSpawned` — 지금 쓰진 않지만
  이후 내비게이션·퍼셉션에 필요하다.
- `CharMoveComp.bRunPhysicsWithNoController = true`
- Tick 디버그에 노란 구(`Foot_L` 소켓) 추가. 매 프레임 로그를 찍던
  PrintString은 스팸이라 제거했다.
