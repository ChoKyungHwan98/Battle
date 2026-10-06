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
    bool IsActive() const { return bActive || bReassessing; }
    float FailureMultiplier(int32 Slot) const;
    /** Transient test override; the caller must be the MotionLab fixture. 0=combat, 1=no travel, 2=one step. */
    int32 MotionLabPunchMode = 0;
    /** Runtime-only fixture permissions. Start override exists only inside a manual lab request. */
    bool bLabStartRequestScope = false;
    bool bLabRangeMeasurementAction = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float RunSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float MaxDuration = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReplanInterval = .2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float TurnSpeed = 160.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float FailureWindow = 6.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReassessDuration = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float SideEntryAngle = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float SideEntrySpeed = 220.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float PostAttackProbeChance = .25f;
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
};

UCLASS()
class BATTLEBOSSPLANNING_API UBossCombatIntentLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Bypasses distance/facing/cooldown starts only in the scoped MotionLab manual request. */
    UFUNCTION(BlueprintPure, Category="Boss|Motion Lab") static bool IsLabStartLimitOverride(AActor* Boss);
    static bool IsLabRangeMeasurementAction(AActor* Boss);
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
