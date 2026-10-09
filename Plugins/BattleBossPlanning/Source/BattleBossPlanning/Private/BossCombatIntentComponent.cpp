#include "BossCombatIntentComponent.h"
#include "BossPositionPlanner.h"
#include "BossHealthBarWidget.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Engine.h"
#include "Engine/DamageEvents.h"
#include "GameFramework/DamageType.h"
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
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet/GameplayStatics.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "Materials/MaterialInterface.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraShakeBase.h"
#include <limits>

namespace
{
bool PendingSlamRange(bool bPending, bool bPhaseTwo, float Distance, float Min, float Max)
{
    return bPending && bPhaseTwo && FMath::IsFinite(Distance) && Distance >= Min && Distance <= Max;
}
// ---- 제자리 버전 / 달려드는 버전 --------------------------------------------------------------------------------
// 판단에 "단거리·중거리·장거리" 같은 거리 구간은 없다. 공격(모션)마다 닿는 거리가 있고, 예상 거리가 그 안이면 후보다.
// 왼손(0)·오른손(1)·어퍼컷(2)·잽잽훅(4)은 같은 공격에 여러 모션이 있다. 상체는 같고 하체만 다르다.
//   제자리 버전: 발을 옮기지 않는다. 몸도 옮기지 않는다(예전에는 코드로 몸을 밀었고, 그것이 미끄러지는 전진이었다).
//   달려드는 버전: 두 걸음 달려든다. 가까운 쪽과 먼 쪽이 있고, 먼 쪽은 달려드는 거리만 더 길다.
// (아래 함수 이름의 Short/Mid/Far는 이 세 모션을 가리킨다.)
// 원칙: 발 애니메이션의 보폭과 몸의 이동이 맞지 않는 공격은 고르지 않는다. 그래서 공격마다 "고르지 않는 구간"이 있을 수 있다.
constexpr double MaxRunInReach = 650.0;         // 달려들며 치는 공격을 고를 수 있는 가장 먼 거리(모션의 실측 한계). 거리 구간이 아니다

// ---- 예측 --------------------------------------------------------------------------------------------------------
// 전에는 "지금 거리"로 공격을 고르고 달려드는 거리도 정했다. 실제 플레이 기록: 공격 21회 중 15회 헛침, 중거리에 있던 시간의
// 3분의 2가 헛스윙과 그 후딜이었다. 뒤로 걷는 플레이어는 보스가 칠 때쯤 그 자리에 없다.
// 이제 "칠 때쯤의 거리"로 판단한다: 지금 거리 + 멀어지는 속도 x 타격까지의 시간. 플레이어가 그 속도로 끝까지 가지는 않으므로
// 70%만 믿고, 220cm까지만 보정한다(회피 한 번의 순간 속도로 예측이 튀지 않게).
// 전후 비교용 콘솔 변수: boss.LeadTrust 0 이면 예측을 끄고, boss.OutcomeMemory 0 이면 결과의 기억을 끈다.
float LeadTrust = .7f;
FAutoConsoleVariableRef CVarLeadTrust(TEXT("boss.LeadTrust"), LeadTrust, TEXT("How much of the player's current speed the boss trusts when aiming (0 = no prediction)."));
int32 OutcomeMemory = 1;
FAutoConsoleVariableRef CVarOutcomeMemory(TEXT("boss.OutcomeMemory"), OutcomeMemory, TEXT("0 = attacks do not remember whether they hit or missed."));
constexpr float MaxLead = 220.f;
float PredictedDistance(float Distance, float SpeedAway, float Seconds)
{
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(SpeedAway) || !FMath::IsFinite(Seconds)) return Distance;
    return FMath::Max(0.f, Distance + FMath::Clamp(SpeedAway * FMath::Max(0.f, Seconds) * LeadTrust, -MaxLead, MaxLead));
}

// ---- 결과의 기억 ---------------------------------------------------------------------------------------------------
// 헛친 공격을 같은 상황에서 또 고르면 "헛침 -> 추격 -> 헛침"이 반복된다. 공격마다 최근 결과를 기억한다.
// 한 번 헛치면 0.7배, 연달아 두 번 이상이면 0.45배에서 시작해 20초에 걸쳐 돌아온다. 맞히면 1.25배에서 10초에 걸쳐 돌아온다.
// 막힌 것은 닿기는 한 것이라 헛침을 지우기만 한다. 달려오기에는 기억이 없어서, 공격이 계속 헛치면 거리를 좁히는 쪽이 올라온다.
float OutcomeScale(int32 Whiffs, bool bHit, float SecondsSince)
{
    if (!OutcomeMemory || !FMath::IsFinite(SecondsSince) || SecondsSince < 0.f) return 1.f;
    if (Whiffs > 0) return FMath::Lerp(Whiffs >= 2 ? .45f : .7f, 1.f, FMath::Clamp(SecondsSince / 20.f, 0.f, 1.f));
    return bHit ? FMath::Lerp(1.25f, 1.f, FMath::Clamp(SecondsSince / 10.f, 0.f, 1.f)) : 1.f;
}

// 단거리 버전이 제자리에서 닿는 가장 먼 거리(직접 잰 값). 연속기는 마지막 훅까지 닿는 거리다.
float ShortVersionReach(int32 Id)
{
    switch (Id) { case 0: return 344.f; case 1: return 320.f; case 2: return 295.f; case 4: return 235.f; default: return 0.f; }
}

// 이 거리부터 중거리 버전을 쓴다. 걸음의 60% 이상을 실제로 걸을 수 있는 거리다(그보다 가까우면 발이 미끄러진다).
// 0이면 중거리 버전이 없는 공격.
float MidVersionStart(int32 Id)
{
    switch (Id) { case 0: return 345.f; case 1: return 325.f; case 2: return 368.f; case 4: return 345.f; default: return 0.f; }
}

// 중거리 버전으로 고를 수 있는 가장 먼 거리. 연속기는 첫 타가 붙어야 뒤의 두 타가 제자리에서 닿아서 510까지만.
float MidVersionEnd(int32 Id)
{
    return Id == 4 ? 510.f : static_cast<float>(MaxRunInReach);
}

// 이 거리부터는 먼 쪽 버전.
float FarVersionStart(int32 Id)
{
    switch (Id) { case 0: return 500.f; case 1: return 510.f; case 2: return 545.f; case 4: return 408.f; default: return 0.f; }
}

bool UsesFarVersion(int32 Id, float StartDistance)
{
    const float From = FarVersionStart(Id);
    return From > 0.f && FMath::IsFinite(StartDistance) && StartDistance >= From;
}

// 바로 시작해도 닿는 가장 먼 거리(먼 쪽 버전의 실측에서 여유를 뺀 값). 중거리 끝(650)에서 고르면 이 거리 안으로 먼저 짧게 들어간다.
float MidVersionReach(int32 Id)
{
    switch (Id) { case 0: return 610.f; case 1: return 610.f; case 2: return 590.f; case 4: return 510.f; default: return 0.f; }
}

bool UsesMidVersion(int32 Id, float StartDistance)
{
    const float From = MidVersionStart(Id);
    return From > 0.f && FMath::IsFinite(StartDistance) && StartDistance >= From;
}

float DistanceBandMultiplier(int32 Id, double Distance)
{
    // 버전이 여럿인 공격: 단거리 버전이 닿는 거리이거나, 중거리 버전이 걸음을 제대로 쓸 수 있는 거리일 때만 후보다.
    // 그 사이(예: 어퍼컷 296~367cm)는 닿지 않거나 발이 미끄러지는 구간이라 고르지 않는다.
    if (MidVersionStart(Id) > 0.f)
        return Distance <= ShortVersionReach(Id) || (Distance >= MidVersionStart(Id) && Distance < MidVersionEnd(Id)) ? 1.f : 0.f;
    return Id == 9 && Distance >= 500.0 ? 0.f : 1.f;
}

// ---- 한 걸음이면 닿는 공격 ---------------------------------------------------------------------------------------
// 전에는 "지금 서 있는 거리에서 바로 칠 수 있는 공격"만 후보였다. 그래서 단거리 끝(약 290~345cm)에서는 후보가 왼손·오른손·휩쓸기뿐이었다.
// 이제 한 걸음(StepReach) 들어가거나 물러나면 칠 수 있는 공격도 후보에 넣는다(점수는 StepDiscount배). 그 걸음은 GOAP가 만든다.
constexpr float StepReach = 90.f;
constexpr float StepDiscount = .6f;

// 이 공격을 칠 수 있는 거리 구간 중 지금 거리에서 가장 가까운 것을 Lo..Hi에 담고, 거기까지의 거리를 돌려준다(안이면 0).
// 버전이 여럿인 공격은 구간이 둘이다(단거리 버전 / 중거리 버전). 그 사이에 있을 때는 안쪽(단거리)으로만 들어간다:
// 물러났다가 다시 달려드는 것은 어색하다.
float NearestStartBand(int32 Id, float Distance, float CardMin, float CardMax, float& Lo, float& Hi)
{
    Lo = CardMin; Hi = CardMax;
    if (Id == 9) Hi = FMath::Min(Hi, 500.f);
    if (MidVersionStart(Id) > 0.f)
    {
        const float MidLo = MidVersionStart(Id), MidHi = FMath::Min(CardMax, MidVersionEnd(Id));
        if (CardMax < MidLo) Hi = FMath::Min(CardMax, ShortVersionReach(Id));                 // 단거리 카드
        else if (CardMin >= ShortVersionReach(Id)) { Lo = FMath::Max(CardMin, MidLo); Hi = MidHi; }   // 중거리 카드
        else if (Distance >= MidLo) { Lo = MidLo; Hi = MidHi; }                              // 한 카드가 둘 다 맡는 경우
        else Hi = FMath::Min(CardMax, ShortVersionReach(Id));
    }
    return Distance < Lo ? Lo - Distance : (Distance > Hi ? Distance - Hi : 0.f);
}

// 이 카드가 "달려들며 치는" 중거리 패턴인가. 같은 공격의 단거리 패턴과는 별개의 카드이고 점수·감점·쿨다운도 따로 센다.
bool IsMidPattern(int32 Id, float CardMin)
{
    return MidVersionStart(Id) > 0.f && CardMin >= ShortVersionReach(Id);
}

// ---- 오래 안 쓴 공격 ---------------------------------------------------------------------------------------------
// 추첨만으로는 운이 나쁘면 어떤 공격이 한 판 내내 안 나온다(실제 플레이 77초: 어퍼컷 0회, 왼손·오른손이 63%).
// 10초 넘게 안 쓴 공격은 점수가 오르기 시작해서 30초에 2배가 된다. 쓰면 원래대로 돌아간다.
float StaleBonus(float SecondsUnused)
{
    return 1.f + FMath::Clamp((SecondsUnused - 10.f) / 20.f, 0.f, 1.f);
}

// ---- 맞고 있으면 떼어낸다 ----------------------------------------------------------------------------------------
// 플레이어가 붙어서 계속 때리고 있으면(4초에 3번 이상) 넓게 치거나 띄우는 공격을 올린다.
float PressureBoost(int32 Id, int32 HitsTaken, float Distance)
{
    if (HitsTaken < 3 || Distance > 300.f) return 1.f;
    return Id == 3 ? 2.5f : (Id == 2 ? 1.5f : (Id == 9 ? 1.3f : 1.f));
}

// 연속기의 점수 몫: 회피를 못 봤어도 30%, 2번 보면 절반, 3번 이상이면 전부.
float ComboShare(int32 Dodges)
{
    return Dodges >= 3 ? 1.f : (Dodges >= 2 ? .5f : .3f);
}

// ---- 이어 치기(몰아치기) ------------------------------------------------------------------------------------------
// 실제 플레이 기록(125초, 공격 32회): 공격 사이가 2~4초인 경우가 31번 중 20번이었다. "한 대 치고 서 있고, 한 대 치고 서 있다."
// 정해진 표(왼손 다음은 어퍼컷)로 잇던 연계는 "다음 공격이 그 자리에서 닿을 때만"이라 회피하는 플레이어에게는 거의 안 나왔다(1회).
// 이제 무엇을 몇 번 이을지를 계획(GOAP)이 짠다:
//   Utility가 정하는 것: 첫 공격, 그리고 이번에 몇 번 칠지(1~3).
//   GOAP가 짜는 것: 남은 공격의 순서. 행동마다 조건(닿는 거리, 각도, 아직 안 쓴 공격)과 결과(달려들면 붙는다, 제자리면 조금 벌어진다)가 있고,
//                  "마지막은 큰 한 방으로 끝낸다"는 목표에 가장 싸게 닿는 순서를 고른다.
//   HFSM이 지키는 것: 다음 타는 열린 후딜에서만 시작하고, 몰아치기의 마지막 공격은 후딜을 끝까지 보낸다.
// 플레이어가 그 사이 움직이므로, 타마다 열린 후딜에서 남은 순서를 지금 상황으로 다시 짠다.
constexpr int32 OverheadId = 10;                  // 오른손 내려찍기
struct FStringStep { int32 Id = -1; bool bRunIn = false; };

bool IsFinisher(int32 Id) { return Id == 2 || Id == 3 || Id == OverheadId; }      // 어퍼컷, 휩쓸기, 내려찍기

// 제자리에서 이 공격이 닿는 가장 먼 거리.
float PlantedReach(int32 Id)
{
    switch (Id) { case 0: return 344.f; case 1: return 320.f; case 2: return 295.f; case 3: return 360.f; case OverheadId: return 285.f; default: return 0.f; }
}

// 이 걸음이 지금 조건에서 가능한가. Angle은 플레이어가 정면에서 벗어난 각도(절댓값).
// 제자리 공격은 돌아서며 칠 수 있어서 100도까지(휩쓸기는 넓어서 120도), 달려드는 공격은 방향을 크게 못 바꿔서 45도까지.
bool StringStepPossible(const FStringStep& Step, float Distance, float Angle)
{
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(Angle)) return false;
    if (Step.bRunIn) return MidVersionStart(Step.Id) > 0.f && Step.Id != 4 && Distance >= MidVersionStart(Step.Id) && Distance <= MidVersionReach(Step.Id) && Angle <= 45.f;
    return PlantedReach(Step.Id) > 0.f && Distance <= PlantedReach(Step.Id) && Angle <= (Step.Id == 3 ? 120.f : 100.f);
}

// 이 걸음의 비용. 손이 자연스럽게 이어지면 싸고(왼손→오른손, 오른손→왼손, 오른손→같은 손 내려찍기, 왼손→어퍼컷, 2연타→휩쓸기),
// 마지막이 큰 한 방이 아니거나 큰 한 방이 중간에 오면 비싸다. Noise(0..1)는 같은 상황에서도 순서가 달라지게 하는 작은 흔들림이다.
float StringStepCost(int32 PreviousId, const FStringStep& Step, bool bLast, float Noise)
{
    const bool bFlows = (PreviousId == 0 && (Step.Id == 1 || Step.Id == 2)) || (PreviousId == 1 && (Step.Id == 0 || Step.Id == OverheadId))
        || (PreviousId == 9 && Step.Id == 3);
    float Cost = (Step.bRunIn ? 1.5f : 1.f) + (bFlows ? 0.f : .4f) + FMath::Clamp(Noise, 0.f, 1.f) * .5f;
    if (bLast && !IsFinisher(Step.Id)) Cost += 1.f;
    if (!bLast && IsFinisher(Step.Id)) Cost += 2.f;
    return Cost;
}

// 남은 Hits번의 공격 순서를 짠다. Used: 이번 몰아치기에서 이미 친 공격. Available(Id, bRunIn): 그 카드를 지금 쓸 수 있는가(쿨다운 등).
// 전부는 못 이어도 이을 수 있는 데까지 잇는다(가장 긴 것 중 가장 싼 것). 아무것도 안 되면 빈 배열.
TArray<FStringStep> PlanAttackString(float Distance, float Angle, int32 Hits, int32 PreviousId, const TArray<int32>& Used,
    TFunctionRef<bool(int32, bool)> Available, TFunctionRef<float()> Noise)
{
    static const FStringStep Options[] = {{0, false}, {1, false}, {2, false}, {3, false}, {OverheadId, false}, {0, true}, {1, true}, {2, true}};
    TArray<FStringStep> Best;
    float BestCost = TNumericLimits<float>::Max();
    if (Hits <= 0) return Best;
    Hits = FMath::Min(Hits, 2);
    for (const FStringStep& First : Options)
    {
        if (Used.Contains(First.Id) || !StringStepPossible(First, Distance, Angle) || !Available(First.Id, First.bRunIn)) continue;
        const float FirstNoise = Noise();
        // 결과: 달려들면 붙고(약 230cm) 정면이 된다. 제자리에서 치면 플레이어가 조금 물러난다고 본다(+30cm).
        const float After = First.bRunIn ? 230.f : Distance + 30.f;
        bool bExtended = false;
        if (Hits >= 2)
            for (const FStringStep& Second : Options)
            {
                if (Second.Id == First.Id || Used.Contains(Second.Id) || !StringStepPossible(Second, After, 0.f) || !Available(Second.Id, Second.bRunIn)) continue;
                bExtended = true;
                const float Cost = StringStepCost(PreviousId, First, false, FirstNoise) + StringStepCost(First.Id, Second, true, Noise());
                if (Best.Num() < 2 || Cost < BestCost) { Best = {First, Second}; BestCost = Cost; }
            }
        if (!bExtended && Best.Num() < 2)
        {
            const float Cost = StringStepCost(PreviousId, First, true, FirstNoise);
            if (Best.Num() == 0 || Cost < BestCost) { Best = {First}; BestCost = Cost; }
        }
    }
    return Best;
}

// 이번에 몇 번 칠지(Utility의 몫). 왼손·오른손으로 시작했을 때만 길게 잇는다. 2연타는 한 번 더(휩쓸기 등), 나머지는 그 자체로 끝이다:
// 연속기(잽잽훅)는 이미 세 번이고, 큰 한 방·돌진·가드 브레이크는 하나로 읽혀야 하는 공격이다.
int32 ChooseStringLength(int32 FirstId, float Roll, float TwoShare, float ThreeShare)
{
    if (FirstId == 9) return Roll < TwoShare + ThreeShare ? 2 : 1;
    if (FirstId != 0 && FirstId != 1) return 1;
    return Roll < ThreeShare ? 3 : (Roll < ThreeShare + TwoShare ? 2 : 1);
}

// 연계로 나온 공격에서 한 번 더 이을 확률은 절반이고, 세 번째 공격에서는 끝난다. 반격할 틈은 반드시 돌아온다.
float ChainLinkChance(float Base, int32 Depth)
{
    return Depth <= 0 ? Base : (Depth == 1 ? Base * .5f : 0.f);
}

// ---- 추격 --------------------------------------------------------------------------------------------------------
// 후딜은 "피한 플레이어가 반격하는 시간"이다. 플레이어가 반격할 수 없는 거리로 빠졌다면 그 후딜은 보스가 서 있기만 하는 시간이다.
// 그때는 후딜을 끊고 바로 다음 행동(달려들며 치기, 슈퍼맨 펀치)을 고른다. 붙어서 피한 플레이어의 반격 시간은 그대로다.
// ---- 몰아치기와 그 끝 ----------------------------------------------------------------------------------------------
// 보스는 연달아 몰아치지만(연계, 추격) 끝이 있다: 한 번에 세 번까지이고, 이어진 공격의 후딜은 줄이지 않는다.
// 그래서 몰아치기를 다 피한 플레이어에게는 평소보다 긴 반격 시간이 반드시 돌아온다. 첫 공격만 치고 끝나면 평소 후딜이다.
float RecoveryScaleFor(int32 StringDepth, float Ordinary, float Ender)
{
    return FMath::Clamp(StringDepth >= 1 ? Ender : Ordinary, .3f, 1.f);
}

bool PursuitHolds(float Distance, float Dot, bool bPlayerDown, float MinDistance)
{
    return !bPlayerDown && FMath::IsFinite(Distance) && FMath::IsFinite(Dot) && Distance >= MinDistance && Dot >= .5f;
}

// ---- 각 맞추는 걸음 ------------------------------------------------------------------------------------------------
// 실제 플레이 기록: 제자리 턴 13번 중 8번이 60도 이하였다. 작은 각도에서 발만 구르고 자리는 그대로라 굳어 보였다.
// 작은 각도는 걸으면서 돌아본다. 큰 각도(옆·뒤)는 턴 동작을 그대로 쓴다.
bool FacingStepWanted(float AbsAngle, float MinAngle, float MaxAngle)
{
    return FMath::IsFinite(AbsAngle) && AbsAngle >= MinAngle && AbsAngle <= MaxAngle;
}

// 플레이어가 물러나는 중인가(초당 120cm 넘게 멀어짐).
bool IsRetreating(float SpeedAway) { return FMath::IsFinite(SpeedAway) && SpeedAway >= 120.f; }

// ---- 연속기(잽 → 잽 → 훅)의 타별 걸음 -----------------------------------------------------------------------------
// 연속기는 타마다 "걸어 들어가며 칠지, 제자리에서 칠지"를 그 타가 시작될 때의 거리로 정한다. 두 몽타주(제자리 / 걸음)는
// 시간과 상체가 같아서, 타 사이에 같은 시각으로 바꿔 재생해도 자세가 이어진다.
// 전에는 걸음 몽타주를 끝까지 재생해서, 플레이어가 물러나지 않으면 2타와 훅이 제자리에서 걷는 동작만 했다(발이 미끄러졌다).
constexpr float ComboStageTimes[] = {1.55f, 2.81f};          // 2타, 훅의 걸음이 시작되기 직전(몽타주 시간, 초)
constexpr float ComboStageStops[] = {225.f, 225.f, 200.f};   // 1타, 2타, 훅의 걸음이 끝났을 때 남길 간격
constexpr float ComboStageTravel[] = {215.f, 214.f};         // 2타, 훅의 걸음이 가진 전진량(게임 cm)

// 이번 타를 걸어 들어가며 칠 것인가: 걸음의 절반 이상을 실제로 걸을 수 있을 때만.
bool ComboStageStrides(float Distance, float Stop, float Travel)
{
    return FMath::IsFinite(Distance) && Distance - Stop >= .5f * Travel;
}

int32 ComboStageAt(float MontageSeconds)
{
    return MontageSeconds < ComboStageTimes[0] - .05f ? 0 : (MontageSeconds < ComboStageTimes[1] - .05f ? 1 : 2);
}

float OnePunchStep(float StartDistance, float AuthoredDistance, float RetreatSpeed)
{
    if (!FMath::IsFinite(StartDistance) || !FMath::IsFinite(AuthoredDistance)
        || !FMath::IsFinite(RetreatSpeed)) return 0.f;
    if (StartDistance < 300.f) return FMath::Clamp(AuthoredDistance, 0.f, 145.f);
    // The designer accepted MotionLab's full single step. Use that same finite
    // request in the 300..400cm starting band, with the existing foot curve.
    // Capsule clearance can shorten travel; target movement cannot extend it.
    return 145.f;
}

float ApplyLabPunchMode(bool bMotionLab, int32 Mode, float CombatStep, float Budget)
{
    if (!bMotionLab || Mode == 0) return CombatStep;
    if (Mode == 1) return 0.f;
    if (Mode == 2) return FMath::Clamp(Budget,0.f,145.f);
    return CombatStep;
}

float ComboFollowStep(float Distance, float Authored, float RetreatSpeed)
{
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(Authored) || !FMath::IsFinite(RetreatSpeed)) return 0.f;
    // A new step for a new strike. Never chase continuously during the punch.
    const float Room = FMath::Max(0.f, Distance - 250.f);
    const float Lead = FMath::Clamp(RetreatSpeed, 0.f, 450.f) * .08f;
    if (Room <= 0.f) return 0.f;
    return FMath::Min(FMath::Max(0.f, Distance - 175.f),
        FMath::Clamp(FMath::Max(Authored, Room + Lead), 0.f, 180.f));
}

bool ChoosePostAttackProbe(int32 ActionId, float Distance, float Min, float Max, float Dot,
    bool bFreshRecovery, bool bCooldownReady, float Roll, float Chance)
{
    // Keep reactive/special attacks direct; only ordinary boxing preparations vary.
    return bFreshRecovery && bCooldownReady && (ActionId == 0 || ActionId == 1 || ActionId == 9)
        && Distance >= FMath::Max(225.f, Min + 20.f) && Distance <= Max && Dot >= .5f
        && Roll >= 0.f && Roll < FMath::Clamp(Chance, 0.f, 1.f);
}

FVector LateralEntryGoal(const FVector& Boss, const FVector& Player, float Range, float Degrees)
{
    FVector Goal = Player + (Boss - Player).GetSafeNormal2D().RotateAngleAxis(Degrees, FVector::UpVector) * Range;
    Goal.Z = Boss.Z;
    return Goal;
}

