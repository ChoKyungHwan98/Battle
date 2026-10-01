#include "BossMotionLabDirector.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Components/SizeBox.h"
#include "Components/VerticalBox.h"
#include "Blueprint/WidgetTree.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameplayTagContainer.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "UObject/StructOnScope.h"

namespace
{
constexpr TCHAR ClipRoot[] = TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations/");
constexpr float Distances[] = { 170.f, 230.f, 380.f, 700.f };
const TCHAR* const FocusNames[] = {
    TEXT("Ability_Combo_01"), TEXT("Ability_Combo_01_Slow"), TEXT("Ability_Combo_01_Recovery"),
    TEXT("Ability_Combo_02"), TEXT("Ability_Combo_02_Slow"), TEXT("Ability_Combo_02_Recovery"),
    TEXT("Ability_Combo_03"), TEXT("Ability_Combo_03_Slow"), TEXT("Ability_Combo_04_Slow"),
    TEXT("Ability_Hook_Empowered"), TEXT("Ability_GutPunch"), TEXT("Ability_Hook"), TEXT("Ability_Uppercut"),
    TEXT("Ability_DashingCross_Start"), TEXT("Ability_DashingCross"),
    TEXT("Ability_Dashing_Recovery"), TEXT("Ability_Dashing_Recovery_Hit"),
    TEXT("MM_Attack_01"), TEXT("MM_Attack_02"), TEXT("MM_Attack_03"), TEXT("MM_ChargedAttack")
};

FSoftObjectPath ClipPath(const TCHAR* Name)
{
    const FString AssetName(Name);
    return FSoftObjectPath(FString::Printf(TEXT("%s%s.%s"), ClipRoot, *AssetName, *AssetName));
}

float ReadNumber(const AActor* Actor, FName Name)
{
    if (!IsValid(Actor)) return -1.f;
    if (const FFloatProperty* P = FindFProperty<FFloatProperty>(Actor->GetClass(), Name))
        return P->GetPropertyValue_InContainer(Actor);
    if (const FDoubleProperty* P = FindFProperty<FDoubleProperty>(Actor->GetClass(), Name))
        return static_cast<float>(P->GetPropertyValue_InContainer(Actor));
    return -1.f;
}

bool ReadBool(const AActor* Actor, FName Name)
{
    if (!IsValid(Actor)) return false;
    if (const FBoolProperty* P = FindFProperty<FBoolProperty>(Actor->GetClass(), Name))
        return P->GetPropertyValue_InContainer(Actor);
    return false;
}

FName ReadName(const AActor* Actor, FName Name)
{
    if (!IsValid(Actor)) return NAME_None;
    if (const FNameProperty* P = FindFProperty<FNameProperty>(Actor->GetClass(), Name))
        return P->GetPropertyValue_InContainer(Actor);
    return NAME_None;
}

void WriteNumber(AActor* Actor, FName Name, double Value)
{
    if (!IsValid(Actor)) return;
    if (FFloatProperty* P = FindFProperty<FFloatProperty>(Actor->GetClass(), Name))
        P->SetPropertyValue_InContainer(Actor, static_cast<float>(Value));
    if (FDoubleProperty* P = FindFProperty<FDoubleProperty>(Actor->GetClass(), Name))
        P->SetPropertyValue_InContainer(Actor, Value);
}

int32 ReadActiveActionId(const AActor* Boss)
{
    if (!IsValid(Boss)) return INDEX_NONE;
    const FObjectProperty* Active = FindFProperty<FObjectProperty>(Boss->GetClass(), TEXT("ActiveAction"));
    const UObject* Action = Active ? Active->GetObjectPropertyValue_InContainer(Boss) : nullptr;
    const FIntProperty* Id = Action ? FindFProperty<FIntProperty>(Action->GetClass(), TEXT("ActionId")) : nullptr;
    return Id ? Id->GetPropertyValue_InContainer(Action) : INDEX_NONE;
}
}

