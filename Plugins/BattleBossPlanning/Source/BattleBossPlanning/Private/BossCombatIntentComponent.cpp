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

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
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
