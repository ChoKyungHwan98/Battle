#include "BossCombatIntentComponent.h"
#include "BossPositionPlanner.h"
#include "AIController.h"
#include "Navigation/PathFollowingComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameplayTagContainer.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet/GameplayStatics.h"
#include <limits>

namespace
{
bool PendingSlamRange(bool bPending, bool bPhaseTwo, float Distance, float Min, float Max)
{
    return bPending && bPhaseTwo && FMath::IsFinite(Distance) && Distance >= Min && Distance <= Max;
}
float DistanceBandMultiplier(int32 Id, double Distance)
{
    // Ordinary punches can prepare a short entry in the 400..500 gap, never at dash range.
    return (Id == 0 || Id == 1 || Id == 9) && Distance >= 500.0 ? 0.f : 1.f;
}

float OnePunchStep(float StartDistance, float AuthoredDistance, float RetreatSpeed)
{
    if (!FMath::IsFinite(StartDistance) || !FMath::IsFinite(AuthoredDistance)
        || !FMath::IsFinite(RetreatSpeed)) return 0.f;
    if (StartDistance < 300.f) return FMath::Clamp(AuthoredDistance, 0.f, 145.f);
    // Designer's single-step band is 300..400cm. Do not add steps or change tempo.
    const float Lead = FMath::Clamp(RetreatSpeed, 0.f, 450.f) * .1f;
    return FMath::Clamp(FMath::Max(AuthoredDistance, StartDistance - 255.f + Lead), 0.f, 145.f);
}

bool ChoosePostAttackProbe(int32 ActionId, float Distance, float Min, float Max, float Dot,
    bool bFreshRecovery, bool bCooldownReady, float Roll, float Chance)
{
    // Keep reactive/special attacks direct; only ordinary boxing preparations vary.
    return bFreshRecovery && bCooldownReady && (ActionId == 0 || ActionId == 1 || ActionId == 9)
        && Distance >= FMath::Max(225.f, Min + 20.f) && Distance <= Max && Dot >= .5f
        && Roll >= 0.f && Roll < FMath::Clamp(Chance, 0.f, 1.f);
}

FVector LateralEntryGoal(const FVector& Boss, const FVector& Player, float Range, float Degrees)
{
    FVector Goal = Player + (Boss - Player).GetSafeNormal2D().RotateAngleAxis(Degrees, FVector::UpVector) * Range;
    Goal.Z = Boss.Z;
    return Goal;
}

// Failures in unrelated encounters/time windows must not accumulate forever.
bool RecordEntryFailure(int32& Count, double& LastAt, double Now, double Window)
{
    Count = LastAt >= 0.0 && Now >= LastAt && Now - LastAt <= Window ? Count + 1 : 1;
    LastAt = Now;
    if (Count < 2) return false;
    Count = 0;
    return true;
}

double Number(const UObject* O, FName Name, double Default = 0.0)
{
    if (!IsValid(O)) return Default;
    if (const FNumericProperty* P = FindFProperty<FNumericProperty>(O->GetClass(), Name))
    {
        const void* V = P->ContainerPtrToValuePtr<void>(O);
        return P->IsInteger() ? static_cast<double>(P->GetSignedIntPropertyValue(V)) : P->GetFloatingPointPropertyValue(V);
    }
    return Default;
}
void SetNumber(UObject* O, FName Name, double Value)
{
    if (IsValid(O)) if (FNumericProperty* P = FindFProperty<FNumericProperty>(O->GetClass(), Name))
    {
        void* V = P->ContainerPtrToValuePtr<void>(O);
        if (P->IsInteger()) P->SetIntPropertyValue(V, static_cast<int64>(Value));
        else P->SetFloatingPointPropertyValue(V, Value);
    }
}
bool Flag(const UObject* O, FName Name)
{
    const FBoolProperty* P = IsValid(O) ? FindFProperty<FBoolProperty>(O->GetClass(), Name) : nullptr;
    return P && P->GetPropertyValue_InContainer(O);
}
void SetFlag(UObject* O, FName Name, bool Value)
{
    if (IsValid(O)) if (FBoolProperty* P = FindFProperty<FBoolProperty>(O->GetClass(), Name)) P->SetPropertyValue_InContainer(O, Value);
}
UObject* Object(const UObject* O, FName Name)
{
    const FObjectPropertyBase* P = IsValid(O) ? FindFProperty<FObjectPropertyBase>(O->GetClass(), Name) : nullptr;
    return P ? P->GetObjectPropertyValue_InContainer(O) : nullptr;
}
void SetText(UObject* O, FName Name, const FString& Value)
{
    if (IsValid(O)) if (FStrProperty* P = FindFProperty<FStrProperty>(O->GetClass(), Name)) P->SetPropertyValue_InContainer(O, Value);
}
FString Text(const UObject* O, FName Name)
{
    if (IsValid(O)) if (const FStrProperty* P = FindFProperty<FStrProperty>(O->GetClass(), Name))
        return P->GetPropertyValue_InContainer(O);
    return FString();
}
bool StateIs(const UObject* O, const TCHAR* Name)
{
    const FStructProperty* P = IsValid(O) ? FindFProperty<FStructProperty>(O->GetClass(), TEXT("BossState")) : nullptr;
    return P && P->Struct == FGameplayTag::StaticStruct()
        && P->ContainerPtrToValuePtr<FGameplayTag>(O)->GetTagName() == FName(Name);
}
void Invoke(AActor* Boss, FName Name, const FString& Text = FString())
{
    if (!IsValid(Boss)) return;
    if (UFunction* Fn = Boss->FindFunction(Name))
    {
        FStructOnScope Params(Fn);
        for (TFieldIterator<FProperty> It(Fn); It; ++It)
        {
            if (!It->HasAnyPropertyFlags(CPF_Parm) || It->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
            if (FStrProperty* P = CastField<FStrProperty>(*It)) P->SetPropertyValue_InContainer(Params.GetStructMemory(), Text);
        }
        Boss->ProcessEvent(Fn, Params.GetStructMemory());
    }
}

bool FillTransitionParameters(UFunction* Fn, void* Params, const FGameplayTag& Expected,
    const FGameplayTag& Next, const FString& Reason)
{
    if (!Fn || !Params || !Expected.IsValid() || !Next.IsValid()) return false;
    FStructProperty* ExpectedPin = FindFProperty<FStructProperty>(Fn, TEXT("ExpectedState"));
    FStructProperty* NextPin = FindFProperty<FStructProperty>(Fn, TEXT("NewState"));
    FStrProperty* ReasonPin = FindFProperty<FStrProperty>(Fn, TEXT("Reason"));
    if (!ExpectedPin || !NextPin || !ReasonPin
        || ExpectedPin->Struct != FGameplayTag::StaticStruct() || NextPin->Struct != FGameplayTag::StaticStruct()
        || !ExpectedPin->HasAnyPropertyFlags(CPF_Parm) || !NextPin->HasAnyPropertyFlags(CPF_Parm)
        || !ReasonPin->HasAnyPropertyFlags(CPF_Parm)) return false;
    // ExpectedState is the source-state guard, never the requested destination.
    *ExpectedPin->ContainerPtrToValuePtr<FGameplayTag>(Params) = Expected;
    *NextPin->ContainerPtrToValuePtr<FGameplayTag>(Params) = Next;
    ReasonPin->SetPropertyValue_InContainer(Params, Reason);
    return true;
}

bool TransitionState(AActor* Boss, const TCHAR* Expected, const TCHAR* Next, const FString& Reason)
{
    if (!IsValid(Boss) || !StateIs(Boss, Expected)) return false;
    UFunction* Fn = Boss->FindFunction(TEXT("TransitionBossState"));
    if (!Fn) return false;
    FStructOnScope Params(Fn);
    if (!FillTransitionParameters(Fn, Params.GetStructMemory(),
        FGameplayTag::RequestGameplayTag(FName(Expected)), FGameplayTag::RequestGameplayTag(FName(Next)), Reason)) return false;
    Boss->ProcessEvent(Fn, Params.GetStructMemory());
    // A successful ProcessEvent call does not mean the Blueprint accepted the transition.
    return StateIs(Boss, Next);
}
}

UBossCombatIntentComponent::UBossCombatIntentComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = true;
}