// Failures in unrelated encounters/time windows must not accumulate forever.
bool RecordEntryFailure(int32& Count, double& LastAt, double Now, double Window)
{
    Count = LastAt >= 0.0 && Now >= LastAt && Now - LastAt <= Window ? Count + 1 : 1;
    LastAt = Now;
    if (Count < 2) return false;
    Count = 0;
    return true;
}

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
FString Text(const UObject* O, FName Name)
{
    if (IsValid(O)) if (const FStrProperty* P = FindFProperty<FStrProperty>(O->GetClass(), Name))
        return P->GetPropertyValue_InContainer(O);
    return FString();
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

void UBossCombatIntentComponent::ClearCombatEffects()
{
    if (UpperChargeFX) { UpperChargeFX->DestroyComponent(); UpperChargeFX = nullptr; }
    if (bGuardOverlayActive)
        if (ACharacter* Boss = Cast<ACharacter>(GetOwner())) Boss->GetMesh()->SetOverlayMaterial(PreviousOverlay);
    PreviousOverlay = nullptr;
    bGuardOverlayActive = false;
    bUpperBurstPlayed = false;
}

void UBossCombatIntentComponent::UpdateCombatEffects()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss || !Boss->GetMesh() || !GetWorld()) return;
    const int32 Id = static_cast<int32>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("ActionId"), -1));
    const bool bWindup = StateIs(Boss, TEXT("Boss.Combat.Attack.Windup"));
    const bool bStrike = StateIs(Boss, TEXT("Boss.Combat.Attack.Active"));
    const bool bAlive = Number(Boss, TEXT("CurrentHealth")) > 0;
    const bool bGuardAura = bAlive && Id == 5 && (bWindup || bStrike);
    if (bGuardAura && !bGuardOverlayActive)
    {
        if (!GuardOverlay) GuardOverlay = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/BossArena/Boss/Materials/M_Crunch_GuardBodyAura.M_Crunch_GuardBodyAura"));
        if (GuardOverlay)
        {
            PreviousOverlay = Boss->GetMesh()->GetOverlayMaterial();
            Boss->GetMesh()->SetOverlayMaterial(GuardOverlay);
            bGuardOverlayActive = true;
        }
    }
    else if (!bGuardAura && bGuardOverlayActive)
    {
        Boss->GetMesh()->SetOverlayMaterial(PreviousOverlay);
        PreviousOverlay = nullptr;
        bGuardOverlayActive = false;
    }

    const double Elapsed = GetWorld()->GetTimeSeconds() - Number(Boss, TEXT("AttackStartedAt"));
    // 어퍼컷은 주먹을 모으는 동안(첫 타격 직전까지) 불꽃이 커진다. 전에는 예고 시간(0.4초) 동안만 켰는데, 이제 예고는 짧고 모으는 동작이 길다.
    double Charge = 0.0;
    if (const UObject* Card = Object(Boss, TEXT("ActiveAction")))
        if (const FArrayProperty* Times = FindFProperty<FArrayProperty>(Card->GetClass(), TEXT("ImpactTimes")))
            if (const FNumericProperty* Inner = CastField<FNumericProperty>(Times->Inner))
            {
                FScriptArrayHelper Values(Times, Times->ContainerPtrToValuePtr<void>(Card));
                if (Values.Num() > 0 && Inner->IsFloatingPoint()) Charge = Inner->GetFloatingPointPropertyValue(Values.GetRawPtr(0));
            }
    // 불을 모으는 공격: 어퍼컷(왼손)과 내려찍기(오른손).
    const bool bFireAttack = Id == 2 || Id == 10;
    const FName FireHand = Id == 10 ? TEXT("hand_r") : TEXT("hand_l");
    const bool bCharging = bAlive && bFireAttack && (bWindup || StateIs(Boss, TEXT("Boss.Combat.Attack.Telegraph"))) && Charge > 0 && Elapsed >= 0 && Elapsed < Charge;
    if (bCharging)
    {
        if (!UpperChargeFX)
        {
            UParticleSystem* Flame = LoadObject<UParticleSystem>(nullptr,
                TEXT("/Game/ParagonCrunch/FX/Particles/Abilities/Uppercut/FX/P_Crunch_Fist_Fire_UpperCut.P_Crunch_Fist_Fire_UpperCut"));
            if (Flame) UpperChargeFX = UGameplayStatics::SpawnEmitterAttached(Flame, Boss->GetMesh(), FireHand,
                FVector::ZeroVector, FRotator::ZeroRotator, FVector(.2f), EAttachLocation::KeepRelativeOffset, true);
        }
        if (UpperChargeFX) UpperChargeFX->SetRelativeScale3D(FVector(FMath::Lerp(.2f, .85f,
            static_cast<float>(FMath::Clamp(Elapsed / Charge, 0.0, 1.0)))));
    }
    else if (UpperChargeFX) { UpperChargeFX->DestroyComponent(); UpperChargeFX = nullptr; }

    if (bAlive && bFireAttack && bStrike && !bUpperBurstPlayed)
    {
        // Release cue at the fist; actual damage/contact FX still use the hand trace.
        UParticleSystem* Burst = LoadObject<UParticleSystem>(nullptr,
            TEXT("/Game/ParagonCrunch/FX/Particles/Abilities/Uppercut/FX/P_Crunch_Uppercut_Impact.P_Crunch_Uppercut_Impact"));
        if (Burst) UGameplayStatics::SpawnEmitterAtLocation(Boss, Burst, Boss->GetMesh()->GetSocketLocation(FireHand),
            Boss->GetActorRotation(), FVector(.9f), true);
        bUpperBurstPlayed = true;
    }
    if (!bFireAttack || (!bWindup && !bStrike)) bUpperBurstPlayed = false;
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
    if (!Boss || IsActive() || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    Action = Object(Boss, TEXT("ActiveAction"));
    Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    Slot = static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1));
    if (!Action.IsValid() || !Target.IsValid() || Slot < 0) return;
    const double Now = GetWorld()->GetTimeSeconds();
    StartedAt = NextPlanAt = Now;
    bSideEntryActive = bSideEntryUsed = false;
    PreviousSpeed = Boss->GetCharacterMovement()->MaxWalkSpeed;
    const float Distance = FVector::Dist2D(Boss->GetActorLocation(), Target->GetActorLocation());
    // 카드의 최대 거리는 "후보가 되는 거리"(중거리 끝)다. 바로 시작해도 닿는 거리는 그보다 짧을 수 있어서, 그 안으로 먼저 들어간다.
    const int32 SelectedId = static_cast<int32>(Number(Action.Get(), TEXT("ActionId"), -1));
    const float Reach = MidVersionReach(SelectedId);
    float BandLo = 0.f, BandHi = 0.f;
    NearestStartBand(SelectedId, Distance, static_cast<float>(Number(Action.Get(), TEXT("MinDistance"))),
        static_cast<float>(Number(Action.Get(), TEXT("MaxDistance"))), BandLo, BandHi);
    // 중거리 버전의 구간이면 "바로 시작해도 닿는 거리"까지만 인정한다. 그보다 멀면 먼저 그 안으로 들어간다.
    const float StartMax = Reach > 0.f && BandLo >= MidVersionStart(SelectedId) ? FMath::Min(BandHi, Reach) : BandHi;
    GoalMinDistance = BandLo;
    const float Facing = FVector::DotProduct(Boss->GetActorForwardVector(),
        (Target->GetActorLocation()-Boss->GetActorLocation()).GetSafeNormal2D());
    const bool bFreshRecovery = Flag(Boss, TEXT("bPostAttackProbePending")) && Now <= PostAttackDecisionUntil;
    bPostProbeRequested = ChoosePostAttackProbe(static_cast<int32>(Number(Action.Get(), TEXT("ActionId"), -1)),
        Distance, GoalMinDistance, StartMax, Facing, bFreshRecovery,
        Now >= Number(Boss, TEXT("GoapProbeCooldownUntil")), FMath::FRand(), PostAttackProbeChance);
    // Consume once after the Utility choice, never once per scoring tick.
    SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
    PostAttackDecisionUntil = 0;
    // Once entry is needed, go inside the start boundary rather than stopping
    // at its outer edge. Already-close attacks never back away to this target.
    GoalMaxDistance = Distance > StartMax ? FMath::Max(GoalMinDistance + 20.f, StartMax - 40.f) : StartMax;
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

namespace { float RearTurnSpeedFor(float Angle, float ImpactSeconds, float MaxSpeed); float FirstImpactSeconds(const UObject* Card); }

void UBossCombatIntentComponent::RecordAttackRecoveryEnd()
{
    AActor* Boss = GetOwner();
    if (IsActive() || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    const int32 FinishedId = static_cast<int32>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("ActionId"), -1));
    const bool bOrdinaryCombatEnd = (FinishedId >= 0 && FinishedId <= 6) || FinishedId == 9 || FinishedId == OverheadId;
    SetFlag(Boss, TEXT("bPostAttackProbePending"), bOrdinaryCombatEnd);
    PostAttackDecisionUntil = bOrdinaryCombatEnd ? GetWorld()->GetTimeSeconds() + 2.0 : 0.0;
    ++AttackStreak;
    LastRecoveryLocation = Boss->GetActorLocation();
    const int32 Chained = ChainSlot;
    const int32 Depth = ChainDepth;
    const bool bPursuit = bPursuitExit;
    ChainSlot = INDEX_NONE;
    bChainedAttack = false;
    ChainDepth = 0;
    bPursuitExit = false;
    if (Chained != INDEX_NONE)
    {
        SetText(Boss, TEXT("AttackRequestSource"), TEXT("chain"));
        if (RequestLinkSlot(Chained, bLinkPivot))
        {
            bChainedAttack = true;
            ChainDepth = Depth + 1;
            if (LinkAngle > 15.f)
            {
                // 플레이어가 비껴 있으면 준비 동작 동안 고르게 돌아서 타격 직전에 정면이 된다(돌아서며 친다).
                bRearResponseActive = true;
                RearTurnRate = RearTurnSpeedFor(LinkAngle, FirstImpactSeconds(Object(Boss, TEXT("ActiveAction"))), RearResponseTurnSpeed);
            }
            SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("chain"));
            return;
        }
    }
    if (bPursuit) ChainDepth = Depth + 1;      // 추격 뒤의 공격도 몰아치기의 일부로 센다
    // 몰아치기가 끝났다: 긴 후딜을 다 보낸 뒤에도 뒤쪽 대응으로 덮지 않는다. 다 피한 플레이어의 차례다.
    const bool bStringEnded = Depth >= 1 && !bPursuit;
    if (!bStringEnded) TryRearResponse();
    if (TryFacingStep()) return;
    if (!bPursuit) TryFootwork();      // 쫓는 중에는 발놀림으로 쉬지 않는다
}

namespace
{
// ---- 공격 뒤 기동(발놀림) -------------------------------------------------------------------------------------
// 실전 기록: 플레이어가 붙어 있으면 보스는 표본의 99%에서 서 있었다. 후딜이 끝나는 프레임에 다음 공격을 골랐기 때문이다.
// "언제 발을 옮기나"는 아래 확률이, "무엇을 노리나"는 의도 추첨이, "어떤 걸음을 어떤 순서로"는 GOAP(PlanFootwork)가 정한다.
// 걸음은 고정된 지점으로 가지 않는다. 매 프레임 플레이어의 지금 위치를 기준으로 방향을 다시 잡아서, 움직이는 플레이어를 따라 돈다.
float FootworkChance(int32 Streak, bool bCrowded, bool bPhaseTwo, float PhaseTwoScale)
{
    const float Base = Streak <= 1 ? .25f : (Streak == 2 ? .55f : .85f);
    return FMath::Clamp((Base + (bCrowded ? .2f : 0.f)) * (bPhaseTwo ? PhaseTwoScale : 1.f), 0.f, .9f);
}

// 기동을 할 수 있는 상황인가: 플레이어가 앞에 있고, 달려가야 할 만큼 멀지 않고, 가드를 깨야 할 때가 아니다.
bool FootworkAllowed(float Distance, float Dot, float MaxDistance, float GuardSeconds)
{
    return FMath::IsFinite(Distance) && FMath::IsFinite(Dot) && Distance <= MaxDistance && Dot >= .5f && GuardSeconds < 2.f;
}

// 옆으로 돌 방향의 비용. 플레이어가 옆으로 움직이는 중이면 그쪽으로 따라 돌아 길을 끊고(반대쪽이 비싸다),
// 서 있으면 Coin(0..1)으로 한쪽을 조금 싸게 해서 늘 같은 쪽으로 돌지 않게 한다.
void FootworkSideCosts(float PlayerSpeedToBossRight, float Coin, float& LeftCost, float& RightCost)
{
    LeftCost = RightCost = 0.f;
    if (PlayerSpeedToBossRight > 80.f) LeftCost = .4f;
    else if (PlayerSpeedToBossRight < -80.f) RightCost = .4f;
    else (Coin < .5f ? LeftCost : RightCost) = .2f;
}

// 이번 기동이 노리는 것. 거리대마다 고를 수 있는 의도가 다르다.
struct FFootworkWants { bool bSpace = false, bAngle = false, bPocket = false; };
FFootworkWants ChooseFootworkWants(float Distance, float Crowd, float Pocket, float Roll)
{
    FFootworkWants W;
    if (Distance < Crowd) { W.bSpace = true; W.bAngle = Roll >= .35f; }      // 붙어 있다: 빠지기 35 / 빠지며 각 바꾸기 65
    else if (Distance <= Pocket) W.bAngle = true;                             // 주먹 거리: 각 바꾸기
    else { W.bPocket = true; W.bAngle = Roll >= .6f; }                        // 주먹 거리 밖: 걸어 들어가기 60 / 돌면서 들어가기 40
    return W;
}

// 걸음 한 번이 끝났는가. Progress: 뒤로·걸어 들어가기는 지금 간격, 돌기는 돈 각도.
bool FootworkLegDone(EBossPositionAction Leg, float Distance, float Swept, float SweepTarget, float Comfort, float PressStop, float Seconds)
{
    switch (Leg)
    {
    case EBossPositionAction::StepBack: return Distance >= Comfort - 10.f || Seconds >= .9f;
    case EBossPositionAction::DirectApproach: return Distance <= PressStop || Seconds >= 1.3f;
    case EBossPositionAction::OrbitLeft:
    case EBossPositionAction::OrbitRight: return Swept >= SweepTarget || Seconds >= 1.5f;
    default: return true;
    }
}

// 길이 열려 있는가: 바닥(네비게이션)을 따라 From에서 To까지 막힘 없이 갈 수 있는지.
bool NavOpen(UObject* World, const FVector& From, const FVector& To)
{
    FVector Hit;
    return !UNavigationSystemV1::NavigationRaycast(World, From, To, Hit);
}
}

// 공격이 끝났을 때 플레이어가 조금 비껴 있으면, 제자리 턴 대신 걸으면서 돌아본다. 가까우면 옆으로 한 걸음, 멀면 걸어 들어가며.
bool UBossCombatIntentComponent::TryFacingStep()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss || !GetWorld() || bFootworkActive || bActive || bReassessing) return false;
    if (!StateIs(Boss, TEXT("Boss.Combat.Ready")) || Number(Boss, TEXT("CurrentHealth")) <= 0) return false;
    if (GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"))) return false;
    if (Flag(Boss, TEXT("bFirstSlamPending")) && Flag(Boss, TEXT("bPhaseTwo"))) return false;
    const ACharacter* Player = Cast<ACharacter>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerCharacter(this, 0);
    if (!IsValid(Player) || Number(Player, TEXT("CurrentHealth"), 1) <= 0 || Flag(Player, TEXT("bKnockedDown"))) return false;
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const float Angle = FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw, Delta.Rotation().Yaw));
    if (!FacingStepWanted(Angle, FacingStepMinAngle, FacingStepMaxAngle)) return false;
    const FVector Away = -Delta.GetSafeNormal2D();
    const FVector LeftDir = Away.RotateAngleAxis(90.f, FVector::UpVector);
    // 옆걸음은 몸이 이미 향한 쪽으로 딛는다(반대로 디디면 뒷걸음이 된다).
    const bool bLeft = FVector::DotProduct(Boss->GetActorForwardVector(), LeftDir) >= 0.f;
    const bool bWalkIn = Delta.Size2D() > PocketDistance;
    const EBossPositionAction Leg = bWalkIn ? EBossPositionAction::DirectApproach
        : (bLeft ? EBossPositionAction::OrbitLeft : EBossPositionAction::OrbitRight);
    const FVector Floor = Boss->GetActorLocation() - FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    if (!NavOpen(this, Floor, Floor + (bWalkIn ? -Away : (bLeft ? LeftDir : -LeftDir)) * 100.f)) return false;
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Position"), TEXT("각을 맞추는 걸음"))) return false;
    if (AAIController* Controller = Cast<AAIController>(Boss->GetController())) Controller->StopMovement();
    FootworkLegs.Reset();
    FootworkLegs.Add(static_cast<uint8>(Leg));
    bFootworkActive = true;
    bFacingStep = true;
    FootworkLegIndex = 0;
    FootworkStartedAt = GetWorld()->GetTimeSeconds();
    FootworkSpeedBefore = Boss->GetCharacterMovement()->MaxWalkSpeed;
    CircleSweepWanted = 90.f;                       // 각이 맞으면 끝난다. 이 값까지 도는 일은 없다
    SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
    PostAttackDecisionUntil = 0;
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    SetFlag(Boss, TEXT("bAttackIntentActive"), true);
    const FString Reason = bWalkIn ? TEXT("각을 맞춘다: 걸어 들어가며 돌아본다") : TEXT("각을 맞춘다: 옆으로 디디며 돌아본다");
    Status = Reason;
    SetText(Boss, TEXT("IntentPhase"), TEXT("footwork"));
    SetText(Boss, TEXT("IntentReason"), Reason);
    SetText(Boss, TEXT("GoapReason"), Reason);
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("facing_step"));
    BeginFootworkLeg();
    return true;
}

namespace { float BowKick(float PeakDegrees); }

// 후딜이 끝난 순간, 다음 공격을 고르기 전에 발을 옮길지 정한다. 옮긴다면 Position 상태로 들어가 계획한 걸음들을 차례로 하고,
// 끝나면 Ready로 돌아가 그 자리에서 Utility가 새로 고른다.
void UBossCombatIntentComponent::TryFootwork()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss || !GetWorld() || bFootworkActive || bActive || bReassessing) return;
    if (!StateIs(Boss, TEXT("Boss.Combat.Ready")) || Number(Boss, TEXT("CurrentHealth")) <= 0) return;
    if (GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"))) return;      // 모션랩은 측정용: 보스가 스스로 움직이지 않는다
    if (Flag(Boss, TEXT("bFirstSlamPending")) && Flag(Boss, TEXT("bPhaseTwo"))) return;
    ACharacter* Player = Cast<ACharacter>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerCharacter(this, 0);
    if (!IsValid(Player) || Number(Player, TEXT("CurrentHealth"), 1) <= 0 || Flag(Player, TEXT("bKnockedDown"))) return;
    const FVector BossLocation = Boss->GetActorLocation(), PlayerLocation = Player->GetActorLocation();
    const FVector Delta = PlayerLocation - BossLocation;
    const float Distance = Delta.Size2D();
    const float Dot = FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D());
    if (!FootworkAllowed(Distance, Dot, FootworkMaxDistance, static_cast<float>(Number(Boss, TEXT("RecentGuardSeconds"))))) return;
    const bool bCrowded = Distance < CrowdDistance;
    // 숙이며 빠지기: 붙어서 맞고 있으면 걸음 대신 상체를 숙이고 빠르게 뒤로 빠진다. 묵직하지만 굼뜨지는 않다.
    if (Distance < ComfortDistance && HitsTakenWithin(2.f) >= SwayHits && FMath::FRand() < SwayChance)
    {
        const FVector Floor = BossLocation - FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
        if (NavOpen(this, Floor, Floor - Delta.GetSafeNormal2D() * 180.f)
            && TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Position"), TEXT("숙이며 빠지기")))
        {
            if (AAIController* Controller = Cast<AAIController>(Boss->GetController())) Controller->StopMovement();
            FootworkLegs.Reset();
            FootworkLegs.Add(static_cast<uint8>(EBossPositionAction::StepBack));
            bFootworkActive = bSwayBack = true;
            FootworkLegIndex = 0;
            FootworkStartedAt = GetWorld()->GetTimeSeconds();
            FootworkSpeedBefore = Boss->GetCharacterMovement()->MaxWalkSpeed;
            AttackStreak = 0;
            BowVelocity -= BowKick(SwayDuckPitch);
            SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
            PostAttackDecisionUntil = 0;
            SetNumber(Boss, TEXT("UtilityAction"), 0);
            SetFlag(Boss, TEXT("bAttackIntentActive"), true);
            Status = TEXT("맞고 있다: 숙이며 뒤로 빠진다");
            SetText(Boss, TEXT("IntentPhase"), TEXT("footwork"));
            SetText(Boss, TEXT("IntentReason"), Status);
            SetText(Boss, TEXT("GoapReason"), Status);
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("sway_back"));
            BeginFootworkLeg();
            return;
        }
    }
    const float Chance = Distance > PocketDistance ? PressChance
        : FootworkChance(AttackStreak, bCrowded, Flag(Boss, TEXT("bPhaseTwo")), PhaseTwoFootworkScale);
    if (FMath::FRand() >= Chance) return;

    // 어느 쪽이 열려 있는지 바닥을 따라 확인한다. 계획은 "열려 있다"고 확인된 걸음만 쓴다.
    const FVector BossFloor = BossLocation - FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    const FVector Away = -Delta.GetSafeNormal2D();                        // 플레이어에서 보스 쪽
    const FVector LeftDir = Away.RotateAngleAxis(90.f, FVector::UpVector);  // 왼쪽으로 돌 때 보스가 가는 방향
    const bool bBackOpen = NavOpen(this, BossFloor, BossFloor + Away * 130.f);
    const bool bLeftOpen = NavOpen(this, BossFloor, BossFloor + LeftDir * 150.f);
    const bool bRightOpen = NavOpen(this, BossFloor, BossFloor - LeftDir * 150.f);
    const bool bForwardOpen = NavOpen(this, BossFloor, BossFloor - Away * 100.f);
    const FFootworkWants Wants = ChooseFootworkWants(Distance, CrowdDistance, PocketDistance, FMath::FRand());
    float LeftCost, RightCost;
    FootworkSideCosts(FVector::DotProduct(Player->GetVelocity(), Boss->GetActorRightVector()), FMath::FRand(), LeftCost, RightCost);
    const auto Plan = UBossPositionPlanner::PlanFootwork(Distance, Dot, CrowdDistance, PocketDistance, .5f,
        bBackOpen, bLeftOpen, bRightOpen, bForwardOpen, Wants.bSpace, Wants.bAngle, Wants.bPocket,
        FMath::Max(0.f, ComfortDistance - Distance) / FMath::Max(1.f, StepBackSpeed) + .15f, LeftCost, RightCost,
        FMath::Max(0.f, Distance - PressStopDistance) / FMath::Max(1.f, PressSpeed) + .1f);
    if (!Plan.bFound) return;
    FootworkLegs.Reset();
    for (const EBossPositionAction Step : Plan.Steps)
        if (Step != EBossPositionAction::FaceTarget && Step != EBossPositionAction::None) FootworkLegs.Add(static_cast<uint8>(Step));   // 걷는 내내 플레이어를 본다
    if (FootworkLegs.IsEmpty()) return;
    // 돌기와 걸어 들어가기가 함께 있으면 돌기를 먼저 한다: 안쪽으로 감아 들어가는 한 동작이 된다.
    FootworkLegs.StableSort([](uint8 A, uint8 B)
    { return A != static_cast<uint8>(EBossPositionAction::DirectApproach) && B == static_cast<uint8>(EBossPositionAction::DirectApproach); });
    FString Names;
    for (const uint8 Leg : FootworkLegs)
    {
        const EBossPositionAction Step = static_cast<EBossPositionAction>(Leg);
        Names += (Names.IsEmpty() ? TEXT("") : TEXT(" → "));
        Names += Step == EBossPositionAction::StepBack ? TEXT("뒤로 한 걸음")
            : (Step == EBossPositionAction::DirectApproach ? TEXT("걸어 들어가기")
            : (Step == EBossPositionAction::OrbitLeft ? TEXT("왼쪽으로 돌기") : TEXT("오른쪽으로 돌기")));
    }
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Position"), TEXT("공격 뒤 기동"))) return;
    if (AAIController* Controller = Cast<AAIController>(Boss->GetController())) Controller->StopMovement();
    bFootworkActive = true;
    FootworkLegIndex = 0;
    FootworkStartedAt = GetWorld()->GetTimeSeconds();
    FootworkSpeedBefore = Boss->GetCharacterMovement()->MaxWalkSpeed;
    // 도는 각도는 매번 조금 다르다(30~45도).
    CircleSweepWanted = FMath::FRandRange(FMath::Max(10.f, FootworkAngle), FootworkAngle + 15.f);
    AttackStreak = 0;
    // 이번 판단에서는 "고른 뒤 옆걸음"을 겹쳐 하지 않는다.
    SetFlag(Boss, TEXT("bPostAttackProbePending"), false);
    PostAttackDecisionUntil = 0;
    SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Plan.FirstAction));
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    SetFlag(Boss, TEXT("bAttackIntentActive"), true);
    const TCHAR* Intent = Wants.bPocket ? (Wants.bAngle ? TEXT("돌면서 조인다") : TEXT("걸어 들어가 조인다"))
        : (Wants.bAngle ? (bCrowded ? TEXT("빠지며 각을 바꾼다") : TEXT("각을 바꾼다")) : TEXT("간격을 만든다"));
    const FString Reason = FString::Printf(TEXT("%s: %s"), Intent, *Names);
    Status = Reason;
    SetText(Boss, TEXT("IntentPhase"), TEXT("footwork"));
    SetText(Boss, TEXT("IntentReason"), Reason);
    SetText(Boss, TEXT("GoapReason"), Reason);
    Invoke(Boss, TEXT("RecordCombatQA"), Wants.bPocket ? TEXT("footwork_press")
        : (Wants.bAngle ? TEXT("footwork_angle") : TEXT("footwork_space")));
    BeginFootworkLeg();
}

void UBossCombatIntentComponent::BeginFootworkLeg()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    const AActor* Player = Boss ? Cast<AActor>(Object(Boss, TEXT("ObservedPlayer"))) : nullptr;
    if (!Boss || !IsValid(Player) || !FootworkLegs.IsValidIndex(FootworkLegIndex)) return;
    const EBossPositionAction Leg = static_cast<EBossPositionAction>(FootworkLegs[FootworkLegIndex]);
    const FVector Away = (Boss->GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
    FootworkLegStartedAt = GetWorld()->GetTimeSeconds();
    LegSwept = 0.f;
    LegLastBearing = Away.Rotation().Yaw;
    LegSweepTarget = CircleSweepWanted;
    // 뒤에 "걸어 들어가기"가 남아 있으면 제자리 원이 아니라 안쪽으로 감아 들어간다. 아니면 지금 간격(붙어 있었다면 여유 간격)을 지키며 돈다.
    LegRadius = FootworkLegs.Contains(static_cast<uint8>(EBossPositionAction::DirectApproach)) ? PressStopDistance
        : FMath::Max(FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation()), ComfortDistance);
    bLegFlipped = false;
    Boss->GetCharacterMovement()->MaxWalkSpeed = FMath::Max(1.f, (bSwayBack ? SwaySpeed : Leg == EBossPositionAction::StepBack ? StepBackSpeed
        : (Leg == EBossPositionAction::DirectApproach && !bFacingStep ? PressSpeed : SideStepSpeed)) * (Flag(Boss, TEXT("bPhaseTwo")) ? PhaseTwoStepSpeedScale : 1.f));
    Invoke(Boss, TEXT("RecordCombatQA"), Leg == EBossPositionAction::StepBack ? TEXT("footwork_leg_back")
        : (Leg == EBossPositionAction::DirectApproach ? TEXT("footwork_leg_press") : TEXT("footwork_leg_circle")));
}

