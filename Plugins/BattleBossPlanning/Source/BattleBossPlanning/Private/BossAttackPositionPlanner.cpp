#include "BossPositionPlanner.h"

FBossPositionPlan UBossPositionPlanner::PlanAttackPosition(
    float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
    bool bForwardOpen, bool bBackOpen, bool bLeftOpen, bool bRightOpen,
    bool bProbeRequested, float MoveSpeed)
{
    FBossPositionPlan Result;
    Result.Goal = bProbeRequested ? EBossPositionGoal::ProbeThenStrike : EBossPositionGoal::PrepareStrike;
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(FacingDot) || !FMath::IsFinite(StartMin)
        || !FMath::IsFinite(StartMax) || !FMath::IsFinite(MoveSpeed)
        || !FMath::IsFinite(MinimumFacingDot) || StartMin < 0.f || StartMax < StartMin || MoveSpeed <= 0.f)
    {
        Result.Reason = TEXT("Invalid selected attack goal");
        return Result;
    }
    constexpr uint8 Range = 1, Facing = 2, Probe = 4;
    const uint8 Initial = (Distance >= StartMin && Distance <= StartMax ? Range : 0)
        | (FacingDot >= MinimumFacingDot ? Facing : 0);
    const uint8 Goal = Range | Facing | (bProbeRequested ? Probe : 0);
    struct FStep
    {
        EBossPositionAction Action;
        uint8 Requires, Add, Remove;
        bool Available;
        float Cost;
    };
    const FStep Steps[] = {
        // Translation invalidates the facing assumption. The executor re-observes
        // the real pose after every step; a search result is never proof of arrival.
        {EBossPositionAction::DirectApproach, 0, Range, Facing, Distance > StartMax && bForwardOpen,
            FMath::Max(0.f, Distance - StartMax) / MoveSpeed + .1f},
        {EBossPositionAction::StepBack, 0, Range, Facing, Distance < StartMin && bBackOpen,
            FMath::Max(0.f, StartMin - Distance) / MoveSpeed + .15f},
        {EBossPositionAction::FaceTarget, 0, Facing, 0, true, .25f},
        {EBossPositionAction::OrbitLeft, Range, uint8(Probe | Facing), 0, bLeftOpen, .65f},
        {EBossPositionAction::OrbitRight, Range, uint8(Probe | Facing), 0, bRightOpen, .65f}
    };
    struct FNode { uint8 Facts; float Cost; TArray<EBossPositionAction> Actions; };
    TArray<FNode> Open;
    Open.Add({Initial, 0.f, {}});
    float Best[8];
    for (float& Cost : Best) Cost = TNumericLimits<float>::Max();
    Best[Initial] = 0.f;
    while (!Open.IsEmpty())
    {
        int32 Cheapest = 0;
        for (int32 I = 1; I < Open.Num(); ++I)
            if (Open[I].Cost < Open[Cheapest].Cost) Cheapest = I;
        FNode Current = MoveTemp(Open[Cheapest]);
        Open.RemoveAtSwap(Cheapest, EAllowShrinking::No);
        if (Current.Cost > Best[Current.Facts]) continue;
        if ((Current.Facts & Goal) == Goal)
        {
            Result.bFound = true;
            Result.Steps = MoveTemp(Current.Actions);
            Result.FirstAction = Result.Steps.IsEmpty() ? EBossPositionAction::None : Result.Steps[0];
            Result.TotalCost = Current.Cost;
            Result.Reason = FString::Printf(TEXT("Selected attack: %d positioning steps"), Result.Steps.Num());
            return Result;
        }
        for (const FStep& Step : Steps)
        {
            if (!Step.Available || (Current.Facts & Step.Requires) != Step.Requires) continue;
            const uint8 Next = (Current.Facts & ~Step.Remove) | Step.Add;
            const float Cost = Current.Cost + Step.Cost;
            if (Next == Current.Facts || Cost >= Best[Next]) continue;
            Best[Next] = Cost;
            FNode Candidate = Current;
            Candidate.Facts = Next;
            Candidate.Cost = Cost;
            Candidate.Actions.Add(Step.Action);
            Open.Add(MoveTemp(Candidate));
        }
    }
    Result.Reason = TEXT("No traversable position for selected attack");
    return Result;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossAttackPositionTest, "Battle.GOAP.SelectedAttack",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossAttackPositionTest::RunTest(const FString& Parameters)
{
    auto Plan = [](float D, float Dot, bool Forward, bool Back, bool Left, bool Right, bool Probe)
    { return UBossPositionPlanner::PlanAttackPosition(D, Dot, 180.f, 280.f, .7f, Forward, Back, Left, Right, Probe, 600.f); };
    const auto Ready = Plan(240.f, 1.f, true, true, true, true, false);
    TestTrue(TEXT("Already in selected attack band"), Ready.bFound && Ready.Steps.IsEmpty());
    const auto Approach = Plan(500.f, 1.f, true, true, true, true, false);
    TestTrue(TEXT("Approach planned"), Approach.bFound && Approach.Steps.Num() == 2);
    if (Approach.Steps.Num() == 2)
    {
        TestEqual(TEXT("Approach first"), Approach.Steps[0], EBossPositionAction::DirectApproach);
        TestEqual(TEXT("Recheck facing after translation"), Approach.Steps[1], EBossPositionAction::FaceTarget);
    }
    TestFalse(TEXT("Blocked approach cannot invent range"), Plan(500.f, 1.f, false, true, true, true, false).bFound);
    const auto Back = Plan(150.f, 1.f, true, true, true, true, false);
    TestEqual(TEXT("Too close uses backstep"), Back.FirstAction, EBossPositionAction::StepBack);
    TestFalse(TEXT("No retreat path"), Plan(150.f, 1.f, true, false, true, true, false).bFound);
    TestEqual(TEXT("Behind target turns"), Plan(240.f, -1.f, true, true, true, true, false).FirstAction, EBossPositionAction::FaceTarget);
    TestEqual(TEXT("Only right probe is open"), Plan(240.f, 1.f, true, true, false, true, true).FirstAction, EBossPositionAction::OrbitRight);
    TestFalse(TEXT("Blocked probe cannot be completed"), Plan(240.f, 1.f, true, true, false, false, true).bFound);
    TestFalse(TEXT("Invalid range rejected"), UBossPositionPlanner::PlanAttackPosition(200.f, 1.f, 300.f, 200.f, .7f, true, true, true, true, false, 600.f).bFound);
    return true;
}
#endif
