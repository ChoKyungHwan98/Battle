#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Blueprint/UserWidget.h"
#include "BossMotionLabDirector.generated.h"

class UAnimSequence;
class UTextBlock;
class UDamageType;
class AController;

UCLASS()
class BATTLEBOSSPLANNING_API UBossMotionLabOverlay : public UUserWidget
{
    GENERATED_BODY()

public:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    void SetDisplayText(const FString& Value);

private:
    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> DisplayText;
};

/** Manual motion and contact fixture for Lvl_BossMotionLab. Never used by the fight map. */
UCLASS()
class BATTLEBOSSPLANNING_API ABossMotionLabDirector : public AActor
{
    GENERATED_BODY()

public:
    ABossMotionLabDirector();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Motion Lab")
    TObjectPtr<AActor> BossActor;

private:
    TWeakObjectPtr<AActor> PlayerActor;
    TArray<FSoftObjectPath> AllClips;
    TArray<FSoftObjectPath> FocusClips;
    TArray<FSoftObjectPath>* CurrentClips = nullptr;
    int32 ClipIndex = 0;
    int32 DistanceIndex = 1;
    bool bShowHitboxes = true;
    bool bInitialized = false;
    bool bInputBound = false;
    bool bManualActionActive = false;
    float ManualActionStartTime = 0.f;
    int32 DamageEventCount = 0;
    float DamageTotal = 0.f;
    UPROPERTY(Transient)
    TObjectPtr<UBossMotionLabOverlay> Overlay;
    FString LastResult;
    TArray<FSoftObjectPath> Chain;
    int32 ChainIndex = 0;
    float NextChainTime = 0.f;

    void BindInput();
    void HideBossDebugWidget();
    UFUNCTION()
    void OnPlayerDamage(AActor* DamagedActor, float Damage, const UDamageType* DamageType,
        AController* InstigatedBy, AActor* DamageCauser);
    void OnNumberKey(FKey Key);
    void OnFunctionKey(FKey Key);
    void InitializeFixture();
    void SuppressAutonomousChoice() const;
    void ResetFixture();
    void SetDistance(int32 Index);
    void RequestAction(int32 Index);
    void PreviousClip();
    void NextClip();
    void ToggleCatalog();
    void PreviewSelected();
    void PreviewSequence(const FSoftObjectPath& Path);
    void StartChain(int32 Index);
    void AdvanceChain();
    void ToggleHitboxes();
    void DrawDiagnostics() const;
    void DrawOverlay() const;
    void StopCurrentMotion() const;
    void EnterReadyState() const;
};
