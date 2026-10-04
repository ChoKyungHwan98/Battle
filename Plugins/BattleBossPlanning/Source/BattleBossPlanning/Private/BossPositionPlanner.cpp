#include "BossPositionPlanner.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

namespace
{
constexpr uint8 InMeleeRange = 1 << 0;
constexpr uint8 FacingTarget = 1 << 1;
constexpr uint8 ProbeDone = 1 << 2;
constexpr uint8 InGuardBreakRange = 1 << 3;
constexpr int32 FactCount = 1 << 4;

struct FPlanCost
{
    float Pressure = 0.f;
    float Travel = 0.f;
    float Exposure = 0.f;

    bool IsBetterThan(const FPlanCost& Other) const
    {
        if (!FMath::IsNearlyEqual(Pressure, Other.Pressure, 0.0001f))
        {
            return Pressure < Other.Pressure;
        }
        if (!FMath::IsNearlyEqual(Travel, Other.Travel, 0.0001f))
        {
            return Travel < Other.Travel;
        }
        return Exposure < Other.Exposure - 0.0001f;
    }

    FPlanCost operator+(const FPlanCost& Other) const
    {
        return { Pressure + Other.Pressure, Travel + Other.Travel, Exposure + Other.Exposure };
    }

    float DisplayCost() const
    {
        return Pressure * 1000.f + Travel * 10.f + Exposure;
    }
};

struct FSearchNode
{
    uint8 Facts = 0;
    FPlanCost Cost;
    TArray<EBossPositionAction> Steps;
};

struct FActionDefinition
{
    EBossPositionAction Action;
    uint8 RequiredFacts;
    uint8 AddFacts;
    bool bAvailable;
    FPlanCost Cost;
};
}

void UBossPositionPlanner::CheckSidePaths(
    AActor* Boss,
    AActor* Target,
    float ProbeDistance,
    bool& bLeftPathOpen,
    bool& bRightPathOpen)
{
    bLeftPathOpen = false;
    bRightPathOpen = false;
    if (!IsValid(Boss) || !Boss->GetWorld())
    {
        return;
    }

    const FVector Start = Boss->GetActorLocation() + FVector(0.f, 0.f, 55.f);
    const FVector Right = Boss->GetActorRightVector();
    const float Distance = FMath::Max(ProbeDistance, 1.f);
    FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(BossGoapSidePath), false, Boss);
    QueryParams.AddIgnoredActor(Boss);
    if (IsValid(Target))
    {
        QueryParams.AddIgnoredActor(Target);
    }
    const FCollisionShape Shape = FCollisionShape::MakeSphere(45.f);
    FHitResult Hit;
    bLeftPathOpen = !Boss->GetWorld()->SweepSingleByChannel(
        Hit, Start, Start - Right * Distance, FQuat::Identity,
        ECC_WorldStatic, Shape, QueryParams);
    bRightPathOpen = !Boss->GetWorld()->SweepSingleByChannel(
        Hit, Start, Start + Right * Distance, FQuat::Identity,
        ECC_WorldStatic, Shape, QueryParams);
}

