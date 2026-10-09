#include "BossPositionPlanner.h"

namespace
{
FBossPositionPlan FindAttackPositionPlan(
    float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
    bool bForwardOpen, bool bBackOpen, bool bLeftOpen, bool bRightOpen,
    bool bProbeRequested, float MoveSpeed, bool bSideEntryReachesRange)
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
        {EBossPositionAction::OrbitLeft, uint8(bSideEntryReachesRange ? 0 : Range),
            uint8(bSideEntryReachesRange ? (Probe | Range) : (Probe | Facing)),
            uint8(bSideEntryReachesRange ? Facing : 0), bLeftOpen, .65f},
        {EBossPositionAction::OrbitRight, uint8(bSideEntryReachesRange ? 0 : Range),
            uint8(bSideEntryReachesRange ? (Probe | Range) : (Probe | Facing)),
            uint8(bSideEntryReachesRange ? Facing : 0), bRightOpen, .65f}
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
}

FBossPositionPlan UBossPositionPlanner::PlanAttackPosition(
    float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
    bool bForwardOpen, bool bBackOpen, bool bLeftOpen, bool bRightOpen,
    bool bProbeRequested, float MoveSpeed)
{
    return FindAttackPositionPlan(Distance, FacingDot, StartMin, StartMax, MinimumFacingDot,
        bForwardOpen, bBackOpen, bLeftOpen, bRightOpen, bProbeRequested, MoveSpeed, false);
}

FBossPositionPlan UBossPositionPlanner::PlanAttackEntry(
    float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
    bool bForwardOpen, bool bBackOpen, bool bLeftEntryOpen, bool bRightEntryOpen, float MoveSpeed)
{
    return FindAttackPositionPlan(Distance, FacingDot, StartMin, StartMax, MinimumFacingDot,
        bForwardOpen, bBackOpen, bLeftEntryOpen, bRightEntryOpen, false, MoveSpeed, true);
}