TSharedRef<SWidget> UBossMotionLabOverlay::RebuildWidget()
{
    if (!WidgetTree) return Super::RebuildWidget();
    if (WidgetTree->RootWidget) return Super::RebuildWidget();
    UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
    WidgetTree->RootWidget = Canvas;
    UBorder* Border = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Panel"));
    Border->SetPadding(FMargin(20.f, 16.f));
    Border->SetBrushColor(FLinearColor(0.012f, 0.036f, 0.055f, 0.94f));
    UCanvasPanelSlot* PanelSlot = Canvas->AddChildToCanvas(Border);
    PanelSlot->SetAnchors(FAnchors(1.f, 0.f, 1.f, 0.f));
    PanelSlot->SetAlignment(FVector2D(1.f, 0.f));
    PanelSlot->SetPosition(FVector2D(-24.f, 20.f));
    PanelSlot->SetAutoSize(true);
    USizeBox* Width = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("PanelWidth"));
    Width->SetWidthOverride(700.f);
    UVerticalBox* Stack = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("PanelStack"));
    Width->SetContent(Stack);
    Border->SetContent(Width);
    UTextBlock* Heading = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Heading"));
    FSlateFontInfo HeadingFont = Heading->GetFont();
    HeadingFont.Size = 36;
    Heading->SetFont(HeadingFont);
    Heading->SetText(FText::FromString(TEXT("크런치 모션 실험실")));
    Heading->SetColorAndOpacity(FSlateColor(FLinearColor(0.33f, 0.94f, 0.95f, 1.f)));
    Stack->AddChildToVerticalBox(Heading);
    DisplayText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("LabInfo"));
    FSlateFontInfo Font = DisplayText->GetFont();
    Font.Size = 28;
    DisplayText->SetFont(Font);
    DisplayText->SetColorAndOpacity(FSlateColor(FLinearColor(0.88f, 0.98f, 1.f, 1.f)));
    DisplayText->SetAutoWrapText(true);
    Stack->AddChildToVerticalBox(DisplayText);
    UTextBlock* Hint = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("HelpHint"));
    FSlateFontInfo HintFont = Hint->GetFont();
    HintFont.Size = 22;
    Hint->SetFont(HintFont);
    Hint->SetText(FText::FromString(TEXT("Tab 조작법 보기    ·    R 위치 초기화")));
    Hint->SetColorAndOpacity(FSlateColor(FLinearColor(0.47f, 0.74f, 0.78f, 1.f)));
    Stack->AddChildToVerticalBox(Hint);
    ControlsText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Controls"));
    FSlateFontInfo ControlsFont = ControlsText->GetFont();
    ControlsFont.Size = 22;
    ControlsText->SetFont(ControlsFont);
    ControlsText->SetColorAndOpacity(FSlateColor(FLinearColor(0.78f, 0.88f, 0.91f, 1.f)));
    ControlsText->SetText(FText::FromString(
        TEXT("\n실전 행동  1 잽 · 2 후속 타격 · 3 어퍼컷\n")
        TEXT("               4 휩쓸기 · 5 연계 · 6 가드 크래시\n")
        TEXT("               7 슈퍼맨 · 8 접근 · 9 점프\n")
        TEXT("거리 설정  Z 170 · X 230 · V 380 · B 700 cm\n")
        TEXT("모션 비교  [ / ] 탐색 · O 미리보기 · C 전체 목록\n")
        TEXT("연결 비교  T/Y 콤보 회복 · U/I 대시 적중/실패\n")
        TEXT("표시  H 판정 영역 · Tab 조작법 닫기")));
    ControlsText->SetVisibility(ESlateVisibility::Collapsed);
    Stack->AddChildToVerticalBox(ControlsText);
    return Super::RebuildWidget();
}

void UBossMotionLabOverlay::SetDisplayText(const FString& Value)
{
    if (DisplayText) DisplayText->SetText(FText::FromString(Value));
}

