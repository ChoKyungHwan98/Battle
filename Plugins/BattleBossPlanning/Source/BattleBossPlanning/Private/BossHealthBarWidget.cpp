#include "BossHealthBarWidget.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"

void SBossHealthBar::Construct(const FArguments& InArgs)
{
    SetVisibility(EVisibility::HitTestInvisible);
    SetCanTick(false);
}

int32 SBossHealthBar::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
    FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
    if (Opacity <= .01f) return LayerId;
    const FVector2f Screen = AllottedGeometry.GetLocalSize();
    // 화면 아래 가운데, 폭의 56%. 왼쪽 아래의 플레이어 체력과 겹치지 않는다.
    const float Width = Screen.X * .56f, Height = FMath::Max(12.f, Screen.Y * .018f);
    const FVector2f Origin((Screen.X - Width) * .5f, Screen.Y * .885f);
    const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
    const auto Box = [&](const FVector2f& At, const FVector2f& Size, const FLinearColor& Color, int32 Layer)
    {
        if (Size.X <= 0.f || Size.Y <= 0.f) return;
        FSlateDrawElement::MakeBox(OutDrawElements, Layer, AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform(At)), White,
            ESlateDrawEffect::None, Color * FLinearColor(1.f, 1.f, 1.f, Opacity));
    };
    Box(Origin - FVector2f(3.f), FVector2f(Width + 6.f, Height + 6.f), FLinearColor(.12f, .1f, .07f, .95f), LayerId);        // 테두리
    Box(Origin, FVector2f(Width, Height), FLinearColor(.02f, .02f, .02f, .85f), LayerId + 1);                              // 빈 바
    Box(Origin, FVector2f(Width * FMath::Clamp(Trail, 0.f, 1.f), Height), FLinearColor(.85f, .62f, .12f, 1.f), LayerId + 2);   // 방금 깎인 만큼
    Box(Origin, FVector2f(Width * FMath::Clamp(Health, 0.f, 1.f), Height), FLinearColor(.42f, .02f, .02f, 1.f), LayerId + 3); // 체력

    const FSlateFontInfo NameFont = FCoreStyle::GetDefaultFontStyle("Regular", FMath::Max(12, FMath::RoundToInt32(Screen.Y * .02f)));
    const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const FVector2f NameSize = Measure->Measure(Name, NameFont);
    const auto Text = [&](const FText& Value, const FSlateFontInfo& Font, const FVector2f& At, const FLinearColor& Color)
    {
        // 밝은 바닥 위에서도 읽히도록 그림자를 먼저 그린다.
        FSlateDrawElement::MakeText(OutDrawElements, LayerId + 4, AllottedGeometry.ToPaintGeometry(FVector2f(1.f), FSlateLayoutTransform(At + FVector2f(1.5f))),
            Value, Font, ESlateDrawEffect::None, FLinearColor(0.f, 0.f, 0.f, .8f * Opacity));
        FSlateDrawElement::MakeText(OutDrawElements, LayerId + 5, AllottedGeometry.ToPaintGeometry(FVector2f(1.f), FSlateLayoutTransform(At)),
            Value, Font, ESlateDrawEffect::None, Color * FLinearColor(1.f, 1.f, 1.f, Opacity));
    };
    Text(Name, NameFont, Origin + FVector2f(0.f, -NameSize.Y - 6.f), FLinearColor(.92f, .9f, .85f, 1.f));
    if (RecentDamage >= 1.f)
    {
        const FText Number = FText::AsNumber(FMath::RoundToInt32(RecentDamage));
        const FVector2f NumberSize = Measure->Measure(Number, NameFont);
        Text(Number, NameFont, Origin + FVector2f(Width - NumberSize.X, -NumberSize.Y - 6.f), FLinearColor(.95f, .93f, .9f, 1.f));
    }
    if (NoticeOpacity > .01f && !Notice.IsEmpty())
    {
        const FSlateFontInfo NoticeFont = FCoreStyle::GetDefaultFontStyle("Bold", FMath::Max(14, FMath::RoundToInt32(Screen.Y * .026f)));
        const FVector2f Size = Measure->Measure(Notice, NoticeFont);
        const FVector2f At = Origin + FVector2f((Width - Size.X) * .5f, -Size.Y - NameSize.Y - 14.f);
        FSlateDrawElement::MakeText(OutDrawElements, LayerId + 4, AllottedGeometry.ToPaintGeometry(FVector2f(1.f), FSlateLayoutTransform(At + FVector2f(2.f))),
            Notice, NoticeFont, ESlateDrawEffect::None, FLinearColor(0.f, 0.f, 0.f, .8f * NoticeOpacity * Opacity));
        FSlateDrawElement::MakeText(OutDrawElements, LayerId + 5, AllottedGeometry.ToPaintGeometry(FVector2f(1.f), FSlateLayoutTransform(At)),
            Notice, NoticeFont, ESlateDrawEffect::None, FLinearColor(1.f, .82f, .3f, NoticeOpacity * Opacity));
    }
    return LayerId + 5;
}
