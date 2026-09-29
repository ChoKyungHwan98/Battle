# 보스 HFSM v1 — 구현을 따라 읽는 문서

> 2026-09-10: 현재는 [Utility 전체 구현](BOSS_UTILITY_IMPLEMENTATION.md)과 연결되어 있다.
> Attack 하위에 Telegraph(예고), Link(연계 사이)를 추가했다. Link는 반격 턴이 아니다.
> 아래는 첫 단타 HFSM 구현 이력이다. 최신 공격 실행 함수와 수치는 Utility 문서를 따른다.

2026-09-10 최신 선택 수치와 새 01→02→Ability_Uppercut 콤보 범위는
[BOSS_UTILITY_TUNING.md](BOSS_UTILITY_TUNING.md)를 참고한다. 아래 기록의 폐기된 체인은
이전의 01→02→03 계획이며, 사용자 지정 새 콤보와 구분한다.

최신 변경: [Utility v1](BOSS_UTILITY_IMPLEMENTATION.md)이 Ready에서만 행동을 선택한다.
모든 공격 모션은 독립 단타다. 이전의 보스 3타 체인 계획은 폐기했다.
아래는 HFSM v1 중심 기록이며 최신 선택/이동/패널 내용은 Utility 문서를 참고한다.

2026-09-09 보완: [기본 휘두르기 설계표](BOSS_ATTACK_01_SPEC.md)에서 현재 실행 규칙을
기획 언어로 설명한다. 실행 로직은 유지하고 전이 이유 네 문구를 쉽게 바꿨으며,
경고를 오류로 취급한 컴파일과 에셋 저장에 성공했다. 새로운 플레이테스트 결과는 아니다.

2026-09-08. 이번 대화에서 합의한 첫 단계: 기존 공격 1종을 HFSM으로 관리하고,
전이 이유를 우측 상단에 표시한다. 보스전은 BeginPlay 직후 활성화한다.
사용자 요청에 따라 레벨 보스 스케일은 2.0에서 1.5로 변경했다.

## 1. 에디터에서 볼 곳

- `/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch`
  - `EventGraph`: 시작, 공격 요청, 공격 타이머, 피격, Tick 연결.
  - `TransitionBossState`: 상태 전이와 공통 상태값 갱신.
  - `ExitCombat`: 전투 종료 시 공격 예약과 이동 정리.
  - `CheckBossDeath`: 상태에 관계없이 적용하는 체력 소진 검사.
  - `UpdateBossDebugPanel`: 실제 보스 데이터를 텍스트로 표시.
- `/Game/BossArena/UI/WBP_BossAIDebug`: 우측 상단 반투명 패널의 외형.
- `Config/DefaultGameplayTags.ini`: 상태 경로 정의.

## 2. 현재 상태는 하나다

`BossState`는 GameplayTag 한 개다. 문자열 표시용 `StateDisplay`가 의사결정을
하는 것이 아니다. `Boss.Combat.Attack.Active`는 `Boss.Combat.Attack`과
`Boss.Combat`에 속한다는 사실을 `MatchesTag`로 질의할 수 있다.

```
Boss
├─ Inactive
├─ Combat
│  ├─ Ready
│  └─ Attack
│     ├─ Windup
│     ├─ Active
│     └─ Recovery
└─ Dead
```

BeginPlay가 체력을 초기화한 뒤 `Inactive → Combat.Ready`로 즉시 전이한다.
전투 활성화와 첫 공격은 구분된다. 최신 구현은 0.6초마다 Utility로 판단하며,
거리와 방향 조건을 만족하고 단타가 선택됐을 때 Combo_01을 요청한다.

## 3. 전이를 허용하는 조건