void UBossMotionLabOverlay::SetShowControls(bool bShow)
{
    if (ControlsText) ControlsText->SetVisibility(bShow ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
}

ABossMotionLabDirector::ABossMotionLabDirector()
{
    PrimaryActorTick.bCanEverTick = true;
    bShowHitboxes = true;
}

void ABossMotionLabDirector::BeginPlay()
{
    Super::BeginPlay();
    PlayerActor = UGameplayStatics::GetPlayerCharacter(this, 0);
    FAssetRegistryModule& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    Registry.Get().ScanPathsSynchronous({FString(TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations"))});
    TArray<FAssetData> Assets;
    Registry.Get().GetAssetsByPath(FName(TEXT("/Game/ParagonCrunch/Characters/Heroes/Crunch/Animations")), Assets, false);
    for (const FAssetData& Data : Assets)
        if (Data.AssetClassPath.GetAssetName() == UAnimSequence::StaticClass()->GetFName())
            AllClips.Add(Data.GetSoftObjectPath());
    AllClips.Sort([](const FSoftObjectPath& A, const FSoftObjectPath& B) { return A.GetAssetName() < B.GetAssetName(); });
    for (const TCHAR* Name : FocusNames)
    {
        const FSoftObjectPath Path = ClipPath(Name);
        FocusClips.Add(Path);
    }
    UE_LOG(LogTemp, Display, TEXT("MotionLab catalog: focus=%d all=%d"), FocusClips.Num(), AllClips.Num());
    CurrentClips = &FocusClips;
    GetWorldTimerManager().SetTimerForNextTick(this, &ABossMotionLabDirector::InitializeFixture);
}

void ABossMotionLabDirector::BindInput()
{
    if (!InputComponent || bInputBound) return;
    InputComponent->Priority = 100;
    bInputBound = true;
    const EInputEvent Press = IE_Pressed;
    auto Key = [this, Press](FKey K, void(ABossMotionLabDirector::*Fn)()) { InputComponent->BindKey(K, Press, this, Fn); };
    Key(EKeys::LeftBracket, &ABossMotionLabDirector::PreviousClip);
    Key(EKeys::RightBracket, &ABossMotionLabDirector::NextClip);
    Key(EKeys::O, &ABossMotionLabDirector::PreviewSelected);
    Key(EKeys::C, &ABossMotionLabDirector::ToggleCatalog);
    Key(EKeys::R, &ABossMotionLabDirector::ResetFixture);
    Key(EKeys::H, &ABossMotionLabDirector::ToggleHitboxes);
    Key(EKeys::Tab, &ABossMotionLabDirector::ToggleControls);
    for (const FKey K : {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five,
        EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine})
        InputComponent->BindKey(K, Press, this, &ABossMotionLabDirector::OnNumberKey);
    for (const FKey K : {EKeys::Z, EKeys::X, EKeys::V, EKeys::B, EKeys::T, EKeys::Y, EKeys::U, EKeys::I})
        InputComponent->BindKey(K, Press, this, &ABossMotionLabDirector::OnFunctionKey);
}

void ABossMotionLabDirector::OnNumberKey(FKey Key)
{
    const FKey Keys[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five,
        EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Keys); ++Index)
        if (Key == Keys[Index]) { RequestAction(Index); return; }
}

void ABossMotionLabDirector::OnFunctionKey(FKey Key)
{
    const FKey Keys[] = {EKeys::Z, EKeys::X, EKeys::V, EKeys::B, EKeys::T, EKeys::Y, EKeys::U, EKeys::I};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Keys); ++Index)
        if (Key == Keys[Index]) { if (Index < 4) SetDistance(Index); else StartChain(Index - 4); return; }
}

void ABossMotionLabDirector::InitializeFixture()
{
    if (!IsValid(BossActor) || !PlayerActor.IsValid())
    {
        LastResult = TEXT("Assign BossActor and verify the map GameMode spawns the player");
        return;
    }
    if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
    {
        EnableInput(PC);
        BindInput();
        Overlay = CreateWidget<UBossMotionLabOverlay>(PC, UBossMotionLabOverlay::StaticClass());
        if (Overlay)
        {
            Overlay->AddToViewport(100);
            Overlay->SetShowControls(bShowControls);
        }
    }
    PlayerActor->OnTakeAnyDamage.AddUniqueDynamic(this, &ABossMotionLabDirector::OnPlayerDamage);
    WriteNumber(PlayerActor.Get(), TEXT("MaxHealth"), 1000000.0);
    WriteNumber(PlayerActor.Get(), TEXT("CurrentHealth"), 1000000.0);
    if (ACharacter* BossCharacter = Cast<ACharacter>(BossActor))
        BossCharacter->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    HideBossDebugWidget();
    bInitialized = true;
    ResetFixture();
}

void ABossMotionLabDirector::OnPlayerDamage(AActor* DamagedActor, float Damage,
    const UDamageType*, AController*, AActor*)
{
    if (DamagedActor == PlayerActor.Get() && Damage > 0.f)
    {
        ++DamageEventCount;
        DamageTotal += Damage;
        UE_LOG(LogTemp, Display, TEXT("MotionLab damage event %d: %.1f at %.3fs activeAction=%d"),
            DamageEventCount, Damage, GetWorld()->GetTimeSeconds() - ManualActionStartTime,
            ReadActiveActionId(BossActor));
    }
}

void ABossMotionLabDirector::HideBossDebugWidget()
{
    UClass* DebugWidgetClass = LoadClass<UUserWidget>(nullptr,
        TEXT("/Game/BossArena/UI/WBP_BossAIDebug.WBP_BossAIDebug_C"));
    if (!DebugWidgetClass) return;
    TArray<UUserWidget*> Widgets;
    UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, DebugWidgetClass, false);
    for (UUserWidget* Widget : Widgets)
        if (IsValid(Widget)) Widget->RemoveFromParent();
}

