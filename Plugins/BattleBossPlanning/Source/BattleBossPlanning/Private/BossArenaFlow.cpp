#include "BossArenaFlow.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Styling/CoreStyle.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
// 0 = 시작·끝 화면을 쓰지 않는다(자동 시험은 화면의 버튼을 누를 수 없다).
int32 FlowMode = 1;
FAutoConsoleVariableRef CVarFlowMode(TEXT("boss.Flow"), FlowMode, TEXT("0 = no title / result screens, 1 = show them."));
// "다시 하기"로 맵을 다시 열 때는 시작 화면을 건너뛴다.
bool bSkipTitleOnce = false;

double NumberOf(const UObject* Object, const TCHAR* Name, double Default = 0.0)
{
    const FNumericProperty* Property = IsValid(Object) ? FindFProperty<FNumericProperty>(Object->GetClass(), Name) : nullptr;
    if (!Property) return Default;
    const void* Value = Property->ContainerPtrToValuePtr<void>(Object);
    return Property->IsInteger() ? static_cast<double>(Property->GetSignedIntPropertyValue(Value)) : Property->GetFloatingPointPropertyValue(Value);
}

const FLinearColor Ink(.94f, .93f, .9f, 1.f), Dim(.62f, .64f, .68f, 1.f), Ember(1.f, .42f, .16f, 1.f), Blood(.75f, .06f, .05f, 1.f), Gold(.98f, .78f, .3f, 1.f);
FSlateFontInfo Font(const TCHAR* Weight, int32 Size) { return FCoreStyle::GetDefaultFontStyle(Weight, Size); }
}

// 화면 하나로 세 가지를 그린다: 0 시작, 1 패배, 2 승리.
class SBossFlowScreen : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SBossFlowScreen) {}
        SLATE_ARGUMENT(int32, Mode)
        SLATE_ARGUMENT(FText, Line1)
        SLATE_ARGUMENT(FText, Line2)
        SLATE_ARGUMENT(FText, Line3)
        SLATE_EVENT(FSimpleDelegate, OnPrimary)
        SLATE_EVENT(FSimpleDelegate, OnSecondary)
    SLATE_END_ARGS()

    float Fade = 1.f;

    void Construct(const FArguments& Args)
    {
        Primary = Args._OnPrimary;
        Secondary = Args._OnSecondary;
        const int32 Mode = Args._Mode;
        const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
        TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
        const auto Text = [&](const FText& Value, const FSlateFontInfo& InFont, const FLinearColor& Color, float Below)
        {
            Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 0.f, 0.f, Below)
            [ SNew(STextBlock).Text(Value).Font(InFont).ColorAndOpacity(FSlateColor(Color)).ShadowOffset(FVector2D(0., 2.)).ShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, .8f)) ];
        };
        if (Mode == 0)
        {
            Text(FText::FromString(TEXT("BOSS BATTLE")), Font(TEXT("Bold"), 14), Ember, 10.f);
            Text(FText::FromString(TEXT("CRUNCH")), Font(TEXT("Bold"), 84), Ink, 0.f);
            Text(FText::FromString(TEXT("크런치")), Font(TEXT("Regular"), 22), Dim, 18.f);
            Text(FText::FromString(TEXT("묵직한 복서, 플레이어에게 붙어서 연격을 가한다.")), Font(TEXT("Regular"), 20), Ink, 38.f);
            Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 0.f, 0.f, 44.f)[ Keys() ];
            Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[ Button(FText::FromString(TEXT("전투 시작")), Ember, true) ];
        }
        else
        {
            const bool bWin = Mode == 2;
            Text(FText::FromString(bWin ? TEXT("VICTORY") : TEXT("YOU DIED")), Font(TEXT("Bold"), 76), bWin ? Gold : Blood, 8.f);
            Text(FText::FromString(bWin ? TEXT("크런치를 쓰러뜨렸다") : TEXT("크런치에게 쓰러졌다")), Font(TEXT("Regular"), 20), Dim, 30.f);
            TSharedRef<SHorizontalBox> Stats = SNew(SHorizontalBox);
            const auto Stat = [&](const FText& Label, const FText& Value)
            {
                Stats->AddSlot().AutoWidth().Padding(26.f, 0.f)
                [ SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ SNew(STextBlock).Text(Value).Font(Font(TEXT("Bold"), 30)).ColorAndOpacity(FSlateColor(Ink)) ]
                    + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ SNew(STextBlock).Text(Label).Font(Font(TEXT("Regular"), 14)).ColorAndOpacity(FSlateColor(Dim)) ] ];
            };
            Stat(FText::FromString(TEXT("걸린 시간")), Args._Line1);
            Stat(FText::FromString(TEXT("받은 피해")), Args._Line2);
            Stat(FText::FromString(bWin ? TEXT("남은 체력") : TEXT("보스의 남은 체력")), Args._Line3);
            Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 0.f, 0.f, 44.f)[ Stats ];
            Column->AddSlot().AutoHeight().HAlign(HAlign_Center)
            [ SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(8.f, 0.f)[ Button(FText::FromString(TEXT("다시 하기")), bWin ? Gold : Ember, true) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(8.f, 0.f)[ Button(FText::FromString(TEXT("처음으로")), Dim, false) ] ];
        }
        ChildSlot
        [ SNew(SOverlay)
            + SOverlay::Slot()[ SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor(.015f, .015f, .02f, Mode == 0 ? .9f : .78f)) ]
            + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)[ Column ] ];
        SetRenderOpacity(1.f);
    }

    virtual bool SupportsKeyboardFocus() const override { return true; }
    // Enter나 Space로도 첫 버튼을 누를 수 있다.
    virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override
    {
        if (Event.GetKey() == EKeys::Enter || Event.GetKey() == EKeys::SpaceBar) { Primary.ExecuteIfBound(); return FReply::Handled(); }
        return FReply::Unhandled();
    }