void UBossCombatIntentComponent::Publish(const FString& Phase, const FString& Reason)
{
    Status = Reason;
    SetFlag(GetOwner(), TEXT("bAttackIntentActive"), bActive);
    SetText(GetOwner(), TEXT("IntentPhase"), Phase);
    SetText(GetOwner(), TEXT("IntentReason"), Reason);
    SetText(GetOwner(), TEXT("GoapReason"), Reason);
}

void UBossCombatIntentComponent::BeginSelectedIntent()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss || IsActive() || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    Action = Object(Boss, TEXT("ActiveAction"));
    Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    Slot = static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1));
    if (!Action.IsValid() || !Target.IsValid() || Slot < 0) return;
    const double Now = GetWorld()->GetTimeSeconds();
    StartedAt = NextPlanAt = Now;
    bSideEntryActive = bSideEntryUsed = false;
    PreviousSpeed = Boss->GetCharacterMovement()->MaxWalkSpeed;
    const float Distance = FVector::Dist2D(Boss->GetActorLocation(), Target->GetActorLocation());
    const float StartMax = Number(Action.Get(), TEXT("MaxDistance"));
    const float Facing = FVector::DotProduct(Boss->GetActorForwardVector(),
        (Target->GetActorLocation()-Boss->GetActorLocation()).GetSafeNormal2D());
    const bool bFreshRecovery = Flag(Boss, TEXT("bPostAttackProbePending")) && Now <= PostAttackDecisionUntil;
    bPostProbeRequested = ChoosePostAttackProbe(static_cast<int32>(Number(Action.Get(), TEXT("ActionId"), -1)),
        Distance, Number(Action.Get(), TEXT("MinDistance")), StartMax, Facing, bFreshRecovery,
        Now >= Number(Boss, TEXT("GoapProbeCooldownUntil")), FMath::FRand(), PostAttackProbeChance);
    // Consume once after the Utility choice, never once per scoring tick.
    SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
    PostAttackDecisionUntil = 0;
    // Once entry is needed, go inside the start boundary rather than stopping
    // at its outer edge. Already-close attacks never back away to this target.
    GoalMaxDistance = Distance > StartMax ? FMath::Max(static_cast<float>(Number(Action.Get(), TEXT("MinDistance"))) + 20.f, StartMax - 40.f) : StartMax;
    SetNumber(Boss, TEXT("IntentSelectionDistance"), Distance);
    SetNumber(Boss, TEXT("IntentElapsed"), 0);
    SetNumber(Boss, TEXT("IntentSerial"), Number(Boss, TEXT("IntentSerial")) + 1);
    SetFlag(Boss, TEXT("bCombatApproachActive"), false);
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    Invoke(Boss, TEXT("StopBossLocomotion"));
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Position"), TEXT("선택한 공격을 위한 위치 잡기")))
    {
        FailedUntilBySlot.Add(Slot, Now + 3.0);
        Publish(TEXT("cancelled"), TEXT("위치 잡기 상태 전환이 거부됨"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_aborted"));
        return;
    }
    bActive = true;
    Publish(TEXT("position"), TEXT("선택한 공격을 유지하며 진입"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_begin"));
    Advance();
}

void UBossCombatIntentComponent::RecordAttackRecoveryEnd()
{
    AActor* Boss = GetOwner();
    if (IsActive() || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    const int32 FinishedId = static_cast<int32>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("ActionId"), -1));
    const bool bOrdinaryCombatEnd = (FinishedId >= 0 && FinishedId <= 6) || FinishedId == 9;
    SetFlag(Boss, TEXT("bPostAttackProbePending"), bOrdinaryCombatEnd);
    PostAttackDecisionUntil = bOrdinaryCombatEnd ? GetWorld()->GetTimeSeconds() + 2.0 : 0.0;
}

bool UBossCombatIntentComponent::ReachableCenter(const FVector& Desired, FVector& Center) const
{
    const ACharacter* Boss = Cast<ACharacter>(GetOwner());
    UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!Boss || !Nav) return false;
    const UCapsuleComponent* Capsule = Boss->GetCapsuleComponent();
    const float Half = Capsule->GetScaledCapsuleHalfHeight();
    const float Radius = Capsule->GetScaledCapsuleRadius();
    const FVector FloorGoal = Desired - FVector(0.f, 0.f, Half);
    FNavLocation Projected;
    const FNavAgentProperties& Agent = Boss->GetCharacterMovement()->GetNavAgentPropertiesRef();
    if (!Nav->ProjectPointToNavigation(FloorGoal, Projected, FVector(60.f, 60.f, 120.f), &Agent)
        || FVector::Dist2D(FloorGoal, Projected.Location) > 60.f) return false;
    UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(
        GetWorld(), Boss->GetActorLocation(), Projected.Location, const_cast<ACharacter*>(Boss));
    if (!Path || !Path->IsValid() || Path->IsPartial() || Path->PathPoints.Num() < 2) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BossIntentPath), false, Boss);
    const FCollisionShape Shape = FCollisionShape::MakeCapsule(Radius, FMath::Max(Radius, Half - 2.f));
    FVector Previous = Boss->GetActorLocation();
    for (int32 I = 1; I < Path->PathPoints.Num(); ++I)
    {
        const FVector Next = Path->PathPoints[I] + FVector(0.f, 0.f, Half + 2.f);
        FHitResult Hit;
        if (GetWorld()->SweepSingleByChannel(Hit, Previous, Next, FQuat::Identity, ECC_Pawn, Shape, Query)) return false;
        Previous = Next;
    }
    Center = Projected.Location + FVector(0.f, 0.f, Half);
    return true;
}