void ABossMotionLabDirector::SuppressAutonomousChoice() const
{
    if (IsValid(BossActor))
    {
        UKismetSystemLibrary::K2_ClearTimer(BossActor, TEXT("EvaluateCombatUtility"));
        UKismetSystemLibrary::K2_ClearTimer(BossActor, TEXT("EvaluateUtility"));
    }
}

void ABossMotionLabDirector::EnterReadyState() const
{
    if (!IsValid(BossActor)) return;
    UFunction* Fn = BossActor->FindFunction(TEXT("TransitionBossState"));
    if (!Fn) return;
    FStructOnScope Params(Fn);
    const FStructProperty* CurrentStateProperty = FindFProperty<FStructProperty>(BossActor->GetClass(), TEXT("BossState"));
    const FGameplayTag CurrentState = CurrentStateProperty ?
        *CurrentStateProperty->ContainerPtrToValuePtr<FGameplayTag>(BossActor) : FGameplayTag();
    int32 FirstTagOffset = MAX_int32;
    for (TFieldIterator<FProperty> It(Fn); It; ++It)
        if (const FStructProperty* TagProperty = CastField<FStructProperty>(*It))
            if (TagProperty->HasAnyPropertyFlags(CPF_Parm) && TagProperty->Struct == FGameplayTag::StaticStruct())
                FirstTagOffset = FMath::Min(FirstTagOffset, TagProperty->GetOffset_ForInternal());
    for (TFieldIterator<FProperty> It(Fn); It; ++It)
    {
        FProperty* Property = *It;
        if (!Property->HasAnyPropertyFlags(CPF_Parm | CPF_ReturnParm) || Property->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
        void* Value = Property->ContainerPtrToValuePtr<void>(Params.GetStructMemory());
        if (FStructProperty* TagProperty = CastField<FStructProperty>(Property))
        {
            if (TagProperty->Struct == FGameplayTag::StaticStruct())
            {
                FGameplayTag* Tag = static_cast<FGameplayTag*>(Value);
                *Tag = TagProperty->GetOffset_ForInternal() == FirstTagOffset ?
                    FGameplayTag::RequestGameplayTag(TEXT("Boss.Combat.Ready")) : CurrentState;
            }
        }
        else if (FStrProperty* StringProperty = CastField<FStrProperty>(Property))
            StringProperty->SetPropertyValue(Value, TEXT("motion lab reset"));
    }
    BossActor->ProcessEvent(Fn, Params.GetStructMemory());
}

void ABossMotionLabDirector::StopCurrentMotion() const
{
    if (!IsValid(BossActor)) return;
    if (ACharacter* Boss = Cast<ACharacter>(BossActor))
    {
        if (UAnimInstance* Anim = Boss->GetMesh()->GetAnimInstance()) Anim->Montage_Stop(0.08f);
        Boss->GetCharacterMovement()->StopMovementImmediately();
        Boss->GetCharacterMovement()->DisableMovement();
    }
    for (const TCHAR* Name : {TEXT("FinishBossIntro"), TEXT("FinishBossObserve"), TEXT("OpenActionImpact"),
        TEXT("CloseActionImpact"), TEXT("FinishCombatAction"), TEXT("OnAttackHit"), TEXT("OnAttackEnd"), TEXT("OnHitWindowClose")})
        UKismetSystemLibrary::K2_ClearTimer(BossActor, Name);
}

void ABossMotionLabDirector::ResetFixture()
{
    if (!bInitialized) return;
    Chain.Reset();
    bManualActionActive = false;
    DamageEventCount = 0;
    DamageTotal = 0.f;
    ManualActionIndex = INDEX_NONE;
    FirstHandContactAt = FirstWindowOpenAt = LastHandContactAt = ClosestHandGapAt = LastContactSampleAt = -1.f;
    ClosestHandGap = BIG_NUMBER;
    SuppressAutonomousChoice();
    StopCurrentMotion();
    EnterReadyState();
    if (FObjectProperty* Active = FindFProperty<FObjectProperty>(BossActor->GetClass(), TEXT("ActiveAction")))
        Active->SetObjectPropertyValue_InContainer(BossActor, nullptr);
    if (FBoolProperty* Open = FindFProperty<FBoolProperty>(BossActor->GetClass(), TEXT("bPhysicalStrikeOpen")))
        Open->SetPropertyValue_InContainer(BossActor, false);
    if (FBoolProperty* Hit = FindFProperty<FBoolProperty>(BossActor->GetClass(), TEXT("bPhysicalStrikeHit")))
        Hit->SetPropertyValue_InContainer(BossActor, false);
    AActor* Player = PlayerActor.Get();
    Player->SetActorLocation(FVector(0.f, 0.f, 92.f), false, nullptr, ETeleportType::TeleportPhysics);
    Player->SetActorRotation(FRotator(0.f, 0.f, 0.f));
    if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0)) PC->SetControlRotation(FRotator::ZeroRotator);
    const ACharacter* Boss = Cast<ACharacter>(BossActor);
    const ACharacter* Char = Cast<ACharacter>(Player);
    const float BossHalf = Boss ? Boss->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 135.f;
    const float PlayerHalf = Char ? Char->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 92.f;
    BossActor->SetActorLocation(FVector(Distances[DistanceIndex], 0.f, 92.f + BossHalf - PlayerHalf), false, nullptr, ETeleportType::TeleportPhysics);
    BossActor->SetActorRotation(FRotator(0.f, 180.f, 0.f));
    BossActor->SetActorTickEnabled(false);
    WriteNumber(Player, TEXT("MaxHealth"), 1000000.0);
    WriteNumber(Player, TEXT("CurrentHealth"), 1000000.0);
    const float BossCurrent = ReadNumber(BossActor, TEXT("CurrentHealth"));
    const float BossMaximum = ReadNumber(BossActor, TEXT("MaxHealth"));
    if (BossCurrent >= 0.f && BossMaximum > BossCurrent)
        UGameplayStatics::ApplyDamage(BossActor, BossCurrent - BossMaximum, nullptr, this, nullptr);
    LastResult = FString::Printf(TEXT("위치 초기화 · %.0f cm"), Distances[DistanceIndex]);
}