void UBossCombatIntentComponent::TickFootwork(float DeltaTime)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    AActor* Player = Boss ? Cast<AActor>(Object(Boss, TEXT("ObservedPlayer"))) : nullptr;
    // 다른 시스템이 상태를 바꿨으면(피격 연출, 사망, 후속 공격) 조용히 손을 뗀다.
    if (!Boss || !StateIs(Boss, TEXT("Boss.Combat.Position"))) { EndFootwork(false, TEXT("상태 변경으로 기동 중단")); return; }
    if (!IsValid(Player) || Number(Boss, TEXT("CurrentHealth")) <= 0 || Number(Player, TEXT("CurrentHealth"), 1) <= 0
        || Flag(Player, TEXT("bKnockedDown"))) { EndFootwork(true, TEXT("대상 변경으로 기동 중단")); return; }
    const FVector BossLocation = Boss->GetActorLocation();
    const FVector ToPlayer = Player->GetActorLocation() - BossLocation;
    const float Distance = ToPlayer.Size2D();
    const FVector Away = -ToPlayer.GetSafeNormal2D();
    // 옆·뒤로 걷는 동안에도 몸은 플레이어를 본다.
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), FRotator(0.f, ToPlayer.Rotation().Yaw, 0.f), DeltaTime, TurnSpeed));
    const double Now = GetWorld()->GetTimeSeconds();
    // 플레이어가 멀리 빠져나갔으면 기동을 접고 다시 판단한다(그때는 달려가는 것이 먼저다).
    if (Now - FootworkStartedAt >= FootworkMaxDuration || (!bFacingStep && Distance > FootworkMaxDistance + 80.f) || !FootworkLegs.IsValidIndex(FootworkLegIndex))
    { EndFootwork(true, TEXT("기동 끝: 이 자리에서 새로 고른다")); return; }
    if (bSwayBack && (Distance >= SwayDistance || Now - FootworkStartedAt >= .5))
    { EndFootwork(true, TEXT("빠졌다: 이 자리에서 고른다")); return; }
    // 각 맞추는 걸음은 플레이어가 정면에 오면 끝난다(너무 짧아 발이 튀지 않게 0.35초는 딛는다).
    if (bFacingStep && Now - FootworkStartedAt >= .35
        && FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw, ToPlayer.Rotation().Yaw)) <= FacingStepDoneAngle)
    { EndFootwork(true, TEXT("각을 맞췄다: 이 자리에서 고른다")); return; }
    EBossPositionAction Leg = static_cast<EBossPositionAction>(FootworkLegs[FootworkLegIndex]);
    const float Bearing = Away.Rotation().Yaw;
    const float Turned = FMath::FindDeltaAngleDegrees(LegLastBearing, Bearing);
    LegLastBearing = Bearing;
    const bool bCircle = Leg == EBossPositionAction::OrbitLeft || Leg == EBossPositionAction::OrbitRight;
    if (bCircle) LegSwept += Leg == EBossPositionAction::OrbitLeft ? Turned : -Turned;
    // 걸음의 방향은 매 프레임 플레이어의 지금 위치에서 다시 잡는다.
    FVector Direction = Away;
    if (Leg == EBossPositionAction::DirectApproach) Direction = -Away;
    else if (bCircle)
    {
        const FVector Tangent = Away.RotateAngleAxis(Leg == EBossPositionAction::OrbitLeft ? 90.f : -90.f, FVector::UpVector);
        Direction = (Tangent + Away * FMath::Clamp((LegRadius - Distance) / 100.f, -1.f, .6f)).GetSafeNormal2D();
    }
    const FVector Floor = BossLocation - FVector(0, 0, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    bool bBlocked = !NavOpen(this, Floor, Floor + Direction * 90.f);
    if (bBlocked && bCircle && !bLegFlipped && LegSwept < 10.f)
    {
        // 돌려던 쪽이 막혔으면 한 번은 반대로 돈다.
        bLegFlipped = true;
        Leg = Leg == EBossPositionAction::OrbitLeft ? EBossPositionAction::OrbitRight : EBossPositionAction::OrbitLeft;
        FootworkLegs[FootworkLegIndex] = static_cast<uint8>(Leg);
        LegSwept = 0.f;
        return;
    }
    if (bBlocked || (!bSwayBack && FootworkLegDone(Leg, Distance, LegSwept, LegSweepTarget, ComfortDistance, PressStopDistance,
        static_cast<float>(Now - FootworkLegStartedAt))))
    {
        if (!FootworkLegs.IsValidIndex(++FootworkLegIndex)) { EndFootwork(true, TEXT("기동 끝: 이 자리에서 새로 고른다")); return; }
        BeginFootworkLeg();
        return;
    }
    Boss->AddMovementInput(Direction, 1.f);
}

void UBossCombatIntentComponent::EndFootwork(bool bReturnToReady, const FString& Reason)
{
    if (!bFootworkActive) return;
    bFootworkActive = false;
    bFacingStep = bSwayBack = false;
    FootworkLegs.Reset();
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss) return;
    Boss->GetCharacterMovement()->MaxWalkSpeed = FootworkSpeedBefore;
    SetFlag(Boss, TEXT("bAttackIntentActive"), false);
    if (bReturnToReady)
    {
        Invoke(Boss, TEXT("StopBossLocomotion"));
        TransitionState(Boss, TEXT("Boss.Combat.Position"), TEXT("Boss.Combat.Ready"), Reason);
    }
    Status = Reason;
    SetText(Boss, TEXT("IntentPhase"), TEXT("ready"));
    SetText(Boss, TEXT("IntentReason"), Reason);
    SetText(Boss, TEXT("GoapReason"), Reason);
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("footwork_end"));
}

namespace
{
// 뒤쪽 대응에 쓰는 공격. 훅은 팔이 짧아(238cm) 가까울 때만, 휩쓸기는 넓게 휘둘러 더 멀리(423cm)까지.
constexpr float RearBehindDot = -.17f;          // 약 100도 이상 벗어남 = 등 뒤 (턴 동작의 "뒤" 기준과 같다)
constexpr float RearHookMaxDistance = 230.f;
constexpr float RearSweepMaxDistance = 400.f;
const TCHAR* RearHookCardPath = TEXT("/Game/BossArena/Boss/AI/Actions/DA_Attack_Hook.DA_Attack_Hook");

// 뒤쪽 대응이 타격 조금 전에 정면에 닿도록 하는 회전 속도. 너무 늦으면 상한으로 돈다.
float RearTurnSpeedFor(float Angle, float ImpactSeconds, float MaxSpeed)
{
    const float Time = FMath::Max(.3f, ImpactSeconds - .15f);
    return FMath::Clamp(Angle / Time, 60.f, FMath::Max(60.f, MaxSpeed));
}

// 카드의 첫 타격 시각(행동 시작부터, 초). 없으면 0.8초로 본다.
float FirstImpactSeconds(const UObject* Card)
{
    const FArrayProperty* Times = IsValid(Card) ? FindFProperty<FArrayProperty>(Card->GetClass(), TEXT("ImpactTimes")) : nullptr;
    const FNumericProperty* Inner = Times ? CastField<FNumericProperty>(Times->Inner) : nullptr;
    if (!Inner || !Inner->IsFloatingPoint()) return .8f;
    FScriptArrayHelper Values(Times, Times->ContainerPtrToValuePtr<void>(Card));
    return Values.Num() > 0 ? static_cast<float>(Inner->GetFloatingPointPropertyValue(Values.GetRawPtr(0))) : .8f;
}

// 제자리 턴에 걸릴 시간: 각도에 비례하되, 너무 짧아 발이 튀거나 너무 길어 굼뜨지 않게 범위를 둔다.
float TurnDuration(float Angle, float DegreesPerSecond)
{
    return FMath::Clamp(FMath::Abs(Angle) / FMath::Max(1.f, DegreesPerSecond), .55f, 1.6f);
}

// Sprint 동작의 재생 속도: 실제 속도 ÷ 동작이 원래 가는 속도. 너무 느리거나 빠르게는 재생하지 않는다.
float SprintPlayRate(float Speed, float NaturalSpeed)
{
    return FMath::Clamp(Speed / FMath::Max(1.f, NaturalSpeed), .7f, 1.25f);
}

// 0 = 대응 없음, 1 = 훅, 2 = 휩쓸기. Roll과 Pick은 0..1 난수.
int32 ChooseRearResponse(float Dot, float Distance, float Roll, float Pick, float Chance)
{
    if (!FMath::IsFinite(Dot) || !FMath::IsFinite(Distance) || Dot > RearBehindDot || Distance > RearSweepMaxDistance) return 0;
    if (Roll < 0.f || Roll >= FMath::Clamp(Chance, 0.f, 1.f)) return 0;
    return Distance <= RearHookMaxDistance && Pick < .5f ? 1 : 2;
}
}

namespace { double ArrayNumber(const UObject* Owner, FName Name, int32 Index, double Default = 0.0); }

// 블루프린트의 카드 목록에 없는 새 공격 카드를 실행 중에 덧붙인다(블루프린트는 그대로 둔다).
void UBossCombatIntentComponent::AddExtraCards()
{
    if (bExtraCardsAdded) return;
    bExtraCardsAdded = true;
    AActor* Boss = GetOwner();
    const FArrayProperty* Cards = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (!CardType) return;
    // 새 공격(내려찍기)과, 달려들며 치는 중거리 패턴 넷. 중거리 패턴은 같은 공격의 단거리 패턴과 ActionId가 같고 자리(슬롯)만 다르다:
    // 손·방향·연속기 처리는 그대로 쓰고, 점수·감점·쿨다운은 자리별로 따로 센다.
    const TCHAR* Paths[] = {
        TEXT("/Game/BossArena/Boss/AI/Actions/DA_Attack_Overhead.DA_Attack_Overhead"),
        TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.DA_Lab_Left_RightFootPlant"),
        TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Right_RightFootStep.DA_Lab_Right_RightFootStep"),
        TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Uppercut_RunIn.DA_Lab_Uppercut_RunIn"),
        TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Combo_FootStep.DA_Lab_Combo_FootStep")};
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    for (const TCHAR* Path : Paths)
    {
        UObject* Card = LoadObject<UObject>(nullptr, Path, nullptr, LOAD_NoWarn);
        if (!IsValid(Card) || !Card->IsA(CardType->PropertyClass)) continue;
        bool bPresent = false;
        for (int32 I = 0; I < Values.Num() && !bPresent; ++I) bPresent = CardType->GetObjectPropertyValue(Values.GetRawPtr(I)) == Card;
        if (!bPresent) CardType->SetObjectPropertyValue(Values.GetRawPtr(Values.AddValue()), Card);
    }
    UBossCombatIntentLibrary::EnsureActionCooldownCapacity(Boss);
    // 달려오다가 이 거리 안에 들어오면 달리기를 멈추고 다시 고른다(예전 400). 중거리 패턴이 닿는 거리에서 끊어야 달려오다 그대로 달려든다.
    SetNumber(Boss, TEXT("ApproachAttackHandoffDistance"), 560.0);
}

namespace
{
int32 FindSlotByActionId(const AActor* Boss, int32 Id)
{
    const FArrayProperty* Cards = IsValid(Boss) ? FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions")) : nullptr;
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (!CardType) return INDEX_NONE;
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    for (int32 I = 0; I < Values.Num(); ++I)
        if (static_cast<int32>(Number(CardType->GetObjectPropertyValue(Values.GetRawPtr(I)), TEXT("ActionId"), -1)) == Id) return I;
    return INDEX_NONE;
}

UObject* CardAtSlot(const AActor* Boss, int32 Slot)
{
    const FArrayProperty* Cards = IsValid(Boss) ? FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions")) : nullptr;
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (!CardType) return nullptr;
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    return Values.IsValidIndex(Slot) ? CardType->GetObjectPropertyValue(Values.GetRawPtr(Slot)) : nullptr;
}
}

// 블루프린트에 "이 자리의 공격을 지금 시작해 달라"고 요청한다. 거리·정면·쿨다운 검사는 블루프린트가 평소대로 한다.
bool UBossCombatIntentComponent::RequestSlot(int32 SlotIndex)
{
    AActor* Boss = GetOwner();
    UFunction* Request = Boss ? Boss->FindFunction(TEXT("RequestCombatAction")) : nullptr;
    if (!Request || SlotIndex == INDEX_NONE) return false;
    SetFlag(Boss, TEXT("bActionStartAllowed"), false);
    FStructOnScope Params(Request);
    for (TFieldIterator<FProperty> It(Request); It; ++It)
        if ((*It)->HasAnyPropertyFlags(CPF_Parm) && !(*It)->HasAnyPropertyFlags(CPF_ReturnParm))
            if (FIntProperty* Int = CastField<FIntProperty>(*It)) { Int->SetPropertyValue_InContainer(Params.GetStructMemory(), SlotIndex); break; }
    Boss->ProcessEvent(Request, Params.GetStructMemory());
    return Flag(Boss, TEXT("bActionStartAllowed"));
}

bool UBossCombatIntentComponent::RequestLinkSlot(int32 SlotIndex, bool bPivot)
{
    // 돌아서며 치는 공격은 정면 조건을 건너뛴다(거리와 쿨다운은 계획이 이미 확인했다).
    TGuardValue<bool> Scope(bRearResponseScope, bPivot);
    return RequestSlot(SlotIndex);
}

namespace
{
// 이 공격의 제자리 패턴 / 달려드는 패턴 카드가 있는 자리. 없으면 INDEX_NONE.
int32 FindPatternSlot(const AActor* Boss, int32 Id, bool bRunIn)
{
    const FArrayProperty* Cards = IsValid(Boss) ? FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions")) : nullptr;
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (!CardType) return INDEX_NONE;
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    for (int32 I = 0; I < Values.Num(); ++I)
    {
        const UObject* Card = CardType->GetObjectPropertyValue(Values.GetRawPtr(I));
        if (static_cast<int32>(Number(Card, TEXT("ActionId"), -1)) == Id
            && IsMidPattern(Id, static_cast<float>(Number(Card, TEXT("MinDistance")))) == bRunIn) return I;
    }
    return INDEX_NONE;
}
}

// 이어 치기: 열린 후딜에 들어온 순간, 남은 공격의 순서를 지금 상황으로 한 번 짠다. 짜지면 후딜을 끊고 첫 걸음을 요청한다.
void UBossCombatIntentComponent::UpdateChain(float Elapsed, float Remaining)
{
    AActor* Boss = GetOwner();
    if (!bLinkWanted || ChainSlot != INDEX_NONE || Remaining <= 0.f) return;
    bLinkWanted = false;                                 // 이 시점에 한 번만 판단한다
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player) || Flag(Player, TEXT("bKnockedDown")) || Number(Player, TEXT("CurrentHealth"), 1) <= 0) return;
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const float Angle = FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw, Delta.Rotation().Yaw));
    // 다음 타가 닿을 때쯤의 거리로 짠다(약 0.6초 뒤).
    const float Distance = PredictedDistance(Delta.Size2D(), PlayerSpeedAway(), .6f);
    const double Now = GetWorld()->GetTimeSeconds();
    const auto Available = [&](int32 Id, bool bRunIn)
    {
        const int32 CardSlot = FindPatternSlot(Boss, Id, bRunIn);
        const UObject* Card = CardAtSlot(Boss, CardSlot);
        return Card && Flag(Card, TEXT("bEnabled")) && IsValid(Object(Card, TEXT("Montage"))) && Now >= ArrayNumber(Boss, TEXT("CooldownUntil"), CardSlot);
    };
    const int32 Previous = StringUsed.Num() ? StringUsed.Last() : -1;
    const TArray<FStringStep> Plan = PlanAttackString(Distance, Angle, StringHitsWanted - StringUsed.Num(), Previous, StringUsed, Available,
        []() { return FMath::FRand(); });
    if (Plan.IsEmpty()) return;
    ChainSlot = FindPatternSlot(Boss, Plan[0].Id, Plan[0].bRunIn);
    if (ChainSlot == INDEX_NONE) return;
    bLinkPivot = !Plan[0].bRunIn && Angle > 40.f;
    LinkAngle = Angle;
    UKismetSystemLibrary::K2_ClearTimer(Boss, TEXT("FinishCombatAction"));
    SetText(Boss, TEXT("IntentReason"), Plan.Num() >= 2 ? TEXT("이어 치기: 두 번 더 잇는다") : TEXT("이어 치기: 한 번 더 잇는다"));
    SetText(Boss, TEXT("GoapReason"), FString::Printf(TEXT("이어 치기 계획: %d번 (%.0fcm, %.0f°)"), Plan.Num(), Distance, Angle));
    Invoke(Boss, TEXT("FinishCombatAction"));      // Ready가 되면 RecordAttackRecoveryEnd가 ChainSlot을 요청한다
}

// 공격이 끝났는데 플레이어가 등 뒤에 있으면, 뒤돌아보기만 하는 대신 돌면서 훅이나 휩쓸기를 친다.
// 뒤를 잡으면 후딜과 턴 동작 내내 때릴 수 있던 것을 막는다. 매번은 아니라서(확률, 쿨다운) 뒤잡기 자체는 여전히 보상이 있다.
void UBossCombatIntentComponent::TryRearResponse()
{
    AActor* Boss = GetOwner();
    if (!GetWorld() || !StateIs(Boss, TEXT("Boss.Combat.Ready")) || Number(Boss, TEXT("CurrentHealth")) <= 0) return;
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now < RearResponseReadyAt) return;
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player) || Number(Player, TEXT("CurrentHealth"), 1) <= 0 || Flag(Player, TEXT("bKnockedDown"))) return;
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const int32 Choice = ChooseRearResponse(FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D()),
        Delta.Size2D(), FMath::FRand(), FMath::FRand(), RearResponseChance);
    if (Choice == 0) return;
    // 훅은 왼손 자리(ActionId 0)로 요청하고 카드만 훅으로 바꾼다. 휩쓸기는 제 자리(ActionId 3)로 요청한다.
    const int32 WantedId = Choice == 1 ? 0 : 3;
    const FArrayProperty* Cards = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    UFunction* Request = Boss->FindFunction(TEXT("RequestCombatAction"));
    if (!CardType || !Request) return;
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    int32 RequestSlot = INDEX_NONE;
    for (int32 I = 0; I < Values.Num() && RequestSlot == INDEX_NONE; ++I)
        if (static_cast<int32>(Number(CardType->GetObjectPropertyValue(Values.GetRawPtr(I)), TEXT("ActionId"), -1)) == WantedId) RequestSlot = I;
    if (RequestSlot == INDEX_NONE) return;
    RearCard = Choice == 1 ? LoadObject<UObject>(nullptr, RearHookCardPath, nullptr, LOAD_NoWarn) : nullptr;
    if (Choice == 1 && !RearCard.IsValid()) return;
    SetFlag(Boss, TEXT("bActionStartAllowed"), false);
    FStructOnScope Params(Request);
    for (TFieldIterator<FProperty> It(Request); It; ++It)
        if ((*It)->HasAnyPropertyFlags(CPF_Parm) && !(*It)->HasAnyPropertyFlags(CPF_ReturnParm))
            if (FIntProperty* Int = CastField<FIntProperty>(*It)) { Int->SetPropertyValue_InContainer(Params.GetStructMemory(), RequestSlot); break; }
    {
        TGuardValue<bool> Scope(bRearResponseScope, true);
        Boss->ProcessEvent(Request, Params.GetStructMemory());
    }
    RearCard = nullptr;
    if (!Flag(Boss, TEXT("bActionStartAllowed"))) return;
    bRearResponseActive = true;
    RearResponseReadyAt = Now + RearResponseCooldown;
    // 타격 직전에 정면이 되도록 고르게 돈다. 빨리 돌아놓고 서 있는 것보다 "돌아서며 휘두르는" 동작으로 읽힌다.
    const float Angle = FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw, Delta.Rotation().Yaw));
    RearTurnRate = RearTurnSpeedFor(Angle, FirstImpactSeconds(Object(Boss, TEXT("ActiveAction"))), RearResponseTurnSpeed);
    SetText(Boss, TEXT("AttackRequestSource"), TEXT("rear"));
    SetText(Boss, TEXT("IntentReason"), Choice == 1 ? TEXT("뒤를 잡힘: 돌면서 훅") : TEXT("뒤를 잡힘: 돌면서 휩쓸기"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("rear_response"));
}

// 뒤쪽 대응은 등을 진 채 시작하므로, 예고와 준비 동작 동안 빠르게 플레이어 쪽으로 돈다. 타격이 열리면 평소 규칙으로 돌아간다.
void UBossCombatIntentComponent::UpdateRearResponse(float DeltaTime)
{
    if (!bRearResponseActive) return;
    AActor* Boss = GetOwner();
    const bool bPreparing = StateIs(Boss, TEXT("Boss.Combat.Attack.Telegraph")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Windup"));
    if (!bPreparing) { if (!StateIs(Boss, TEXT("Boss.Combat.Ready"))) bRearResponseActive = false; return; }
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player)) return;
    const FRotator Wanted(0.f, (Player->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, RearTurnRate));
}

void UBossCombatIntentComponent::RestoreTrueWeights()
{
    if (!bRestoreWeights) return;
    bRestoreWeights = false;
    AActor* Boss = GetOwner();
    const FArrayProperty* Scores = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
    const FNumericProperty* ScoreType = Scores ? CastField<FNumericProperty>(Scores->Inner) : nullptr;
    if (!ScoreType || !ScoreType->IsFloatingPoint()) return;
    FScriptArrayHelper Values(Scores, Scores->ContainerPtrToValuePtr<void>(Boss));
    if (Values.Num() != TrueWeights.Num()) return;
    for (int32 I = 0; I < Values.Num(); ++I) ScoreType->SetFloatingPointPropertyValue(Values.GetRawPtr(I), TrueWeights[I]);
}

// 빠르게 달릴 때는 Sprint, 느릴 때는 Jog. 이동 블렌드스페이스에는 Jog만 있어서, 속도가 SprintOnSpeed를 넘으면
// 전신 Sprint 몽타주를 덮어 재생하고 SprintOffSpeed 아래로 내려가면 뺀다. 재생 속도는 실제 속도에 맞춰 발이 미끄러지지 않게 한다.
void UBossCombatIntentComponent::UpdateSprint()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    UAnimInstance* Anim = Boss && Boss->GetMesh() ? Boss->GetMesh()->GetAnimInstance() : nullptr;
    if (!Anim) return;
    if (!bApproachSpeedApplied)
    {
        bApproachSpeedApplied = true;
        AddExtraCards();
        SetNumber(Boss, TEXT("ApproachRunSpeed"), ApproachSprintSpeed);
        // 블루프린트는 왼손·오른손을 이 거리(예전 500)까지만 후보로 본다. 중거리 끝에 맞춘다.
        SetNumber(Boss, TEXT("IntentSelectionMaxDistance"), MaxRunInReach);
        // 감점은 AdjustIntentCandidate가 "가장 큰 것 하나"로 다시 계산한다. 블루프린트가 곱하던 세 배수는 1로 둔다.
        SetNumber(Boss, TEXT("UtilityRepeatMultiplier"), 1.0);
        SetNumber(Boss, TEXT("RecentUseMinMultiplier"), 1.0);
        SetNumber(Boss, TEXT("PunchFamilyMinMultiplier"), 1.0);
        SprintMontage = LoadObject<UAnimMontage>(nullptr,
            TEXT("/Game/BossArena/Boss/Authoring/AM_Crunch_SprintLoop.AM_Crunch_SprintLoop"), nullptr, LOAD_NoWarn);
    }
    if (!SprintMontage) return;
    const bool bMoving = StateIs(Boss, TEXT("Boss.Combat.Ready")) || StateIs(Boss, TEXT("Boss.Combat.Position"));
    const float Speed = Boss->GetVelocity().Size2D();
    const float Rate = SprintPlayRate(Speed, SprintNaturalSpeed * Boss->GetMesh()->GetComponentScale().X);
    if (Anim->Montage_IsPlaying(SprintMontage))
    {
        if (!bMoving || Speed < SprintOffSpeed) Anim->Montage_Stop(.25f, SprintMontage);
        else Anim->Montage_SetPlayRate(SprintMontage, Rate);
    }
    else if (bMoving && Speed >= SprintOnSpeed && !Anim->GetCurrentActiveMontage())
        Anim->Montage_Play(SprintMontage, Rate);
}