private:
    FSimpleDelegate Primary, Secondary;

    TSharedRef<SWidget> Button(const FText& Label, const FLinearColor& Color, bool bPrimary)
    {
        const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
        TSharedPtr<SButton> Made;
        SAssignNew(Made, SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder")).ContentPadding(FMargin(0.f))
            .OnClicked_Lambda([this, bPrimary]() { (bPrimary ? Primary : Secondary).ExecuteIfBound(); return FReply::Handled(); });
        const TWeakPtr<SButton> Weak = Made;
        Made->SetContent(
            SNew(SBorder).BorderImage(White).Padding(FMargin(46.f, 14.f))
            .BorderBackgroundColor_Lambda([Weak, Color, bPrimary]()
            {
                const bool bHover = Weak.IsValid() && Weak.Pin()->IsHovered();
                return FSlateColor(bPrimary ? Color * FLinearColor(1.f, 1.f, 1.f, bHover ? 1.f : .86f) : FLinearColor(1.f, 1.f, 1.f, bHover ? .22f : .1f));
            })
            [ SNew(STextBlock).Text(Label).Font(Font(TEXT("Bold"), 20)).ColorAndOpacity(FSlateColor(bPrimary ? FLinearColor(.04f, .03f, .02f, 1.f) : Ink)) ]);
        return Made.ToSharedRef();
    }

    // 조작법: 키 모양의 칸과 그 키가 하는 일.
    TSharedRef<SWidget> Keys()
    {
        const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
        const auto Cap = [White](const TCHAR* Label) -> TSharedRef<SWidget>
        {
            return SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor(1.f, 1.f, 1.f, .55f)).Padding(FMargin(1.5f))
                [ SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor(.1f, .11f, .14f, 1.f)).Padding(FMargin(11.f, 6.f))
                    [ SNew(SBox).MinDesiredWidth(18.f).HAlign(HAlign_Center)
                        [ SNew(STextBlock).Text(FText::FromString(Label)).Font(Font(TEXT("Bold"), 15)).ColorAndOpacity(FSlateColor(Ink)) ] ] ];
        };
        const auto Row = [&](std::initializer_list<const TCHAR*> Caps, const TCHAR* Action) -> TSharedRef<SWidget>
        {
            TSharedRef<SHorizontalBox> Line = SNew(SHorizontalBox);
            TSharedRef<SHorizontalBox> CapBox = SNew(SHorizontalBox);
            for (const TCHAR* Label : Caps) CapBox->AddSlot().AutoWidth().Padding(2.f, 0.f)[ Cap(Label) ];
            Line->AddSlot().AutoWidth().VAlign(VAlign_Center)[ SNew(SBox).WidthOverride(220.f).HAlign(HAlign_Right)[ CapBox ] ];
            Line->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(16.f, 0.f, 0.f, 0.f)
                [ SNew(SBox).WidthOverride(240.f)[ SNew(STextBlock).Text(FText::FromString(Action)).Font(Font(TEXT("Regular"), 16)).ColorAndOpacity(FSlateColor(Dim)) ] ];
            return Line;
        };
        const auto Column = [&](std::initializer_list<TSharedRef<SWidget>> Rows) -> TSharedRef<SWidget>
        {
            TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
            for (const TSharedRef<SWidget>& Line : Rows) Box->AddSlot().AutoHeight().Padding(0.f, 5.f)[ Line ];
            return Box;
        };
        return SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().Padding(10.f, 0.f)
            [ Column({ Row({TEXT("W"), TEXT("A"), TEXT("S"), TEXT("D")}, TEXT("이동")), Row({TEXT("마우스")}, TEXT("시점")),
                       Row({TEXT("휠 클릭")}, TEXT("락온")), Row({TEXT("F")}, TEXT("점프")) }) ]
            + SHorizontalBox::Slot().AutoWidth().Padding(10.f, 0.f)
            [ Column({ Row({TEXT("좌클릭")}, TEXT("공격 (연타하면 콤보)")), Row({TEXT("우클릭")}, TEXT("가드 (누르고 있는 동안)")),
                       Row({TEXT("Space")}, TEXT("회피 (짧게 누르기)")), Row({TEXT("Space")}, TEXT("달리기 (길게 누르기)")) }) ];
    }
};