void UBossCombatIntentComponent::Advance()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    AActor* Player = Target.Get();
    if (!Boss || !IsValid(Player) || !Action.IsValid()) { Finish(false, TEXT("대상 또는 공격이 사라짐"), false); return; }
    AAIController* Controller = Cast<AAIController>(Boss->GetController());
    if (bSideEntryActive)
    {
        // Hold the chosen world-space destination: do not chase a moving side point.
        if (FVector::Dist2D(Boss->GetActorLocation(), SideEntryGoal) > 20.f)
        {
            if (!Controller || Controller->GetMoveStatus() == EPathFollowingStatus::Idle)
                Finish(false, TEXT("측면 진입 경로에서 이동 중단"));
            return;
        }
        bSideEntryActive = false;
        if (Controller) Controller->StopMovement();
        Invoke(Boss, TEXT("RecordCombatQA"), bSideMoveIsProbe ? TEXT("intent_probe_arrived") : TEXT("intent_side_arrived"));
    }
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const float Distance = Delta.Size2D();
    const float Facing = FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D());
    const float Min = Number(Action.Get(), TEXT("MinDistance"));
    const float MinimumDot = Number(Boss, TEXT("AttackStartMinDot"), .5);
    SetNumber(Boss, TEXT("UtilityDistance"), Distance);
    if (bPostProbeRequested)
    {
        bPostProbeRequested = false;
        FVector LeftProbe, RightProbe;
        const auto ProbeOpen = [&](float Degrees, FVector& Destination)
        {
            if (!ReachableCenter(LateralEntryGoal(Boss->GetActorLocation(), Player->GetActorLocation(), Distance, Degrees), Destination)) return false;
            const float Range = FVector::Dist2D(Destination, Player->GetActorLocation());
            return Range >= Min && Range <= GoalMaxDistance;
        };
        const float Angle = FMath::Clamp(SideEntryAngle, 5.f, 35.f);
        bool bLeftOpen = ProbeOpen(Angle, LeftProbe), bRightOpen = ProbeOpen(-Angle, RightProbe);
        // When both paths are valid, avoid a permanently preferred orbit direction.
        if (bLeftOpen && bRightOpen)
        {
            if (FMath::RandBool()) bLeftOpen = false;
            else bRightOpen = false;
        }
        const auto Probe = UBossPositionPlanner::PlanAttackPosition(Distance, Facing, Min, GoalMaxDistance, MinimumDot,
            false, false, bLeftOpen, bRightOpen, true, SideEntrySpeed);
        if (Probe.bFound && (Probe.FirstAction == EBossPositionAction::OrbitLeft || Probe.FirstAction == EBossPositionAction::OrbitRight))
        {
            const bool bLeft = Probe.FirstAction == EBossPositionAction::OrbitLeft;
            SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Probe.FirstAction));
            StartSideMove(bLeft ? LeftProbe : RightProbe, bLeft, true);
            return;
        }
        // A blocked optional probe must not discard an otherwise valid attack.
        Publish(TEXT("position"), TEXT("옆걸음 여유가 없어 선택한 공격을 바로 준비"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_probe_skipped"));
    }
    if (Distance >= Min && Distance <= GoalMaxDistance && Facing >= MinimumDot)
    {
        Finish(true, TEXT("선택한 공격을 시작할 위치 도착"));
        return;
    }
    // No retreat is requested when the chosen attack already has a valid close band.
    const FVector Toward = Delta.GetSafeNormal2D();
    const float DesiredRange = Distance > GoalMaxDistance ? GoalMaxDistance - 10.f : Min + 20.f;
    FVector Goal = Player->GetActorLocation() - Toward * DesiredRange;
    Goal.Z = Boss->GetActorLocation().Z;
    FVector Reachable;
    const bool bNeedTranslation = Distance > GoalMaxDistance || Distance < Min;
    const bool bPathOpen = bNeedTranslation && ReachableCenter(Goal, Reachable);
    FVector LeftEntry, RightEntry;
    bool bLeftEntryOpen = false, bRightEntryOpen = false;
    if (bNeedTranslation && !bPathOpen && !bSideEntryUsed)
    {
        const auto SideOpen = [&](float Degrees, FVector& Destination)
        {
            if (!ReachableCenter(LateralEntryGoal(Boss->GetActorLocation(), Player->GetActorLocation(), DesiredRange, Degrees), Destination)) return false;
            const float Range = FVector::Dist2D(Destination, Player->GetActorLocation());
            return Range >= Min && Range <= GoalMaxDistance;
        };
        const float Angle = FMath::Clamp(SideEntryAngle, 5.f, 35.f);
        // Facing toward the player, positive rotation of the outward radius is left.
        bLeftEntryOpen = SideOpen(Angle, LeftEntry);
        bRightEntryOpen = SideOpen(-Angle, RightEntry);
    }
    const auto Plan = UBossPositionPlanner::PlanAttackEntry(Distance, Facing, Min, GoalMaxDistance, MinimumDot,
        bPathOpen && Distance > GoalMaxDistance, bPathOpen && Distance < Min, bLeftEntryOpen, bRightEntryOpen, RunSpeed);
    if (!Plan.bFound) { Finish(false, TEXT("공격할 자리로 가는 길이 막힘")); return; }
    SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Plan.FirstAction));
    if (Plan.FirstAction == EBossPositionAction::FaceTarget)
    {
        if (Controller) Controller->StopMovement();
        Publish(TEXT("face"), TEXT("선택한 공격을 유지하며 몸 돌리기"));
    }
    else if (Plan.FirstAction == EBossPositionAction::DirectApproach || Plan.FirstAction == EBossPositionAction::StepBack)
    {
        if (!Controller) { Finish(false, TEXT("이동 제어기가 없음")); return; }
        Boss->GetCharacterMovement()->MaxWalkSpeed = Plan.FirstAction == EBossPositionAction::StepBack ? 170.f : RunSpeed;
        const FVector FloorDestination = Reachable - FVector(0.f, 0.f, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
        const auto Request = Controller->MoveToLocation(FloorDestination, 10.f, false, true, true, false, nullptr, false);
        if (Request == EPathFollowingRequestResult::Failed) { Finish(false, TEXT("이동 요청 실패")); return; }
        Publish(TEXT("enter"), Plan.FirstAction == EBossPositionAction::StepBack
            ? TEXT("너무 가까워 한 걸음 거리 확보") : TEXT("선택한 공격을 위해 짧게 진입"));
    }
    else if (Plan.FirstAction == EBossPositionAction::OrbitLeft || Plan.FirstAction == EBossPositionAction::OrbitRight)
    {
        const bool bLeft = Plan.FirstAction == EBossPositionAction::OrbitLeft;
        StartSideMove(bLeft ? LeftEntry : RightEntry, bLeft, false);
    }
}

