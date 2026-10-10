#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BossCombatIntentComponent.generated.h"

class UMaterialInterface;
class UParticleSystemComponent;

/** Keeps one Utility choice alive while GOAP prepares its starting position. */
UCLASS(ClassGroup=(Battle), meta=(BlueprintSpawnableComponent))
class BATTLEBOSSPLANNING_API UBossCombatIntentComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBossCombatIntentComponent();
    void BeginSelectedIntent();
    void RecordAttackRecoveryEnd();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    bool IsActive() const { return bActive || bReassessing || bFootworkActive || bPerforming; }
    float FailureMultiplier(int32 Slot) const;
    /** 이번 판단에서 몰아치려 하는가. 판단 번호가 바뀔 때 한 번 정하고, 그 판단의 모든 후보가 같은 답을 본다. */
    bool WantsString(int32 DecisionNumber, bool bPhaseTwo) const;
    /** 지금 거리에서 바로 칠 수 있는 공격들의 기본 가중치 합. "칠지 걸을지"를 정할 때 공격 쪽의 점수로 쓴다. */
    float ReachableAttackWeight(float Distance) const;
    /** 화면 표시용: 마지막 "칠지 걸을지" 판단의 점수 한 줄. */
    FString MoveLine;
    /** 플레이어가 보스에게서 멀어지는 속도(cm/초). 다가오면 음수. */
    float PlayerSpeedAway() const;
    /** 화면 표시용: 지금 후딜이 닫혀 있는지 열려 있는지와 그 공격의 결과. 후딜이 아니면 빈 문자열. */
    FString RecoveryLabel() const;
    /** 최근 Seconds초 동안 맞은 횟수. */
    int32 HitsTakenWithin(float Seconds) const;
    /** 전투에서 처음 판단한 시각. 한 번도 안 쓴 공격의 "안 쓴 시간"을 여기서부터 잰다. */
    double FirstDecisionAt = -1.0;
    /** 마지막 Utility 추첨에서 뽑힌 자리(화면 표시용). 이어 치기로 바뀐 자리와 구분한다. */
    int32 UtilityWinner = -1;
    /** Lab override: 0=combat, 1=no travel, 2=manual step, 3=right-foot root-motion left punch. */
    int32 MotionLabPunchMode = 0;
    /** Runtime-only fixture permissions. Start override exists only inside a manual lab request. */
    bool bLabStartRequestScope = false;
    bool bLabRangeMeasurementAction = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float RunSpeed = 760.f;
    /** 달려오기(접근)의 최고 속도. 블루프린트의 ApproachRunSpeed(예전 440)를 이 값으로 덮어쓴다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Sprint") float ApproachSprintSpeed = 760.f;
    /** 이 속도를 넘으면 Sprint 동작으로 바꾸고, 아래로 내려가면 Jog로 돌아간다(둘 사이는 유지). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Sprint") float SprintOnSpeed = 520.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Sprint") float SprintOffSpeed = 430.f;
    /** Sprint_Fwd가 발이 미끄러지지 않는 속도(배율 1 기준, 발의 접지 구간에서 잰 값). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Sprint") float SprintNaturalSpeed = 686.f;
    /** 제자리 턴 동작이 도는 속도(도/초). 턴 동작의 재생 속도와 몸의 회전을 이 값에 함께 맞춘다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Turn") float TurnMontageSpeed = 130.f;
    /** 제자리 턴 동작의 재생 속도. 몸의 회전은 동작 안의 커브를 따라간다(발이 디디는 만큼만 돈다). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Turn") float TurnPlayRate = 1.1f;
    /** 후딜의 길이에 곱하는 값. 1이면 카드에 적힌 그대로, 0.7이면 30% 짧다. 동작도 같은 비율로 빨리 끝난다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Recovery") float RecoveryScale = .7f;
    /** 후딜이 이만큼 지났을 때 플레이어가 FlankExitAngle 넘게 옆·뒤에 있으면 후딜을 일찍 끝낸다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Recovery") float FlankExitFraction = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Recovery") float FlankExitAngle = 60.f;
    /** 고른 공격의 자리를 잡는 데 쓰는 최대 시간. 넘으면 포기하고 다시 고른다. 길면 물러나는 플레이어를 쫓느라 공격이 끊긴다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float MaxDuration = 1.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReplanInterval = .2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float TurnSpeed = 160.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float FailureWindow = 6.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReassessDuration = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float SideEntryAngle = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float SideEntrySpeed = 220.f;
    /** 공격을 고른 뒤 치기 전에 옆으로 한 번 도는 확률. 공격 뒤 발놀림(Footwork)이 같은 일을 하므로 0으로 둔다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float PostAttackProbeChance = 0.f;
    /** 공격 뒤 발놀림: 이보다 가까우면 "붙었다"고 본다(몸이 닿는 거리는 약 172cm). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float CrowdDistance = 200.f;
    /** 발놀림이 끝났을 때 두려는 간격. 단거리 공격이 전부 닿는 거리다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float ComfortDistance = 260.f;
    /** 옆으로 돌 때 플레이어를 중심으로 도는 각도. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FootworkAngle = 30.f;
    /** 이보다 멀면 발놀림을 하지 않는다(그때는 다가가는 것이 먼저다). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FootworkMaxDistance = 460.f;
    /** 기동 전체(여러 걸음)의 최대 시간. 넘으면 그 자리에서 끝내고 공격을 고른다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FootworkMaxDuration = 2.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float StepBackSpeed = 330.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SideStepSpeed = 340.f;
    /** 주먹 거리: 이보다 멀면 "걸어 들어가 조이기"를 할 수 있다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float PocketDistance = 300.f;
    /** 걸어 들어갈 때 멈추는 간격과 속도. 달리지 않고 성큼성큼 걷는다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float PressStopDistance = 240.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float PressSpeed = 330.f;
    /** 움직임의 점수. 공격 뒤 "칠지 걸을지"를 정할 때, 지금 칠 수 있는 공격들의 가중치 합과 같은 표에서 겨룬다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float CircleScore = 40.f;   // 둘레를 걷는다
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float PressScore = 45.f;    // 걸어 들어간다
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SpaceScore = 25.f;    // 빠진다

    /** 2페이즈는 덜 쉬고 더 몰아친다: 발놀림 확률에 곱한다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float PhaseTwoFootworkScale = .7f;
    /** 뒤쪽 대응: 공격이 끝났을 때 플레이어가 등 뒤에 있으면, 뒤돌아보는 대신 돌면서 치는 확률. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Rear") float RearResponseChance = .6f;
    /** 뒤쪽 대응 뒤 다시 쓸 수 있을 때까지의 시간(초). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Rear") float RearResponseCooldown = 6.f;
    /** 뒤쪽 대응의 준비 동작 동안 플레이어 쪽으로 도는 속도(도/초). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Rear") float RearResponseTurnSpeed = 300.f;
    // ---- 연기: 판단에는 영향을 주지 않고, 보스가 살아 있는 상대로 보이게 하는 것들 ----
    /** 시선: 공격하지 않을 때 상체와 머리가 플레이어를 따라가는 최대 각도와 따라가는 빠르기. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float LookMaxYaw = 70.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float LookSpeed = 5.f;
    /** 후딜의 이 비율이 지나면 시선이 플레이어를 따라가기 시작한다(발과 몸통의 방향은 그대로). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float RecoveryLookStart = .25f;
    /** 움찔: 맞았을 때 몸이 밀렸다 돌아오는 세기(cm/초). 공격은 끊기지 않는다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float FlinchImpulse = 420.f;
    /** 도발: 플레이어가 이보다 멀리 달아나면 달려가기 전에 한 번 도발한다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float TauntDistance = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float TauntCooldown = 25.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float TauntMaxSeconds = 2.2f;
    /** 2페이즈: 덜 움찔하고, 더 자주 도발하고, 걸음이 빨라진다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float PhaseTwoFlinchScale = .55f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float PhaseTwoTauntCooldownScale = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float PhaseTwoStepSpeedScale = 1.15f;
    /** 연계: 공격 뒤에 후딜을 끊고 정해진 다음 공격으로 잇는 확률(1페이즈 / 2페이즈)과, 후딜의 어느 지점에서 잇는지. */
    /** 이어 치기: 왼손·오른손으로 시작했을 때 두 번 / 세 번까지 이을 몫(나머지는 한 번만 친다). */
    /** 몰아치려는 의도: 판단마다 이 확률로 "이번에는 몰아친다"를 정한다(1페이즈 / 2페이즈). 그러면 몰아치기를 여는 공격(왼손·오른손)의 점수가 StringOpenerBoost배가 된다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float StringIntentChance = .55f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PhaseTwoStringIntentChance = .9f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float StringOpenerBoost = 2.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float StringTwoShare = .4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float StringThreeShare = .25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PhaseTwoStringThreeShare = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PhaseTwoStringTwoShare = .45f;
    // ---- 2페이즈: 과열 ----
    /** 2페이즈의 첫 공격 후딜 배율(1페이즈는 RecoveryScale). 더 빨리 다음으로 넘어간다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float PhaseTwoRecoveryScale = .6f;
    /** 열: 2페이즈에서 공격할 때마다 쌓이고, 공격하지 않는 동안 식는다. 가득 찬 채로 몰아치기가 끝나면 지쳐서 멈춘다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float HeatPerAttack = .17f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float HeatCoolPerSecond = .04f;
    /** 지쳐서 멈추는 시간(초). 플레이어가 크게 때릴 수 있는 틈이다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float VentSeconds = 2.8f;
    /** 김의 양(초당 뭉치 수): 2페이즈 기본, 열이 가득 찼을 때 더해지는 양, 지쳐서 멈췄을 때. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float SteamBaseRate = 18.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float SteamHeatRate = 26.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Overheat") float SteamBurstRate = 70.f;
    /** 플레이어가 최근 회피를 두 번 넘게 했으면 세 번까지 이을 몫에 더한다(한 번 피하고 들어오는 것을 잡는다). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float DodgeStringBonus = .15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float ChainStartFraction = .35f;
    /** 추격: 후딜의 연계 지점에서 플레이어가 이보다 멀리(반격할 수 없는 거리) 앞에 있으면 후딜을 끊고 바로 다음 행동을 고른다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PursuitDistance = 360.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PursuitChance = .75f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float PhaseTwoPursuitChance = 1.f;
    /** 몰아치기의 끝: 연계나 추격으로 이어진 공격은 후딜을 줄이지 않는다(1 = 카드에 적힌 그대로). 몰아친 뒤에는 반드시 큰 틈이 온다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Chain") float EnderRecoveryScale = 1.f;
    /** 헛침: 공격이 닿지 않았으면 후딜이 시작될 때 상체가 앞으로 쏠렸다 돌아오고(도), 몸이 조금 딸려 나간다(cm/초). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float WhiffBowPitch = 10.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float WhiffLurch = 200.f;
    /** 헛친 뒤에는 시선이 이 배수로 빨리 플레이어를 찾는다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float WhiffLookSpeedScale = 2.2f;
    /** 숨 고르기: 후딜 동안 상체가 오르내리는 폭(도)과 빠르기(초당 횟수). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float BreathPitch = 2.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Acting") float BreathRate = .9f;
    /** 각 맞추는 걸음: 공격 뒤 플레이어가 이 각도 범위로 비껴 있으면 제자리 턴 대신 걸으면서 돌아본다. 그보다 크면 턴 동작을 쓴다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FacingStepMinAngle = 32.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FacingStepMaxAngle = 110.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float FacingStepDoneAngle = 12.f;
    /** 숙이며 빠지기: 붙어서 맞고 있으면(2초에 SwayHits번 이상) 상체를 숙이며 뒤로 빠르게 빠진다. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SwayChance = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") int32 SwayHits = 2;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SwaySpeed = 520.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SwayDistance = 330.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Footwork") float SwayDuckPitch = 14.f;
    /** 공격을 준비하는 동안 제자리에서 플레이어 쪽으로 돌 수 있는 각도. 넘으면 방향이 고정된다(옆으로 피하면 빗나간다). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Turn") float WindupTurnLimit = 25.f;
    // ---- 플레이어의 가드 ----
    /** 저스트 가드: 맞기 직전 이 시간 안에 올린 가드는 피해를 받지 않는다(보통 가드는 20%를 받는다). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Guard Reward") float JustGuardWindow = .25f;
    /** 뒤쪽 대응을 요청하는 동안만 참: 정면 조건을 건너뛰고 카드를 바꿀 수 있다. */
    bool bRearResponseScope = false;
    TWeakObjectPtr<UObject> RearCard;
    UPROPERTY(BlueprintReadOnly, Category="Boss|Intent") FString Status;