// 제자리 턴: 예전에는 몸은 1초 만에 돌고 턴 동작은 2.5초 동안 재생되어, 다 돌아놓고 발만 구르며 서 있었다.
// 돌아야 할 각도에서 걸릴 시간을 정하고, 턴 동작의 재생 속도·몸의 회전 속도·"턴 중" 대기 시간을 그 시간에 함께 맞춘다.
void UBossCombatIntentComponent::UpdateTurnSync()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    UAnimInstance* Anim = Boss && Boss->GetMesh() ? Boss->GetMesh()->GetAnimInstance() : nullptr;
    if (!Anim) return;
    UAnimMontage* Active = Anim->GetCurrentActiveMontage();
    const bool bTurning = Active && Active->GetName().StartsWith(TEXT("AM_Boss_Turn"));
    if (!bTurning)
    {
        if (SyncedTurnMontage.IsValid() || SavedTurnSpeed >= 0.f)
        {
            if (SavedTurnSpeed >= 0.f) SetNumber(Boss, TEXT("TurnSpeed"), SavedTurnSpeed);
            SavedTurnSpeed = -1.f;
            SyncedTurnMontage = nullptr;
        }
        return;
    }
    if (SyncedTurnMontage.Get() == Active) return;
    SyncedTurnMontage = Active;
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player)) return;
    const float Angle = FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw,
        (Player->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw));
    const float Length = Active->GetPlayLength();
    const float Duration = TurnDuration(Angle, TurnMontageSpeed);
    Anim->Montage_SetPlayRate(Active, Length / Duration);
    if (SavedTurnSpeed < 0.f) SavedTurnSpeed = static_cast<float>(Number(Boss, TEXT("TurnSpeed"), 160.0));
    SetNumber(Boss, TEXT("TurnSpeed"), Angle / Duration);
    // 블루프린트는 "턴 동작이 끝나는 시각"까지 판단을 미룬다. 줄어든 길이만큼 그 시각을 당긴다.
    const double Until = Number(Boss, TEXT("TurnAnimationUntil"));
    if (Until > 0.0) SetNumber(Boss, TEXT("TurnAnimationUntil"), Until - (Length - Duration));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("turn_synced"));
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
    if (!Boss || !IsValid(Player) || !Action.IsValid()) { Finish(false, TEXT("대상 또는 공격이 사라짐"), false); return; }
    AAIController* Controller = Cast<AAIController>(Boss->GetController());
    if (bSideEntryActive)
    {
        // Hold the chosen world-space destination: do not chase a moving side point.
        if (FVector::Dist2D(Boss->GetActorLocation(), SideEntryGoal) > 20.f)
        {
            if (!Controller || Controller->GetMoveStatus() == EPathFollowingStatus::Idle)
                Finish(false, TEXT("측면 진입 경로에서 이동 중단"));
            return;
        }
        bSideEntryActive = false;
        if (Controller) Controller->StopMovement();
        Invoke(Boss, TEXT("RecordCombatQA"), bSideMoveIsProbe ? TEXT("intent_probe_arrived") : TEXT("intent_side_arrived"));
    }
    const FVector Delta = Player->GetActorLocation() - Boss->GetActorLocation();
    const float Distance = Delta.Size2D();
    const float Facing = FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D());
    const float Min = GoalMinDistance;
    const float MinimumDot = Number(Boss, TEXT("AttackStartMinDot"), .5);
    SetNumber(Boss, TEXT("UtilityDistance"), Distance);
    if (bPostProbeRequested)
    {
        bPostProbeRequested = false;
        FVector LeftProbe, RightProbe;
        const auto ProbeOpen = [&](float Degrees, FVector& Destination)
        {
            if (!ReachableCenter(LateralEntryGoal(Boss->GetActorLocation(), Player->GetActorLocation(), Distance, Degrees), Destination)) return false;
            const float Range = FVector::Dist2D(Destination, Player->GetActorLocation());
            return Range >= Min && Range <= GoalMaxDistance;
        };
        const float Angle = FMath::Clamp(SideEntryAngle, 5.f, 35.f);
        bool bLeftOpen = ProbeOpen(Angle, LeftProbe), bRightOpen = ProbeOpen(-Angle, RightProbe);
        // When both paths are valid, avoid a permanently preferred orbit direction.
        if (bLeftOpen && bRightOpen)
        {
            if (FMath::RandBool()) bLeftOpen = false;
            else bRightOpen = false;
        }
        const auto Probe = UBossPositionPlanner::PlanAttackPosition(Distance, Facing, Min, GoalMaxDistance, MinimumDot,
            false, false, bLeftOpen, bRightOpen, true, SideEntrySpeed);
        if (Probe.bFound && (Probe.FirstAction == EBossPositionAction::OrbitLeft || Probe.FirstAction == EBossPositionAction::OrbitRight))
        {
            const bool bLeft = Probe.FirstAction == EBossPositionAction::OrbitLeft;
            SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Probe.FirstAction));
            StartSideMove(bLeft ? LeftProbe : RightProbe, bLeft, true);
            return;
        }
        // A blocked optional probe must not discard an otherwise valid attack.
        Publish(TEXT("position"), TEXT("옆걸음 여유가 없어 선택한 공격을 바로 준비"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_probe_skipped"));
    }
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
    FVector LeftEntry, RightEntry;
    bool bLeftEntryOpen = false, bRightEntryOpen = false;
    if (bNeedTranslation && !bPathOpen && !bSideEntryUsed)
    {
        const auto SideOpen = [&](float Degrees, FVector& Destination)
        {
            if (!ReachableCenter(LateralEntryGoal(Boss->GetActorLocation(), Player->GetActorLocation(), DesiredRange, Degrees), Destination)) return false;
            const float Range = FVector::Dist2D(Destination, Player->GetActorLocation());
            return Range >= Min && Range <= GoalMaxDistance;
        };
        const float Angle = FMath::Clamp(SideEntryAngle, 5.f, 35.f);
        // Facing toward the player, positive rotation of the outward radius is left.
        bLeftEntryOpen = SideOpen(Angle, LeftEntry);
        bRightEntryOpen = SideOpen(-Angle, RightEntry);
    }
    const auto Plan = UBossPositionPlanner::PlanAttackEntry(Distance, Facing, Min, GoalMaxDistance, MinimumDot,
        bPathOpen && Distance > GoalMaxDistance, bPathOpen && Distance < Min, bLeftEntryOpen, bRightEntryOpen, RunSpeed);
    if (!Plan.bFound) { Finish(false, TEXT("공격할 자리로 가는 길이 막힘")); return; }
    SetNumber(Boss, TEXT("GoapFirstAction"), static_cast<int32>(Plan.FirstAction));
    if (Plan.FirstAction == EBossPositionAction::FaceTarget)
    {
        if (Controller) Controller->StopMovement();
        Publish(TEXT("face"), TEXT("선택한 공격을 유지하며 몸 돌리기"));
    }
    else if (Plan.FirstAction == EBossPositionAction::DirectApproach || Plan.FirstAction == EBossPositionAction::StepBack)
    {
        if (!Controller) { Finish(false, TEXT("이동 제어기가 없음")); return; }
        // 한두 걸음이면 되는 거리는 달리지 않고 걸어서 맞춘다. 멀 때만 달린다.
        const bool bShortEntry = Distance - GoalMaxDistance < 160.f
            && !IsRetreating(static_cast<float>(FVector::DotProduct(Player->GetVelocity(), Delta.GetSafeNormal2D())));
        Boss->GetCharacterMovement()->MaxWalkSpeed = Plan.FirstAction == EBossPositionAction::StepBack ? 210.f : (bShortEntry ? 240.f : RunSpeed);
        const FVector FloorDestination = Reachable - FVector(0.f, 0.f, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
        const auto Request = Controller->MoveToLocation(FloorDestination, 10.f, false, true, true, false, nullptr, false);
        if (Request == EPathFollowingRequestResult::Failed) { Finish(false, TEXT("이동 요청 실패")); return; }
        Publish(TEXT("enter"), Plan.FirstAction == EBossPositionAction::StepBack
            ? TEXT("너무 가까워 한 걸음 거리 확보") : TEXT("선택한 공격을 위해 짧게 진입"));
    }
    else if (Plan.FirstAction == EBossPositionAction::OrbitLeft || Plan.FirstAction == EBossPositionAction::OrbitRight)
    {
        const bool bLeft = Plan.FirstAction == EBossPositionAction::OrbitLeft;
        StartSideMove(bLeft ? LeftEntry : RightEntry, bLeft, false);
    }
}

void UBossCombatIntentComponent::StartSideMove(const FVector& Destination, bool bLeft, bool bProbe)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    AAIController* Controller = Boss ? Cast<AAIController>(Boss->GetController()) : nullptr;
    if (!Controller) { Finish(false, TEXT("측면 이동 제어기가 없음")); return; }
    SideEntryGoal = Destination;
    Boss->GetCharacterMovement()->MaxWalkSpeed = FMath::Max(1.f, SideEntrySpeed);
    const FVector FloorDestination = SideEntryGoal - FVector(0.f, 0.f, Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    const auto Request = Controller->MoveToLocation(FloorDestination, 10.f, false, true, true, false, nullptr, false);
    if (Request == EPathFollowingRequestResult::Failed) { Finish(false, TEXT("측면 진입 이동 요청 실패")); return; }
    bSideEntryActive = bSideEntryUsed = true;
    bSideMoveIsProbe = bProbe;
    if (bProbe) SetNumber(Boss, TEXT("GoapProbeCooldownUntil"), GetWorld()->GetTimeSeconds() + 4.0);
    Publish(bProbe ? TEXT("probe") : TEXT("side_entry"), bProbe
        ? (bLeft ? TEXT("다음 공격 유지: 왼쪽으로 짧게 자리를 바꿈") : TEXT("다음 공격 유지: 오른쪽으로 짧게 자리를 바꿈"))
        : (bLeft ? TEXT("정면 길이 막혀 왼쪽 공격 자리로 이동") : TEXT("정면 길이 막혀 오른쪽 공격 자리로 이동")));
    Invoke(Boss, TEXT("RecordCombatQA"), bProbe ? TEXT("intent_probe_begin") : TEXT("intent_side_begin"));
}

void UBossCombatIntentComponent::Finish(bool bAttack, const FString& Reason, bool bCountFailure)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    if (!Boss) { bActive = false; return; }
    bActive = false;
    bSideEntryActive = false;
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
            // 치러 걸어 들어왔으면 그것이 이미 발놀림이다.
            if (FVector::Dist2D(Boss->GetActorLocation(), LastRecoveryLocation) > 120.f) AttackStreak = 0;
            ConsecutiveEntryFailures = 0;
            LastEntryFailureAt = -1.0;
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_arrived"));
            return;
        }
        Publish(TEXT("cancelled"), TEXT("도착 후 공격 시작 검사에서 거부됨"));
    }
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_aborted"));
    // Death, knockdown and externally changed states are interruptions, not bad entries.
    if (!bCountFailure || !StateIs(Boss, TEXT("Boss.Combat.Ready"))
        || Number(Boss, TEXT("CurrentHealth")) <= 0 || !Target.IsValid()
        || Number(Target.Get(), TEXT("CurrentHealth")) <= 0 || Flag(Target.Get(), TEXT("bKnockedDown")))
    {
        ConsecutiveEntryFailures = 0;
        LastEntryFailureAt = -1.0;
        return;
    }
    const double Now = GetWorld()->GetTimeSeconds();
    FailedUntilBySlot.Add(Slot, Now + 3.0);
    if (!RecordEntryFailure(ConsecutiveEntryFailures, LastEntryFailureAt, Now, FailureWindow)) return;
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Observe"),
        TEXT("연속 진입 실패: 추격을 끊고 상황 관찰"))) return;
    bReassessing = true;
    ReassessUntil = Now + FMath::Max(.1f, ReassessDuration);
    SetFlag(Boss, TEXT("bCombatApproachActive"), false);
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    Publish(TEXT("reassess"), TEXT("진입 2회 실패: 잠깐 멈춰 거리를 살핀 뒤 다시 선택"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_reassess_begin"));
}

void UBossCombatIntentComponent::TickReassessment(float DeltaTime)
{
    AActor* Boss = GetOwner();
    const bool bOwnsState = StateIs(Boss, TEXT("Boss.Combat.Observe"));
    const bool bTargetAvailable = Target.IsValid() && Number(Target.Get(), TEXT("CurrentHealth")) > 0
        && !Flag(Target.Get(), TEXT("bKnockedDown"));
    if (!bOwnsState || Number(Boss, TEXT("CurrentHealth")) <= 0 || !bTargetAvailable)
    {
        bReassessing = false;
        if (bOwnsState && Number(Boss, TEXT("CurrentHealth")) > 0)
            TransitionState(Boss, TEXT("Boss.Combat.Observe"), TEXT("Boss.Combat.Ready"), TEXT("대상 변경: 관찰 종료"));
        Publish(TEXT("cancelled"), TEXT("상태 또는 대상 변경으로 관찰 중단"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_reassess_cancelled"));
        return;
    }
    const FRotator Wanted(0.f, (Target->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, TurnSpeed * .5f));
    if (GetWorld()->GetTimeSeconds() < ReassessUntil) return;
    bReassessing = false;
    const bool bReady = TransitionState(Boss, TEXT("Boss.Combat.Observe"), TEXT("Boss.Combat.Ready"), TEXT("관찰 종료: 현재 상황으로 새 행동 선택"));
    Publish(bReady ? TEXT("ready") : TEXT("cancelled"), bReady
        ? TEXT("짧은 관찰 완료: 이전 공격을 강제하지 않고 다시 판단") : TEXT("관찰 후 대기 복귀 거부됨"));
    Invoke(Boss, TEXT("RecordCombatQA"), bReady ? TEXT("intent_reassess_end") : TEXT("intent_reassess_cancelled"));
}

namespace
{
// 전진이 끝났을 때 보스와 목표 사이에 남길 거리(중심 간)의 기본값. 애니메이션의 TravelStop 커브가 있으면 그 값을 쓴다
// (타마다 다르다: 먼저 치는 타가 너무 붙으면 다음 타가 디딜 자리가 없다).
constexpr float TravelStopDistance = 210.f;

// 가까이서 시작했을 때는 걸음을 줄이는 대신 더 붙는다. 걸음 애니메이션의 보폭은 그대로인데 몸만 덜 가면 발이 미끄러지기 때문이다.
// 전진량을 다 써도 MinStop보다 붙지 않으면 다 쓰고, 그러지 못할 때만 MinStop에서 멈추도록 줄인다.
constexpr float MinTravelStop = 190.f;         // 몸이 닿는 거리(약 172cm) 바로 바깥
float AdaptiveStop(float Distance, float AuthoredTravel, float AuthoredStop, float MinStop = MinTravelStop)
{
    return FMath::Min(AuthoredStop, FMath::Max(MinStop, Distance - AuthoredTravel));
}

// 한 전진 구간에서 애니메이션이 가진 전진량 중 실제로 쓸 비율.
float TravelScale(float Distance, float AuthoredTravel, float StopDistance = TravelStopDistance)
{
    if (!FMath::IsFinite(Distance) || !FMath::IsFinite(AuthoredTravel) || AuthoredTravel <= 1.f) return 1.f;
    return FMath::Clamp((Distance - StopDistance) / AuthoredTravel, 0.f, 1.f);
}
}

// 중거리용 전진 애니메이션은 가장 먼 거리(510cm)에 맞춰 만들어져 있다. 더 가까이서 시작하면 그만큼만 나가도록,
// 몸이 나가기 시작하는 순간 "이번 구간의 전진량"과 "지금 필요한 거리"를 비교해 비율을 한 번 정한다.
// 구간 도중에는 바꾸지 않으므로 발걸음이 고르게 줄고, 그 사이 플레이어가 물러나면 헛치게 된다.
void UBossCombatIntentComponent::UpdateTravelScale()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    USkeletalMeshComponent* Mesh = Boss ? Boss->GetMesh() : nullptr;
    UAnimInstance* Anim = Mesh ? Mesh->GetAnimInstance() : nullptr;
    const UAnimMontage* Montage = Anim ? Anim->GetCurrentActiveMontage() : nullptr;
    const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!Montage || !Player || !Montage->GetName().Contains(TEXT("RunIn")))
    {
        if (Boss && TravelMontage.IsValid()) Boss->SetAnimRootMotionTranslationScale(1.f);
        TravelMontage = nullptr;
        TravelBurstEnd = -1.f;
        return;
    }
    const float Now = Anim->Montage_GetPosition(Montage);
    if (TravelMontage.Get() != Montage || Now < TravelBurstEnd - 1.f) { TravelMontage = Montage; TravelBurstEnd = -1.f; }
    if (Now < TravelBurstEnd) return;
    const float Step = 1.f / 30.f, Length = Montage->GetPlayLength();
    const FAnimExtractContext Context(0.0, true);
    const auto Moves = [&](float Time)
    {
        return Time + Step <= Length
            && Montage->ExtractRootMotionFromTrackRange(Time, Time + Step, Context).GetTranslation().Size2D() >= .05f;
    };
    if (!Moves(Now)) return;
    float End = Now;
    while (Moves(End)) End += Step;
    const float Authored = Montage->ExtractRootMotionFromTrackRange(Now, End, Context).GetTranslation().Size2D()
        * Mesh->GetComponentScale().X;
    float Stop = TravelStopDistance;
    if (Montage->SlotAnimTracks.Num() && Montage->SlotAnimTracks[0].AnimTrack.AnimSegments.Num())
    {
        const UAnimSequenceBase* Clip = Montage->SlotAnimTracks[0].AnimTrack.AnimSegments[0].GetAnimReference();
        const float Authoring = Clip ? Clip->EvaluateCurveData(TEXT("TravelStop"), FAnimExtractContext(static_cast<double>(Now))) : 0.f;
        if (Authoring > 1.f) Stop = Authoring;
    }
    // 달려드는 거리는 "걸음이 끝날 때 플레이어가 있을 자리"에 맞춘다. 여전히 걸음이 시작될 때 한 번만 정한다.
    const bool bLabMap = GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"));
    const float Raw = FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation());
    const float Distance = bLabMap ? Raw : PredictedDistance(Raw, PlayerSpeedAway(), (End - Now) / FMath::Max(.1f, Anim->Montage_GetPlayRate(Montage)));
    // 한 번 치는 공격은 걸음을 다 쓰는 쪽으로 멈출 거리를 당긴다. 연속기는 다음 타가 디딜 자리를 남겨야 해서 정해둔 거리를 지킨다.
    if (Montage->GetName().Contains(TEXT("JabJabHook"))) Stop = ComboStageStops[ComboStageAt(Now)];
    else Stop = AdaptiveStop(Distance, Authored, Stop);
    Boss->SetAnimRootMotionTranslationScale(TravelScale(Distance, Authored, Stop));
    TravelBurstEnd = End;
}

namespace
{
// ---- 연기 -------------------------------------------------------------------------------------------------------
// 시선이 플레이어를 따라가도 되는 정도(0..1). 공격을 준비하거나 치는 동안은 0: 자세가 바뀌면 예고 동작과 타격 위치가 달라진다.
// 후딜에서는 발과 몸통의 방향은 그대로 두고(반격 시간), 조금 지나서부터 상체와 머리만 따라간다.
float LookWeight(bool bAttacking, bool bRecovery, float RecoveryFraction, float RecoveryLookStart, bool bTurning, bool bAlive)
{
    if (!bAlive || bAttacking || bTurning) return 0.f;
    if (bRecovery) return RecoveryFraction >= RecoveryLookStart ? 1.f : 0.f;
    return 1.f;
}

// 고개를 돌릴 각도. 플레이어가 등 뒤(120도 넘게)에 있으면 억지로 돌리지 않고 정면을 본다.
float LookTarget(float AngleToPlayer, float MaxYaw, float Weight)
{
    if (!FMath::IsFinite(AngleToPlayer) || FMath::Abs(AngleToPlayer) > 120.f) return 0.f;
    return FMath::Clamp(AngleToPlayer, -MaxYaw, MaxYaw) * FMath::Clamp(Weight, 0.f, 1.f);
}

// 움찔: 임계 감쇠 스프링. 한 번 밀리고 흔들림 없이 돌아온다.
void StepFlinch(FVector& Offset, FVector& Velocity, float DeltaTime, float Stiffness = 300.f)
{
    const float Damping = 2.f * FMath::Sqrt(Stiffness);
    float Remaining = FMath::Clamp(DeltaTime, 0.f, .1f);
    while (Remaining > 0.f)
    {
        const float Step = FMath::Min(Remaining, 1.f / 120.f);
        Velocity += (-Stiffness * Offset - Damping * Velocity) * Step;
        Offset += Velocity * Step;
        Remaining -= Step;
    }
}

// 0 = 없음, 1 = 멀리 달아난 플레이어에게 도발, 2 = 쓰러뜨린 플레이어를 내려다보며 웃기.
int32 ChoosePerformance(float Distance, bool bPlayerDown, bool bDownAlreadyTaunted, bool bTauntReady, float TauntDistance)
{
    if (!FMath::IsFinite(Distance)) return 0;
    if (bPlayerDown) return !bDownAlreadyTaunted && Distance < 700.f ? 2 : 0;
    return bTauntReady && Distance >= TauntDistance && Distance < 2500.f ? 1 : 0;
}

const TCHAR* TauntClip = TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Emote_RaisedFist.Emote_RaisedFist");
const TCHAR* LaughClip = TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Emote_Laugh.Emote_Laugh");
const TCHAR* IdleVariationClip = TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/Idle_Combat_Var1.Idle_Combat_Var1");
constexpr float BowStiffness = 90.f;            // 헛침의 쏠림: 움찔(300)보다 느리게 돌아온다
// 쏠림이 가장 클 때의 각도가 PeakDegrees가 되는 처음 속도(임계 감쇠: 최대 변위 = v / (e·ω)).
float BowKick(float PeakDegrees) { return PeakDegrees * 2.71828f * FMath::Sqrt(BowStiffness); }
const FName ActingSlot(TEXT("UpperBody"));      // 이 애니메이션 그래프의 하나뿐인 슬롯. 서 있을 때는 전신에 적용된다
}

// 준비 동작 동안의 제자리 회전을 제한한다. 전에는 발을 둔 채 몸만 플레이어를 따라 끝까지 돌아서, 미끄러지듯 도는 것으로 보였다.
// 공격이 시작된 방향에서 WindupTurnLimit도까지만 따라가고, 넘으면 방향을 고정한다. 돌아서며 치는 공격(뒤쪽 대응, 이어 치기의 회전)은 제외한다.
void UBossCombatIntentComponent::UpdateWindupTurn()
{
    AActor* Boss = GetOwner();
    const bool bPreparing = StateIs(Boss, TEXT("Boss.Combat.Attack.Telegraph")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Windup"));
    if (!bPreparing || bRearResponseActive || WindupTurnLimit <= 0.f || (GetWorld() && GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"))))
    { bWindupTracked = false; return; }
    const float Yaw = Boss->GetActorRotation().Yaw;
    if (!bWindupTracked) { bWindupTracked = true; WindupStartYaw = Yaw; return; }
    if (FMath::Abs(FMath::FindDeltaAngleDegrees(WindupStartYaw, Yaw)) >= WindupTurnLimit && Flag(Boss, TEXT("bCanTurn")))
    {
        SetFlag(Boss, TEXT("bCanTurn"), false);
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("windup_turn_locked"));
    }
}

// 이번 공격이 닿았는지 본다: 공격하는 동안 플레이어의 체력이 줄었거나(맞음) 가드 압박이 올랐으면(막힘) 닿은 것이다.
void UBossCombatIntentComponent::UpdateWhiff()
{
    AActor* Boss = GetOwner();
    const AActor* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player)) return;
    const bool bAttacking = StateIs(Boss, TEXT("Boss.Combat.Attack.Telegraph")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Windup"))
        || StateIs(Boss, TEXT("Boss.Combat.Attack.Active")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Link"));
    const double Health = Number(Player, TEXT("CurrentHealth")), Pressure = Number(Boss, TEXT("GuardPressure"));
    const double Dodges = Number(Boss, TEXT("RecentDodgeCount"));
    if (bAttacking && !bWasAttacking)
    {
        bAttackConnected = bAttackHit = bDodgedThisAttack = false;
        const int32 Id = static_cast<int32>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("ActionId"), -1));
        if (ChainDepth == 0)
        {
            // 새 몰아치기의 첫 공격: 이번에 몇 번 칠지 정한다.
            StringUsed.Reset();
            const bool bPhaseTwo = Flag(Boss, TEXT("bPhaseTwo"));
            const bool bLab = GetWorld() && GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"));
            StringHitsWanted = bLab ? 1 : ChooseStringLength(Id, FMath::FRand(), StringTwoShare,
                (bPhaseTwo ? PhaseTwoStringThreeShare : StringThreeShare) + (Dodges >= 2.0 ? DodgeStringBonus : 0.f));
        }
        StringUsed.Add(Id);
    }
    if (Dodges > DodgeCountSeen + .5 && (bAttacking || StateIs(Boss, TEXT("Boss.Combat.Attack.Recovery")))) bDodgedThisAttack = true;
    DodgeCountSeen = Dodges;
    if ((bAttacking || StateIs(Boss, TEXT("Boss.Combat.Attack.Recovery"))) && WhiffPlayerHealth >= 0.0)
    {
        if (Pressure > WhiffPressure + .01) bAttackConnected = true;                              // 막혔다
        else if (Health < WhiffPlayerHealth - .01) bAttackConnected = bAttackHit = true;          // 맞혔다
    }
    bWasAttacking = bAttacking;
    WhiffPlayerHealth = Health;
    WhiffPressure = Pressure;
}

