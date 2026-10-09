#include "BossAIPanelWidget.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"

void SBossAIPanel::Construct(const FArguments& InArgs)
{
    SetVisibility(EVisibility::HitTestInvisible);
    SetCanTick(false);
}

int32 SBossAIPanel::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
    FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
    if (Opacity <= .01f || Stage < 0) return LayerId;
    const FVector2f Screen = AllottedGeometry.GetLocalSize();
    const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
    const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const int32 Small = FMath::Max(9, FMath::RoundToInt32(Screen.Y * .0135f)), Body = FMath::Max(11, FMath::RoundToInt32(Screen.Y * .017f));
    const FSlateFontInfo HeadFont = FCoreStyle::GetDefaultFontStyle("Bold", Small);
    const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle("Regular", Body);
    const FSlateFontInfo BoldFont = FCoreStyle::GetDefaultFontStyle("Bold", Body);
    const FSlateFontInfo ChipFont = FCoreStyle::GetDefaultFontStyle("Bold", Small);
    const float Line = Body * 1.75f, Pad = Screen.Y * .014f;
    const FLinearColor Ink(.93f, .94f, .95f, 1.f), Dim(.62f, .66f, .7f, 1.f), Back(.03f, .04f, .06f, .72f);
    // 시스템마다 색 하나: HFSM 청록, GOAP 연두, Utility 호박색. 화면 어디서든 같은 색이 같은 시스템이다.
    const FLinearColor State(.25f, .8f, .88f, 1.f), Goap(.55f, .85f, .35f, 1.f), Utility(.98f, .72f, .2f, 1.f), Strike(.95f, .32f, .25f, 1.f);

    const auto Box = [&](const FVector2f& At, const FVector2f& Size, const FLinearColor& Color, int32 Layer)
    {
        if (Size.X <= 0.f || Size.Y <= 0.f) return;
        FSlateDrawElement::MakeBox(OutDrawElements, LayerId + Layer, AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform(At)), White,
            ESlateDrawEffect::None, Color * FLinearColor(1.f, 1.f, 1.f, Opacity));
    };
    const auto Text = [&](const FText& Value, const FSlateFontInfo& Font, const FVector2f& At, const FLinearColor& Color)
    {
        FSlateDrawElement::MakeText(OutDrawElements, LayerId + 3, AllottedGeometry.ToPaintGeometry(FVector2f(1.f), FSlateLayoutTransform(At)),
            Value, Font, ESlateDrawEffect::None, Color * FLinearColor(1.f, 1.f, 1.f, Opacity));
    };
    // 폭에 맞지 않으면 뒤를 줄인다(패널 밖으로 글자가 나가지 않게).
    const auto Fit = [&](const FText& Value, const FSlateFontInfo& Font, float MaxWidth)
    {
        FString S = Value.ToString();
        if (static_cast<float>(Measure->Measure(S, Font).X) <= MaxWidth) return Value;
        while (S.Len() > 1 && static_cast<float>(Measure->Measure(S + TEXT("…"), Font).X) > MaxWidth) S.LeftChopInline(1);
        return FText::FromString(S + TEXT("…"));
    };

    // ---------------------------------------------------------------- 왼쪽: HFSM + GOAP
    {
        const float Width = Screen.X * .285f, Inner = Width - Pad * 2.f;
        const FVector2f Origin(Screen.X * .02f, Screen.Y * .05f);
        const float ChipHeight = Small * 2.3f;
        const float Height = Pad * 2.f + Small * 1.6f + ChipHeight + Line * 1.2f + Pad * .6f + Small * 1.6f + Line + Pad * .6f + Small * 1.6f + Line;
        Box(Origin, FVector2f(Width, Height), Back, 0);
        Box(Origin, FVector2f(3.f, Height), State, 1);
        FVector2f At = Origin + FVector2f(Pad, Pad);
        Text(FText::FromString(TEXT("HFSM   지금 무엇을 하고 있나")), HeadFont, At, State);
        At.Y += Small * 1.9f;
        // 단계 여섯 칸. 지금 칸만 채운다. 타격은 붉게, 닫힌 후딜(플레이어의 반격 시간)은 가장 밝게.
        static const TCHAR* Names[] = {TEXT("선택"), TEXT("이동"), TEXT("준비"), TEXT("타격"), TEXT("후딜 닫힘"), TEXT("후딜 열림")};
        static const float Share[] = {.13f, .13f, .13f, .13f, .24f, .24f};
        const float Gap = 4.f, Usable = Inner - Gap * 5.f;
        float X = At.X;
        for (int32 I = 0; I < 6; ++I)
        {
            const float ChipWidth = Usable * Share[I];
            const bool bNow = I == Stage;
            const FLinearColor Fill = I == 3 ? Strike : State;
            Box(FVector2f(X, At.Y), FVector2f(ChipWidth, ChipHeight), bNow ? Fill : FLinearColor(1.f, 1.f, 1.f, .08f), 1);
            const FText Label = FText::FromString(Names[I]);
            const FVector2f Size = Measure->Measure(Label, ChipFont);
            Text(Label, ChipFont, FVector2f(X + (ChipWidth - Size.X) * .5f, At.Y + (ChipHeight - Size.Y) * .5f), bNow ? FLinearColor(.02f, .03f, .05f, 1.f) : Dim);
            X += ChipWidth + Gap;
        }
        At.Y += ChipHeight + Line * .25f;
        Text(Fit(Reason, BodyFont, Inner), BodyFont, At, Ink);
        At.Y += Line + Pad * .3f;
        // 이번 몰아치기: 치려는 수만큼 칸, 친 만큼 채운다.
        Text(FText::FromString(TEXT("몰아치기   이번에 몇 번 치나")), HeadFont, At, State);
        At.Y += Small * 1.9f;
        const float Pip = Body * .95f;
        for (int32 I = 0; I < FMath::Clamp(StringWanted, 1, 3); ++I)
            Box(FVector2f(At.X + I * (Pip + 5.f), At.Y + Body * .25f), FVector2f(Pip, Pip), I < StringDone ? State : FLinearColor(1.f, 1.f, 1.f, .14f), 1);
        const float PipsWidth = 3.f * (Pip + 5.f) + 6.f;
        Text(Fit(StringText, BodyFont, Inner - PipsWidth), BodyFont, At + FVector2f(PipsWidth, 0.f), Ink);
        At.Y += Line + Pad * .3f;
        Text(FText::FromString(TEXT("GOAP   어떻게 할 것인가")), HeadFont, At, Goap);
        At.Y += Small * 1.9f;
        Text(Fit(Plan, BodyFont, Inner), BodyFont, At, Ink);
    }

    // ---------------------------------------------------------------- 오른쪽: Utility
    {
        const int32 Rows = FMath::Min(Scores.Num(), 6);
        const float Width = Screen.X * .255f, Inner = Width - Pad * 2.f;
        const float Height = Pad * 2.f + Small * 1.6f + Line * 1.15f + FMath::Max(1, Rows) * Line;
        const FVector2f Origin(Screen.X * .98f - Width, Screen.Y * .05f);
        Box(Origin, FVector2f(Width, Height), Back, 0);
        Box(Origin + FVector2f(Width - 3.f, 0.f), FVector2f(3.f, Height), Utility, 1);
        FVector2f At = Origin + FVector2f(Pad, Pad);
        Text(FText::FromString(TEXT("UTILITY   무엇을 고를 것인가")), HeadFont, At, Utility);
        At.Y += Small * 1.9f;
        Text(Fit(Distance, BodyFont, Inner), BodyFont, At, Dim);
        At.Y += Line * 1.15f;
        float Top = 1.f;
        for (int32 I = 0; I < Rows; ++I) Top = FMath::Max(Top, Scores[I].Value);
        const float LabelWidth = Inner * .46f, NumberWidth = Inner * .12f, BarWidth = Inner - LabelWidth - NumberWidth - 8.f;
        for (int32 I = 0; I < Rows; ++I)
        {
            const FScore& Row = Scores[I];
            const FLinearColor Color = Row.bPicked ? Utility : FLinearColor(.75f, .78f, .82f, .55f);
            if (Row.bPicked) Box(FVector2f(Origin.X + 3.f, At.Y - Line * .12f), FVector2f(Width - 6.f, Line), FLinearColor(Utility.R, Utility.G, Utility.B, .13f), 1);
            Text(Fit(Row.Label, Row.bPicked ? BoldFont : BodyFont, LabelWidth), Row.bPicked ? BoldFont : BodyFont, At, Row.bPicked ? Ink : Dim);
            Box(FVector2f(At.X + LabelWidth, At.Y + Body * .45f), FVector2f(BarWidth, Body * .5f), FLinearColor(1.f, 1.f, 1.f, .07f), 1);
            Box(FVector2f(At.X + LabelWidth, At.Y + Body * .45f), FVector2f(BarWidth * FMath::Clamp(Row.Value / Top, 0.f, 1.f), Body * .5f), Color, 2);
            const FText Number = FText::AsNumber(FMath::RoundToInt32(Row.Value));
            const FVector2f NumberSize = Measure->Measure(Number, BodyFont);
            Text(Number, BodyFont, FVector2f(At.X + Inner - NumberSize.X, At.Y), Row.bPicked ? Ink : Dim);
            At.Y += Line;
        }
        if (Rows == 0) Text(FText::FromString(TEXT("아직 고르지 않았다")), BodyFont, At, Dim);
    }
    return LayerId + 3;
}