private:
    void Advance();
    void Finish(bool bAttack, const FString& Reason, bool bCountFailure = true);
    void TickReassessment(float DeltaTime);
    void StartSideMove(const FVector& Destination, bool bLeft, bool bProbe);
    void Publish(const FString& Phase, const FString& Reason);
    void UpdateCombatEffects();
    void ClearCombatEffects();
    bool ReachableCenter(const FVector& Desired, FVector& Center) const;
    TWeakObjectPtr<UObject> Action;
    TWeakObjectPtr<AActor> Target;
    int32 Slot = INDEX_NONE;
    TMap<int32, double> FailedUntilBySlot;
    double StartedAt = 0.0;
    double NextPlanAt = 0.0;
    float PreviousSpeed = 0.f;
    float GoalMaxDistance = 0.f;
    float GoalMinDistance = 0.f;
    int32 ConsecutiveEntryFailures = 0;
    double LastEntryFailureAt = -1.0;
    double ReassessUntil = 0.0;
    double PostAttackDecisionUntil = 0.0;
    FVector SideEntryGoal = FVector::ZeroVector;
    bool bActive = false;
    bool bReassessing = false;
    bool bSideEntryActive = false;
    bool bSideEntryUsed = false;
    bool bSideMoveIsProbe = false;
    bool bPostProbeRequested = false;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> PreviousOverlay;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> GuardOverlay;
    UPROPERTY(Transient) TObjectPtr<UParticleSystemComponent> UpperChargeFX;
    bool bGuardOverlayActive = false;
    bool bUpperBurstPlayed = false;
    /** 전진 애니메이션(RunIn)의 전진량을 시작 거리에 맞춰 줄인다. 전진 구간마다 한 번 정한다. */
    void UpdateTravelScale();
    void UpdateComboStages();
    void UpdateChain(float Elapsed, float Remaining);
    bool RequestSlot(int32 SlotIndex);
    void AddExtraCards();
    mutable int32 StringIntentDecision = -1;
    mutable bool bStringIntent = false;
    bool bLinkWanted = false;        // 이번 후딜에서 다음 타로 이으려 하는가(열린 후딜에서 한 번 계획한다)
    bool bStringEndLogged = false;
    bool bLinkPivot = false;         // 이을 공격이 돌아서며 치는 것인가(정면 조건을 건너뛰고 준비 동작 동안 돈다)
    float LinkAngle = 0.f;
    int32 StringHitsWanted = 1;      // 이번 몰아치기에서 치려는 공격 수(Utility가 정한다)
    TArray<int32> StringUsed;        // 이번 몰아치기에서 이미 친 공격(ActionId)
    bool bDodgedThisAttack = false;  // 이번 공격 동안 플레이어가 회피했는가
    double DodgeCountSeen = 0.0;
    bool RequestLinkSlot(int32 SlotIndex, bool bPivot);
    int32 ChainSlot = INDEX_NONE;    // 후딜을 끊었고, Ready가 되면 바로 요청할 자리
    bool bChainedAttack = false;     // 지금 공격이 연계로 나온 것인가
    int32 ChainDepth = 0;            // 지금 공격이 몰아치기(연계·추격)의 몇 번째인가(0 = 첫 공격). 세 번까지만 잇는다
    bool bPursuitWanted = false;     // 이번 후딜에서 멀어진 플레이어를 쫓을 것인가
    bool bPursuitExit = false;       // 추격으로 후딜을 끊었다: 발놀림 없이 바로 고른다
    void UpdateWhiff();
    bool TryFacingStep();
    bool bFacingStep = false;        // 지금 기동이 "각 맞추는 걸음"인가
    bool bSwayBack = false;          // 지금 기동이 "숙이며 빠지기"인가
    void UpdateWindupTurn();
    float WindupStartYaw = 0.f;
    bool bWindupTracked = false;
    bool bWasAttacking = false;
    bool bAttackConnected = false;   // 이번 공격이 닿았는가(맞혔거나 막혔다)
    bool bWhiffed = false;           // 이번 후딜은 헛친 뒤의 후딜인가
    bool bAttackHit = false;         // 이번 공격이 피해를 줬는가(막힌 것은 아니다)
    bool bRecoveryOpen = false;      // 후딜의 하위 상태: 거짓 = 닫힘(어떤 이유로도 못 나감), 참 = 열림(규칙이 맞으면 나감)
    double WhiffPlayerHealth = -1.0;
    double WhiffPressure = -1.0;
    float BowPitch = 0.f;
    float BowVelocity = 0.f;
    float BreathNow = 0.f;
    bool bExtraCardsAdded = false;
    void UpdateLook(float DeltaTime);
    void UpdateHealthBar(float DeltaTime);
    void UpdateGuardReward();
    void ShowNotice(const FString& Message);
    double LastGuardPressure = -1.0;
    double LastPlayerHealth = -1.0;
    FString BarNotice;
    double BarNoticeUntil = -1.0;
    TSharedPtr<class SBossHealthBar> HealthBar;
    /** 처음 보는 사람이 읽는 AI 표시(왼쪽 HFSM·GOAP, 오른쪽 Utility). 콘솔 boss.Panel 0 = 끔, 1 = 이 표시, 2 = 예전 글자 패널. */
    void UpdateAIPanel();
    TSharedPtr<class SBossAIPanel> AIPanel;
    // ---- 2페이즈 과열과 점프 내려찍기의 표시 ----
    void UpdateOverheat(float DeltaTime);
    bool TryVent();
    void UpdateSlam(float DeltaTime);
    void ClearSlamDecals();
    float Heat = 0.f;
    bool bVenting = false;
    UPROPERTY(Transient) TObjectPtr<class UMaterialInstanceDynamic> HeatOverlay;
    UPROPERTY(Transient) TArray<TObjectPtr<UParticleSystemComponent>> HeatFX;
    UPROPERTY(Transient) TObjectPtr<UParticleSystemComponent> VentFX;
    UPROPERTY(Transient) TObjectPtr<class UPointLightComponent> HeatLight;
    // 김: 몸 여러 곳에서 피어오르는 뭉치들. 열이 높을수록, 지쳐서 멈춘 동안에는 훨씬 많이 나온다.
    void UpdateSteam(float DeltaTime, bool bHot, bool bBurst);
    struct FSteamPuff { FVector Location = FVector::ZeroVector; FVector Velocity = FVector::ZeroVector; float Age = 0.f; float Life = 0.f; float StartSize = 0.f; float EndSize = 0.f; float Peak = 0.f; bool bAlive = false; };
    TArray<FSteamPuff> SteamPuffs;
    UPROPERTY(Transient) TArray<TObjectPtr<class UMaterialBillboardComponent>> SteamSprites;
    UPROPERTY(Transient) TArray<TObjectPtr<class UMaterialInstanceDynamic>> SteamMaterials;
    float SteamDebt = 0.f;
    // 지친 동작: 비틀거리기 시작하는 동작 뒤에 비틀거리는 동작을 이어 붙인다. 점프 착지 뒤에도 쓴다.
    void PlayExhausted(float Seconds);
    void UpdateExhausted();
    double ExhaustLoopAt = -1.0;
    double ExhaustUntil = -1.0;
    UPROPERTY(Transient) TObjectPtr<class UAnimMontage> ExhaustMontage;
    double SlamStunAt = -1.0;
    UPROPERTY(Transient) TObjectPtr<class UDecalComponent> SlamDirectDecal;
    UPROPERTY(Transient) TObjectPtr<class UDecalComponent> SlamShockDecal;
    UPROPERTY(Transient) TObjectPtr<class UDecalComponent> SlamWaveDecal;
    UPROPERTY(Transient) TObjectPtr<class UMaterialInstanceDynamic> SlamDirectMaterial;
    UPROPERTY(Transient) TObjectPtr<class UMaterialInstanceDynamic> SlamShockMaterial;
    UPROPERTY(Transient) TObjectPtr<class UMaterialInstanceDynamic> SlamWaveMaterial;
    double SlamStartedAt = -1.0;
    double SlamWaveAt = -1.0;
    FVector SlamWaveCenter = FVector::ZeroVector;
    float BarTrail = 1.f;
    float BarDamage = 0.f;
    float BarOpacity = 0.f;
    double BarLastHitAt = -100.0;
    double BarDeadAt = -1.0;
    double BarHealth = -1.0;
    /** 맞은 시각들(최근 것만). "붙어서 계속 때리는 플레이어"를 알아보는 데 쓴다. */
    TArray<double> HitTimes;
    void UpdateFlinch(float DeltaTime);
    /** 도발과 대기 변주. 도발 중이면 참을 돌려준다(그동안 다른 이동 처리를 하지 않는다). */
    bool UpdatePerformance(float DeltaTime);
    float LookYaw = 0.f;
    bool bLookConfigured = false;
    double LastHealth = -1.0;
    FVector FlinchOffset = FVector::ZeroVector;
    FVector FlinchVelocity = FVector::ZeroVector;
    FVector MeshBaseLocation = FVector::ZeroVector;
    bool bMeshBaseSaved = false;
    bool bPerforming = false;
    bool bKnockdownTaunted = false;
    double PerformUntil = 0.0;
    double NextTauntAt = 0.0;
    double NextLaughAt = 0.0;
    double IdleSince = -1.0;
    double NextIdleVariationAt = 0.0;
    UPROPERTY(Transient) TObjectPtr<class UAnimMontage> PerformMontage;
    UPROPERTY(Transient) TObjectPtr<class UAnimMontage> IdleVariationMontage;
    int32 ComboStage = 0;
    float ComboLastPosition = 0.f;
    void UpdateRecoveryTurn(float DeltaTime);
    void TryRearResponse();
    void UpdateSprint();
    void UpdateTurnSync();
    UPROPERTY(Transient) TObjectPtr<class UAnimMontage> SprintMontage;
    TWeakObjectPtr<const class UAnimMontage> SyncedTurnMontage;
    float SavedTurnSpeed = -1.f;
    float TurnStartYaw = 0.f;        // 제자리 턴: 시작할 때의 방향
    float TurnTotal = 0.f;           // 돌아야 할 각도(부호 있음)
    float TurnCurveStart = 0.f;      // 턴 동작의 커브가 시작할 때 가리키는 각도
    float TurnStepEnd = 0.f;         // 발이 다 디디는 시각(동작 안의 초)
    float RearTurnRate = 300.f;
    bool bApproachSpeedApplied = false;
