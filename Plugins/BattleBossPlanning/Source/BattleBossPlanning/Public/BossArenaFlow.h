#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "BossArenaFlow.generated.h"

/**
 * 한 판의 처음과 끝. 전투 맵이 열리면 시작 화면을 띄우고(게임은 멈춰 있다), 시작을 누르면 보스의 등장으로 이어진다.
 * 플레이어가 쓰러지면 패배 화면, 보스가 쓰러지면 승리 화면을 띄우고 다시 하기를 받는다.
 * 전투의 판단에는 관여하지 않는다. 콘솔 boss.Flow 0 이면 전부 끈다(자동 시험용).
 */
UCLASS()
class BATTLEBOSSPLANNING_API UBossArenaFlowSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UBossArenaFlowSubsystem, STATGROUP_Tickables); }
    virtual bool IsTickableWhenPaused() const override { return true; }
    virtual bool IsTickableInEditor() const override { return false; }

    void StartFight();
    void Restart(bool bSkipTitle);

private:
    enum class EStage : uint8 { Boot, Title, Fighting, Ending, Ended, Off };
    void ShowScreen(int32 Mode);
    void HideScreen();
    void SetUiInput(bool bUi);
    EStage Stage = EStage::Boot;
    TSharedPtr<class SBossFlowScreen> Screen;
    TWeakObjectPtr<AActor> Boss;
    double FightStartedAt = 0.0;      // 전투가 시작된 때(게임 시간)
    double EndingAt = 0.0;            // 승패가 정해진 때(실제 시간)
    bool bWon = false;
    float DamageTaken = 0.f;
    double LastPlayerHealth = -1.0;
    float FadeOut = -1.f;             // 시작 화면이 사라지는 중(1 -> 0)
};