FBossPositionPlan UBossPositionPlanner::PlanFootwork(
    float Distance, float FacingDot, float CrowdDistance, float PocketDistance, float MinimumFacingDot,
    bool bBackOpen, bool bLeftOpen, bool bRightOpen, bool bForwardOpen,
    bool bWantSpace, bool bWantAngle, bool bWantPocket,
    float BackCost, float LeftCost, float RightCost, float PressCost)
{
    FBossPositionPlan Result;
    Result.Goal = EBossPositionGoal::Footwork;
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(FacingDot) || !FMath::IsFinite(CrowdDistance) || !FMath::IsFinite(PocketDistance))
    {
        Result.Reason = TEXT("Invalid footwork input");
        return Result;
    }
    constexpr uint8 Spaced = 1, Facing = 2, Angled = 4, InPocket = 8;
    const uint8 Initial = (Distance >= CrowdDistance ? Spaced : 0) | (FacingDot >= MinimumFacingDot ? Facing : 0)
        | (Distance <= PocketDistance ? InPocket : 0);
    const uint8 Goal = Facing | (bWantSpace ? Spaced : 0) | (bWantAngle ? Angled : 0) | (bWantPocket ? InPocket : 0);
    struct FStep { EBossPositionAction Action; uint8 Add, Remove; bool Available; float Cost; };
    const FStep Steps[] = {
        // 움직이고 나면 정면인지 다시 확인해야 한다(칠 자리 만들기와 같은 규칙).
        {EBossPositionAction::StepBack, Spaced, Facing, Distance < CrowdDistance && bBackOpen, FMath::Max(.05f, BackCost)},
        {EBossPositionAction::FaceTarget, Facing, 0, true, .25f},
        // 옆으로 돌 때는 간격이 확보되는 반지름을 따라 돈다: 붙어 있었다면 한 번에 간격과 각을 함께 얻는다.
        {EBossPositionAction::OrbitLeft, uint8(Spaced | Angled), Facing, bLeftOpen, .65f + FMath::Max(0.f, LeftCost)},
        {EBossPositionAction::OrbitRight, uint8(Spaced | Angled), Facing, bRightOpen, .65f + FMath::Max(0.f, RightCost)},
        // 걸어 들어가 조이기: 주먹 거리 밖에 있을 때만.
        {EBossPositionAction::DirectApproach, InPocket, Facing, Distance > PocketDistance && bForwardOpen, FMath::Max(.05f, PressCost)}
    };
    struct FNode { uint8 Facts; float Cost; TArray<EBossPositionAction> Actions; };
    TArray<FNode> Open;
    Open.Add({Initial, 0.f, {}});
    float Best[16];
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
            Result.Reason = FString::Printf(TEXT("Footwork: %d steps"), Result.Steps.Num());
            return Result;
        }
        for (const FStep& Step : Steps)
        {
            if (!Step.Available) continue;
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
    Result.Reason = TEXT("No room for footwork");
    return Result;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossFootworkPlanTest, "Battle.GOAP.Footwork",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossFootworkPlanTest::RunTest(const FString& Parameters)
{
    using A = EBossPositionAction;
    struct FQ { float D = 172; bool Back = true, Left = true, Right = true, Forward = true;
        bool Space = false, Angle = false, Pocket = false; float LeftCost = 0, RightCost = 0; };
    auto Plan = [](const FQ& Q)
    { return UBossPositionPlanner::PlanFootwork(Q.D, 1, 200, 300, .5f, Q.Back, Q.Left, Q.Right, Q.Forward,
        Q.Space, Q.Angle, Q.Pocket, .5f, Q.LeftCost, Q.RightCost, .6f); };
    FQ Q;
    Q = FQ(); Q.D = 260;
    TestTrue(TEXT("Nothing wanted: nothing to do"), Plan(Q).Steps.IsEmpty());
    Q = FQ(); Q.Space = true;
    TestEqual(TEXT("Crowded: step back to make room"), Plan(Q).FirstAction, A::StepBack);
    Q = FQ(); Q.Space = true; Q.Back = Q.Left = false;
    TestEqual(TEXT("Crowded with a wall behind: pivot out sideways"), Plan(Q).FirstAction, A::OrbitRight);
    Q = FQ(); Q.Space = Q.Angle = true; Q.Right = false;
    TestEqual(TEXT("Crowded and an angle wanted: one side move does both"), Plan(Q).FirstAction, A::OrbitLeft);
    TestEqual(TEXT("...in one move plus facing"), Plan(Q).Steps.Num(), 2);
    Q = FQ(); Q.D = 260; Q.Angle = true; Q.LeftCost = .4f;
    TestEqual(TEXT("Cheaper side wins"), Plan(Q).FirstAction, A::OrbitRight);
    Q = FQ(); Q.D = 400; Q.Pocket = true;
    TestEqual(TEXT("Out of punching range: walk in"), Plan(Q).FirstAction, A::DirectApproach);
    Q = FQ(); Q.D = 400; Q.Pocket = Q.Angle = true;
    TestEqual(TEXT("Walk in and change the angle: two moves, then face"), Plan(Q).Steps.Num(), 3);
    Q = FQ(); Q.Space = true; Q.Back = Q.Left = Q.Right = false;
    TestFalse(TEXT("Cornered boss: no plan, so it simply attacks"), Plan(Q).bFound);
    Q = FQ(); Q.D = 400; Q.Pocket = true; Q.Forward = false;
    TestFalse(TEXT("Blocked ahead: cannot walk in"), Plan(Q).bFound);
    return true;
}

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
    const auto SideEntry = UBossPositionPlanner::PlanAttackEntry(500, 1, 180, 280, .7f, false, false, false, true, 600);
    TestTrue(TEXT("Verified lateral destination can prepare attack"), SideEntry.bFound && SideEntry.Steps.Num() == 2);
    if (SideEntry.Steps.Num() == 2)
    {
        TestEqual(TEXT("Open right entry is used"), SideEntry.Steps[0], EBossPositionAction::OrbitRight);
        TestEqual(TEXT("Lateral entry also rechecks facing"), SideEntry.Steps[1], EBossPositionAction::FaceTarget);
    }
    TestFalse(TEXT("No certified entry cannot invent a route"),
        UBossPositionPlanner::PlanAttackEntry(500, 1, 180, 280, .7f, false, false, false, false, 600).bFound);
    TestEqual(TEXT("Open nearby direct approach remains preferable"),
        UBossPositionPlanner::PlanAttackEntry(350, 1, 180, 280, .7f, true, false, true, true, 600).FirstAction,
        EBossPositionAction::DirectApproach);
    TestFalse(TEXT("Invalid range rejected"), UBossPositionPlanner::PlanAttackPosition(200.f, 1.f, 300.f, 200.f, .7f, true, true, true, true, false, 600.f).bFound);
    return true;
}
#endif