public:
    /** 추첨 직후 한 프레임 동안만: 당첨 표시를 지우고 화면에 보일 진짜 점수로 되돌릴 값. */
    TArray<double> TrueWeights;
    bool bRestoreWeights = false;
private:
    void RestoreTrueWeights();
    bool bFlankExitDone = false;
    void TryFootwork();
    void TickFootwork(float DeltaTime);
    void EndFootwork(bool bReturnToReady, const FString& Reason);
    bool bFootworkActive = false;
    void BeginFootworkLeg();
    /** 이번 기동의 걸음들(EBossPositionAction 값). 계획이 낸 순서 그대로 하나씩 한다. */
    TArray<uint8> FootworkLegs;
    int32 FootworkLegIndex = 0;
    double FootworkLegStartedAt = 0.0;
    float LegSweepTarget = 0.f;      // 돌기: 플레이어 둘레로 돌 각도
    float LegSwept = 0.f;
    float LegLastBearing = 0.f;
    float LegRadius = 0.f;           // 돌기: 유지할 간격
    float CircleSweepWanted = 0.f;
    bool bLegFlipped = false;
    double FootworkStartedAt = 0.0;
    float FootworkSpeedBefore = 0.f;
    /** 발을 옮기지 않고 연달아 친 공격 수. 발놀림을 하거나 공격하러 걸어 들어가면 0으로 돌아간다. */
    int32 AttackStreak = 0;
    FVector LastRecoveryLocation = FVector::ZeroVector;
    void UpdateRearResponse(float DeltaTime);
    bool bRearResponseActive = false;
    double RearResponseReadyAt = 0.0;
    double RecoveryStartedAt = -1.0;
    TWeakObjectPtr<const class UAnimMontage> TravelMontage;
    float TravelBurstEnd = -1.f;
};