FBossPositionPlan UBossPositionPlanner::PlanPosition(
    float Distance,
    float FacingDot,
    float AttackRange,
    float GuardBreakRange,
    bool bGuardPressureReady,
    bool bGuardRecentlySeen,
    bool bProbeRequested,
    bool bLeftPathOpen,
    bool bRightPathOpen,
    float MoveSpeed,
    float LeftExposure,
    float RightExposure,
    float AttackMinRange,
    float GuardBreakMinRange)
{
    FBossPositionPlan Result;
    Result.Goal = bGuardPressureReady && bGuardRecentlySeen
        ? EBossPositionGoal::PrepareGuardBreak
        : (bProbeRequested ? EBossPositionGoal::ProbeThenStrike : EBossPositionGoal::PrepareStrike);

    const float SafeAttackRange = FMath::Max(AttackRange, 1.f);
    const float SafeGuardRange = FMath::Max(GuardBreakRange, 1.f);
    const float SafeAttackMin = FMath::Clamp(AttackMinRange, 0.f, SafeAttackRange);
    const float SafeGuardMin = FMath::Clamp(GuardBreakMinRange, 0.f, SafeGuardRange);
    const float SafeSpeed = FMath::Max(MoveSpeed, 1.f);
    uint8 StartFacts = 0;
    if (Distance >= SafeAttackMin && Distance <= SafeAttackRange)
    {
        StartFacts |= InMeleeRange;
    }
    if (Distance >= SafeGuardMin && Distance <= SafeGuardRange)
    {
        StartFacts |= InGuardBreakRange;
    }
    if (FacingDot >= 0.7f)
    {
        StartFacts |= FacingTarget;
    }

    const uint8 GoalFacts = Result.Goal == EBossPositionGoal::PrepareGuardBreak
        ? InGuardBreakRange | FacingTarget
        : (Result.Goal == EBossPositionGoal::ProbeThenStrike
            ? InMeleeRange | FacingTarget | ProbeDone
            : InMeleeRange | FacingTarget);

    const float ApproachTargetRange = Result.Goal == EBossPositionGoal::PrepareGuardBreak
        ? SafeGuardRange : SafeAttackRange;
    const bool bCanApproach = Distance > ApproachTargetRange;
    uint8 ApproachResultFacts = 0;
    if (ApproachTargetRange >= SafeAttackMin && ApproachTargetRange <= SafeAttackRange)
    {
        ApproachResultFacts |= InMeleeRange;
    }
    if (ApproachTargetRange >= SafeGuardMin && ApproachTargetRange <= SafeGuardRange)
    {
        ApproachResultFacts |= InGuardBreakRange;
    }
    const float ApproachTravel = FMath::Max(0.f, Distance - ApproachTargetRange) / SafeSpeed;
    const FActionDefinition Actions[] = {
        { EBossPositionAction::DirectApproach, 0, ApproachResultFacts, bCanApproach,
            { 0.f, ApproachTravel + 0.1f, 0.2f } },
        { EBossPositionAction::FaceTarget, 0, FacingTarget, true,
            { 0.f, 0.25f, 0.f } },
        { EBossPositionAction::OrbitLeft, InMeleeRange, uint8(ProbeDone | FacingTarget), bLeftPathOpen,
            { 0.1f, 0.65f, FMath::Max(0.f, LeftExposure) } },
        { EBossPositionAction::OrbitRight, InMeleeRange, uint8(ProbeDone | FacingTarget), bRightPathOpen,
            { 0.1f, 0.65f, FMath::Max(0.f, RightExposure) } }
    };

    // Dijkstra over sixteen possible fact sets. Definitions above determine the plan;
    // there are no fixed action sequences or goal-specific movement branches.
    TArray<FSearchNode> Open;
    Open.Add({ StartFacts, {}, {} });
    FPlanCost BestCost[FactCount];
    bool bReached[FactCount] = {};
    bReached[StartFacts] = true;
    BestCost[StartFacts] = {};

    while (!Open.IsEmpty())
    {
        int32 CheapestIndex = 0;
        for (int32 Index = 1; Index < Open.Num(); ++Index)
        {
            if (Open[Index].Cost.IsBetterThan(Open[CheapestIndex].Cost))
            {
                CheapestIndex = Index;
            }
        }
        FSearchNode Current = MoveTemp(Open[CheapestIndex]);
        Open.RemoveAtSwap(CheapestIndex, EAllowShrinking::No);
        if (BestCost[Current.Facts].IsBetterThan(Current.Cost))
        {
            continue;
        }
        if ((Current.Facts & GoalFacts) == GoalFacts)
        {
            Result.bFound = true;
            Result.Steps = MoveTemp(Current.Steps);
            Result.FirstAction = Result.Steps.IsEmpty() ? EBossPositionAction::None : Result.Steps[0];
            Result.TotalCost = Current.Cost.DisplayCost();
            const TCHAR* GoalName = Result.Goal == EBossPositionGoal::PrepareGuardBreak
                ? TEXT("GuardBreak")
                : (Result.Goal == EBossPositionGoal::ProbeThenStrike ? TEXT("Probe then strike") : TEXT("Strike"));
            const TCHAR* FirstName = Result.FirstAction == EBossPositionAction::DirectApproach
                ? TEXT("Approach")
                : (Result.FirstAction == EBossPositionAction::FaceTarget ? TEXT("Face target")
                : (Result.FirstAction == EBossPositionAction::OrbitLeft ? TEXT("Orbit left")
                : (Result.FirstAction == EBossPositionAction::OrbitRight ? TEXT("Orbit right") : TEXT("Ready"))));
            Result.Reason = FString::Printf(TEXT("%s: %s (%d step(s))"),
                GoalName, FirstName, Result.Steps.Num());
            return Result;
        }
        for (const FActionDefinition& Action : Actions)
        {
            if (!Action.bAvailable
                || (Current.Facts & Action.RequiredFacts) != Action.RequiredFacts
                || (Current.Facts & Action.AddFacts) == Action.AddFacts)
            {
                continue;
            }
            const uint8 NextFacts = Current.Facts | Action.AddFacts;
            const FPlanCost NextCost = Current.Cost + Action.Cost;
            if (bReached[NextFacts] && !NextCost.IsBetterThan(BestCost[NextFacts]))
            {
                continue;
            }
            bReached[NextFacts] = true;
            BestCost[NextFacts] = NextCost;
            FSearchNode Next = Current;
            Next.Facts = NextFacts;
            Next.Cost = NextCost;
            Next.Steps.Add(Action.Action);
            Open.Add(MoveTemp(Next));
        }
    }

    Result.Reason = TEXT("No available actions satisfy the goal");
    return Result;
}