void UBossCombatIntentComponent::StartSideMove(const FVector& Destination, bool bLeft, bool bProbe)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    AAIController* Controller = Boss ? Cast<AAIController>(Boss->GetController()) : nullptr;
    if (!Controller) { Finish(false, TEXT("측면 이동 제어기가 없음")); return; }
    SideEntryGoal = Destination;
    Boss->GetCharacterMovement()->MaxWalkSpeed = FMath::Max(1.f, SideEntrySpeed);
    const FVector FloorDestination = SideEntryGoal - FVector(0.f, 0.f, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    const auto Request = Controller->MoveToLocation(FloorDestination, 10.f, false, true, true, false, nullptr, false);
    if (Request == EPathFollowingRequestResult::Failed) { Finish(false, TEXT("측면 진입 이동 요청 실패")); return; }
    bSideEntryActive = bSideEntryUsed = true;
    bSideMoveIsProbe = bProbe;
    if (bProbe) SetNumber(Boss, TEXT("GoapProbeCooldownUntil"), GetWorld()->GetTimeSeconds() + 4.0);
    Publish(bProbe ? TEXT("probe") : TEXT("side_entry"), bProbe
        ? (bLeft ? TEXT("다음 공격 유지: 왼쪽으로 짧게 자리를 바꿈") : TEXT("다음 공격 유지: 오른쪽으로 짧게 자리를 바꿈"))
        : (bLeft ? TEXT("정면 길이 막혀 왼쪽 공격 자리로 이동") : TEXT("정면 길이 막혀 오른쪽 공격 자리로 이동")));
    Invoke(Boss, TEXT("RecordCombatQA"), bProbe ? TEXT("intent_probe_begin") : TEXT("intent_side_begin"));
}