void ABossMotionLabDirector::SetDistance(int32 Index)
{
    DistanceIndex = FMath::Clamp(Index, 0, 3);
    ResetFixture();
}

void ABossMotionLabDirector::RequestAction(int32 Index)
{
    if (!bInitialized || !IsValid(BossActor)) return;
    Chain.Reset();
    SuppressAutonomousChoice();
    DamageEventCount = 0;
    DamageTotal = 0.f;
    ManualActionIndex = Index;
    FirstHandContactAt = FirstWindowOpenAt = LastHandContactAt = ClosestHandGapAt = LastContactSampleAt = -1.f;
    ClosestHandGap = BIG_NUMBER;
    BossActor->SetActorTickEnabled(true);
    bManualActionActive = true;
    ManualActionStartTime = GetWorld()->GetTimeSeconds();
    if (FFloatProperty* Distance = FindFProperty<FFloatProperty>(BossActor->GetClass(), TEXT("UtilityDistance")))
        Distance->SetPropertyValue_InContainer(BossActor, FVector::Dist2D(BossActor->GetActorLocation(), PlayerActor->GetActorLocation()));
    // A numbered lab request measures exactly one action. The boss's ordinary
    // follow-up chooser clears this flag at the end of that action.
    if (FBoolProperty* Followup = FindFProperty<FBoolProperty>(BossActor->GetClass(), TEXT("bInFollowup")))
        Followup->SetPropertyValue_InContainer(BossActor, true);
    if (UFunction* Fn = BossActor->FindFunction(TEXT("RequestCombatAction")))
    {
        FStructOnScope Params(Fn);
        for (TFieldIterator<FProperty> It(Fn); It; ++It)
            if ((*It)->HasAnyPropertyFlags(CPF_Parm) && !(*It)->HasAnyPropertyFlags(CPF_ReturnParm))
                if (FIntProperty* Int = CastField<FIntProperty>(*It)) { Int->SetPropertyValue_InContainer(Params.GetStructMemory(), Index); break; }
        BossActor->ProcessEvent(Fn, Params.GetStructMemory());
        LastResult = FString::Printf(TEXT("%d번 실전 행동 실행 중"), Index + 1);
    }
    else LastResult = TEXT("실전 행동 요청 함수를 찾지 못함");
}

void ABossMotionLabDirector::PreviousClip()
{
    if (CurrentClips && !CurrentClips->IsEmpty()) ClipIndex = (ClipIndex - 1 + CurrentClips->Num()) % CurrentClips->Num();
}

void ABossMotionLabDirector::NextClip()
{
    if (CurrentClips && !CurrentClips->IsEmpty()) ClipIndex = (ClipIndex + 1) % CurrentClips->Num();
}