// 시선: 애니메이션 그래프의 조준 오프셋은 "조종 방향 - 몸 방향"을 입력으로 쓴다. 그 조종 방향을 플레이어 쪽으로 돌려서
// 상체와 머리가 플레이어를 따라가게 한다. 몸(캡슐)은 돌리지 않는다.
void UBossCombatIntentComponent::UpdateLook(float DeltaTime)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    AAIController* Controller = Boss ? Cast<AAIController>(Boss->GetController()) : nullptr;
    if (!Controller) return;
    if (!bLookConfigured)
    {
        // 기본값은 매 프레임 조종 방향을 몸 방향으로 되돌린다. 끈다.
        bLookConfigured = true;
        if (FBoolProperty* FollowPawn = FindFProperty<FBoolProperty>(AAIController::StaticClass(), TEXT("bSetControlRotationFromPawnOrientation")))
            FollowPawn->SetPropertyValue_InContainer(Controller, false);
        // AI 컨트롤러는 매 프레임 조종 방향의 상하 각도를 0으로 되돌린다. 그 뒤, 애니메이션이 읽기 전에 이 컴포넌트가 돌도록 순서를 정한다.
        // (이 순서가 없으면 좌우 시선만 보이고 상체의 숙임과 숨 고르기는 화면에 나오지 않는다.)
        SetTickGroup(TG_PrePhysics);
        AddTickPrerequisiteActor(Controller);
        if (Boss->GetMesh()) Boss->GetMesh()->AddTickPrerequisiteComponent(this);
    }
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    const float BodyYaw = Boss->GetActorRotation().Yaw;
    float WantedYaw = 0.f, WantedBreath = 0.f, Speed = LookSpeed;
    if (IsValid(Player))
    {
        const bool bRecovery = StateIs(Boss, TEXT("Boss.Combat.Attack.Recovery"));
        const bool bAttacking = StateIs(Boss, TEXT("Boss.Combat.Attack.Telegraph")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Windup"))
            || StateIs(Boss, TEXT("Boss.Combat.Attack.Active")) || StateIs(Boss, TEXT("Boss.Combat.Attack.Link")) || StateIs(Boss, TEXT("Boss.Combat.Intro"));
        float Fraction = 0.f;
        if (bRecovery && RecoveryStartedAt >= 0.0)
        {
            const float Elapsed = static_cast<float>(GetWorld()->GetTimeSeconds() - RecoveryStartedAt);
            const float Remaining = UKismetSystemLibrary::K2_GetTimerRemainingTime(Boss, TEXT("FinishCombatAction"));
            Fraction = Elapsed / FMath::Max(.01f, Elapsed + FMath::Max(0.f, Remaining));
        }
        const UAnimInstance* Anim = Boss->GetMesh() ? Boss->GetMesh()->GetAnimInstance() : nullptr;
        const UAnimMontage* Active = Anim ? Anim->GetCurrentActiveMontage() : nullptr;
        const bool bTurning = Active && Active->GetName().StartsWith(TEXT("AM_Boss_Turn"));
        const float Angle = FMath::FindDeltaAngleDegrees(BodyYaw, (Player->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw);
        // 헛친 뒤에는 기다리지 않고 바로, 더 빨리 플레이어를 찾는다.
        WantedYaw = LookTarget(Angle, LookMaxYaw, LookWeight(bAttacking, bRecovery, Fraction, bWhiffed ? 0.f : RecoveryLookStart, bTurning || bPerforming,
            Number(Boss, TEXT("CurrentHealth")) > 0));
        // 숨 고르기: 후딜 동안 상체가 천천히 오르내린다. 후딜이 시작되고 0.3초에 걸쳐 커진다.
        if (bRecovery && RecoveryStartedAt >= 0.0 && Number(Boss, TEXT("CurrentHealth")) > 0)
        {
            const float Elapsed = static_cast<float>(GetWorld()->GetTimeSeconds() - RecoveryStartedAt);
            WantedBreath = -BreathPitch * FMath::Min(1.f, Elapsed / .3f) * FMath::Sin(2.f * PI * BreathRate * Elapsed);
        }
        if (bRecovery && bWhiffed) Speed *= WhiffLookSpeedScale;
    }
    LookYaw = FMath::FInterpTo(LookYaw, WantedYaw, DeltaTime, Speed);
    BreathNow = FMath::FInterpTo(BreathNow, WantedBreath, DeltaTime, 10.f);
    // 헛침의 쏠림: 느린 임계 감쇠 스프링(한 번 숙였다가 흔들림 없이 돌아온다).
    FVector Bow(BowPitch, 0.f, 0.f), BowSpeed(BowVelocity, 0.f, 0.f);
    StepFlinch(Bow, BowSpeed, DeltaTime, BowStiffness);
    BowPitch = static_cast<float>(Bow.X); BowVelocity = static_cast<float>(BowSpeed.X);
    Controller->SetControlRotation(FRotator(BowPitch + BreathNow, BodyYaw + LookYaw, 0.f));
}

// 움찔: 맞으면 몸(메시)이 맞은 반대쪽으로 살짝 밀렸다 돌아온다. 애니메이션과 판단은 건드리지 않아서 공격은 끊기지 않는다.
void UBossCombatIntentComponent::UpdateFlinch(float DeltaTime)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    USkeletalMeshComponent* Mesh = Boss ? Boss->GetMesh() : nullptr;
    if (!Mesh) return;
    if (!bMeshBaseSaved) { bMeshBaseSaved = true; MeshBaseLocation = Mesh->GetRelativeLocation(); }
    const double Health = Number(Boss, TEXT("CurrentHealth"));
    if (LastHealth >= 0.0 && Health < LastHealth - .5 && Health > 0.0)
    {
        const AActor* Player = UGameplayStatics::GetPlayerPawn(this, 0);
        const FVector Away = IsValid(Player) ? (Boss->GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D() : -Boss->GetActorForwardVector();
        FlinchVelocity += Away * FlinchImpulse * (Flag(Boss, TEXT("bPhaseTwo")) ? PhaseTwoFlinchScale : 1.f);
        HitTimes.Add(GetWorld()->GetTimeSeconds());
        if (HitTimes.Num() > 16) HitTimes.RemoveAt(0);
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("flinch"));
    }
    LastHealth = Health;
    if (FlinchOffset.IsNearlyZero(.02f) && FlinchVelocity.IsNearlyZero(.5f))
    {
        if (!FlinchOffset.IsZero()) { FlinchOffset = FlinchVelocity = FVector::ZeroVector; Mesh->SetRelativeLocation(MeshBaseLocation); }
        return;
    }
    StepFlinch(FlinchOffset, FlinchVelocity, DeltaTime);
    Mesh->SetRelativeLocation(MeshBaseLocation + Boss->GetActorTransform().InverseTransformVectorNoScale(FlinchOffset));
}

namespace
{
// ---- 저스트 가드 --------------------------------------------------------------------------------------------------
// 맞기 직전에 올린 가드는 피해를 받지 않는다. 보통 가드는 피해의 20%를 받는다.
// 처음에는 "막은 직후 첫 타 2배(저스트 가드 3배)"와 스태미나 회복도 넣었는데, 디자이너 판단으로 뺐다.
bool IsJustGuard(double GuardStartedAt, double BlockedAt, float Window)
{
    return GuardStartedAt > 0.0 && BlockedAt >= GuardStartedAt && BlockedAt - GuardStartedAt <= Window;
}

}

void UBossCombatIntentComponent::ShowNotice(const FString& Message)
{
    BarNotice = Message;
    BarNoticeUntil = GetWorld() ? GetWorld()->GetTimeSeconds() + 1.4 : -1.0;
}

// 플레이어가 보스의 공격을 막았는지 본다. 블루프린트는 막힐 때마다 보스의 "가드 압박" 값을 올린다(가드 브레이크용): 그 값이 오른 순간이 막은 순간이다.
void UBossCombatIntentComponent::UpdateGuardReward()
{
    AActor* Boss = GetOwner();
    AActor* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player) || !GetWorld()) return;
    const double Pressure = Number(Boss, TEXT("GuardPressure"));
    const double Health = Number(Player, TEXT("CurrentHealth"));
    if (LastGuardPressure >= 0.0 && Pressure > LastGuardPressure + .01 && Health > 0.0)
    {
        const bool bJust = IsJustGuard(Number(Player, TEXT("GuardStartTime"), -1.0), UKismetSystemLibrary::GetGameTimeInSeconds(Player), JustGuardWindow);
        if (bJust)
        {
            // 저스트 가드: 가드 위로 새는 피해를 돌려준다.
            if (LastPlayerHealth > Health) SetNumber(Player, TEXT("CurrentHealth"), LastPlayerHealth);
            if (UParticleSystem* Spark = Cast<UParticleSystem>(Object(Player, TEXT("HitImpactFX"))))
                UGameplayStatics::SpawnEmitterAtLocation(this, Spark, Player->GetActorLocation() + Player->GetActorForwardVector() * 45.f + FVector(0, 0, 30.f),
                    Player->GetActorRotation(), FVector(1.6f), true);
            ShowNotice(TEXT("저스트 가드"));
        }
        Invoke(Boss, TEXT("RecordCombatQA"), bJust ? TEXT("just_guard") : TEXT("guard_block"));
    }
    LastGuardPressure = Pressure;
    LastPlayerHealth = Number(Player, TEXT("CurrentHealth"));
}

int32 UBossCombatIntentComponent::HitsTakenWithin(float Seconds) const
{
    const double Since = (GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0) - Seconds;
    int32 Count = 0;
    for (const double Time : HitTimes) if (Time >= Since) ++Count;
    return Count;
}

namespace
{
// 체력 바의 노란 띠: 맞은 뒤 Hold초 동안 그대로 있다가 체력 쪽으로 내려온다. 방금 얼마나 깎았는지 보인다.
float TrailToward(float Trail, float Health, float SecondsSinceHit, float DeltaTime, float Hold = .6f, float Speed = .6f)
{
    if (Trail <= Health) return Health;
    return SecondsSinceHit < Hold ? Trail : FMath::Max(Health, Trail - Speed * DeltaTime);
}
}

// 보스 체력 바(화면 아래 가운데). 실전 맵에서만 보인다.
void UBossCombatIntentComponent::UpdateHealthBar(float DeltaTime)
{
    AActor* Boss = GetOwner();
    UGameViewportClient* Viewport = GetWorld() && GetWorld()->IsGameWorld() ? GetWorld()->GetGameViewport() : nullptr;
    if (!Viewport) return;
    if (GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"))) return;
    if (!HealthBar.IsValid())
    {
        HealthBar = SNew(SBossHealthBar);
        HealthBar->Name = FText::FromString(TEXT("크런치"));
        Viewport->AddViewportWidgetContent(HealthBar.ToSharedRef(), 5);
    }
    const double Now = GetWorld()->GetTimeSeconds();
    const double Max = FMath::Max(1.0, Number(Boss, TEXT("MaxHealth"), 1.0));
    const double Health = FMath::Clamp(Number(Boss, TEXT("CurrentHealth")), 0.0, Max);
    if (BarHealth < 0.0) { BarHealth = Health; BarTrail = static_cast<float>(Health / Max); }
    if (Health < BarHealth - .5)
    {
        // 이어서 때리면 숫자가 쌓이고, 2초 쉬면 새로 센다.
        BarDamage = (Now - BarLastHitAt < 2.0 ? BarDamage : 0.f) + static_cast<float>(BarHealth - Health);
        BarLastHitAt = Now;
    }
    else if (Health > BarHealth) BarTrail = static_cast<float>(Health / Max);
    BarHealth = Health;
    const float Fraction = static_cast<float>(Health / Max);
    BarTrail = TrailToward(BarTrail, Fraction, static_cast<float>(Now - BarLastHitAt), DeltaTime);
    if (Health <= 0.0 && BarDeadAt < 0.0) BarDeadAt = Now;
    const bool bShow = !StateIs(Boss, TEXT("Boss.Combat.Intro")) && (BarDeadAt < 0.0 || Now - BarDeadAt < 2.5) && FirstDecisionAt >= 0.0;
    BarOpacity = FMath::FInterpConstantTo(BarOpacity, bShow ? 1.f : 0.f, DeltaTime, 2.f);
    HealthBar->Health = Fraction;
    HealthBar->Trail = BarTrail;
    HealthBar->RecentDamage = Now - BarLastHitAt < 2.5 ? BarDamage : 0.f;
    HealthBar->Opacity = BarOpacity;
    HealthBar->Notice = FText::FromString(BarNotice);
    HealthBar->NoticeOpacity = static_cast<float>(FMath::Clamp((BarNoticeUntil - Now) / .35, 0.0, 1.0));
}

// 도발과 대기 변주. 도발은 Position 상태에서 한다(판단을 잠깐 멈추고, 끝나면 Ready로 돌아가 평소처럼 고른다).
bool UBossCombatIntentComponent::UpdatePerformance(float DeltaTime)
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    UAnimInstance* Anim = Boss && Boss->GetMesh() ? Boss->GetMesh()->GetAnimInstance() : nullptr;
    if (!Anim || !GetWorld() || GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"))) return false;
    const double Now = GetWorld()->GetTimeSeconds();
    AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    const bool bAlive = Number(Boss, TEXT("CurrentHealth")) > 0;
    if (bPerforming)
    {
        const bool bStill = StateIs(Boss, TEXT("Boss.Combat.Position"));
        if (bStill && bAlive && IsValid(Player) && Now < PerformUntil)
        {
            const FRotator Wanted(0.f, (Player->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
            Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, TurnSpeed));
            return true;
        }
        bPerforming = false;
        if (PerformMontage && Anim->Montage_IsPlaying(PerformMontage)) Anim->Montage_Stop(.25f, PerformMontage);
        PerformMontage = nullptr;
        SetFlag(Boss, TEXT("bAttackIntentActive"), false);
        if (bStill) TransitionState(Boss, TEXT("Boss.Combat.Position"), TEXT("Boss.Combat.Ready"), TEXT("도발 끝: 평소처럼 고른다"));
        SetText(Boss, TEXT("IntentPhase"), TEXT("ready"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("taunt_end"));
        return false;
    }
    const bool bReady = StateIs(Boss, TEXT("Boss.Combat.Ready"));
    const bool bWaiting = bReady || StateIs(Boss, TEXT("Boss.Combat.Observe"));
    // 대기 변주: 서서 기다리는 시간이 길어지면(플레이어가 쓰러져 있을 때 등) 같은 대기 동작만 반복하지 않는다.
    const bool bIdle = bWaiting && bAlive && Boss->GetVelocity().Size2D() < 5.f;
    if (IdleVariationMontage && Anim->Montage_IsPlaying(IdleVariationMontage))
    {
        const float Angle = IsValid(Player) ? FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw,
            (Player->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw)) : 0.f;
        if (!bIdle || Angle > 35.f) Anim->Montage_Stop(.2f, IdleVariationMontage);      // 움직이거나 돌아야 하면 바로 비킨다
    }
    if (!bIdle || Anim->GetCurrentActiveMontage()) IdleSince = -1.0;
    else if (IdleSince < 0.0) IdleSince = Now;
    if (!bReady || !bAlive || bActive || bReassessing || bFootworkActive || !IsValid(Player) || Number(Player, TEXT("CurrentHealth"), 1) <= 0) return false;
    if (Flag(Boss, TEXT("bFirstSlamPending")) && Flag(Boss, TEXT("bPhaseTwo"))) return false;
    const float Distance = FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation());
    const bool bDown = Flag(Player, TEXT("bKnockedDown"));
    if (!bDown) bKnockdownTaunted = false;
    // 웃기는 쓰러질 때마다 하면 전투가 늘어진다: 한 번 웃으면 20초는 그냥 기다린다.
    const int32 Choice = ChoosePerformance(Distance, bDown, bKnockdownTaunted || Now < NextLaughAt, Now >= NextTauntAt, TauntDistance);
    if (Choice == 0)
    {
        if (IdleSince >= 0.0 && Now - IdleSince >= 1.5 && Now >= NextIdleVariationAt)
            if (UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr, IdleVariationClip, nullptr, LOAD_NoWarn))
            {
                NextIdleVariationAt = Now + 7.0;
                IdleVariationMontage = Anim->PlaySlotAnimationAsDynamicMontage(Clip, ActingSlot, .35f, .35f, 1.f, 1, -1.f, 0.f);
            }
        return false;
    }
    UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr, Choice == 1 ? TauntClip : LaughClip, nullptr, LOAD_NoWarn);
    if (!Clip) return false;
    if (Choice == 1) NextTauntAt = Now + TauntCooldown * (Flag(Boss, TEXT("bPhaseTwo")) ? PhaseTwoTauntCooldownScale : 1.f);
    else { bKnockdownTaunted = true; NextLaughAt = Now + 20.0; }
    if (!TransitionState(Boss, TEXT("Boss.Combat.Ready"), TEXT("Boss.Combat.Position"), TEXT("도발"))) return false;
    Invoke(Boss, TEXT("StopBossLocomotion"));
    if (AAIController* Controller = Cast<AAIController>(Boss->GetController())) Controller->StopMovement();
    SetFlag(Boss, TEXT("bCombatApproachActive"), false);
    SetNumber(Boss, TEXT("UtilityAction"), 0);
    SetFlag(Boss, TEXT("bAttackIntentActive"), true);
    const float Rate = 1.3f;
    PerformMontage = Anim->PlaySlotAnimationAsDynamicMontage(Clip, ActingSlot, .2f, .25f, Rate, 1, -1.f, 0.f);
    bPerforming = true;
    PerformUntil = Now + FMath::Min(TauntMaxSeconds, Clip->GetPlayLength() / Rate);
    const FString Reason = Choice == 1 ? TEXT("멀리 달아났다: 도발하고 달려간다") : TEXT("쓰러뜨렸다: 내려다보며 웃는다");
    Status = Reason;
    SetText(Boss, TEXT("IntentPhase"), TEXT("taunt"));
    SetText(Boss, TEXT("IntentReason"), Reason);
    SetText(Boss, TEXT("GoapReason"), Reason);
    Invoke(Boss, TEXT("RecordCombatQA"), Choice == 1 ? TEXT("taunt_far") : TEXT("taunt_down"));
    return true;
}

// 연속기의 2타와 훅이 시작되기 직전에, 그 타를 걸어 들어가며 칠지 제자리에서 칠지 정하고 필요하면 몽타주를 바꾼다.
void UBossCombatIntentComponent::UpdateComboStages()
{
    ACharacter* Boss = Cast<ACharacter>(GetOwner());
    UAnimInstance* Anim = Boss && Boss->GetMesh() ? Boss->GetMesh()->GetAnimInstance() : nullptr;
    UAnimMontage* Montage = Anim ? Anim->GetCurrentActiveMontage() : nullptr;
    const FString Name = Montage ? Montage->GetName() : FString();
    const bool bStriding = Name.Contains(TEXT("JabJabHookRunIn"));
    const bool bPlanted = Name == TEXT("AM_Boss_Jab_Jab_Hook_Matched");
    if (!bStriding && !bPlanted) { ComboStage = 0; ComboLastPosition = 0.f; return; }
    // 모션랩에서는 "디딤 공격" 방식일 때만. 다른 방식은 고른 모션을 그대로 본다.
    if (GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab")) && MotionLabPunchMode != 3) return;
    const float Position = Anim->Montage_GetPosition(Montage);
    if (Position < ComboLastPosition - .2f || Position < ComboStageTimes[0] - .2f) ComboStage = 0;
    ComboLastPosition = Position;
    if (ComboStage >= UE_ARRAY_COUNT(ComboStageTimes) || Position < ComboStageTimes[ComboStage]) return;
    const int32 Stage = ComboStage++;
    if (Position > ComboStageTimes[Stage] + .2f) return;       // 이미 그 타의 걸음이 시작됐다: 바꾸지 않는다
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player)) return;
    const float Distance = FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation());
    const bool bStride = ComboStageStrides(Distance, ComboStageStops[Stage + 1], ComboStageTravel[Stage]);
    if (bStride == bStriding) return;
    // 타격 판정은 "지금 카드의 몽타주"가 재생 중일 때만 열린다. 그래서 몽타주와 함께 카드도 바꾼다(두 카드는 시간과 피해가 같다).
    UObject* Card = LoadObject<UObject>(nullptr, bStride
        ? TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Combo_FootStep.DA_Lab_Combo_FootStep")
        : TEXT("/Game/BossArena/Boss/AI/Actions/DA_Attack_Combo.DA_Attack_Combo"), nullptr, LOAD_NoWarn);
    UAnimMontage* Wanted = Cast<UAnimMontage>(Object(Card, TEXT("Montage")));
    FObjectPropertyBase* Active = FindFProperty<FObjectPropertyBase>(Boss->GetClass(), TEXT("ActiveAction"));
    if (!Wanted || !Active) return;
    Active->SetObjectPropertyValue_InContainer(Boss, Card);
    const float Rate = Anim->Montage_GetPlayRate(Montage);
    Boss->SetAnimRootMotionTranslationScale(1.f);
    Anim->Montage_Stop(0.f, Montage);
    Anim->Montage_PlayWithBlendIn(Wanted, FAlphaBlendArgs(0.f), Rate, EMontagePlayReturnType::MontageLength, Position, false);
    Invoke(Boss, TEXT("RecordCombatQA"), bStride ? TEXT("combo_stage_stride") : TEXT("combo_stage_planted"));
}

namespace
{
// 후딜 중 지금 돌아도 되는가: 앞쪽(주먹을 거두는 동안)은 안 되고, 정해진 비율이 지난 뒤쪽만 된다.
bool RecoveryMayTurn(float Elapsed, float Remaining, float StartFraction)
{
    if (!FMath::IsFinite(Elapsed) || !FMath::IsFinite(Remaining) || Elapsed < 0.f || Remaining <= 0.f) return false;
    return Elapsed / (Elapsed + Remaining) >= FMath::Clamp(StartFraction, 0.f, 1.f);
}
}

// 후딜 내내 돌지 않으면 플레이어가 등 뒤로 돌아가 후딜과 그 뒤의 턴 동작까지 계속 때릴 수 있다.
// 그래서 후딜을 둘로 나눈다. 앞쪽은 반격 시간으로 지키고(회전 없음), 뒤쪽은 느리게 플레이어 쪽으로 돈다.
// 새 행동은 여전히 후딜이 끝난 뒤(Ready)에만 고른다.
void UBossCombatIntentComponent::UpdateRecoveryTurn(float DeltaTime)
{
    AActor* Boss = GetOwner();
    if (!StateIs(Boss, TEXT("Boss.Combat.Attack.Recovery"))) { RecoveryStartedAt = -1.0; bFlankExitDone = false; bWhiffed = false; bPursuitWanted = false; return; }
    const double Now = GetWorld()->GetTimeSeconds();
    if (RecoveryStartedAt < 0.0)
    {
        RecoveryStartedAt = Now;
        // 연계를 이을지는 후딜이 시작될 때 한 번 정한다. 연계로 나온 공격에서 또 잇지는 않는다.
        const bool bLab = GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"));
        const bool bPhaseTwo = Flag(Boss, TEXT("bPhaseTwo"));
        bLinkWanted = !bLab && StringUsed.Num() < StringHitsWanted;
        bPursuitWanted = !bLab && FMath::FRand() < ChainLinkChance(bPhaseTwo ? PhaseTwoPursuitChance : PursuitChance, ChainDepth);
        // 헛침: 닿지 않았으면 상체가 앞으로 쏠렸다 돌아오고 몸이 조금 딸려 나간다. 맞혔을 때의 후딜과 달라 보인다.
        const AActor* Dodger = UGameplayStatics::GetPlayerPawn(this, 0);
        bWhiffed = !bLab && !bAttackConnected && IsValid(Dodger) && Number(Dodger, TEXT("CurrentHealth"), 1) > 0 && !Flag(Dodger, TEXT("bKnockedDown"));
        if (!bLab)
        {
            // 결과의 기억: 이 자리(슬롯)의 공격이 이번에 어떻게 됐는지 적어 둔다.
            FAttackOutcome& Outcome = OutcomeBySlot.FindOrAdd(static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1)));
            // 회피로 피한 것은 그 공격의 잘못이 아니다(플레이어가 잘한 것). 회피 없이 빗나간 것만 "안 통했다"로 센다.
            if (bWhiffed && bDodgedThisAttack) { /* 기록을 바꾸지 않는다 */ }
            else Outcome.Whiffs = bWhiffed ? Outcome.Whiffs + 1 : 0;
            Outcome.bHit = bAttackHit;
            Outcome.At = Now;
        }
        bRecoveryOpen = false;
        bStringEndLogged = false;
        if (bWhiffed)
        {
            BowVelocity -= BowKick(WhiffBowPitch);
            FlinchVelocity += Boss->GetActorForwardVector() * WhiffLurch;
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("whiff"));
        }
        // 후딜 줄이기: 남은 후딜 시간과 그동안의 동작을 같은 비율로 줄인다(동작이 잘리지 않고 빨리 끝난다).
        const float Left = UKismetSystemLibrary::K2_GetTimerRemainingTime(Boss, TEXT("FinishCombatAction"));
        const float Scale = RecoveryScaleFor(bLab ? 0 : ChainDepth, RecoveryScale, EnderRecoveryScale);
        if (Left > 0.f && Scale < 1.f)
        {
            UKismetSystemLibrary::K2_SetTimer(Boss, TEXT("FinishCombatAction"), Left * Scale, false);
            if (const ACharacter* Character = Cast<ACharacter>(Boss))
                if (UAnimInstance* Anim = Character->GetMesh() ? Character->GetMesh()->GetAnimInstance() : nullptr)
                    if (UAnimMontage* Active = Anim->GetCurrentActiveMontage())
                        Anim->Montage_SetPlayRate(Active, Anim->Montage_GetPlayRate(Active) / Scale);
        }
    }
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Player) || Number(Boss, TEXT("CurrentHealth")) <= 0) return;
    const float Remaining = UKismetSystemLibrary::K2_GetTimerRemainingTime(Boss, TEXT("FinishCombatAction"));
    const float Elapsed = static_cast<float>(Now - RecoveryStartedAt);
    // 후딜의 하위 상태. 닫힌 후딜에서는 어떤 규칙도 후딜을 끝내지 못한다: 여기서 돌아가면 아래의 연계·추격·옆뒤 대응에 닿지 않는다.
    // 열린 후딜에서만 그 규칙들이 조건을 본다. 플레이어에게 보장하는 반격 시간이 이 한 줄이다.
    if (!bRecoveryOpen)
    {
        if (!RecoveryMayTurn(Elapsed, Remaining, ChainStartFraction)) return;
        bRecoveryOpen = true;
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("recovery_open"));
    }
    UpdateChain(Elapsed, Remaining);
    if (!StateIs(Boss, TEXT("Boss.Combat.Attack.Recovery"))) return;       // 연계로 후딜이 끝났다
    const FVector ToPlayer = Player->GetActorLocation() - Boss->GetActorLocation();
    const FRotator Wanted(0.f, ToPlayer.Rotation().Yaw, 0.f);
    // 추격: 연계 지점에서 플레이어가 반격할 수 없는 거리로 빠져 있으면 후딜을 지키지 않는다.
    if (bPursuitWanted && RecoveryMayTurn(Elapsed, Remaining, ChainStartFraction))
    {
        bPursuitWanted = false;
        // 맞힌 뒤에는 쫓지 않는다: 맞고 밀려난 것은 달아난 것이 아니다(1.5초에 두 대를 연달아 맞는 일이 있었다).
        if (bWhiffed && PursuitHolds(ToPlayer.Size2D(), FVector::DotProduct(Boss->GetActorForwardVector(), ToPlayer.GetSafeNormal2D()),
            Flag(Player, TEXT("bKnockedDown")), PursuitDistance))
        {
            bPursuitExit = true;
            UKismetSystemLibrary::K2_ClearTimer(Boss, TEXT("FinishCombatAction"));
            SetText(Boss, TEXT("IntentReason"), TEXT("멀어진 상대: 후딜을 지키지 않고 쫓는다"));
            Invoke(Boss, TEXT("RecordCombatQA"), TEXT("pursuit"));
            Invoke(Boss, TEXT("FinishCombatAction"));
            return;
        }
    }
    // 옆·뒤를 잡혔으면 후딜을 끝까지 서 있지 않는다. 앞쪽(FlankExitFraction)은 반격 시간으로 지키고, 그 뒤에는
    // 후딜을 일찍 끝내서 제대로 된 턴 동작이나 뒤쪽 대응으로 넘어간다. 발을 둔 채 몸만 돌리는 일은 하지 않는다.
    // 몰아치기의 마지막 공격은 옆·뒤를 잡혀도 후딜을 끝까지 보낸다. 보스를 지나쳐 피한 플레이어가 보상을 잃지 않게 한다.
    const bool bEnder = ChainDepth >= 1 && ChainSlot == INDEX_NONE;
    if (bEnder && !bStringEndLogged) { bStringEndLogged = true; Invoke(Boss, TEXT("RecordCombatQA"), TEXT("string_end")); }
    if (!bFlankExitDone && !bEnder && RecoveryMayTurn(Elapsed, Remaining, FlankExitFraction)
        && FMath::Abs(FMath::FindDeltaAngleDegrees(Boss->GetActorRotation().Yaw, Wanted.Yaw)) >= FlankExitAngle)
    {
        bFlankExitDone = true;
        UKismetSystemLibrary::K2_ClearTimer(Boss, TEXT("FinishCombatAction"));
        SetText(Boss, TEXT("IntentReason"), TEXT("옆·뒤를 잡힘: 후딜을 일찍 끝내고 돌아본다"));
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("recovery_flank_exit"));
        Invoke(Boss, TEXT("FinishCombatAction"));
        return;
    }
    if (RecoveryTurnSpeed <= 0.f || !RecoveryMayTurn(Elapsed, Remaining, RecoveryTurnStart)) return;
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, RecoveryTurnSpeed));
}

void UBossCombatIntentComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    UpdateCombatEffects();
    UpdateComboStages();
    UpdateTravelScale();
    UpdateWhiff();
    UpdateWindupTurn();
    UpdateRecoveryTurn(DeltaTime);
    UpdateRearResponse(DeltaTime);
    UpdateSprint();
    UpdateTurnSync();
    UpdateLook(DeltaTime);
    UpdateGuardReward();
    UpdateFlinch(DeltaTime);
    UpdateHealthBar(DeltaTime);
    RestoreTrueWeights();
    if (UpdatePerformance(DeltaTime)) return;
    if (bReassessing) { TickReassessment(DeltaTime); return; }
    if (bFootworkActive) { TickFootwork(DeltaTime); return; }
    if (!bActive) return;
    AActor* Boss = GetOwner();
    if (!StateIs(Boss, TEXT("Boss.Combat.Position")) || !Target.IsValid()
        || Number(Boss, TEXT("CurrentHealth")) <= 0 || Number(Target.Get(), TEXT("CurrentHealth")) <= 0
        || Flag(Target.Get(), TEXT("bKnockedDown")) || Object(Boss, TEXT("ActiveAction")) != Action.Get()
        || static_cast<int32>(Number(Boss, TEXT("SelectedSlot"), -1)) != Slot)
    { Finish(false, TEXT("상태 또는 대상 변경으로 진입 중단"), false); return; }
    const double Now = GetWorld()->GetTimeSeconds();
    SetNumber(Boss, TEXT("IntentElapsed"), Now - StartedAt);
    if (Now - StartedAt >= MaxDuration) { Finish(false, TEXT("2초 진입 제한: 다음 행동 재평가")); return; }
    const FRotator Wanted(0.f, (Target->GetActorLocation() - Boss->GetActorLocation()).Rotation().Yaw, 0.f);
    Boss->SetActorRotation(FMath::RInterpConstantTo(Boss->GetActorRotation(), Wanted, DeltaTime, TurnSpeed));
    // 도착은 매 프레임 확인한다. 0.2초마다만 보면 달려 들어가다가 칠 자리를 지나쳐서, 중거리 버전을 고르고도 단거리까지 붙어버린다.
    const FVector ToTarget = Target->GetActorLocation() - Boss->GetActorLocation();
    const float Range = ToTarget.Size2D();
    const bool bInPlace = !bSideEntryActive && Action.IsValid() && Range >= GoalMinDistance && Range <= GoalMaxDistance
        && FVector::DotProduct(Boss->GetActorForwardVector(), ToTarget.GetSafeNormal2D()) >= Number(Boss, TEXT("AttackStartMinDot"), .5);
    if (Now >= NextPlanAt || bInPlace)
    {
        NextPlanAt = Now + ReplanInterval;
        Advance();
    }
}

void UBossCombatIntentComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    ClearCombatEffects();
    bActive = false;
    bReassessing = false;
    bSideEntryActive = false;
    bFootworkActive = false;
    bPerforming = false;
    if (HealthBar.IsValid())
    {
        if (UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr) Viewport->RemoveViewportWidgetContent(HealthBar.ToSharedRef());
        HealthBar.Reset();
    }
    Super::EndPlay(Reason);
}

float UBossCombatIntentComponent::OutcomeMultiplier(int32 CandidateSlot) const
{
    const FAttackOutcome* Outcome = OutcomeBySlot.Find(CandidateSlot);
    return Outcome && GetWorld() ? OutcomeScale(Outcome->Whiffs, Outcome->bHit, static_cast<float>(GetWorld()->GetTimeSeconds() - Outcome->At)) : 1.f;
}

float UBossCombatIntentComponent::PlayerSpeedAway() const
{
    const AActor* Boss = GetOwner();
    const AActor* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!IsValid(Boss) || !IsValid(Player)) return 0.f;
    return static_cast<float>(FVector::DotProduct(Player->GetVelocity(), (Player->GetActorLocation() - Boss->GetActorLocation()).GetSafeNormal2D()));
}

FString UBossCombatIntentComponent::RecoveryLabel() const
{
    if (RecoveryStartedAt < 0.0) return FString();
    return FString::Printf(TEXT("후딜 %s · %s"), bRecoveryOpen ? TEXT("열림") : TEXT("닫힘"),
        bWhiffed ? TEXT("헛침") : (bAttackHit ? TEXT("맞힘") : TEXT("막힘")));
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

void UBossCombatIntentLibrary::RecordAttackRecoveryEnd(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    if (!Intent)
    {
        Intent = NewObject<UBossCombatIntentComponent>(Boss, TEXT("CombatIntent"));
        Boss->AddInstanceComponent(Intent);
        Intent->RegisterComponent();
        Intent->AddTickPrerequisiteActor(Boss);
    }
    Intent->RecordAttackRecoveryEnd();
}

bool UBossCombatIntentLibrary::IsAttackIntentActive(AActor* Boss)
{
    const auto* Intent = IsValid(Boss) ? Boss->FindComponentByClass<UBossCombatIntentComponent>() : nullptr;
    return Intent && Intent->IsActive();
}

namespace
{
// ---- 감점 규칙 (Utility 점수 다듬기) -------------------------------------------------------------------------
// 전에는 감점을 전부 곱했다: 같은 공격 연속 0.5 x 최근 사용 0.35 x 주먹 계열 0.55 = 약 0.1.
// (블루프린트에 "쓴 지 얼마 안 됨" 배수도 있지만 실측에서 점수에 반영되지 않았다: 왼손 직후에도 입력 점수가 30 그대로였다.)
// "감점이지 금지가 아니다"라고 했지만 사실상 금지였고, 후보가 둘뿐인 거리에서는 왼손 -> 오른손 -> 왼손으로 순서가 읽혔다.
// 이제 그중 가장 큰 감점 하나만 적용한다. 가장 심해도 0.35배다.
constexpr float RepeatPenalty = .5f;          // 방금 쓴 바로 그 공격
constexpr float RecentUseFloor = .35f;        // 쓴 직후. RecentUseRecover초에 걸쳐 1로 돌아온다
constexpr float RecentUseRecover = 12.f;
constexpr float PunchFamilyFloor = .55f;      // 주먹 계열(왼손·오른손·연속기·2연타)을 쓴 직후. 6초에 걸쳐 회복
constexpr float PunchFamilyRecover = 6.f;
constexpr float ComboBaselineShare = .3f;     // 연속기: 회피를 못 봤어도 기본 가중치의 30%로는 후보에 둔다
constexpr float SweepDodgeBoost = 3.f;        // 휩쓸기: 최근 회피 2회 이상이면 3배
constexpr int32 SweepDodgeCount = 2;

float Recovering(float Floor, float SecondsSince, float RecoverSeconds)
{
    return FMath::Lerp(Floor, 1.f, FMath::Clamp(SecondsSince / FMath::Max(.01f, RecoverSeconds), 0.f, 1.f));
}

// 세 감점 중 가장 큰 것 하나. SecondsSinceUse < 0 = 아직 쓴 적 없음, SecondsSinceFamily < 0 = 주먹 계열이 아님.
// "쓴 시각"은 블루프린트가 그 공격이 끝날 때 찍는다(CooldownUntil - CooldownSeconds). 그래서 후딜 직후의 판단에서는 0초다.
float StrongestPenalty(bool bSameAsLast, float SecondsSinceUse, float SecondsSinceFamily)
{
    float Penalty = bSameAsLast ? RepeatPenalty : 1.f;
    if (SecondsSinceUse >= 0.f) Penalty = FMath::Min(Penalty, Recovering(RecentUseFloor, SecondsSinceUse, RecentUseRecover));
    if (SecondsSinceFamily >= 0.f) Penalty = FMath::Min(Penalty, Recovering(PunchFamilyFloor, SecondsSinceFamily, PunchFamilyRecover));
    return Penalty;
}

double ArrayNumber(const UObject* Owner, FName Name, int32 Index, double Default)
{
    const FArrayProperty* Array = IsValid(Owner) ? FindFProperty<FArrayProperty>(Owner->GetClass(), Name) : nullptr;
    const FNumericProperty* Inner = Array ? CastField<FNumericProperty>(Array->Inner) : nullptr;
    if (!Inner) return Default;
    FScriptArrayHelper Values(Array, Array->ContainerPtrToValuePtr<void>(Owner));
    if (!Values.IsValidIndex(Index)) return Default;
    return Inner->IsInteger() ? static_cast<double>(Inner->GetSignedIntPropertyValue(Values.GetRawPtr(Index)))
        : Inner->GetFloatingPointPropertyValue(Values.GetRawPtr(Index));
}
}

float UBossCombatIntentLibrary::AdjustIntentCandidate(AActor* Boss, int32 CandidateSlot, float Score)
{
    if (!IsValid(Boss)) return 0.f;
    const FArrayProperty* Cards = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FObjectPropertyBase* CardType = Cards ? CastField<FObjectPropertyBase>(Cards->Inner) : nullptr;
    if (!CardType) return FMath::Max(0.f, Score);
    FScriptArrayHelper Values(Cards, Cards->ContainerPtrToValuePtr<void>(Boss));
    if (!Values.IsValidIndex(CandidateSlot)) return 0.f;
    const UObject* Card = CardType->GetObjectPropertyValue(Values.GetRawPtr(CandidateSlot));
    const int32 ActionId = static_cast<int32>(Number(Card, TEXT("ActionId"), -1));
    const double Now = UKismetSystemLibrary::GetGameTimeInSeconds(Boss);
    const double Distance = Number(Boss, TEXT("UtilityDistance"));
    const double Until = ArrayNumber(Boss, TEXT("CooldownUntil"), CandidateSlot);
    const double Cooldown = Number(Card, TEXT("CooldownSeconds"));
    const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    const bool bFootAttack = (ActionId >= 0 && ActionId <= 5) || ActionId == 9 || ActionId == OverheadId;   // 제자리나 걸음으로 치는 공격(돌진·점프·접근 제외)
    const AActor* Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    const bool bRetreating = IsValid(Target) && IsRetreating(static_cast<float>(FVector::DotProduct(Target->GetVelocity(),
        (Target->GetActorLocation() - Boss->GetActorLocation()).GetSafeNormal2D())));
    const float CardMin = static_cast<float>(Number(Card, TEXT("MinDistance"))), CardMax = static_cast<float>(Number(Card, TEXT("MaxDistance")));
    // 닿는지는 "칠 때쯤의 거리"로 본다: 지금 거리 + 멀어지는 속도 x 이 공격의 첫 타격까지의 시간.
    const double Aim = bFootAttack && Intent
        ? PredictedDistance(static_cast<float>(Distance), Intent->PlayerSpeedAway(), FMath::Min(1.2f, FirstImpactSeconds(Card))) : Distance;
    float Lo = 0.f, Hi = 0.f;
    const float Gap = bFootAttack ? NearestStartBand(ActionId, static_cast<float>(Aim), CardMin, CardMax, Lo, Hi) : 0.f;
    if (Score <= 0.f)
    {
        // 블루프린트가 0점을 준 이유가 "거리"나 "회피를 못 봤다"뿐이면 되살린다. 꺼진 카드, 쿨다운, 등 뒤는 그대로 0점이다.
        const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
        const bool bUsable = bFootAttack && Flag(Card, TEXT("bEnabled")) && IsValid(Object(Card, TEXT("Montage"))) && Now >= Until && IsValid(Player)
            && FVector::DotProduct(Boss->GetActorForwardVector(), (Player->GetActorLocation() - Boss->GetActorLocation()).GetSafeNormal2D()) >= .5f;
        if (!bUsable) return 0.f;
        const int32 Rule = static_cast<int32>(Number(Card, TEXT("ObservationRule")));
        const bool bInCardRange = Distance >= CardMin && Distance <= CardMax && Aim >= CardMin && Aim <= CardMax;
        float Base = static_cast<float>(Number(Card, TEXT("BaseWeight")));
        // 연속기(규칙 1): 회피를 못 봤어도 낮은 점수로 후보에 둔다. 가드 브레이크(규칙 2): 가드를 2초 넘게 봤을 때만.
        if (Rule == 1) Base *= ComboShare(static_cast<int32>(Number(Boss, TEXT("RecentDodgeCount"))));
        else if (Rule == 2) { if (Number(Boss, TEXT("RecentGuardSeconds")) < 2.0) return 0.f; }
        else if (bInCardRange) return 0.f;       // 거리 안인데 0점: 블루프린트의 다른 이유. 건드리지 않는다
        Score = Base;
    }
    // 지금 거리에서 바로 칠 수 없으면: 한 걸음이면 닿을 때만 낮은 점수로 남긴다.
    if (bFootAttack && Gap > 0.f)
    {
        if (Gap > StepReach || Aim >= MaxRunInReach) return 0.f;          // 달려드는 모션도 닿지 않는 거리: 걸어 들어가서 치지 않는다(달려온다)
        // 달려드는 패턴은 물러나서 치지 않는다. 제자리 패턴은 달려드는 패턴이 맡는 거리까지 걸어 들어가지 않는다.
        if (IsMidPattern(ActionId, CardMin) && Aim < Lo) return 0.f;
        if (MidVersionStart(ActionId) > 0.f && !IsMidPattern(ActionId, CardMin) && Aim >= MidVersionStart(ActionId)) return 0.f;
        if (bRetreating) return 0.f;                                      // 물러나는 상대에게 걸어가서 치려 하면 못 닿고 시간만 쓴다
        Score *= StepDiscount;
    }
    else Score *= DistanceBandMultiplier(ActionId, Aim);
    // 물러나는 상대에게는 그 자리에서 바로 닿는 공격만 고른다. 먼저 들어가야 하는 공격은 뺀다. 돌진(슈퍼맨 펀치)은 이럴 때 쓰는 공격이다.
    if (bRetreating && MidVersionStart(ActionId) > 0.f && Aim > MidVersionReach(ActionId)) return 0.f;
    if (bRetreating && ActionId == 6) Score *= 1.5f;
    // 휩쓸기는 애매한 회피를 잡는 공격이다. 평소에는 드물고, 회피를 본 뒤에 올라온다.
    if (ActionId == 3 && Number(Boss, TEXT("RecentDodgeCount")) >= SweepDodgeCount) Score *= SweepDodgeBoost;
    const bool bFamily = ActionId <= 1 || ActionId == 4 || ActionId == 9;       // 주먹 계열(단거리·중거리 패턴 모두)
    Score *= StrongestPenalty(static_cast<int32>(Number(Boss, TEXT("LastSelectedSlot"), -1)) == CandidateSlot,
        Until > 0.0 ? static_cast<float>(Now - (Until - Cooldown)) : -1.f,
        bFamily && Number(Boss, TEXT("PunchFamilyLastUsedAt")) > 0.0 ? static_cast<float>(Now - Number(Boss, TEXT("PunchFamilyLastUsedAt"))) : -1.f);
    if ((bFootAttack || ActionId == 6) && Intent && Intent->FirstDecisionAt >= 0.0)
        Score *= StaleBonus(static_cast<float>(Now - (Until > 0.0 ? Until - Cooldown : Intent->FirstDecisionAt)));
    if (Intent)
    {
        Score *= PressureBoost(ActionId, Intent->HitsTakenWithin(4.f), static_cast<float>(Distance));
        Score *= Intent->FailureMultiplier(CandidateSlot);
        Score *= Intent->OutcomeMultiplier(CandidateSlot);
    }
    // 가점이 여러 개 겹쳐도 기본 가중치의 4배까지만. 한 공격이 추첨을 독차지하지 않게 한다(실제 플레이에서 휩쓸기가 15배까지 올랐다).
    return FMath::Min(Score, 4.f * static_cast<float>(Number(Card, TEXT("BaseWeight"))));
}

float UBossCombatIntentLibrary::OrdinaryPunchStepDistance(AActor* Boss, float AuthoredDistance)
{
    // 공격 중에 몸을 밀어서 옮기지 않는다. 예전에는 단거리 공격마다 "발 디딤" 구간에 몸을 앞으로 밀었는데(최대 145cm, 연속기는 180cm),
    // 발 애니메이션에 없는 이동이라 미끄러지듯 전진했다. 전진이 필요한 거리는 걸음이 들어 있는 중거리 버전이 맡는다.
    // 모션랩의 "수동 디딤" 방식(2)만 옛 동작을 비교용으로 남긴다.
    if (!IsValid(Boss)) return 0.f;
    const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    const bool bLab = Boss->GetWorld() && Boss->GetWorld()->GetMapName().Contains(TEXT("Lvl_BossMotionLab"));
    const int32 Id = static_cast<int32>(Number(Object(Boss,TEXT("ActiveAction")),TEXT("ActionId"),-1));
    if (bLab && Intent && Intent->MotionLabPunchMode == 2 && (Id == 0 || Id == 1) && !IsComboFollowStep(Boss))
        return ApplyLabPunchMode(true, 2, 0.f, static_cast<float>(FMath::Max(0.0,Number(Boss,TEXT("AttackAdvanceBudget")))));
    return 0.f;
}

bool UBossCombatIntentLibrary::IsComboFollowStep(AActor* Boss)
{
    const int32 Id = static_cast<int32>(Number(Object(Boss,TEXT("ActiveAction")),TEXT("ActionId"),-1));
    return IsValid(Boss) && (Id == 4 || Id == 9) && Number(Boss,TEXT("HitIndex")) > 0;
}

void UBossCombatIntentLibrary::CommitComboStep(AActor* Boss)
{
    if (!IsComboFollowStep(Boss)) return;
    SetFlag(Boss,TEXT("bDirectionCommitted"),true);
    SetFlag(Boss,TEXT("bCanTurn"),false);
    Invoke(Boss,TEXT("RecordCombatQA"),TEXT("combo_follow_step_committed"));
}

void UBossCombatIntentLibrary::PlayPlayerHitShake(AActor* Player, float Scale)
{
    if (!IsValid(Player)) return;
    const APawn* Pawn = Cast<APawn>(Player);
    APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!Controller) return;
    UClass* Shake = LoadClass<UCameraShakeBase>(nullptr,
        TEXT("/Game/BossArena/Player/Blueprints/BP_CamShake_Hit.BP_CamShake_Hit_C"));
    if (Shake) Controller->ClientStartCameraShake(Shake, FMath::Clamp(Scale,0.f,2.f));
}