void UBossCombatIntentComponent::Finish(bool bAttack, const FString& Reason, bool bCountFailure)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss) { bActive = false; return; }
    bActive = false;
    bSideEntryActive = false;
    Invoke(Boss, TEXT("StopBossLocomotion"));
    Boss->GetCharacterMovement()->MaxWalkSpeed = PreviousSpeed;
    const bool bReturnedToReady = TransitionState(Boss, TEXT("Boss.Combat.Position"), TEXT("Boss.Combat.Ready"), Reason);
    const bool bMayAttack = bAttack && bReturnedToReady;
    Publish(bMayAttack ? TEXT("attack") : TEXT("cancelled"),
        bAttack && !bReturnedToReady ? TEXT("공격 전 대기 상태 복귀가 거부됨") : Reason);
    if (bMayAttack)
    {
        SetText(Boss, TEXT("AttackRequestSource"), TEXT("intent"));
        Invoke(Boss, TEXT("BeginCombatAction"));
        if (Flag(Boss, TEXT("bActionStartAllowed")))
        {
            ConsecutiveEntryFailures = 0;
            LastEntryFailureAt = -1.0;
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_arrived"));
            return;
        }
        Publish(TEXT("cancelled"), TEXT("도착 후 공격 시작 검사에서 거부됨"));
    }
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_aborted"));
    // Death, knockdown and externally changed states are interruptions, not bad entries.
    if (!bCountFailure || !StateIs(Boss, TEXT("Boss.Combat.Ready"))
        || Number(Boss, TEXT("CurrentHealth")) <= 0 || !Target.IsValid()
        || Number(Target.Get(), TEXT("CurrentHealth")) <= 0 || Flag(Target.Get(), TEXT("bKnockedDown")))
    {
        ConsecutiveEntryFailures = 0;
        LastEntryFailureAt = -1.0;
        return;
    }
    const double Now = GetWorld()->GetTimeSeconds();
    FailedUntilBySlot.Add(Slot, Now + 3.0);
    if (!RecordEntryFailure(ConsecutiveEntryFailures, LastEntryFailureAt, Now, FailureWindow)) return;
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Observe"),
        TEXT("연속 진입 실패: 추격을 끊고 상황 관찰"))) return;
    bReassessing = true;
    ReassessUntil = Now + FMath::Max(.1f, ReassessDuration);
    SetFlag(Boss, TEXT("bCombatApproachActive"), false);
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    Publish(TEXT("reassess"), TEXT("진입 2회 실패: 잠깐 멈춰 거리를 살핀 뒤 다시 선택"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_reassess_begin"));
}

void UBossCombatIntentComponent::TickReassessment(float DeltaTime)
{
    AActor* Boss = GetOwner();
    const bool bOwnsState = StateIs(Boss, TEXT("Boss.Combat.Observe"));
    const bool bTargetAvailable = Target.IsValid() && Number(Target.Get(), TEXT("CurrentHealth")) > 0
        && !Flag(Target.Get(), TEXT("bKnockedDown"));
    if (!bOwnsState || Number(Boss, TEXT("CurrentHealth")) <= 0 || !bTargetAvailable)
    {
        bReassessing = false;
        if (bOwnsState && Number(Boss, TEXT("CurrentHealth")) > 0)
            TransitionState(Boss, TEXT("Boss.Combat.Observe"), TEXT("Boss.Combat.Ready"), TEXT("대상 변경: 관찰 종료"));
        Publish(TEXT("cancelled"), TEXT("상태 또는 대상 변경으로 관찰 중단"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_reassess_cancelled"));
        return;
    }
    const FRotator Wanted(0.f, (Target->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, TurnSpeed * .5f));
    if (GetWorld()->GetTimeSeconds() < ReassessUntil) return;
    bReassessing = false;
    const bool bReady = TransitionState(Boss, TEXT("Boss.Combat.Observe"), TEXT("Boss.Combat.Ready"), TEXT("관찰 종료: 현재 상황으로 새 행동 선택"));
    Publish(bReady ? TEXT("ready") : TEXT("cancelled"), bReady
        ? TEXT("짧은 관찰 완료: 이전 공격을 강제하지 않고 다시 판단") : TEXT("관찰 후 대기 복귀 거부됨"));
    Invoke(Boss, TEXT("RecordCombatQA"), bReady ? TEXT("intent_reassess_end") : TEXT("intent_reassess_cancelled"));
}

void UBossCombatIntentComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (bReassessing) { TickReassessment(DeltaTime); return; }
    if (!bActive) return;
    AActor* Boss = GetOwner();
    if (!StateIs(Boss, TEXT("Boss.Combat.Position")) || !Target.IsValid()
        || Number(Boss, TEXT("CurrentHealth")) <= 0 || Number(Target.Get(), TEXT("CurrentHealth")) <= 0
        || Flag(Target.Get(), TEXT("bKnockedDown")) || Object(Boss, TEXT("ActiveAction")) != Action.Get()
        || static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1)) != Slot)
    { Finish(false, TEXT("상태 또는 대상 변경으로 진입 중단"), false); return; }
    const double Now = GetWorld()->GetTimeSeconds();
    SetNumber(Boss, TEXT("IntentElapsed"), Now - StartedAt);
    if (Now - StartedAt >= MaxDuration) { Finish(false, TEXT("2초 진입 제한: 다음 행동 재평가")); return; }
    const FRotator Wanted(0.f, (Target->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, TurnSpeed));
    if (Now >= NextPlanAt)
    {
        NextPlanAt = Now + ReplanInterval;
        Advance();
    }
}

void UBossCombatIntentComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    bActive = false;
    bReassessing = false;
    bSideEntryActive = false;
    Super::EndPlay(Reason);
}

float UBossCombatIntentComponent::FailureMultiplier(int32 CandidateSlot) const
{
    const double* Until = FailedUntilBySlot.Find(CandidateSlot);
    return Until && GetWorld() && GetWorld()->GetTimeSeconds() < *Until ? .25f : 1.f;
}

void UBossCombatIntentLibrary::BeginSelectedAttackIntent(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    UBossCombatIntentComponent* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    if (!Intent)
    {
        Intent = NewObject<UBossCombatIntentComponent>(Boss, TEXT("CombatIntent"));
        Boss->AddInstanceComponent(Intent);
        Intent->RegisterComponent();
        Intent->AddTickPrerequisiteActor(Boss);
    }
    Intent->BeginSelectedIntent();
}

void UBossCombatIntentLibrary::RecordAttackRecoveryEnd(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    if (!Intent)
    {
        Intent = NewObject<UBossCombatIntentComponent>(Boss, TEXT("CombatIntent"));
        Boss->AddInstanceComponent(Intent);
        Intent->RegisterComponent();
        Intent->AddTickPrerequisiteActor(Boss);
    }
    Intent->RecordAttackRecoveryEnd();
}

bool UBossCombatIntentLibrary::IsAttackIntentActive(AActor* Boss)
{
    const auto* Intent = IsValid(Boss) ? Boss->FindComponentByClass<UBossCombatIntentComponent>() : nullptr;
    return Intent && Intent->IsActive();
}

float UBossCombatIntentLibrary::AdjustIntentCandidate(AActor* Boss, int32 CandidateSlot, float Score)
{
    if (!IsValid(Boss) || Score <= 0.f) return 0.f;
    const FArrayProperty* Cards = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (CardType)
    {
        FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
        if (!Values.IsValidIndex(CandidateSlot)) return 0.f;
        const UObject* Card = CardType->GetObjectPropertyValue(Values.GetRawPtr(CandidateSlot));
        Score *= DistanceBandMultiplier(static_cast<int32>(Number(Card,TEXT("ActionId"),-1)), Number(Boss,TEXT("UtilityDistance")));
    }
    if (const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>()) Score *= Intent->FailureMultiplier(CandidateSlot);
    return Score;
}

float UBossCombatIntentLibrary::OrdinaryPunchStepDistance(AActor* Boss, float AuthoredDistance)
{
    if (!IsValid(Boss) || !Flag(Boss,TEXT("bPunchFootSync"))) return FMath::Max(0.f, AuthoredDistance);
    const int32 Id = static_cast<int32>(Number(Object(Boss,TEXT("ActiveAction")),TEXT("ActionId"),-1));
    if (Id != 0 && Id != 1) return FMath::Max(0.f, AuthoredDistance);
    const AActor* Player = Cast<AActor>(Object(Boss,TEXT("ObservedPlayer")));
    const float Retreat = IsValid(Player) ? FVector::DotProduct(Player->GetVelocity(), Boss->GetActorForwardVector()) : 0.f;
    // Start distance is captured by eligibility. This pure result is stored once in BeginAttackStep;
    // ticking the attack uses the stored distance and original foot curve, not this query again.
    return FMath::Min(OnePunchStep(Number(Boss,TEXT("AttackStartDistance")), AuthoredDistance, Retreat),
        static_cast<float>(FMath::Max(0.0,Number(Boss,TEXT("AttackAdvanceBudget")))));
}