void ABossMotionLabDirector::ToggleCatalog()
{
    CurrentClips = CurrentClips == &FocusClips ? &AllClips : &FocusClips;
    ClipIndex = 0;
}

void ABossMotionLabDirector::PreviewSelected()
{
    if (!CurrentClips || CurrentClips->IsEmpty()) { LastResult = TEXT("Catalog empty"); return; }
    Chain.Reset();
    StopCurrentMotion();
    EnterReadyState();
    PreviewSequence((*CurrentClips)[ClipIndex]);
}

void ABossMotionLabDirector::PreviewSequence(const FSoftObjectPath& Path)
{
    ACharacter* Boss = Cast<ACharacter>(BossActor);
    UAnimSequence* Sequence = Cast<UAnimSequence>(Path.TryLoad());
    if (!Boss || !Sequence) { LastResult = FString::Printf(TEXT("Missing clip %s"), *Path.GetAssetName()); return; }
    if (UAnimInstance* Anim = Boss->GetMesh()->GetAnimInstance())
    {
        UAnimMontage* Played = Anim->PlaySlotAnimationAsDynamicMontage(Sequence, TEXT("UpperBody"), 0.05f, 0.08f);
        LastResult = FString::Printf(TEXT("원본 미리보기 %s · %s · 피해 없음"), Played ? TEXT("재생 중") : TEXT("실패"), *Path.GetAssetName());
        UE_LOG(LogTemp, Display, TEXT("MotionLab %s"), *LastResult);
    }
}

void ABossMotionLabDirector::StartChain(int32 Index)
{
    Chain.Reset();
    StopCurrentMotion();
    EnterReadyState();
    auto Add = [this](const TCHAR* Name) { Chain.Add(ClipPath(Name)); };
    if (Index == 0) { Add(TEXT("Ability_Combo_01_Slow")); Add(TEXT("Ability_Combo_01_Recovery")); }
    if (Index == 1) { Add(TEXT("Ability_Combo_02_Slow")); Add(TEXT("Ability_Combo_02_Recovery")); }
    if (Index == 2 || Index == 3)
    {
        Add(TEXT("Ability_DashingCross_Start")); Add(TEXT("Ability_DashingCross"));
        Add(Index == 2 ? TEXT("Ability_Dashing_Recovery_Hit") : TEXT("Ability_Dashing_Recovery"));
    }
    ChainIndex = 0;
    AdvanceChain();
}

void ABossMotionLabDirector::AdvanceChain()
{
    if (!Chain.IsValidIndex(ChainIndex)) { Chain.Reset(); return; }
    const FSoftObjectPath Path = Chain[ChainIndex++];
    if (const UAnimSequence* Sequence = Cast<UAnimSequence>(Path.TryLoad()))
    {
        PreviewSequence(Path);
        NextChainTime = GetWorld()->GetTimeSeconds() + FMath::Max(0.1f, Sequence->GetPlayLength() - 0.06f);
    }
    else { LastResult = FString::Printf(TEXT("Missing chain clip %s"), *Path.GetAssetName()); Chain.Reset(); }
}

void ABossMotionLabDirector::ToggleHitboxes() { bShowHitboxes = !bShowHitboxes; }

void ABossMotionLabDirector::ToggleControls()
{
    bShowControls = !bShowControls;
    if (Overlay) Overlay->SetShowControls(bShowControls);
}