namespace
{
// 시험용: 시작 화면의 "전투 시작"을 누른 것과 같다(자동 시험은 화면의 버튼을 누를 수 없다).
FAutoConsoleCommandWithWorld CmdFlowStart(TEXT("boss.FlowStart"), TEXT("Press the title screen's start button (test only)."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (UBossArenaFlowSubsystem* Flow = World ? World->GetSubsystem<UBossArenaFlowSubsystem>() : nullptr) Flow->StartFight();
    }));
}

bool UBossArenaFlowSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    const UWorld* World = Cast<UWorld>(Outer);
    return World && World->IsGameWorld() && World->GetMapName().Contains(TEXT("Lvl_Arena"));
}

void UBossArenaFlowSubsystem::Deinitialize()
{
    HideScreen();
    Super::Deinitialize();
}

void UBossArenaFlowSubsystem::SetUiInput(bool bUi)
{
    APlayerController* Controller = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    if (!Controller) return;
    Controller->SetShowMouseCursor(bUi);
    if (bUi)
    {
        FInputModeUIOnly Mode;
        if (Screen.IsValid()) Mode.SetWidgetToFocus(Screen);
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Controller->SetInputMode(Mode);
    }
    else Controller->SetInputMode(FInputModeGameOnly());
}

void UBossArenaFlowSubsystem::ShowScreen(int32 Mode)
{
    UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;
    if (!Viewport) return;
    HideScreen();
    const double Seconds = FMath::Max(0.0, GetWorld()->GetTimeSeconds() - FightStartedAt);
    const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    const double Left = Mode == 2 ? NumberOf(Player, TEXT("CurrentHealth")) : NumberOf(Boss.Get(), TEXT("CurrentHealth"));
    const double Max = FMath::Max(1.0, Mode == 2 ? NumberOf(Player, TEXT("MaxHealth"), 320.0) : NumberOf(Boss.Get(), TEXT("MaxHealth"), 1200.0));
    Screen = SNew(SBossFlowScreen).Mode(Mode)
        .Line1(FText::FromString(FString::Printf(TEXT("%d:%02d"), static_cast<int32>(Seconds) / 60, static_cast<int32>(Seconds) % 60)))
        .Line2(FText::AsNumber(FMath::RoundToInt32(DamageTaken)))
        .Line3(FText::FromString(FString::Printf(TEXT("%.0f%%"), 100.0 * FMath::Clamp(Left / Max, 0.0, 1.0))))
        .OnPrimary(FSimpleDelegate::CreateWeakLambda(this, [this, Mode]() { if (Mode == 0) StartFight(); else Restart(true); }))
        .OnSecondary(FSimpleDelegate::CreateWeakLambda(this, [this]() { Restart(false); }));
    Viewport->AddViewportWidgetContent(Screen.ToSharedRef(), 100);
    SetUiInput(true);
}