UCLASS()
class BATTLEBOSSPLANNING_API UBossCombatIntentLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Bypasses distance/facing/cooldown starts only in the scoped MotionLab manual request. */
    UFUNCTION(BlueprintPure, Category="Boss|Motion Lab") static bool IsLabStartLimitOverride(AActor* Boss);
    static bool IsLabRangeMeasurementAction(AActor* Boss);
    /** Called after validated ordinary configuration, before entering attack. Never changes Arena choices. */
    UFUNCTION(BlueprintCallable, Category="Boss|Motion Lab") static void ConfigureLabRightFootPunch(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void BeginSelectedAttackIntent(AActor* Boss);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static FString DescribeCombatDebug(AActor* Boss);
    /** One finite step in an ordinary punch; sampled once when the step opens. */
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static float OrdinaryPunchStepDistance(AActor* Boss, float AuthoredDistance);
    /** Only a later strike in a selected boxing pattern may take a fresh forward step. */
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static bool IsComboFollowStep(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void CommitComboStep(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Battle|Feedback") static void PlayPlayerHitShake(AActor* Player, float Scale = 1.15f);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static bool CanStartPendingSlam(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void RecordAttackRecoveryEnd(AActor* Boss);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static bool IsAttackIntentActive(AActor* Boss);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static float AdjustIntentCandidate(AActor* Boss, int32 Slot, float Score);
    /** Called after every candidate has been scored, before the weighted draw. */
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void FinalizeIntentScores(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void EnsureActionCooldownCapacity(AActor* Boss);
    /** False means the two-hit pattern has entered its abort recovery. Other patterns pass through. */
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static bool ContinueTwoHitOrRecover(AActor* Boss);
};