void ABossMotionLabDirector::SampleHandContact()
{
    if (!bManualActionActive || ManualActionIndex != 0 || !IsValid(BossActor) || !PlayerActor.IsValid()) return;
    const ACharacter* Boss = Cast<ACharacter>(BossActor);
    const ACharacter* Player = Cast<ACharacter>(PlayerActor.Get());
    if (!Boss || !Player) return;
    const UCapsuleComponent* Capsule = Player->GetCapsuleComponent();
    const FVector Center = Capsule->GetComponentLocation();
    const FVector Axis = Capsule->GetUpVector();
    const float Radius = Capsule->GetScaledCapsuleRadius();
    const float InnerHalf = Capsule->GetScaledCapsuleHalfHeight() - Radius;
    const FVector Hand = Boss->GetMesh()->GetSocketLocation(TEXT("hand_l"));
    const float Gap = FMath::PointDistToSegment(Hand, Center - Axis * InnerHalf, Center + Axis * InnerHalf) - Radius - 52.f;
    const FVector OtherHand = Boss->GetMesh()->GetSocketLocation(TEXT("hand_r"));
    const float OtherGap = FMath::PointDistToSegment(OtherHand, Center - Axis * InnerHalf, Center + Axis * InnerHalf) - Radius - 52.f;
    const float Elapsed = GetWorld()->GetTimeSeconds() - ManualActionStartTime;
    if (Gap < ClosestHandGap) { ClosestHandGap = Gap; ClosestHandGapAt = Elapsed; }
    if (Gap <= 0.f)
    {
        if (FirstHandContactAt < 0.f) FirstHandContactAt = Elapsed;
        LastHandContactAt = Elapsed;
    }
    const bool bOpen = ReadBool(BossActor, TEXT("bPhysicalStrikeOpen"));
    if (bOpen && FirstWindowOpenAt < 0.f) FirstWindowOpenAt = Elapsed;
    if (Elapsed - LastContactSampleAt >= 0.06f)
    {
        const UAnimInstance* Anim = Boss->GetMesh()->GetAnimInstance();
        const FObjectProperty* MontageProperty = FindFProperty<FObjectProperty>(BossActor->GetClass(), TEXT("AttackMontage"));
        const UAnimMontage* Montage = MontageProperty ? Cast<UAnimMontage>(MontageProperty->GetObjectPropertyValue_InContainer(BossActor)) : nullptr;
        const float MontageTime = Anim && Montage ? Anim->Montage_GetPosition(Montage) : -1.f;
        UE_LOG(LogTemp, Display, TEXT("MotionLab action1 t=%.3f montage=%.3f action=%d leftGap=%.1fcm rightGap=%.1fcm left=(%.1f,%.1f,%.1f) target=(%.1f,%.1f,%.1f) window=%d damageEvents=%d"),
            Elapsed, MontageTime, ReadActiveActionId(BossActor), Gap, OtherGap,
            Hand.X, Hand.Y, Hand.Z, Center.X, Center.Y, Center.Z, bOpen ? 1 : 0, DamageEventCount);
        LastContactSampleAt = Elapsed;
    }
}

void ABossMotionLabDirector::DrawDiagnostics() const
{
    if (!bShowHitboxes || !IsValid(BossActor) || !PlayerActor.IsValid()) return;
    const ACharacter* Boss = Cast<ACharacter>(BossActor);
    const ACharacter* Player = Cast<ACharacter>(PlayerActor.Get());
    if (!Boss || !Player) return;
    const UCapsuleComponent* Capsule = Player->GetCapsuleComponent();
    DrawDebugCapsule(GetWorld(), Capsule->GetComponentLocation(), Capsule->GetScaledCapsuleHalfHeight(),
        Capsule->GetScaledCapsuleRadius(), Capsule->GetComponentQuat(), FColor::Cyan, false, 0.f, 0, 2.f);
    const bool bCanDamage = ReadBool(BossActor, TEXT("bPhysicalStrikeOpen")) &&
        !ReadBool(BossActor, TEXT("bPhysicalStrikeHit"));
    const FName ActiveHand = ReadName(BossActor, TEXT("PhysicalStrikeSocket"));
    for (const FName Hand : {FName(TEXT("hand_l")), FName(TEXT("hand_r"))})
    {
        const FVector Position = Boss->GetMesh()->GetSocketLocation(Hand);
        DrawDebugSphere(GetWorld(), Position, 52.f, 12,
            bCanDamage && Hand == ActiveHand ? FColor::Red : FColor::Yellow, false, 0.f, 0, 2.f);
    }
}

