#pragma once
#include "CoreMinimal.h"
#include "Widgets/SLeafWidget.h"

/**
 * 보스 AI를 처음 보는 사람이 한눈에 읽는 화면 표시. 세 시스템을 질문 하나씩으로 나눠 보여준다.
 *   왼쪽  HFSM   "지금 무엇을 하고 있나"  : 단계 여섯 칸 중 지금 칸, 이번 몰아치기의 진행
 *                GOAP   "어떻게 할 것인가"     : 지금의 계획 한 줄
 *   오른쪽 Utility "무엇을 고를 것인가"     : 마지막 판단의 후보와 점수 막대, 뽑힌 것
 */
class BATTLEBOSSPLANNING_API SBossAIPanel : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SBossAIPanel) {}
    SLATE_END_ARGS()
    void Construct(const FArguments& InArgs);
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(1280., 720.); }

    struct FScore { FText Label; float Value = 0.f; bool bPicked = false; };
    int32 Stage = -1;            // 0 선택, 1 이동, 2 준비, 3 타격, 4 후딜(닫힘), 5 후딜(열림). -1이면 표시하지 않는다
    FText Reason;                // 지금 단계의 이유 한 줄
    int32 StringDone = 0;        // 이번 몰아치기에서 친 공격 수
    int32 StringWanted = 1;      // 치려는 공격 수
    FText StringText;            // 친 공격들의 이름
    FText Plan;                  // GOAP의 지금 계획
    FText Distance;              // 거리와 예상 거리
    TArray<FScore> Scores;       // 점수가 높은 순서
    float Opacity = 0.f;
};