bool UBossCombatIntentLibrary::CanStartPendingSlam(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    const AActor* Player = Cast<AActor>(Object(Boss,TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerCharacter(Boss,0);
    if (!IsValid(Player)) return false;
    return PendingSlamRange(Flag(Boss,TEXT("bFirstSlamPending")),Flag(Boss,TEXT("bPhaseTwo")),
        FVector::Dist2D(Boss->GetActorLocation(),Player->GetActorLocation()),1000.f,5000.f);
}

namespace
{
// 화면에 보여줄 "지금 이 거리에서 닿는 공격 수". 거리 구간 이름 대신 이것을 보여준다(쿨다운·감점은 보지 않고 거리만 본다).
int32 ReachableAttackCount(const AActor* Boss, float Distance)
{
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FObjectPropertyBase* ActionType = Actions ? CastField<FObjectPropertyBase>(Actions->Inner) : nullptr;
    if (!ActionType) return 0;
    FScriptArrayHelper Cards(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
    int32 Count = 0;
    for (int32 I = 0; I < Cards.Num(); ++I)
    {
        const UObject* Card = ActionType->GetObjectPropertyValue(Cards.GetRawPtr(I));
        const int32 Id = static_cast<int32>(Number(Card, TEXT("ActionId"), -1));
        if (Id < 0 || Id == 7 || !Flag(Card, TEXT("bEnabled"))) continue;
        float Lo = 0.f, Hi = 0.f;
        if (FMath::IsNearlyZero(NearestStartBand(Id, Distance, static_cast<float>(Number(Card, TEXT("MinDistance"))),
            static_cast<float>(Number(Card, TEXT("MaxDistance"))), Lo, Hi))) ++Count;
    }
    return Count;
}
}

FString UBossCombatIntentLibrary::DescribeCombatDebug(AActor* Boss)
{
    if (!IsValid(Boss)) return TEXT("보스 대기 중");
    FString Result = FString::Printf(TEXT("HFSM %s\n%s\n회전 %s | 손 판정 %s | HP %.0f\n\n선택 %s\n거리 %.0fcm | 판단 #%d\n"),
        *Text(Boss, TEXT("StateDisplay")), *Text(Boss, TEXT("TransitionReason")),
        Flag(Boss, TEXT("bCanTurn")) ? TEXT("가능") : TEXT("제한"),
        Flag(Boss, TEXT("bPhysicalStrikeOpen")) ? TEXT("열림") : TEXT("닫힘"),
        Number(Boss, TEXT("CurrentHealth")), *Text(Boss, TEXT("UtilityChoice")),
        Number(Boss, TEXT("UtilityDistance")), static_cast<int32>(Number(Boss, TEXT("UtilityDecisionCount"))));
    // 지금 이 순간의 거리(중심에서 중심까지). 위의 "거리"는 마지막으로 판단했을 때의 값이라 플레이 중에는 멈춰 있다.
    {
        const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
        if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(Boss, 0);
        if (IsValid(Player))
        {
            const float Live = FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation());
            FString Top = FString::Printf(TEXT("▶ 지금 거리 %.0fcm · 닿는 공격 %d개\n"), Live, ReachableAttackCount(Boss, Live));
            if (const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>())
            {
                const float Away = Intent->PlayerSpeedAway();
                if (FMath::Abs(Away) >= 60.f) Top += FString::Printf(TEXT("  0.8초 뒤 예상 %.0fcm\n"), PredictedDistance(Live, Away, .8f));
                const FString Recovery = Intent->RecoveryLabel();
                if (!Recovery.IsEmpty()) Top += TEXT("  ") + Recovery + TEXT("\n");
            }
            Result = Top + Result;
        }
        const FString Phase = Text(Boss, TEXT("IntentPhase"));
        if (Phase == TEXT("footwork")) Result += FString::Printf(TEXT("기동: %s\n"), *Text(Boss, TEXT("IntentReason")));
        if (Phase == TEXT("taunt")) Result += FString::Printf(TEXT("연기: %s\n"), *Text(Boss, TEXT("IntentReason")));
    }
    const FArrayProperty* Scores = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FNumericProperty* ScoreType = Scores ? CastField<FNumericProperty>(Scores->Inner) : nullptr;
    const FObjectPropertyBase* ActionType = Actions ? CastField<FObjectPropertyBase>(Actions->Inner) : nullptr;
    if (ScoreType && ScoreType->IsFloatingPoint() && ActionType)
    {
        FScriptArrayHelper Values(Scores, Scores->ContainerPtrToValuePtr<void>(Boss));
        FScriptArrayHelper Cards(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
        const bool bHasDecision = Number(Boss, TEXT("UtilityDecisionCount")) > 0 && Values.Num() == Cards.Num();
        const TCHAR* Labels[] = {TEXT("왼손"), TEXT("오른손"), TEXT("어퍼"), TEXT("휩쓸기"),
            TEXT("3타"), TEXT("가드깨기"), TEXT("슈퍼맨"), TEXT("접근"), TEXT("점프"), TEXT("2타"), TEXT("찍기")};
        for (int32 I = 0; I < Cards.Num(); ++I)
        {
            UObject* Card = ActionType->GetObjectPropertyValue(Cards.GetRawPtr(I));
            const int32 Id = static_cast<int32>(Number(Card, TEXT("ActionId"), -1));
            const FString Label = (Id >= 0 && Id < UE_ARRAY_COUNT(Labels) ? FString(Labels[Id]) : Text(Card, TEXT("DisplayName")))
                + (IsMidPattern(Id, static_cast<float>(Number(Card, TEXT("MinDistance")))) ? TEXT("(달려)") : TEXT(""));
            Result += Label + (bHasDecision
                ? FString::Printf(TEXT(" %.1f"), ScoreType->GetFloatingPointPropertyValue(Values.GetRawPtr(I))) : TEXT(" —"));
            Result += (I % 3 == 2 || I == Cards.Num()-1) ? TEXT("\n") : TEXT(" · ");
        }
        if (!bHasDecision) Result += TEXT("점수 판단 전\n");
        else Result += TEXT("점수는 마지막 선택 시점 기준\n");
    }
    Result += FString::Printf(TEXT("최근 6초: 회피 %d회 · 가드 %.1f초"),
        static_cast<int32>(Number(Boss, TEXT("RecentDodgeCount"))), Number(Boss, TEXT("RecentGuardSeconds")));
    return Result;
}

namespace
{
// 달려오기(접근)의 몫. 거리 구간으로 정하지 않는다: 닿는 공격이 적을수록 달려오기가 오른다.
//   제자리에서 닿는 공격이 있다(주먹 거리 안)  -> 달려오지 않는다
//   달려드는 공격만 닿는다                    -> 공격 점수 합의 ApproachShare배까지만(공격이 셋 이상이면 약 8번에 1번)
//   닿는 공격이 없다                          -> 달려온다
double ApproachShare(int32 ReachingAttacks)
{
    return ReachingAttacks <= 1 ? 1.5 : (ReachingAttacks == 2 ? .5 : .15);
}
// 플레이어가 물러나는 중이면(초당 RetreatSpeed 이상 멀어짐) 달려오기의 몫을 두 배로 한다. 도망가는 상대에게는 붙는 것이 먼저다.
constexpr double RetreatSpeed = 150.0;

// 점수 비율대로 하나를 뽑는다. Roll은 0..1 난수. 후보가 없으면 INDEX_NONE.
int32 WeightedPick(const TArray<double>& Weights, double Roll)
{
    double Total = 0;
    for (const double W : Weights) Total += FMath::Max(0.0, W);
    if (Total <= 0.0) return INDEX_NONE;
    double Remaining = FMath::Clamp(Roll, 0.0, 1.0) * Total;
    int32 Last = INDEX_NONE;
    for (int32 I = 0; I < Weights.Num(); ++I)
    {
        if (Weights[I] <= 0.0) continue;
        Last = I;
        if (Remaining < Weights[I]) return I;
        Remaining -= Weights[I];
    }
    return Last;
}

double FinalizeWeights(TArray<double>& Weights, const TArray<bool>& IsApproach, const TArray<bool>& IsPlanted, bool bRetreating = false)
{
    double AttackTotal = 0;
    int32 Reaching = 0;
    bool bPlantedReaches = false;
    for (int32 I = 0; I < Weights.Num(); ++I)
        if (IsApproach.IsValidIndex(I) && !IsApproach[I] && Weights[I] > 0.0)
        {
            AttackTotal += Weights[I];
            ++Reaching;
            bPlantedReaches |= IsPlanted.IsValidIndex(I) && IsPlanted[I];
        }
    const double Cap = bPlantedReaches ? 0.0 : AttackTotal * ApproachShare(Reaching) * (bRetreating ? 2.0 : 1.0);
    double Total = 0;
    for (int32 I = 0; I < Weights.Num(); ++I)
    {
        if (AttackTotal > 0.0 && IsApproach.IsValidIndex(I) && IsApproach[I]) Weights[I] = FMath::Min(Weights[I], Cap);
        Total += Weights[I];
    }
    return Total;
}

bool CanLinkTwoHit(float Distance, float Dot, float Min, float Max, bool bTargetAvailable)
{
    // A link is permission to prepare the next strike, not permission to hit.
    // A backwards roll may open a fresh, bounded step for the second jab.
    // This start permission does not enlarge the physical hand trace.
    return bTargetAvailable && FMath::IsFinite(Distance) && FMath::IsFinite(Dot)
        && Distance >= Min && Distance <= Max + 240.f && Dot >= 0.f;
}

bool LabMeasurementPolicy(const FString& LevelName, const FString& Source, bool bMeasurement)
{
    return bMeasurement && LevelName == TEXT("Lvl_BossMotionLab") && Source == TEXT("manual");
}

bool CanLinkMeasuredTwoHit(bool bMeasurement, bool bTargetAvailable, bool bCombatLink)
{
    return bTargetAvailable && (bMeasurement || bCombatLink);
}

// 디딤 시험 방식(모드 3)을 쓸 수 있는 행동: 1 왼손(0), 2 오른손(1), 3 어퍼컷(2), 5 잽잽훅(4).
bool IsLabStepAction(int32 ActionId)
{
    return ActionId == 0 || ActionId == 1 || ActionId == 2 || ActionId == 4;
}

// 행동별 디딤 시험 카드. 카드가 아직 없으면 호출부가 원래 모션을 그대로 쓴다.
const TCHAR* LabStepCardPath(int32 ActionId)
{
    switch (ActionId)
    {
    case 0: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RightFootPlant.DA_Lab_Left_RightFootPlant");
    case 1: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Right_RightFootStep.DA_Lab_Right_RightFootStep");
    case 2: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Uppercut_RunIn.DA_Lab_Uppercut_RunIn");
    case 4: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Combo_FootStep.DA_Lab_Combo_FootStep");
    default: return nullptr;
    }
}

// 같은 공격의 먼 쪽(약 500~600cm) 카드.
const TCHAR* FarStepCardPath(int32 ActionId)
{
    switch (ActionId)
    {
    case 0: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Left_RunInFar.DA_Lab_Left_RunInFar");
    case 1: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Right_RunInFar.DA_Lab_Right_RunInFar");
    case 2: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Uppercut_RunInFar.DA_Lab_Uppercut_RunInFar");
    case 4: return TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Combo_RunInFar.DA_Lab_Combo_RunInFar");
    default: return nullptr;
    }
}

// 모드 4: 훅 단독 시험(K키). 1번(왼손) 자리로 요청된 것을 훅 카드로 바꾼다.
const TCHAR* LabHookCardPath = TEXT("/Game/BossArena/Boss/AI/Actions/DA_Lab_Hook.DA_Lab_Hook");

bool LabRightFootPolicy(const FString& LevelName, const FString& Source, bool bRequestScope, int32 Mode, int32 ActionId)
{
    return LabMeasurementPolicy(LevelName, Source, true) && bRequestScope
        && ((Mode == 3 && IsLabStepAction(ActionId)) || (Mode == 4 && ActionId == 0));
}
}

bool UBossCombatIntentLibrary::IsLabRangeMeasurementAction(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    const UBossCombatIntentComponent* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    return Intent && LabMeasurementPolicy(UGameplayStatics::GetCurrentLevelName(Boss, true),
        Text(Boss, TEXT("AttackRequestSource")), Intent->bLabRangeMeasurementAction);
}

bool UBossCombatIntentLibrary::IsLabStartLimitOverride(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    const UBossCombatIntentComponent* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    // 뒤쪽 대응도 정면·거리 조건을 건너뛴다(거리와 쿨다운은 TryRearResponse가 직접 검사한다).
    return Intent && (Intent->bRearResponseScope || (Intent->bLabStartRequestScope && IsLabRangeMeasurementAction(Boss)));
}

void UBossCombatIntentLibrary::ConfigureLabRightFootPunch(AActor* Boss)
{
    if (!IsValid(Boss) || !StateIs(Boss, TEXT("Boss.Combat.Ready"))) return;
    const auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>();
    if (Intent && Intent->bRearResponseScope)
    {
        // 뒤쪽 대응의 훅: 왼손 자리로 요청된 것을 훅 카드로 바꾼다. 휩쓸기는 바꿀 카드가 없다.
        FObjectPropertyBase* ActiveCard = FindFProperty<FObjectPropertyBase>(Boss->GetClass(), TEXT("ActiveAction"));
        if (ActiveCard && Intent->RearCard.IsValid() && IsValid(Object(Intent->RearCard.Get(), TEXT("Montage"))))
        {
            ActiveCard->SetObjectPropertyValue_InContainer(Boss, Intent->RearCard.Get());
            SetFlag(Boss, TEXT("bPunchFootSync"), false);
            SetNumber(Boss, TEXT("AttackAdvanceBudget"), 0);
            SetText(Boss, TEXT("UtilityChoice"), Text(Intent->RearCard.Get(), TEXT("DisplayName")));
        }
        return;
    }
    const int32 ActionId = static_cast<int32>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("ActionId"), -1));
    const FString Level = UGameplayStatics::GetCurrentLevelName(Boss, true);
    const bool bLab = Level == TEXT("Lvl_BossMotionLab");
    // 실전: 공격이 시작되는 지금 거리가 단거리 버전으로 닿지 않으면 중거리 버전으로 바꾼다. 모션랩은 키로 고른 방식만 따른다.
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    if (!IsValid(Player)) Player = UGameplayStatics::GetPlayerPawn(Boss, 0);
    const float RawStart = IsValid(Player) ? FVector::Dist2D(Boss->GetActorLocation(), Player->GetActorLocation()) : 0.f;
    // 실전에서는 칠 때쯤의 거리로 모션을 고른다(물러나는 상대에게는 더 멀리 달려드는 모션).
    const float StartDistance = bLab || !Intent ? RawStart : PredictedDistance(RawStart, Intent->PlayerSpeedAway(), .8f);
    const bool bCombatMid = !bLab && IsValid(Player) && UsesMidVersion(ActionId, StartDistance);
    // 중거리 패턴을 골랐는데 그 사이 플레이어가 단거리 안으로 들어왔으면 제자리 모션으로 친다(가까이서 달려드는 걸음은 미끄러진다).
    if (!bLab && IsValid(Player) && !bCombatMid && StartDistance <= ShortVersionReach(ActionId)
        && IsMidPattern(ActionId, static_cast<float>(Number(Object(Boss, TEXT("ActiveAction")), TEXT("MinDistance")))))
    {
        UObject* Short = CardAtSlot(Boss, FindSlotByActionId(Boss, ActionId));
        FObjectPropertyBase* Current = FindFProperty<FObjectPropertyBase>(Boss->GetClass(), TEXT("ActiveAction"));
        if (IsValid(Short) && Current && IsValid(Object(Short, TEXT("Montage")))) Current->SetObjectPropertyValue_InContainer(Boss, Short);
        return;
    }
    if (!bCombatMid && (!Intent || !LabRightFootPolicy(Level,
        Text(Boss, TEXT("AttackRequestSource")), Intent->bLabStartRequestScope, Intent->MotionLabPunchMode,
        ActionId))) return;
    // 이 행동의 중거리 카드. 아직 만들지 않았으면 로드가 실패해 원래 모션이 그대로 재생된다.
    // 먼 쪽 버전은 실전과 모션랩(디딤 공격 방식) 모두 시작 거리로 고른다. 카드가 없으면 가까운 쪽 버전을 쓴다.
    const bool bHook = !bCombatMid && Intent->MotionLabPunchMode == 4;
    UObject* Card = !bHook && UsesFarVersion(ActionId, StartDistance)
        ? LoadObject<UObject>(nullptr, FarStepCardPath(ActionId), nullptr, LOAD_NoWarn) : nullptr;
    if (!IsValid(Card) || !IsValid(Object(Card, TEXT("Montage"))))
        Card = LoadObject<UObject>(nullptr, bHook ? LabHookCardPath : LabStepCardPath(ActionId), nullptr, LOAD_NoWarn);
    FObjectPropertyBase* Active = FindFProperty<FObjectPropertyBase>(Boss->GetClass(), TEXT("ActiveAction"));
    if (!IsValid(Card) || !IsValid(Object(Card, TEXT("Montage"))) || !Active) return;
    Active->SetObjectPropertyValue_InContainer(Boss, Card);
    // The new animation root owns travel. Do not also run the legacy manual step.
    SetFlag(Boss, TEXT("bPunchFootSync"), false);
    SetFlag(Boss, TEXT("bPunchFootSampleValid"), false);
    SetNumber(Boss, TEXT("AttackAdvanceBudget"), 0);
    SetNumber(Boss, TEXT("AttackAdvanceStepCount"), 0);
    SetText(Boss, TEXT("UtilityChoice"), Text(Card, TEXT("DisplayName")));
    if (bCombatMid) Invoke(Boss, TEXT("RecordCombatQA"), TEXT("mid_version"));
}

void UBossCombatIntentLibrary::EnsureActionCooldownCapacity(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    const FArrayProperty* Cooldowns = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("CooldownUntil"));
    if (!Actions || !Cooldowns) return;
    FScriptArrayHelper ActionValues(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
    FScriptArrayHelper CooldownValues(Cooldowns, Cooldowns->ContainerPtrToValuePtr<void>(Boss));
    if (CooldownValues.Num() < ActionValues.Num()) CooldownValues.Resize(ActionValues.Num());
}

void UBossCombatIntentLibrary::FinalizeIntentScores(AActor* Boss)
{
    if (!IsValid(Boss)) return;
    // 달리기 전환과 턴 맞추기는 이 컴포넌트의 Tick이 한다. 첫 판단 때부터 있도록 여기서 만든다.
    if (!Boss->FindComponentByClass<UBossCombatIntentComponent>())
    {
        auto* Created = NewObject<UBossCombatIntentComponent>(Boss, TEXT("CombatIntent"));
        Boss->AddInstanceComponent(Created);
        Created->RegisterComponent();
        Created->AddTickPrerequisiteActor(Boss);
    }
    const FArrayProperty* Scores = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("ActionWeights"));
    const FArrayProperty* Actions = FindFProperty<FArrayProperty>(Boss->GetClass(), TEXT("Actions"));
    if (!Scores || !Actions) return;
    const FNumericProperty* ScoreType = CastField<FNumericProperty>(Scores->Inner);
    const FObjectPropertyBase* ActionType = CastField<FObjectPropertyBase>(Actions->Inner);
    if (!ScoreType || !ScoreType->IsFloatingPoint() || !ActionType) return;
    FScriptArrayHelper Values(Scores, Scores->ContainerPtrToValuePtr<void>(Boss));
    FScriptArrayHelper Cards(Actions, Actions->ContainerPtrToValuePtr<void>(Boss));
    if (Values.Num() != Cards.Num()) return;
    TArray<double> Weights;
    TArray<bool> Approach, Planted;
    for (int32 I = 0; I < Values.Num(); ++I)
    {
        const UObject* Card = ActionType->GetObjectPropertyValue(Cards.GetRawPtr(I));
        const int32 Id = static_cast<int32>(Number(Card, TEXT("ActionId"), -1));
        Weights.Add(ScoreType->GetFloatingPointPropertyValue(Values.GetRawPtr(I)));
        Approach.Add(Id == 7);
        // 제자리에서 치는 공격: 발로 치는 공격 중 달려드는 패턴이 아닌 것(돌진·점프·접근 제외).
        Planted.Add(((Id >= 0 && Id <= 5) || Id == 9 || Id == OverheadId) && !IsMidPattern(Id, static_cast<float>(Number(Card, TEXT("MinDistance")))));
    }
    if (auto* Timed = Boss->FindComponentByClass<UBossCombatIntentComponent>())
        if (Timed->FirstDecisionAt < 0.0) Timed->FirstDecisionAt = UKismetSystemLibrary::GetGameTimeInSeconds(Boss);
    const AActor* Player = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    const bool bRetreating = IsValid(Player) && FVector::DotProduct(Player->GetVelocity(),
        (Player->GetActorLocation() - Boss->GetActorLocation()).GetSafeNormal2D()) >= RetreatSpeed;
    const double Total = FinalizeWeights(Weights, Approach, Planted, bRetreating);
    // 블루프린트의 선택 단계는 "가장 높은 점수"를 고른다(추첨값은 계산만 하고 쓰지 않았다). 그래서 감점이 돌아가는 순서대로
    // 왼손 -> 오른손 -> 어퍼컷이 똑같이 반복됐고, 점수가 낮은 휩쓸기와 연속기는 한 번도 나오지 않았다.
    // 여기서 점수 비율대로 추첨하고, 당첨된 카드의 점수만 잠깐 가장 높게 만들어 블루프린트가 그것을 고르게 한다.
    // 기록과 화면에는 진짜 점수를 남기고, 표시용 값은 다음 Tick에 되돌린다.
    const int32 Winner = WeightedPick(Weights, FMath::FRand());
    FString Summary;
    for (int32 I = 0; I < Values.Num(); ++I)
    {
        ScoreType->SetFloatingPointPropertyValue(Values.GetRawPtr(I), I == Winner ? Weights[I] + Total + 1.0 : Weights[I]);
        Summary += FString::Printf(TEXT("%s%d:%.2f"), I == 0 ? TEXT("") : TEXT(","), I, Weights[I]);
    }
    if (auto* Intent = Boss->FindComponentByClass<UBossCombatIntentComponent>())
    {
        Intent->TrueWeights = Weights;
        Intent->bRestoreWeights = Winner != INDEX_NONE;
    }
    SetNumber(Boss, TEXT("UtilityTotalScore"), Total);
    SetText(Boss, TEXT("IntentFinalScores"), Summary);
    // Per-candidate rows are before this pass; final weights are recorded separately.
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("intent_scores_finalized"));
}

