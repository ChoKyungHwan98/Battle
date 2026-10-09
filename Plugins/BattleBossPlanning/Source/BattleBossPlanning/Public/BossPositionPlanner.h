#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BossPositionPlanner.generated.h"

UENUM(BlueprintType)
enum class EBossPositionGoal : uint8
{
    PrepareStrike,
    PrepareGuardBreak,
    ProbeThenStrike,
    Footwork
};

UENUM(BlueprintType)
enum class EBossPositionAction : uint8
{
    None,
    DirectApproach,
    FaceTarget,
    OrbitLeft,
    OrbitRight,
    StepBack
};

USTRUCT(BlueprintType)
struct BATTLEBOSSPLANNING_API FBossPositionPlan
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    bool bFound = false;

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    EBossPositionGoal Goal = EBossPositionGoal::PrepareStrike;

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    EBossPositionAction FirstAction = EBossPositionAction::None;

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    TArray<EBossPositionAction> Steps;

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    float TotalCost = 0.f;

    UPROPERTY(BlueprintReadOnly, Category = "Boss|GOAP")
    FString Reason;
};

/**
 * Searches fact states to find a short, low-cost positioning plan.
 * The boss re-runs this after each movement step because the player can move.
 */
UCLASS()
class BATTLEBOSSPLANNING_API UBossPositionPlanner : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Side booleans certify a traversable destination INSIDE this attack's band.
     * Unlike probe clearance, these allow a lateral entry to establish range. */
    static FBossPositionPlan PlanAttackEntry(
        float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
        bool bForwardOpen, bool bBackOpen, bool bLeftEntryOpen, bool bRightEntryOpen, float MoveSpeed);

    /** 공격 뒤 기동(발놀림). 고른 공격 없이 자리만 목표로 한다. 사실은 네 가지:
     * 간격이 있다 / 정면이다 / 각을 바꿨다 / 주먹 거리 안이다. */
    static FBossPositionPlan PlanFootwork(
        float Distance, float FacingDot, float CrowdDistance, float PocketDistance, float MinimumFacingDot,
        bool bBackOpen, bool bLeftOpen, bool bRightOpen, bool bForwardOpen,
        bool bWantSpace, bool bWantAngle, bool bWantPocket,
        float BackCost, float LeftCost, float RightCost, float PressCost);

    /** The caller supplies the selected attack's goal; this never selects another attack. */
    UFUNCTION(BlueprintPure, Category = "Boss|GOAP")
    static FBossPositionPlan PlanAttackPosition(
        float Distance, float FacingDot, float StartMin, float StartMax, float MinimumFacingDot,
        bool bForwardOpen, bool bBackOpen, bool bLeftOpen, bool bRightOpen,
        bool bProbeRequested, float MoveSpeed);

    UFUNCTION(BlueprintCallable, Category = "Boss|GOAP")
    static void CheckSidePaths(
        AActor* Boss,
        AActor* Target,
        float ProbeDistance,
        bool& bLeftPathOpen,
        bool& bRightPathOpen);

    UFUNCTION(BlueprintCallable, Category = "Boss|GOAP")
    static FBossPositionPlan PlanPosition(
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
        float GuardBreakMinRange);
};