void UBossArenaFlowSubsystem::HideScreen()
{
    if (!Screen.IsValid()) return;
    if (UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr) Viewport->RemoveViewportWidgetContent(Screen.ToSharedRef());
    Screen.Reset();
}

void UBossArenaFlowSubsystem::StartFight()
{
    if (Stage != EStage::Title) return;
    UGameplayStatics::SetGamePaused(this, false);
    SetUiInput(false);
    FightStartedAt = GetWorld()->GetTimeSeconds();
    FadeOut = 1.f;                    // 화면이 걷히며 보스의 등장으로 이어진다
    Stage = EStage::Fighting;
}

void UBossArenaFlowSubsystem::Restart(bool bSkipTitle)
{
    UWorld* World = GetWorld();
    if (!World) return;
    bSkipTitleOnce = bSkipTitle;
    UGameplayStatics::SetGlobalTimeDilation(World, 1.f);
    UGameplayStatics::SetGamePaused(World, false);
    HideScreen();
    SetUiInput(false);
    Stage = EStage::Off;
    UGameplayStatics::OpenLevel(World, FName(*UGameplayStatics::GetCurrentLevelName(World, true)));
}

void UBossArenaFlowSubsystem::Tick(float DeltaTime)
{
    UWorld* World = GetWorld();
    if (!World || Stage == EStage::Off) return;
    const float Real = static_cast<float>(FApp::GetDeltaTime());
    if (Stage == EStage::Boot)
    {
        if (!World->HasBegunPlay() || !World->GetFirstPlayerController()) return;
        if (!FlowMode) { Stage = EStage::Off; return; }
        if (bSkipTitleOnce)
        {
            bSkipTitleOnce = false;
            FightStartedAt = World->GetTimeSeconds();
            Stage = EStage::Fighting;
            SetUiInput(false);
            return;
        }
        // 시작 화면: 게임을 멈춰 둔다. 보스의 등장 연출은 시작을 누른 뒤에 돈다.
        Stage = EStage::Title;
        UGameplayStatics::SetGamePaused(World, true);
        ShowScreen(0);
        return;
    }
    if (FadeOut >= 0.f && Screen.IsValid())
    {
        FadeOut -= Real / .45f;
        Screen->SetRenderOpacity(FMath::Clamp(FadeOut, 0.f, 1.f));
        if (FadeOut <= 0.f) { FadeOut = -1.f; HideScreen(); }
    }
    if (Stage == EStage::Fighting)
    {
        if (!Boss.IsValid())
            for (TActorIterator<ACharacter> It(World); It; ++It)
                if (It->GetClass()->GetName().Contains(TEXT("BP_Boss_Crunch"))) { Boss = *It; break; }
        const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
        if (!IsValid(Player)) return;
        const double Health = NumberOf(Player, TEXT("CurrentHealth"), 1.0);
        if (LastPlayerHealth >= 0.0 && Health < LastPlayerHealth) DamageTaken += static_cast<float>(LastPlayerHealth - Health);
        LastPlayerHealth = Health;
        const bool bLost = Health <= 0.0;
        const bool bWin = Boss.IsValid() && NumberOf(Boss.Get(), TEXT("CurrentHealth"), 1.0) <= 0.0;
        if (bLost || bWin)
        {
            bWon = bWin && !bLost;
            Stage = EStage::Ending;
            EndingAt = FApp::GetCurrentTime();
            // 마지막 순간을 잠깐 느리게 보여준다.
            UGameplayStatics::SetGlobalTimeDilation(World, bWon ? .3f : .55f);
        }
        return;
    }
    if (Stage == EStage::Ending && FApp::GetCurrentTime() - EndingAt >= (bWon ? 1.8 : 1.5))
    {
        UGameplayStatics::SetGlobalTimeDilation(World, 1.f);
        Stage = EStage::Ended;
        ShowScreen(bWon ? 2 : 1);
        UGameplayStatics::SetGamePaused(World, true);      // 결과 화면 뒤에서 전투가 계속 돌지 않게 멈춘다
    }
}