bool UBossCombatIntentLibrary::CanStartPendingSlam(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    const AActor* Player = Cast<AActor>(Object(Boss,TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerCharacter(Boss,0);
    if (!IsValid(Player)) return false;
    return PendingSlamRange(Flag(Boss,TEXT("bFirstSlamPending")),Flag(Boss,TEXT("bPhaseTwo")),
        FVector::Dist2D(Boss->GetActorLocation(),Player->GetActorLocation()),1000.f,5000.f);
}

FString UBossCombatIntentLibrary::DescribeCombatDebug(AActor* Boss)
{
    if (!IsValid(Boss)) return TEXT("보스 대기 중");
    FString Result = FString::Printf(TEXT("HFSM %s\n%s\n회전 %s | 손 판정 %s | HP %.0f\n\n선택 %s\n거리 %.0fcm | 판단 #%d\n"),
        *Text(Boss, TEXT("StateDisplay")), *Text(Boss, TEXT("TransitionReason")),
        Flag(Boss, TEXT("bCanTurn")) ? TEXT("가능") : TEXT("제한"),
        Flag(Boss, TEXT("bPhysicalStrikeOpen")) ? TEXT("열림") : TEXT("닫힘"),
        Number(Boss, TEXT("CurrentHealth")), *Text(Boss, TEXT("UtilityChoice")),
        Number(Boss, TEXT("UtilityDistance")), static_cast<int32>(Number(Boss, TEXT("UtilityDecisionCount"))));
    const FArrayProperty* Scores = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FNumericProperty* ScoreType = Scores ? CastField<FNumericProperty>(Scores->Inner) : nullptr;
    const FObjectPropertyBase* ActionType = Actions ? CastField<FObjectPropertyBase>(Actions->Inner) : nullptr;
    if (ScoreType && ScoreType->IsFloatingPoint() && ActionType)
    {
        FScriptArrayHelper Values(Scores, Scores->ContainerPtrToValuePtr<void>(Boss));
        FScriptArrayHelper Cards(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
        const bool bHasDecision = Number(Boss, TEXT("UtilityDecisionCount")) > 0 && Values.Num() == Cards.Num();
        const TCHAR* Labels[] = {TEXT("왼손"), TEXT("오른손"), TEXT("어퍼"), TEXT("휩쓸기"),
            TEXT("3타"), TEXT("가드깨기"), TEXT("슈퍼맨"), TEXT("접근"), TEXT("점프"), TEXT("2타")};
        for (int32 I = 0; I < Cards.Num(); ++I)
        {
            UObject* Card = ActionType->GetObjectPropertyValue(Cards.GetRawPtr(I));
            const int32 Id = static_cast<int32>(Number(Card, TEXT("ActionId"), -1));
            const FString Label = Id >= 0 && Id < UE_ARRAY_COUNT(Labels) ? Labels[Id] : Text(Card, TEXT("DisplayName"));
            Result += Label + (bHasDecision
                ? FString::Printf(TEXT(" %.1f"), ScoreType->GetFloatingPointPropertyValue(Values.GetRawPtr(I))) : TEXT(" —"));
            Result += (I % 3 == 2 || I == Cards.Num()-1) ? TEXT("\n") : TEXT(" · ");
        }
        if (!bHasDecision) Result += TEXT("점수 판단 전\n");
        else Result += TEXT("점수는 마지막 선택 시점 기준\n");
    }
    Result += FString::Printf(TEXT("최근 6초: 회피 %d회 · 가드 %.1f초"),
        static_cast<int32>(Number(Boss, TEXT("RecentDodgeCount"))), Number(Boss, TEXT("RecentGuardSeconds")));
    return Result;
}

namespace
{
double FinalizeWeights(TArray<double>& Weights, const TArray<bool>& IsApproach, bool bWithinEntryRange)
{
    bool bHasAttack = false;
    for (int32 I = 0; I < Weights.Num(); ++I)
        if (IsApproach.IsValidIndex(I) && !IsApproach[I] && Weights[I] > 0.0) bHasAttack = true;
    double Total = 0;
    for (int32 I = 0; I < Weights.Num(); ++I)
    {
        if (bWithinEntryRange && bHasAttack && IsApproach.IsValidIndex(I) && IsApproach[I]) Weights[I] = 0;
        Total += Weights[I];
    }
    return Total;
}

bool CanLinkTwoHit(float Distance, float Dot, float Min, float Max, bool bTargetAvailable)
{
    // A link is permission to prepare the next strike, not permission to hit.
    // Allow 40cm for the existing second step; do not expand the hand trace.
    return bTargetAvailable && FMath::IsFinite(Distance) && FMath::IsFinite(Dot)
        && Distance >= Min && Distance <= Max + 40.f && Dot >= 0.f;
}
}

void UBossCombatIntentLibrary::EnsureActionCooldownCapacity(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FArrayProperty* Cooldowns = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("CooldownUntil"));
    if (!Actions || !Cooldowns) return;
    FScriptArrayHelper ActionValues(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
    FScriptArrayHelper CooldownValues(Cooldowns, Cooldowns->ContainerPtrToValuePtr<void>(Boss));
    if (CooldownValues.Num() < ActionValues.Num()) CooldownValues.Resize(ActionValues.Num());
}

void UBossCombatIntentLibrary::FinalizeIntentScores(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    const FArrayProperty* Scores = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    if (!Scores || !Actions) return;
    const FNumericProperty* ScoreType = CastField<FNumericProperty>(Scores->Inner);
    const FObjectPropertyBase* ActionType = CastField<FObjectPropertyBase>(Actions->Inner);
    if (!ScoreType || !ScoreType->IsFloatingPoint() || !ActionType) return;
    FScriptArrayHelper Values(Scores, Scores->ContainerPtrToValuePtr<void>(Boss));
    FScriptArrayHelper Cards(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
    if (Values.Num() != Cards.Num()) return;
    TArray<double> Weights;
    TArray<bool> Approach;
    for (int32 I = 0; I < Values.Num(); ++I)
    {
        Weights.Add(ScoreType->GetFloatingPointPropertyValue(Values.GetRawPtr(I)));
        Approach.Add(Number(ActionType->GetObjectPropertyValue(Cards.GetRawPtr(I)), TEXT("ActionId"), -1) == 7);
    }
    const double Total = FinalizeWeights(Weights, Approach,
        Number(Boss, TEXT("UtilityDistance")) < 500.0);
    FString Summary;
    for (int32 I = 0; I < Values.Num(); ++I)
    {
        ScoreType->SetFloatingPointPropertyValue(Values.GetRawPtr(I), Weights[I]);
        Summary += FString::Printf(TEXT("%s%d:%.2f"), I == 0 ? TEXT("") : TEXT(","), I, Weights[I]);
    }
    SetNumber(Boss, TEXT("UtilityTotalScore"), Total);
    SetText(Boss, TEXT("IntentFinalScores"), Summary);
    // Per-candidate rows are before this pass; final weights are recorded separately.
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_scores_finalized"));
}

bool UBossCombatIntentLibrary::ContinueTwoHitOrRecover(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    UObject* Action = Object(Boss, TEXT("ActiveAction"));
    if (Number(Action, TEXT("ActionId"), -1) != 9) return true;
    if (!StateIs(Boss, TEXT("Boss.Combat.Attack.Active")) || Number(Boss, TEXT("HitIndex")) != 0) return false;
    AActor* Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    const bool bTargetAvailable = IsValid(Target) && Number(Target, TEXT("CurrentHealth")) > 0
        && !Flag(Target, TEXT("bKnockedDown"));
    const FVector Delta = IsValid(Target) ? Target->GetActorLocation() - Boss->GetActorLocation() : FVector::ZeroVector;
    if (CanLinkTwoHit(Delta.Size2D(), FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D()),
        Number(Action, TEXT("MinDistance")), Number(Action, TEXT("MaxDistance")), bTargetAvailable))
    {
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("two_hit_link_accepted"));
        return true;
    }
    if (!TransitionState(Boss, TEXT("Boss.Combat.Attack.Active"), TEXT("Boss.Combat.Attack.Recovery"), TEXT("2연타 연결 거리·방향 이탈: 왼손 회수"))) return false;
    UKismetSystemLibrary::K2_ClearTimer(Boss, TEXT("OpenActionImpact"));
    SetFlag(Boss, TEXT("bAttackStepActive"), false);
    SetFlag(Boss, TEXT("bPhysicalStrikeOpen"), false);
    Invoke(Boss, TEXT("StopBossLocomotion"));
    if (ACharacter* Character = Cast<ACharacter>(Boss))
        if (UAnimInstance* Anim = Character->GetMesh()->GetAnimInstance())
            if (UAnimMontage* Montage = Cast<UAnimMontage>(Object(Action, TEXT("Montage"))))
                if (Anim->Montage_IsPlaying(Montage) && Montage->GetSectionIndex(TEXT("AbortLeftRecovery")) != INDEX_NONE)
                    Anim->Montage_JumpToSection(TEXT("AbortLeftRecovery"), Montage);
    UKismetSystemLibrary::K2_SetTimer(Boss, TEXT("FinishCombatAction"), .85f, false);
    SetText(Boss, TEXT("IntentReason"), TEXT("다음 주먹 범위 이탈: 0.85초 회수 후 재판단"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("two_hit_link_aborted"));
    return false;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossDesignerDistanceBandTest, "Battle.GOAP.DesignerDistanceBands",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossDesignerDistanceBandTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Close punch preserves source step"), OnePunchStep(175,66,450), 66.f);
    TestEqual(TEXT("400cm has finite one-step travel"), OnePunchStep(400,66,0),145.f);
    TestEqual(TEXT("Retreat cannot extend step past cap"), OnePunchStep(400,66,650),145.f);
    TestEqual(TEXT("Invalid geometry cannot move"), OnePunchStep(std::numeric_limits<float>::quiet_NaN(),66,0),0.f);
    TestEqual(TEXT("Ordinary candidate allowed below dash boundary"), DistanceBandMultiplier(0,499),1.f);
    TestEqual(TEXT("500cm stops ordinary candidate"), DistanceBandMultiplier(0,500),0.f);
    TestEqual(TEXT("500cm stops two-hit entry"), DistanceBandMultiplier(9,500),0.f);
    TestEqual(TEXT("Dash candidate retains its own eligibility"), DistanceBandMultiplier(6,500),1.f);
    TestFalse(TEXT("Phase one never executes pending slam"), PendingSlamRange(true,false,1000,1000,5000));
    TestFalse(TEXT("Close phase entry does not force jump"), PendingSlamRange(true,true,175,1000,5000));
    TestFalse(TEXT("Below jump band remains normal combat"), PendingSlamRange(true,true,999,1000,5000));
    TestTrue(TEXT("Phase two 1000cm can start pending jump"), PendingSlamRange(true,true,1000,1000,5000));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossPostAttackProbeTest, "Battle.GOAP.PostAttackProbe",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossPostAttackProbeTest::RunTest(const FString& Parameters)
{
    const auto Choose = [](int32 Id, float Distance, bool Fresh, bool Cooldown, float Roll)
    { return ChoosePostAttackProbe(Id, Distance, 0, 350, 1, Fresh, Cooldown, Roll, .25f); };
    TestTrue(TEXT("Ordinary next punch may prepare with a side step"), Choose(0, 250, true, true, .1f));
    TestFalse(TEXT("Not every eligible attack probes"), Choose(1, 250, true, true, .25f));
    TestFalse(TEXT("Expired post-attack choice stays direct"), Choose(0, 250, false, true, 0));
    TestFalse(TEXT("Probe cooldown is respected"), Choose(0, 250, true, false, 0));
    TestFalse(TEXT("Close pressure does not force retreat"), Choose(0, 173, true, true, 0));
    TestFalse(TEXT("Far target still needs attack entry"), Choose(0, 500, true, true, 0));
    TestFalse(TEXT("Guard break is not delayed by decorative movement"), Choose(5, 250, true, true, 0));
    TestTrue(TEXT("Two-hit intention can use the same preparation"), Choose(9, 250, true, true, 0));
    TestFalse(TEXT("Rear target must turn first"), ChoosePostAttackProbe(0, 250, 0, 350, -.5f, true, true, 0, .25f));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossIntentFailureTest, "Battle.GOAP.IntentFailureReassessment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossIntentFailureTest::RunTest(const FString& Parameters)
{
    int32 Count = 0;
    double Last = -1;
    TestFalse(TEXT("One failed entry can retry"), RecordEntryFailure(Count, Last, 1, 6));
    TestTrue(TEXT("Second recent failure breaks pursuit"), RecordEntryFailure(Count, Last, 3, 6));
    TestFalse(TEXT("Observation starts a new failure pair"), RecordEntryFailure(Count, Last, 4, 6));
    TestFalse(TEXT("Old failure expires"), RecordEntryFailure(Count, Last, 11, 6));
    TestTrue(TEXT("Window includes boundary"), RecordEntryFailure(Count, Last, 17, 6));
    Count = 0; Last = -1; // Successful attack entry resets the episode.
    TestFalse(TEXT("Success prevents old failures triggering observation"), RecordEntryFailure(Count, Last, 18, 6));
    TestFalse(TEXT("Clock reset cannot carry failures into a new world"), RecordEntryFailure(Count, Last, 0, 6));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossSideEntryGeometryTest, "Battle.GOAP.SideEntryGeometry",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossSideEntryGeometryTest::RunTest(const FString& Parameters)
{
    const FVector Boss(500, 0, 200), Player(0, 0, 96);
    const FVector Left = LateralEntryGoal(Boss, Player, 270, 20);
    const FVector Right = LateralEntryGoal(Boss, Player, 270, -20);
    TestTrue(TEXT("Left keeps attack radius"), FMath::IsNearlyEqual(FVector::Dist2D(Left, Player), 270.f, .01f));
    TestTrue(TEXT("Right keeps attack radius"), FMath::IsNearlyEqual(FVector::Dist2D(Right, Player), 270.f, .01f));
    TestTrue(TEXT("Sides lie on opposite tangents"), Left.Y > 0 && Right.Y < 0);
    TestTrue(TEXT("Actor center height stays with boss, not player"), Left.Z == Boss.Z && Right.Z == Boss.Z);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossIntentChoiceTest, "Battle.GOAP.IntentChoiceAndLink",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossIntentChoiceTest::RunTest(const FString& Parameters)
{
    TArray<double> LaterAttack{0, 88, 20};
    TestEqual(TEXT("Later attack suppresses earlier approach"), FinalizeWeights(LaterAttack, {false,true,false}, true), 20.0);
    TestEqual(TEXT("Approach removed after all candidates"), LaterAttack[1], 0.0);
    TArray<double> EarlierAttack{20,88,0};
    TestEqual(TEXT("Candidate order does not change total"), FinalizeWeights(EarlierAttack, {false,true,false}, true), 20.0);
    TArray<double> NoAttack{0,88,0};
    TestEqual(TEXT("Unavailable attacks preserve approach"), FinalizeWeights(NoAttack, {false,true,false}, true), 88.0);
    TArray<double> Far{20,88,0};
    TestEqual(TEXT("Long distance keeps approach"), FinalizeWeights(Far, {false,true,false}, false), 108.0);
    TestTrue(TEXT("Valid front link"), CanLinkTwoHit(285, 1, 0, 285, true));
    TestTrue(TEXT("Existing step allowance boundary"), CanLinkTwoHit(325, 0, 0, 285, true));
    TestFalse(TEXT("Too far aborts"), CanLinkTwoHit(326, 1, 0, 285, true));
    TestFalse(TEXT("Behind aborts"), CanLinkTwoHit(200, -.01f, 0, 285, true));
    TestFalse(TEXT("Unavailable target aborts"), CanLinkTwoHit(200, 1, 0, 285, false));
    TestFalse(TEXT("Inside minimum aborts"), CanLinkTwoHit(100, 1, 150, 285, true));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossIntentTransitionParametersTest, "Battle.GOAP.IntentTransitionParameters",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossIntentTransitionParametersTest::RunTest(const FString& Parameters)
{
    // Inspect the actual Blueprint contract without spawning actors or starting PIE.
    UClass* BossClass = LoadClass<AActor>(nullptr, TEXT("/Game/BossArena/Boss/Blueprints/BP_Boss_Crunch.BP_Boss_Crunch_C"));
    if (!TestNotNull(TEXT("Crunch class exists"), BossClass)) return false;
    UFunction* Fn = BossClass->FindFunctionByName(TEXT("TransitionBossState"));
    if (!TestNotNull(TEXT("State transition function exists"), Fn)) return false;
    const FGameplayTag Ready = FGameplayTag::RequestGameplayTag(TEXT("Boss.Combat.Ready"));
    const FGameplayTag Position = FGameplayTag::RequestGameplayTag(TEXT("Boss.Combat.Position"));
    for (bool bEntering : {true, false})
    {
        FStructOnScope Params(Fn);
        const FGameplayTag Expected = bEntering ? Ready : Position;
        const FGameplayTag Next = bEntering ? Position : Ready;
        if (!TestTrue(TEXT("Named Blueprint parameters are supported"),
            FillTransitionParameters(Fn, Params.GetStructMemory(), Expected, Next, TEXT("contract test")))) return false;
        const FStructProperty* ExpectedPin = FindFProperty<FStructProperty>(Fn, TEXT("ExpectedState"));
        const FStructProperty* NextPin = FindFProperty<FStructProperty>(Fn, TEXT("NewState"));
        TestTrue(TEXT("Source guard remains source"), *ExpectedPin->ContainerPtrToValuePtr<FGameplayTag>(Params.GetStructMemory()) == Expected);
        TestTrue(TEXT("Destination remains destination"), *NextPin->ContainerPtrToValuePtr<FGameplayTag>(Params.GetStructMemory()) == Next);
        TestEqual(TEXT("Reason is preserved"), FindFProperty<FStrProperty>(Fn, TEXT("Reason"))->GetPropertyValue_InContainer(Params.GetStructMemory()), FString(TEXT("contract test")));
    }
    TestFalse(TEXT("Missing function is rejected"), FillTransitionParameters(nullptr, nullptr, Ready, Position, TEXT("")));
    FStructOnScope Params(Fn);
    TestFalse(TEXT("Empty source guard is rejected"), FillTransitionParameters(Fn, Params.GetStructMemory(), FGameplayTag(), Position, TEXT("")));
    return true;
}
#endif
