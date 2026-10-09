#pragma once
#include "CoreMinimal.h"
#include "Widgets/SLeafWidget.h"

/** 화면 아래 가운데의 보스 체력 바. 이름, 붉은 체력, 방금 깎인 만큼 잠깐 남는 노란 띠, 방금 준 피해 숫자. */
class BATTLEBOSSPLANNING_API SBossHealthBar : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SBossHealthBar) {}
    SLATE_END_ARGS()
    void Construct(const FArguments& InArgs);
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(1280., 720.); }

    FText Name;
    float Health = 1.f;         // 0..1
    float Trail = 1.f;          // 0..1, 체력보다 늦게 따라 내려온다
    float RecentDamage = 0.f;   // 최근 연속으로 준 피해의 합. 0이면 숫자를 그리지 않는다
    float Opacity = 0.f;        // 0..1
    FText Notice;               // 바 위 가운데에 잠깐 뜨는 알림(가드 반격 등)
    float NoticeOpacity = 0.f;  // 0..1
};
