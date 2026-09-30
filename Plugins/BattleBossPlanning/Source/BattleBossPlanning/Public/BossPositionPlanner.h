#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BossPositionPlanner.generated.h"

UENUM(BlueprintType)
enum class EBossPositionGoal : uint8
{
    PrepareStrike,
    PrepareGuardBreak,
    ProbeThenStrike
};

UENUM(BlueprintType)
enum class EBossPositionAction : uint8
{
    None,
    DirectApproach,
    FaceTarget,
    OrbitLeft,
    OrbitRight
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
        float RightExposure);
};