void ABossMotionLabDirector::DrawOverlay() const
{
    if (!GEngine) return;
    const FString Clip = CurrentClips && CurrentClips->IsValidIndex(ClipIndex) ? (*CurrentClips)[ClipIndex].GetAssetName() : TEXT("none");
    const TCHAR* Names[] = { TEXT("왼손 잽"), TEXT("후속 타격"), TEXT("어퍼컷"), TEXT("양손 휩쓸기"),
        TEXT("잽·잽·훅"), TEXT("가드 크래시"), TEXT("슈퍼맨 펀치"), TEXT("접근"), TEXT("점프 내려찍기") };
    const FString Action = ManualActionIndex >= 0 && ManualActionIndex < UE_ARRAY_COUNT(Names) ?
        FString::Printf(TEXT("%d  %s"), ManualActionIndex + 1, Names[ManualActionIndex]) : TEXT("행동 선택 대기");
    const FString Contact = FirstHandContactAt >= 0.f ?
        FString::Printf(TEXT("%.2f초"), FirstHandContactAt) : TEXT("없음");
    const FString Window = FirstWindowOpenAt >= 0.f ?
        FString::Printf(TEXT("%.2f초"), FirstWindowOpenAt) : TEXT("없음");
    const FString ContactLine = ManualActionIndex == 0
        ? FString::Printf(TEXT("손 접촉  %s  ·  판정 시작  %s\n"), *Contact, *Window)
        : TEXT("");
    const FString Text = FString::Printf(
        TEXT("\n%s\n")
        TEXT("거리  %.0f cm  ·  타격 창  %s\n")
        TEXT("피해  %d회 / %.0f  ·  적중  %s\n")
        TEXT("%s")
        TEXT("\n미리보기 선택 %d/%d  %s\n")
        TEXT("보스 HP  %.0f  ·  플레이어 불사\n")
        TEXT("\n%s\n"),
        *Action,
        IsValid(BossActor) && PlayerActor.IsValid() ? FVector::Dist2D(BossActor->GetActorLocation(), PlayerActor->GetActorLocation()) : -1.f,
        ReadBool(BossActor, TEXT("bPhysicalStrikeOpen"))
            ? (ReadBool(BossActor, TEXT("bPhysicalStrikeHit")) ? TEXT("소진") : TEXT("열림"))
            : TEXT("닫힘"),
        DamageEventCount, DamageTotal,
        ReadBool(BossActor, TEXT("bPhysicalStrikeHit")) ? TEXT("성공") : TEXT("없음"),
        *ContactLine,
        ClipIndex + 1, CurrentClips ? CurrentClips->Num() : 0, *Clip,
        ReadNumber(BossActor, TEXT("CurrentHealth")),
        *LastResult);
    if (Overlay) Overlay->SetDisplayText(Text);
}

void ABossMotionLabDirector::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bInitialized) return;
    if (ReadNumber(PlayerActor.Get(), TEXT("CurrentHealth")) < 10000.f)
        WriteNumber(PlayerActor.Get(), TEXT("CurrentHealth"), 1000000.0);
    SuppressAutonomousChoice();
    if (bManualActionActive)
        if (FBoolProperty* Followup = FindFProperty<FBoolProperty>(BossActor->GetClass(), TEXT("bInFollowup")))
            Followup->SetPropertyValue_InContainer(BossActor, true);
    SampleHandContact();
    if (bManualActionActive)
    {
        const FStructProperty* StateProperty = FindFProperty<FStructProperty>(BossActor->GetClass(), TEXT("BossState"));
        const FGameplayTag* State = StateProperty ? StateProperty->ContainerPtrToValuePtr<FGameplayTag>(BossActor) : nullptr;
        const bool bReady = State && State->MatchesTagExact(FGameplayTag::RequestGameplayTag(TEXT("Boss.Combat.Ready")));
        const ACharacter* BossCharacter = Cast<ACharacter>(BossActor);
        const UAnimInstance* Anim = BossCharacter ? BossCharacter->GetMesh()->GetAnimInstance() : nullptr;
        const bool bMontagePlaying = Anim && Anim->Montage_IsPlaying(nullptr);
        if (bReady && !bMontagePlaying && GetWorld()->GetTimeSeconds() - ManualActionStartTime > 0.35f)
        {
            bManualActionActive = false;
            BossActor->SetActorTickEnabled(false);
            LastResult = ManualActionIndex == 0 && ClosestHandGap < BIG_NUMBER * 0.5f
                ? FString::Printf(TEXT("행동 완료 · 최근접 %.0f cm (%.2f초)"), ClosestHandGap, ClosestHandGapAt)
                : TEXT("행동 완료");
        }
    }
    else
    {
        BossActor->SetActorTickEnabled(false);
        const FStructProperty* StateProperty = FindFProperty<FStructProperty>(BossActor->GetClass(), TEXT("BossState"));
        const FGameplayTag* State = StateProperty ? StateProperty->ContainerPtrToValuePtr<FGameplayTag>(BossActor) : nullptr;
        if (State && !State->MatchesTagExact(FGameplayTag::RequestGameplayTag(TEXT("Boss.Combat.Ready"))))
        {
            StopCurrentMotion();
            EnterReadyState();
        }
        if (FObjectProperty* Active = FindFProperty<FObjectProperty>(BossActor->GetClass(), TEXT("ActiveAction")))
            Active->SetObjectPropertyValue_InContainer(BossActor, nullptr);
    }
    if (!Chain.IsEmpty() && GetWorld()->GetTimeSeconds() >= NextChainTime) AdvanceChain();
    DrawDiagnostics();
    DrawOverlay();
}
