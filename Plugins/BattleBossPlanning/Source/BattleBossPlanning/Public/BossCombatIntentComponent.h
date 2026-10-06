#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BossCombatIntentComponent.generated.h"

/** Keeps one Utility choice alive while GOAP prepares its starting position. */
UCLASS(ClassGroup=(Battle), meta=(BlueprintSpawnableComponent))
class BATTLEBOSSPLANNING_API UBossCombatIntentComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBossCombatIntentComponent();
    void BeginSelectedIntent();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    bool IsActive() const { return bActive || bReassessing; }
    float FailureMultiplier(int32 Slot) const;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float RunSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float MaxDuration = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReplanInterval = .2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float TurnSpeed = 90.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float FailureWindow = 6.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Boss|Intent") float ReassessDuration = .65f;
    UPROPERTY(BlueprintReadOnly, Category="Boss|Intent") FString Status;
private:
    void Advance();
    void Finish(bool bAttack, const FString& Reason, bool bCountFailure = true);
    void TickReassessment(float DeltaTime);
    void Publish(const FString& Phase, const FString& Reason);
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
    bool bActive = false;
    bool bReassessing = false;
};

UCLASS()
class BATTLEBOSSPLANNING_API UBossCombatIntentLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void BeginSelectedAttackIntent(AActor* Boss);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static bool IsAttackIntentActive(AActor* Boss);
    UFUNCTION(BlueprintPure, Category="Boss|Intent") static float AdjustIntentCandidate(AActor* Boss, int32 Slot, float Score);
    /** Called after every candidate has been scored, before the weighted draw. */
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void FinalizeIntentScores(AActor* Boss);
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static void EnsureActionCooldownCapacity(AActor* Boss);
    /** False means the two-hit pattern has entered its abort recovery. Other patterns pass through. */
    UFUNCTION(BlueprintCallable, Category="Boss|Intent") static bool ContinueTwoHitOrRecover(AActor* Boss);
};