bool UBossCombatIntentLibrary::ContinueTwoHitOrRecover(AActor* Boss)
{
    if (!IsValid(Boss)) return false;
    UObject* Action = Object(Boss, TEXT("ActiveAction"));
    const int32 Id = static_cast<int32>(Number(Action, TEXT("ActionId"), -1));
    if (Id != 4 && Id != 9) return true;
    if (Id == 4)
    {
        // Between strikes, prepare the next aim. Its step commits direction again.
        if (Number(Boss,TEXT("HitIndex")) < 2)
        {
            SetFlag(Boss,TEXT("bDirectionCommitted"),false);
            SetFlag(Boss,TEXT("bCanTurn"),true);
            Invoke(Boss,TEXT("RecordCombatQA"),TEXT("combo_next_strike_prepare"));
        }
        return true;
    }
    if (!StateIs(Boss, TEXT("Boss.Combat.Attack.Active")) || Number(Boss, TEXT("HitIndex")) != 0) return false;
    AActor* Target = Cast<AActor>(Object(Boss, TEXT("ObservedPlayer")));
    const bool bTargetAvailable = IsValid(Target) && Number(Target, TEXT("CurrentHealth")) > 0
        && !Flag(Target, TEXT("bKnockedDown"));
    const FVector Delta = IsValid(Target) ? Target->GetActorLocation() - Boss->GetActorLocation() : FVector::ZeroVector;
    if (CanLinkMeasuredTwoHit(IsLabRangeMeasurementAction(Boss), bTargetAvailable,
        CanLinkTwoHit(Delta.Size2D(), FVector::DotProduct(Boss->GetActorForwardVector(), Delta.GetSafeNormal2D()),
            Number(Action, TEXT("MinDistance")), Number(Action, TEXT("MaxDistance")), bTargetAvailable)))
    {
        SetFlag(Boss,TEXT("bDirectionCommitted"),false);
        SetFlag(Boss,TEXT("bCanTurn"),true);
        Invoke(Boss, TEXT("RecordCombatQA"), TEXT("two_hit_link_accepted"));
        return true;
    }
    if (!TransitionState(Boss, TEXT("Boss.Combat.Attack.Active"), TEXT("Boss.Combat.Attack.Recovery"), TEXT("2연타 연결 거리·방향 이탈: 왼손 회수"))) return false;
    UKismetSystemLibrary::K2_ClearTimer(Boss, TEXT("OpenActionImpact"));
    SetFlag(Boss, TEXT("bAttackStepActive"), false);
    SetFlag(Boss, TEXT("bPhysicalStrikeOpen"), false);
    Invoke(Boss, TEXT("StopBossLocomotion"));
    if (ACharacter* Character = Cast<ACharacter>(Boss))
        if (UAnimInstance* Anim = Character->GetMesh()->GetAnimInstance())
            if (UAnimMontage* Montage = Cast<UAnimMontage>(Object(Action, TEXT("Montage"))))
                if (Anim->Montage_IsPlaying(Montage) && Montage->GetSectionIndex(TEXT("AbortLeftRecovery")) != INDEX_NONE)
                    Anim->Montage_JumpToSection(TEXT("AbortLeftRecovery"), Montage);
    UKismetSystemLibrary::K2_SetTimer(Boss, TEXT("FinishCombatAction"), .85f, false);
    SetText(Boss, TEXT("IntentReason"), TEXT("다음 주먹 범위 이탈: 0.85초 회수 후 재판단"));
    Invoke(Boss, TEXT("RecordCombatQA"), TEXT("two_hit_link_aborted"));
    return false;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossRecoveryTurnTest,"Battle.Boss.RecoveryTurn",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossRecoveryTurnTest::RunTest(const FString& Parameters)
{
    TestFalse(TEXT("First half of the recovery keeps the punish window"), RecoveryMayTurn(.4f, 1.6f, .5f));
    TestTrue(TEXT("Second half may turn slowly"), RecoveryMayTurn(1.2f, .8f, .5f));
    TestFalse(TEXT("No recovery timer, no turn"), RecoveryMayTurn(1.f, 0.f, .5f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossGuardRewardTest,"Battle.Player.GuardReward",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossGuardRewardTest::RunTest(const FString& Parameters)
{
    TestTrue(TEXT("Guard raised just before the hit"), IsJustGuard(10.0, 10.2, .25f));
    TestFalse(TEXT("Guard held for a while is an ordinary block"), IsJustGuard(10.0, 10.6, .25f));
    TestFalse(TEXT("Never guarded"), IsJustGuard(-1.0, 10.0, .25f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossVarietyTest,"Battle.Boss.Variety",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossVarietyTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Recently used: no bonus"), StaleBonus(5.f), 1.f);
    TestEqual(TEXT("Unused for 20s: half way"), StaleBonus(20.f), 1.5f);
    TestEqual(TEXT("Unused for a long time: doubled, no more"), StaleBonus(90.f), 2.f);
    float Lo, Hi;
    TestEqual(TEXT("Sweep in its range"), NearestStartBand(3, 300.f, 170.f, 360.f, Lo, Hi), 0.f);
    TestEqual(TEXT("Sweep one step out"), NearestStartBand(3, 400.f, 170.f, 360.f, Lo, Hi), 40.f);
    TestEqual(TEXT("Uppercut between its versions: step in to the short one"), NearestStartBand(2, 330.f, 165.f, 295.f, Lo, Hi), 35.f);
    TestEqual(TEXT("...and the goal is the short band"), Hi, 295.f);
    TestEqual(TEXT("Uppercut where the stride is real: in range"), NearestStartBand(2, 400.f, 368.f, 650.f, Lo, Hi), 0.f);
    TestEqual(TEXT("...and the goal is the mid-range band"), Lo, 368.f);
    TestEqual(TEXT("Combo just past the hook: one step in"), NearestStartBand(4, 290.f, 0.f, 235.f, Lo, Hi), 55.f);
    TestTrue(TEXT("Combo far past its run-in: more than a step"), NearestStartBand(4, 640.f, 345.f, 510.f, Lo, Hi) > StepReach);
    TestTrue(TEXT("The run-in left punch is its own pattern"), IsMidPattern(0, 345.f) && !IsMidPattern(0, 165.f));
    TestFalse(TEXT("Attacks without a run-in have no mid pattern"), IsMidPattern(3, 400.f));
    TestEqual(TEXT("Run-in pattern in its range"), NearestStartBand(0, 450.f, 345.f, 650.f, Lo, Hi), 0.f);
    TestEqual(TEXT("Short pattern stops at its reach"), NearestStartBand(0, 400.f, 165.f, 344.f, Lo, Hi), 56.f);
    TestEqual(TEXT("One card covering both still works (motion lab)"), NearestStartBand(0, 450.f, 165.f, 650.f, Lo, Hi), 0.f);
    TestEqual(TEXT("Too close for a sweep: one step back"), NearestStartBand(3, 150.f, 170.f, 360.f, Lo, Hi), 20.f);
    TestEqual(TEXT("Being hit up close raises the sweep"), PressureBoost(3, 3, 200.f), 2.5f);
    TestEqual(TEXT("A couple of hits is not pressure"), PressureBoost(3, 2, 200.f), 1.f);
    TestEqual(TEXT("Pressure is a close-range idea"), PressureBoost(3, 5, 400.f), 1.f);
    TestEqual(TEXT("Main punches are not pressure answers"), PressureBoost(0, 5, 200.f), 1.f);
    TestEqual(TEXT("Combo without dodges: a small share"), ComboShare(0), .3f);
    TestEqual(TEXT("Combo after three dodges: full"), ComboShare(3), 1.f);
    {
        const auto All = [](int32, bool) { return true; };
        const auto Flat = []() { return 0.f; };
        TArray<FStringStep> Plan = PlanAttackString(250.f, 0.f, 2, 0, {0}, All, Flat);
        TestEqual(TEXT("Left, two more: a flowing hit, then a finisher"), Plan.Num(), 2);
        TestTrue(TEXT("... right hand next, then a big hit to end"), Plan.Num() == 2 && Plan[0].Id == 1 && IsFinisher(Plan[1].Id));
        Plan = PlanAttackString(250.f, 0.f, 1, 0, {0}, All, Flat);
        TestTrue(TEXT("Left, one more: the uppercut ends it"), Plan.Num() == 1 && Plan[0].Id == 2);
        Plan = PlanAttackString(250.f, 0.f, 1, 1, {1}, All, Flat);
        TestTrue(TEXT("Right, one more: the overhead with the same hand"), Plan.Num() == 1 && Plan[0].Id == OverheadId);
        Plan = PlanAttackString(480.f, 0.f, 2, 0, {0}, All, Flat);
        TestTrue(TEXT("Player backed off: run in with the other hand, then finish in place"),
            Plan.Num() == 2 && Plan[0].bRunIn && Plan[0].Id == 1 && !Plan[1].bRunIn && IsFinisher(Plan[1].Id));
        Plan = PlanAttackString(250.f, 90.f, 1, 0, {0}, All, Flat);
        TestTrue(TEXT("Player at the side: only a planted hit can pivot to them"), Plan.Num() == 1 && !Plan[0].bRunIn);
        Plan = PlanAttackString(480.f, 90.f, 2, 0, {0}, All, Flat);
        TestEqual(TEXT("Far and at the side: nothing links"), Plan.Num(), 0);
        Plan = PlanAttackString(700.f, 0.f, 2, 0, {0}, All, Flat);
        TestEqual(TEXT("Out of every reach: nothing links"), Plan.Num(), 0);
        Plan = PlanAttackString(250.f, 0.f, 2, 0, {0}, [](int32 Id, bool) { return Id == 3; }, Flat);
        TestTrue(TEXT("Only the sweep is off cooldown: a shorter string"), Plan.Num() == 1 && Plan[0].Id == 3);
        Plan = PlanAttackString(250.f, 0.f, 1, 9, {9}, All, Flat);
        TestTrue(TEXT("Two-hit ends in the sweep"), Plan.Num() == 1 && Plan[0].Id == 3);
    }
    TestEqual(TEXT("Jab-jab-hook is already a string"), ChooseStringLength(4, 0.f, .4f, .25f), 1);
    TestEqual(TEXT("A big hit stands alone"), ChooseStringLength(2, 0.f, .4f, .25f), 1);
    TestEqual(TEXT("Left can open three"), ChooseStringLength(0, .1f, .4f, .25f), 3);
    TestEqual(TEXT("Left can open two"), ChooseStringLength(0, .5f, .4f, .25f), 2);
    TestEqual(TEXT("Left can stay single"), ChooseStringLength(0, .9f, .4f, .25f), 1);
    TestEqual(TEXT("Two-hit takes at most one more"), ChooseStringLength(9, .1f, .4f, .25f), 2);
    TestEqual(TEXT("First link uses the full chance"), ChainLinkChance(.5f, 0), .5f);
    TestEqual(TEXT("A chained attack links again half as often"), ChainLinkChance(.5f, 1), .25f);
    TestEqual(TEXT("Three in a row is the limit"), ChainLinkChance(.5f, 2), 0.f);
    TestEqual(TEXT("A lone attack keeps the shortened recovery"), RecoveryScaleFor(0, .7f, 1.f), .7f);
    TestEqual(TEXT("A linked attack pays the full recovery"), RecoveryScaleFor(1, .7f, 1.f), 1.f);
    TestTrue(TEXT("Player out of punishing range in front: drop the recovery and chase"), PursuitHolds(450.f, .9f, false, 360.f));
    TestFalse(TEXT("Player close enough to punish: the recovery stands"), PursuitHolds(250.f, .9f, false, 360.f));
    TestFalse(TEXT("No chase on a downed player"), PursuitHolds(450.f, .9f, true, 360.f));
    TestFalse(TEXT("No chase when the player is behind"), PursuitHolds(450.f, 0.f, false, 360.f));
    TestTrue(TEXT("Small angle: step instead of turning in place"), FacingStepWanted(45.f, 32.f, 70.f));
    TestFalse(TEXT("Big angle: the turn animation"), FacingStepWanted(110.f, 32.f, 70.f));
    TestFalse(TEXT("Nearly facing: nothing to do"), FacingStepWanted(10.f, 32.f, 70.f));
    TestTrue(TEXT("Bow peaks near the asked angle"), FMath::IsNearlyEqual(BowKick(10.f) / (2.71828f * FMath::Sqrt(BowStiffness)), 10.f, .01f));
    TestTrue(TEXT("Backing off at a walk counts as retreating"), IsRetreating(300.f));
    TestFalse(TEXT("Standing is not retreating"), IsRetreating(20.f));
    TestEqual(TEXT("Overhead in range"), NearestStartBand(OverheadId, 250.f, 165.f, 285.f, Lo, Hi), 0.f);
    TestEqual(TEXT("Trail holds right after a hit"), TrailToward(.8f, .6f, .2f, .1f), .8f);
    TestTrue(TEXT("Trail then falls toward health"), TrailToward(.8f, .6f, 1.f, .1f) < .8f);
    TestEqual(TEXT("Trail never drops below health"), TrailToward(.61f, .6f, 1.f, .5f), .6f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossActingTest,"Battle.Boss.Acting",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossActingTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("No look while winding up or striking"), LookWeight(true, false, 0, .25f, false, true), 0.f);
    TestEqual(TEXT("Early recovery: frozen"), LookWeight(false, true, .1f, .25f, false, true), 0.f);
    TestEqual(TEXT("Later recovery: the head follows"), LookWeight(false, true, .5f, .25f, false, true), 1.f);
    TestEqual(TEXT("Neutral: follows"), LookWeight(false, false, 0, .25f, false, true), 1.f);
    TestEqual(TEXT("Turn animation owns the body"), LookWeight(false, false, 0, .25f, true, true), 0.f);
    TestEqual(TEXT("Clamped to what a neck can do"), LookTarget(100.f, 70.f, 1.f), 70.f);
    TestEqual(TEXT("Player behind: face forward"), LookTarget(160.f, 70.f, 1.f), 0.f);
    TestEqual(TEXT("Weight scales the look"), LookTarget(40.f, 70.f, 0.f), 0.f);
    FVector Offset = FVector::ZeroVector, Velocity(420.f, 0.f, 0.f);
    float Peak = 0.f;
    for (int32 I = 0; I < 120; ++I) { StepFlinch(Offset, Velocity, 1.f / 60.f); Peak = FMath::Max(Peak, static_cast<float>(Offset.X)); TestTrue(TEXT("Flinch never swings past rest"), Offset.X > -.01); }
    TestTrue(TEXT("Flinch is a small shove"), Peak > 6.f && Peak < 12.f);
    TestTrue(TEXT("...and settles within two seconds"), Offset.Size() < .1f);
    TestEqual(TEXT("Far player: taunt"), ChoosePerformance(900, false, false, true, 800), 1);
    TestEqual(TEXT("Taunt on cooldown"), ChoosePerformance(900, false, false, false, 800), 0);
    TestEqual(TEXT("Near player: no taunt"), ChoosePerformance(400, false, false, true, 800), 0);
    TestEqual(TEXT("Knocked-down player: laugh once"), ChoosePerformance(300, true, false, false, 800), 2);
    TestEqual(TEXT("...only once per knockdown"), ChoosePerformance(300, true, true, true, 800), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossFootworkTest,"Battle.Boss.Footwork",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossFootworkTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("One attack, room to breathe: mostly keeps punching"), FootworkChance(1, false, false, .7f), .25f);
    TestEqual(TEXT("Crowded raises it"), FootworkChance(1, true, false, .7f), .45f);
    TestEqual(TEXT("Three planted attacks: almost always moves"), FootworkChance(3, false, false, .7f), .85f);
    TestEqual(TEXT("Never certain"), FootworkChance(5, true, false, .7f), .9f);
    TestTrue(TEXT("Phase two rests less"), FootworkChance(2, true, true, .7f) < FootworkChance(2, true, false, .7f));
    TestTrue(TEXT("Player in front and near"), FootworkAllowed(180, 1, 460, 0));
    TestFalse(TEXT("Far player: approach instead"), FootworkAllowed(500, 1, 460, 0));
    TestFalse(TEXT("Player behind: turning comes first"), FootworkAllowed(180, 0, 460, 0));
    TestFalse(TEXT("Guarding player: break the guard, do not dance"), FootworkAllowed(180, 1, 460, 2.5f));
    float Left, Right;
    FootworkSideCosts(200, .1f, Left, Right);
    TestTrue(TEXT("Player circling to the boss's right: step right to cut off"), Right < Left);
    FootworkSideCosts(-200, .9f, Left, Right);
    TestTrue(TEXT("Player circling left: step left"), Left < Right);
    FootworkSideCosts(0, .1f, Left, Right);
    const float StillLeft = Left;
    FootworkSideCosts(0, .9f, Left, Right);
    TestTrue(TEXT("Standing player: the side varies"), StillLeft != Left);

    const auto Crowded = ChooseFootworkWants(172, 200, 300, .1f);
    TestTrue(TEXT("Crowded, low roll: just make room"), Crowded.bSpace && !Crowded.bAngle && !Crowded.bPocket);
    TestTrue(TEXT("Crowded, higher roll: room and angle"), ChooseFootworkWants(172, 200, 300, .5f).bAngle);
    TestTrue(TEXT("In the pocket: only the angle"), !ChooseFootworkWants(260, 200, 300, .1f).bSpace && ChooseFootworkWants(260, 200, 300, .1f).bAngle);
    TestTrue(TEXT("Out of the pocket: always walks in"), ChooseFootworkWants(400, 200, 300, .1f).bPocket);
    TestTrue(TEXT("Out of the pocket, higher roll: walks in on an angle"), ChooseFootworkWants(400, 200, 300, .7f).bAngle);

    using A = EBossPositionAction;
    TestTrue(TEXT("Step back ends at the comfort distance"), FootworkLegDone(A::StepBack, 255, 0, 0, 260, 240, .2f));
    TestFalse(TEXT("Step back continues while still crowded"), FootworkLegDone(A::StepBack, 200, 0, 0, 260, 240, .2f));
    TestTrue(TEXT("Walking in stops short of the player"), FootworkLegDone(A::DirectApproach, 238, 0, 0, 260, 240, .2f));
    TestTrue(TEXT("Circle ends at its sweep"), FootworkLegDone(A::OrbitLeft, 260, 41, 40, 260, 240, .2f));
    TestTrue(TEXT("Every leg times out"), FootworkLegDone(A::OrbitRight, 260, 5, 40, 260, 240, 1.6f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossUtilityPenaltyTest,"Battle.Boss.UtilityPenalty",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossUtilityPenaltyTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Never used, not the last one: no penalty"), StrongestPenalty(false, -1.f, -1.f), 1.f);
    TestEqual(TEXT("Just used: only the strongest penalty applies, not their product"), StrongestPenalty(true, 0.f, 0.f), RecentUseFloor);
    TestEqual(TEXT("The other punch right after a punch: the family penalty"), StrongestPenalty(false, -1.f, 0.f), PunchFamilyFloor);
    TestEqual(TEXT("Recent use recovers linearly"), StrongestPenalty(false, 6.f, -1.f), .675f);
    TestEqual(TEXT("Long ago: nothing left"), StrongestPenalty(false, 20.f, 20.f), 1.f);
    TestEqual(TEXT("A low roll picks the first candidate"), WeightedPick({30,24,0,12}, 0.0), 0);
    TestEqual(TEXT("The roll walks the cumulative weights"), WeightedPick({30,24,0,12}, .6), 1);
    TestEqual(TEXT("Low-scored cards can win"), WeightedPick({30,24,0,12}, .95), 3);
    TestEqual(TEXT("Zero-scored cards never win"), WeightedPick({0,24,0,0}, .99), 1);
    TestEqual(TEXT("No candidate, no pick"), WeightedPick({0,0}, .5), static_cast<int32>(INDEX_NONE));
    TArray<double> Chased = {20,88,0};
    TestEqual(TEXT("A retreating player doubles the approach share"), FinalizeWeights(Chased, {false,true,false}, {false,false,false}, true), 80.0);
    TestEqual(TEXT("Standing player: nothing to predict"), PredictedDistance(450.f, 0.f, .8f), 450.f);
    TestEqual(TEXT("Walking back: aim further"), PredictedDistance(450.f, 300.f, 1.f), 660.f);
    TestEqual(TEXT("A dodge's burst of speed cannot push the guess past the cap"), PredictedDistance(450.f, 900.f, 1.f), 670.f);
    TestEqual(TEXT("Coming in: aim closer"), PredictedDistance(450.f, -200.f, 1.f), 310.f);
    TestEqual(TEXT("One whiff lowers the attack"), OutcomeScale(1, false, 0.f), .7f);
    TestEqual(TEXT("Two in a row lower it more"), OutcomeScale(2, false, 0.f), .45f);
    TestEqual(TEXT("The memory fades in 20 seconds"), OutcomeScale(2, false, 20.f), 1.f);
    TestEqual(TEXT("A hit raises the attack"), OutcomeScale(0, true, 0.f), 1.25f);
    TestEqual(TEXT("A block is neither"), OutcomeScale(0, false, 0.f), 1.f);
    TestEqual(TEXT("Never used: no memory"), OutcomeScale(0, false, -1.f), 1.f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossRearResponseTest,"Battle.Boss.RearResponse",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossRearResponseTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Player in front: no rear response"), ChooseRearResponse(.9f, 200.f, 0.f, 0.f, 1.f), 0);
    TestEqual(TEXT("Behind and close: hook or sweep"), ChooseRearResponse(-.8f, 200.f, 0.f, .2f, 1.f), 1);
    TestEqual(TEXT("Behind and close, other pick: sweep"), ChooseRearResponse(-.8f, 200.f, 0.f, .8f, 1.f), 2);
    TestEqual(TEXT("Behind but past the hook's reach: sweep only"), ChooseRearResponse(-.8f, 300.f, 0.f, .2f, 1.f), 2);
    TestEqual(TEXT("Behind but too far: turn as before"), ChooseRearResponse(-.8f, 450.f, 0.f, .2f, 1.f), 0);
    TestEqual(TEXT("The chance roll can decline"), ChooseRearResponse(-.8f, 200.f, .7f, .2f, .6f), 0);
    TestEqual(TEXT("Rear turn arrives just before the hit"), RearTurnSpeedFor(130.f, .8f, 300.f), 200.f);
    TestEqual(TEXT("Rear turn never exceeds its cap"), RearTurnSpeedFor(170.f, .4f, 300.f), 300.f);
    TestEqual(TEXT("A half turn takes its angle over the turn speed"), TurnDuration(130.f, 130.f), 1.f);
    TestEqual(TEXT("Small turns are not instant"), TurnDuration(40.f, 130.f), .55f);
    TestEqual(TEXT("A full about-face is capped"), TurnDuration(180.f, 100.f), 1.6f);
    TestEqual(TEXT("Sprint plays at the speed it travels"), SprintPlayRate(760.f, 892.f), 760.f / 892.f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossTravelScaleTest,"Battle.Boss.TravelScale",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossTravelScaleTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Farthest start uses the whole authored travel"), TravelScale(510.f, 177.f), 1.f);
    TestEqual(TEXT("Half the needed distance, half the travel"), TravelScale(TravelStopDistance + 50.f, 100.f), .5f);
    TestEqual(TEXT("Already close: stay"), TravelScale(180.f, 177.f), 0.f);
    TestEqual(TEXT("No authored travel leaves the scale alone"), TravelScale(300.f, 0.f), 1.f);
    TestEqual(TEXT("Room for the whole stride: stop closer rather than shorten it"), AdaptiveStop(400.f, 177.f, 300.f), 223.f);
    TestEqual(TEXT("...so the stride plays in full"), TravelScale(400.f, 177.f, AdaptiveStop(400.f, 177.f, 300.f)), 1.f);
    TestEqual(TEXT("Never closer than the minimum"), AdaptiveStop(345.f, 177.f, 300.f), MinTravelStop);
    TestEqual(TEXT("Far start keeps the authored stop"), AdaptiveStop(520.f, 177.f, 300.f), 300.f);
    TestEqual(TEXT("An earlier hit stops farther out, leaving the next hit room to step"), TravelScale(330.f, 100.f, 280.f), .5f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossLabRightFootPolicyTest,"Battle.MotionLab.RightFootPunchPolicy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossLabRightFootPolicyTest::RunTest(const FString& Parameters)
{
    TestTrue(TEXT("Scoped manual left punch uses the new lab motion"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,3,0));
    TestFalse(TEXT("Arena is unchanged"), LabRightFootPolicy(TEXT("Lvl_Arena_01"),TEXT("manual"),true,3,0));
    TestFalse(TEXT("Other modes retain their motion"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,2,0));
    TestTrue(TEXT("Scoped manual right punch uses its step motion"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,3,1));
    TestTrue(TEXT("Scoped manual jab-jab-hook uses its step motion"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,3,4));
    TestFalse(TEXT("Other actions are unchanged"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,3,3));
    TestTrue(TEXT("Hook-only request rides the left punch slot"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,4,0));
    TestFalse(TEXT("Hook-only request does not touch other slots"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,4,1));
    TestTrue(TEXT("Scoped manual uppercut uses its ducking entry"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),true,3,2));
    TestEqual(TEXT("Each step action has its own card"), FString(LabStepCardPath(1)).Contains(TEXT("DA_Lab_Right_RightFootStep")), true);
    TestFalse(TEXT("Automatic choice is unchanged"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("utility"),true,3,0));
    TestFalse(TEXT("Permission cannot persist beyond the request"), LabRightFootPolicy(TEXT("Lvl_BossMotionLab"),TEXT("manual"),false,3,0));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossLabMeasurementPolicyTest,"Battle.MotionLab.RangeMeasurementPolicy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossLabMeasurementPolicyTest::RunTest(const FString& Parameters)
{
    TestTrue(TEXT("Manual lab measurement permits range sampling"), LabMeasurementPolicy(TEXT("Lvl_BossMotionLab"), TEXT("manual"), true));
    TestFalse(TEXT("Arena retains its combat limits"), LabMeasurementPolicy(TEXT("Lvl_Arena_01"), TEXT("manual"), true));
    TestFalse(TEXT("Similar map name does not authorize measurement"), LabMeasurementPolicy(TEXT("Lvl_BossMotionLab_Copy"), TEXT("manual"), true));
    TestFalse(TEXT("Automatic choices retain their limits"), LabMeasurementPolicy(TEXT("Lvl_BossMotionLab"), TEXT("utility"), true));
    TestFalse(TEXT("Combat check mode retains limits"), LabMeasurementPolicy(TEXT("Lvl_BossMotionLab"), TEXT("manual"), false));
    TestTrue(TEXT("Measurement continues distant two-hit animation"), CanLinkMeasuredTwoHit(true, true, false));
    TestFalse(TEXT("Combat still aborts an invalid link"), CanLinkMeasuredTwoHit(false, true, false));
    TestFalse(TEXT("Measurement cannot link to unavailable target"), CanLinkMeasuredTwoHit(true, false, false));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossLabPunchModeTest,"Battle.MotionLab.PunchModes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossLabPunchModeTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Combat mode preserves requested step"),ApplyLabPunchMode(true,0,80,145),80.f);
    TestEqual(TEXT("Basic fixture suppresses body travel"),ApplyLabPunchMode(true,1,80,145),0.f);
    TestEqual(TEXT("Single-step fixture requests full finite step"),ApplyLabPunchMode(true,2,80,145),145.f);
    TestEqual(TEXT("Remaining budget still bounds forced step"),ApplyLabPunchMode(true,2,80,40),40.f);
    TestEqual(TEXT("Forced mode cannot override fight-map movement"),ApplyLabPunchMode(false,1,80,145),80.f);
    TestEqual(TEXT("Forced step cannot leak into fight map"),ApplyLabPunchMode(false,2,80,145),80.f);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossDesignerDistanceBandTest, "Battle.GOAP.DesignerDistanceBands",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossDesignerDistanceBandTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Close punch preserves source step"), OnePunchStep(175,66,450), 66.f);
    TestEqual(TEXT("Below single-step band preserves source travel"), OnePunchStep(299,87,0),87.f);
    TestEqual(TEXT("300cm uses the accepted lab step"), OnePunchStep(300,66,0),145.f);
    TestEqual(TEXT("350cm uses the accepted lab step"), OnePunchStep(350,87,0),145.f);
    TestEqual(TEXT("400cm has finite one-step travel"), OnePunchStep(400,66,0),145.f);
    TestEqual(TEXT("Retreat cannot extend step past cap"), OnePunchStep(400,66,650),145.f);
    TestEqual(TEXT("Invalid geometry cannot move"), OnePunchStep(std::numeric_limits<float>::quiet_NaN(),66,0),0.f);
    TestEqual(TEXT("Punch with a mid-range version stays a candidate through mid range"), DistanceBandMultiplier(0,599),1.f);
    TestEqual(TEXT("650cm ends mid range"), DistanceBandMultiplier(0,650),0.f);
    TestEqual(TEXT("Just inside the end of mid range"), DistanceBandMultiplier(0,640),1.f);
    TestEqual(TEXT("Uppercut in reach of the short version"), DistanceBandMultiplier(2,290),1.f);
    TestEqual(TEXT("Uppercut between the versions: would whiff or slide, so not chosen"), DistanceBandMultiplier(2,330),0.f);
    TestEqual(TEXT("Uppercut where the stride is real"), DistanceBandMultiplier(2,400),1.f);
    TestEqual(TEXT("Combo up close: all three land planted"), DistanceBandMultiplier(4,230),1.f);
    TestEqual(TEXT("Combo just outside the hook: not chosen"), DistanceBandMultiplier(4,300),0.f);
    TestEqual(TEXT("Combo with a run-in"), DistanceBandMultiplier(4,450),1.f);
    TestEqual(TEXT("Combo too far for the later hits"), DistanceBandMultiplier(4,560),0.f);
    TestFalse(TEXT("Left punch at 344cm: short version still reaches"), UsesMidVersion(0,344));
    TestTrue(TEXT("Left punch at 345cm: mid-range version"), UsesMidVersion(0,345));
    TestTrue(TEXT("Right punch switches at 325cm"), UsesMidVersion(1,325) && !UsesMidVersion(1,324));
    TestFalse(TEXT("Sweep has no mid-range version"), UsesMidVersion(3,500));
    TestFalse(TEXT("Two-hit has no mid-range version"), UsesMidVersion(9,400));
    TestTrue(TEXT("Single punches start directly anywhere in mid range"), MidVersionReach(0) >= 600.f && MidVersionReach(2) >= 590.f);
    TestTrue(TEXT("Left punch: near version below 500cm, far version from 500cm"), !UsesFarVersion(0,499) && UsesFarVersion(0,500));
    TestFalse(TEXT("No far version without a mid-range version"), UsesFarVersion(3,580) || UsesFarVersion(9,580));
    TestTrue(TEXT("Every far card has a path"), FarStepCardPath(0) && FarStepCardPath(1) && FarStepCardPath(2) && FarStepCardPath(4));
    TestTrue(TEXT("A stride at the switch distance uses most of itself"), TravelScale(345.f, 177.f, AdaptiveStop(345.f, 177.f, 300.f)) > .8f);
    TestTrue(TEXT("Combo hit strides when the player backed off"), ComboStageStrides(400.f, 225.f, 215.f));
    TestFalse(TEXT("Combo hit stays planted when the player is in reach"), ComboStageStrides(250.f, 225.f, 215.f));
    TestEqual(TEXT("Combo stage by montage time"), ComboStageAt(.3f) * 100 + ComboStageAt(2.f) * 10 + ComboStageAt(3.2f), 12);
    TestEqual(TEXT("500cm stops two-hit entry"), DistanceBandMultiplier(9,500),0.f);
    TestEqual(TEXT("Dash candidate retains its own eligibility"), DistanceBandMultiplier(6,500),1.f);
    TestFalse(TEXT("Phase one never executes pending slam"), PendingSlamRange(true,false,1000,1000,5000));
    TestFalse(TEXT("Close phase entry does not force jump"), PendingSlamRange(true,true,175,1000,5000));
    TestFalse(TEXT("Below jump band remains normal combat"), PendingSlamRange(true,true,999,1000,5000));
    TestTrue(TEXT("Phase two 1000cm can start pending jump"), PendingSlamRange(true,true,1000,1000,5000));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossPostAttackProbeTest, "Battle.GOAP.PostAttackProbe",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossPostAttackProbeTest::RunTest(const FString& Parameters)
{
    const auto Choose = [](int32 Id, float Distance, bool Fresh, bool Cooldown, float Roll)
    { return ChoosePostAttackProbe(Id, Distance, 0, 350, 1, Fresh, Cooldown, Roll, .25f); };
    TestTrue(TEXT("Ordinary next punch may prepare with a side step"), Choose(0, 250, true, true, .1f));
    TestFalse(TEXT("Not every eligible attack probes"), Choose(1, 250, true, true, .25f));
    TestFalse(TEXT("Expired post-attack choice stays direct"), Choose(0, 250, false, true, 0));
    TestFalse(TEXT("Probe cooldown is respected"), Choose(0, 250, true, false, 0));
    TestFalse(TEXT("Close pressure does not force retreat"), Choose(0, 173, true, true, 0));
    TestFalse(TEXT("Far target still needs attack entry"), Choose(0, 500, true, true, 0));
    TestFalse(TEXT("Guard break is not delayed by decorative movement"), Choose(5, 250, true, true, 0));
    TestTrue(TEXT("Two-hit intention can use the same preparation"), Choose(9, 250, true, true, 0));
    TestFalse(TEXT("Rear target must turn first"), ChoosePostAttackProbe(0, 250, 0, 350, -.5f, true, true, 0, .25f));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossIntentFailureTest, "Battle.GOAP.IntentFailureReassessment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossIntentFailureTest::RunTest(const FString& Parameters)
{
    int32 Count = 0;
    double Last = -1;
    TestFalse(TEXT("One failed entry can retry"), RecordEntryFailure(Count, Last, 1, 6));
    TestTrue(TEXT("Second recent failure breaks pursuit"), RecordEntryFailure(Count, Last, 3, 6));
    TestFalse(TEXT("Observation starts a new failure pair"), RecordEntryFailure(Count, Last, 4, 6));
    TestFalse(TEXT("Old failure expires"), RecordEntryFailure(Count, Last, 11, 6));
    TestTrue(TEXT("Window includes boundary"), RecordEntryFailure(Count, Last, 17, 6));
    Count = 0; Last = -1; // Successful attack entry resets the episode.
    TestFalse(TEXT("Success prevents old failures triggering observation"), RecordEntryFailure(Count, Last, 18, 6));
    TestFalse(TEXT("Clock reset cannot carry failures into a new world"), RecordEntryFailure(Count, Last, 0, 6));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossSideEntryGeometryTest, "Battle.GOAP.SideEntryGeometry",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossSideEntryGeometryTest::RunTest(const FString& Parameters)
{
    const FVector Boss(500, 0, 200), Player(0, 0, 96);
    const FVector Left = LateralEntryGoal(Boss, Player, 270, 20);
    const FVector Right = LateralEntryGoal(Boss, Player, 270, -20);
    TestTrue(TEXT("Left keeps attack radius"), FMath::IsNearlyEqual(FVector::Dist2D(Left, Player), 270.f, .01f));
    TestTrue(TEXT("Right keeps attack radius"), FMath::IsNearlyEqual(FVector::Dist2D(Right, Player), 270.f, .01f));
    TestTrue(TEXT("Sides lie on opposite tangents"), Left.Y > 0 && Right.Y < 0);
    TestTrue(TEXT("Actor center height stays with boss, not player"), Left.Z == Boss.Z && Right.Z == Boss.Z);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossIntentChoiceTest, "Battle.GOAP.IntentChoiceAndLink",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossIntentChoiceTest::RunTest(const FString& Parameters)
{
    const TArray<bool> IsRun{false, true, false, false};
    TArray<double> LaterAttack{0, 88, 20};
    TestEqual(TEXT("A planted attack in reach removes the approach"), FinalizeWeights(LaterAttack, IsRun, {false,false,true}), 20.0);
    TestEqual(TEXT("Approach removed after all candidates"), LaterAttack[1], 0.0);
    TArray<double> EarlierAttack{20,88,0};
    TestEqual(TEXT("Candidate order does not change total"), FinalizeWeights(EarlierAttack, IsRun, {true,false,false}), 20.0);
    TArray<double> NoAttack{0,88,0};
    TestEqual(TEXT("Nothing reaches: the whole approach stays"), FinalizeWeights(NoAttack, IsRun, {false,false,false}), 88.0);
    TArray<double> OneRunIn{20,88,0};
    TestEqual(TEXT("Only one run-in attack reaches: approach stays likely"), FinalizeWeights(OneRunIn, IsRun, {false,false,false}), 50.0);
    TArray<double> ThreeRunIns{20,88,20,20};
    TestEqual(TEXT("Three run-in attacks reach: approach is rare"), FinalizeWeights(ThreeRunIns, IsRun, {false,false,false,false}), 69.0);
    TestTrue(TEXT("Valid front link"), CanLinkTwoHit(285, 1, 0, 285, true));
    TestTrue(TEXT("A backwards roll allows the next strike to prepare"), CanLinkTwoHit(500, 1, 0, 285, true));
    TestTrue(TEXT("Finite follow-up allowance boundary"), CanLinkTwoHit(525, 0, 0, 285, true));
    TestFalse(TEXT("Too far aborts"), CanLinkTwoHit(526, 1, 0, 285, true));
    TestFalse(TEXT("Behind aborts"), CanLinkTwoHit(200, -.01f, 0, 285, true));
    TestFalse(TEXT("Unavailable target aborts"), CanLinkTwoHit(200, 1, 0, 285, false));
    TestFalse(TEXT("Inside minimum aborts"), CanLinkTwoHit(100, 1, 150, 285, true));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBossComboFollowStepTest,"Battle.Combat.ComboFollowStep",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBossComboFollowStepTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Close contact does not add forward travel"),ComboFollowStep(175,65,450),0.f);
    TestEqual(TEXT("Short retreat has a finite velocity allowance"),ComboFollowStep(300,65,450),86.f);
    TestEqual(TEXT("Backwards roll can request a fresh jab step"),ComboFollowStep(500,65,450),180.f);
    TestEqual(TEXT("Retreat speed cannot extend the bound"),ComboFollowStep(700,65,1000),180.f);
    TestEqual(TEXT("Invalid target geometry cannot request travel"),ComboFollowStep(std::numeric_limits<float>::quiet_NaN(),65,0),0.f);
    return true;
}
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