`TransitionBossState(NewState, Reason, ExpectedState)`가 실제 상태를 쓰는
단일 지점이다. 현재 상태가 Dead이면 반환하며, ExpectedState에 속하지 않아도
반환한다. 각 공격 이벤트도 실행 전에 해당 단계인지 검사하므로, 거부된
전이 뒤에 몽타주 재생이나 판정 초기화 같은 부수 처리가 실행되지 않는다.

| 호출 계기 | 필요한 현재 상태 | 다음 상태 |
|---|---|---|
| BeginPlay | Inactive | Combat.Ready |
| TryAttack | Combat.Ready | Combat.Attack.Windup |
| OnAttackHit | Combat.Attack.Windup | Combat.Attack.Active |
| OnHitWindowClose | Combat.Attack.Active | Combat.Attack.Recovery |
| OnAttackEnd | Combat.Attack.Recovery | Combat.Ready |
| 체력 소진 | Boss 하위 상태 | Dead |

상태 변경 시 이전 상태 표시, 전이 이유, 진입 시각을 함께 기록한다.
`StateEnteredAt`은 진입 시각 데이터이며, v1 패널에는 경과 시간을 아직 표시하지 않는다.

## 4. 상태가 행동 규칙을 결정한다

| 상태 | 추적 회전 | 공격 판정 | 공격 진행 중 |
|---|---|---|---|
| Ready | 허용 | 닫힘 | 아니오 |
| Windup | 허용 | 닫힘 | 예 |
| Active | 잠금 | 열림 | 예 |
| Recovery | 잠금 | 닫힘 | 예 |
| Dead | 잠금 | 닫힘 | 아니오 |

기존 히트박스/이동 그래프와 연결하기 위해 `bIsAttacking`, `bCanTurn`,
`bHitWindowOpen`, `bLungeActive`는 상태에서 계산되는 호환용 값으로 남아 있다.
네 값은 이제 TransitionBossState에서만 설정한다. 새 로직이 독립적으로 이 값을
바꾸면 안 된다. `bHasHitThisAttack`은 한 공격당 중복 피해를 막는 별도 기록이다.

별도의 OnAttackCommit 이벤트와 타이머는 제거했다. Windup이 끝나 Active에
진입하면 회전 잠금과 판정 개방이 같은 전이에서 적용된다. 기존 Yaw 전용
추적 회전 수정은 유지했다.

## 5. 계층 구조가 실제로 하는 일

어느 공격 단계에서든 체력이 0 이하가 되면 같은 CheckBossDeath를 통과한다.
체력은 0~1로 Clamp한 결과를 정확한 0과 비교해 음수도 소진으로 처리한다.
현재 피해 계산은 원래 체력을 0 이상으로 제한한다.

Combat 외부로 전이할 때 TransitionBossState가 먼저 ExitCombat을 호출한다.
ExitCombat은 다음을 정리한다.

1. EvaluateUtility, OnAttackHit, OnHitWindowClose, OnAttackEnd 타이머 해제.
2. 공격 몽타주 정지.
3. 이동 즉시 정지 및 CharacterMovement 비활성화.

이후 Dead 상태를 기록하고 공격/판정/회전 값을 끈다. 사망 이후 도착하는
전이 요청도 Dead 가드로 차단한다. 따라서 공격의 후딜 종료 이벤트가 보스를
Ready로 되살릴 수 없다. 별도 사망 애니메이션은 이번 단계에 추가하지 않았다.

## 6. 우측 상단 패널

BeginPlay에서 소유 플레이어를 지정해 WBP_BossAIDebug를 생성하고 Viewport에
추가한다. 보스 Tick에서 위젯 참조의 유효성을 검사한 다음 다음 항목을 갱신한다.

- 현재 HFSM 경로.
- 바로 이전 상태 및 마지막 전이 이유.
- 추적 회전 허용/잠금, 공격 판정 열림/닫힘.
- 현재 HP.

