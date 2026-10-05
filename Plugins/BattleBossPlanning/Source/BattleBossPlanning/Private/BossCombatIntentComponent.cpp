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

namespace
{
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
bool StateIs(const UObject* O, const TCHAR* Name)
{
    const FStructProperty* P = IsValid(O) ? FindFProperty<FStructProperty>(O->GetClass(), TEXT("BossState")) : nullptr;
    return P && P->Struct == FGameplayTag::StaticStruct()
        && P->ContainerPtrToValuePtr<FGameplayTag>(O)->GetTagName() == FName(Name);
}
void Invoke(AActor* Boss, FName Name, const FString& Text = FString(), const TCHAR* State = nullptr)
{
    if (!IsValid(Boss)) return;
    if (UFunction* Fn = Boss->FindFunction(Name))
    {
        FStructOnScope Params(Fn);
        for (TFieldIterator<FProperty> It(Fn); It; ++It)
        {
            if (!It->HasAnyPropertyFlags(CPF_Parm) || It->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
            if (FStrProperty* P = CastField<FStrProperty>(*It)) P->SetPropertyValue_InContainer(Params.GetStructMemory(), Text);
            if (State) if (FStructProperty* P = CastField<FStructProperty>(*It))
                if (P->Struct == FGameplayTag::StaticStruct())
                    *P->ContainerPtrToValuePtr<FGameplayTag>(Params.GetStructMemory()) = FGameplayTag::RequestGameplayTag(FName(State));
        }
        Boss->ProcessEvent(Fn, Params.GetStructMemory());
    }
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
    if (!Boss || bActive || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    Action = Object(Boss, TEXT("ActiveAction"));
    Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    Slot = static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1));
    if (!Action.IsValid() || !Target.IsValid() || Slot < 0) return;
    const double Now = GetWorld()->GetTimeSeconds();
    StartedAt = NextPlanAt = Now;
    PreviousSpeed = Boss->GetCharacterMovement()->MaxWalkSpeed;
    const float Distance = FVector::Dist2D(Boss->GetActorLocation(), Target->GetActorLocation());
    const float StartMax = Number(Action.Get(), TEXT("MaxDistance"));
    // Once entry is needed, go inside the start boundary rather than stopping
    // at its outer edge. Already-close attacks never back away to this target.
    GoalMaxDistance = Distance > StartMax ? FMath::Max(static_cast<float>(Number(Action.Get(), TEXT("MinDistance"))) + 20.f, StartMax - 40.f) : StartMax;
    SetNumber(Boss, TEXT("IntentSelectionDistance"), Distance);
    SetNumber(Boss, TEXT("IntentElapsed"), 0);
    SetNumber(Boss, TEXT("IntentSerial"), Number(Boss, TEXT("IntentSerial")) + 1);
    SetFlag(Boss, TEXT("bCombatApproachActive"), false);
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    Invoke(Boss, TEXT("StopBossLocomotion"));
    bActive = true;
    Invoke(Boss, TEXT("TransitionBossState"), TEXT("선택한 공격을 위한 위치 잡기"), TEXT("Boss.Combat.Position"));
    Publish(TEXT("position"), TEXT("선택한 공격을 유지하며 진입"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_begin"));
    Advance();
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
    if (!Boss || !IsValid(Player) || !Action.IsValid()) { Finish(false, TEXT("대상 또는 공격이 사라짐")); return; }
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const float Distance = Delta.Size2D();
    const float Facing = FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D());
    const float Min = Number(Action.Get(), TEXT("MinDistance"));
    const float MinimumDot = Number(Boss, TEXT("AttackStartMinDot"), .5);
    SetNumber(Boss, TEXT("UtilityDistance"), Distance);
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
    const auto Plan = UBossPositionPlanner::PlanAttackPosition(Distance, Facing, Min, GoalMaxDistance, MinimumDot,
        bPathOpen && Distance > GoalMaxDistance, bPathOpen && Distance < Min, false, false, false, RunSpeed);
    if (!Plan.bFound) { Finish(false, TEXT("공격할 자리로 가는 길이 막힘")); return; }
    SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Plan.FirstAction));
    AAIController* Controller = Cast<AAIController>(Boss->GetController());
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
}

void UBossCombatIntentComponent::Finish(bool bAttack, const FString& Reason)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss) { bActive = false; return; }
    bActive = false;
    Invoke(Boss, TEXT("StopBossLocomotion"));
    Boss->GetCharacterMovement()->MaxWalkSpeed = PreviousSpeed;
    if (StateIs(Boss, TEXT("Boss.Combat.Position")))
        Invoke(Boss, TEXT("TransitionBossState"), Reason, TEXT("Boss.Combat.Ready"));
    Publish(bAttack ? TEXT("attack") : TEXT("cancelled"), Reason);
    if (bAttack)
    {
        SetText(Boss, TEXT("AttackRequestSource"), TEXT("intent"));
        Invoke(Boss, TEXT("BeginCombatAction"));
        if (Flag(Boss, TEXT("bActionStartAllowed")))
        {
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_arrived"));
            return;
        }
        Publish(TEXT("cancelled"), TEXT("도착 후 공격 시작 검사에서 거부됨"));
    }
    FailedUntilBySlot.Add(Slot, GetWorld()->GetTimeSeconds() + 3.0);
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_aborted"));
}

void UBossCombatIntentComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!bActive) return;
    AActor* Boss = GetOwner();
    if (!StateIs(Boss, TEXT("Boss.Combat.Position")) || !Target.IsValid()
        || Number(Boss, TEXT("CurrentHealth")) <= 0 || Number(Target.Get(), TEXT("CurrentHealth")) <= 0
        || Flag(Target.Get(), TEXT("bKnockedDown")) || Object(Boss, TEXT("ActiveAction")) != Action.Get()
        || static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1)) != Slot)
    { Finish(false, TEXT("상태 또는 대상 변경으로 진입 중단")); return; }
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

bool UBossCombatIntentLibrary::IsAttackIntentActive(AActor* Boss)
{
    const auto* Intent = IsValid(Boss) ? Boss->FindComponentByClass<UBossCombatIntentComponent>() : nullptr;
    return Intent && Intent->IsActive();
}

float UBossCombatIntentLibrary::AdjustIntentCandidate(AActor* Boss, int32 CandidateSlot, float Score)
{
    if (!IsValid(Boss) || Score <= 0.f) return 0.f;
    if (const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>()) Score *= Intent->FailureMultiplier(CandidateSlot);
    // Existing candidate order evaluates ordinary attacks before the approach card.
    // Only already-positive scores suppress movement: disabled/observationally
    // unavailable attacks must never strand the boss with no eligible action.
    const float Distance = Number(Boss, TEXT("UtilityDistance"));
    if (CandidateSlot == 7 && Distance <= 650.f)
    {
        const FArrayProperty* P = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
        if (P) if (const FNumericProperty* Element = CastField<FNumericProperty>(P->Inner))
        {
            FScriptArrayHelper Values(P, P->ContainerPtrToValuePtr<void>(Boss));
            for (int32 I = 0; I < Values.Num(); ++I)
                if (I != 7 && Element->GetFloatingPointPropertyValue(Values.GetRawPtr(I)) > 0.0) return 0.f;
        }
    }
    return Score;
}