패널은 상태를 표시만 한다. AI의 결정이나 상태 변경을 수행하지 않는다.
최신 패널은 Utility 점수와 선택도 표시한다. GOAP 계획은 아직 구현하지 않아 표시하지 않는다.
v1은 직전 전이 1개를 보여주며 누적 전이 이력 UI는 후속 작업이다.

## 7. 크기와 실제 튜닝값

레벨 보스의 스케일 `(1.5, 1.5, 1.5)`, 배치 `(0, -1200, 157)`.
캡슐 반높이 110 × 1.5 = 165, 지면 Z=-8이므로 배치 Z=157이다.
PIE에서는 CharacterMovement의 바닥 간격을 반영해 Z=159.150002로 안착했다.
Yaw=-90, Pitch/Roll=0. 레벨 외부 액터 패키지까지 저장했다.

기존 전투 튜닝을 유지했다: 재생 배속 0.75, Windup 0.30초, Active 0.15초,
공격 전체 1.244초, 최대 HP 1200. 기존 반복 간격 2.2초는 Utility 연결 후 사용하지 않는다.
주의: 공격 판정 반경은 블루프린트 기본값 85지만 **배치 인스턴스는 110으로
오버라이드**되어 있다. 이는 월드 단위이며 액터 스케일로 자동 축소되지 않는다.
이번 크기 변경에서 기존 반경 튜닝은 수정하지 않았다.

## 8. 검증 결과와 한계

- 최종 PIE 표본에서 Ready → Windup → Active → Recovery → Ready 순환 확인.
- 각 상태의 회전/판정 값이 위 표와 일치함을 확인.
- 임시 테스트 경로로 실제 ApplyDamage를 호출해 Windup, Active, Recovery에서
  각각 Dead로 전환 확인. HP=0, 모든 공격/회전/판정/런지 플래그=false.
- 공격 반복 간격 이후에도 Dead 유지 확인. 테스트 함수와 호출 노드는 제거했다.
- 런타임 WBP의 TextBlock에 실제 상태/이전 상태/사망 이유가 표시되는 것을
  프로퍼티로 확인했다. **화면 캡처 도구가 에디터 창을 찾지 못해 시각적 배치
  검수는 미완료**다. 다음 에디터 확인 시 글자 잘림과 가독성을 확인할 것.
- 블루프린트 컴파일과 저장 완료. 테스트용 강제 사망 코드는 최종 에셋에 없다.

## 9. 설계 문서 §15와의 관계 / 다음 단계

작업 중 확인한 §15는 공격 데이터 테이블과 3타 체인까지 포함한다.
**이번 v1이 §15 전체를 완료한 것은 아니다.** 이번 대화에서 제안한 첫 범위는
기존 공격 1종의 HFSM과 패널이다.

- §15의 E_BossState 대신 현재 구현은 계층 경로를 질의하는 GameplayTag다.
- §15의 SetBossState에 해당하는 함수 이름은 TransitionBossState다.
- 기존 bool 네 개는 제거 대신 상태에서만 계산하는 호환값으로 유지했다.
- S_BossAttack / DT_BossAttacks는 미구현이다. 현재 선택 함수는 EvaluateUtility다.
  사용자 정정으로 3타 체인 계획은 폐기했다.

현재 EvaluateUtility가 선택을 담당하며 직접 접근 이동도 연결했다. 다음 공격은
독립 단타 데이터와 실행 경로를 추가하고 같은 HFSM의 허용·중단 규칙을 따른다.
상시 경직, 페이즈, GOAP은 아직 추가하지 않았다.

## 10. 포트폴리오에서 설명할 문장

“공격 선택과 실행 제약을 분리했습니다. HFSM이 예비동작·판정·후딜을
관리하고, 상위 전투 상태를 종료할 때 공통 정리 함수가 예약된 공격을
해제합니다. 그래서 어떤 공격 단계에서 사망해도 판정이 남지 않습니다.
패널에는 실제 상태와 전이 이유를 표시해 이 규칙을 확인할 수 있게 했습니다.”
