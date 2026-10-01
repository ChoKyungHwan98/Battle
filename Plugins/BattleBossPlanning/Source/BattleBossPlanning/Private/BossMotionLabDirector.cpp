#include "BossMotionLabDirector.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
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
}

TSharedRef<SWidget> UBossMotionLabOverlay::RebuildWidget()
{
    if (!WidgetTree) return Super::RebuildWidget();
    if (WidgetTree->RootWidget) return Super::RebuildWidget();
    UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
    WidgetTree->RootWidget = Canvas;
    UBorder* Border = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Panel"));
    Border->SetPadding(FMargin(12.f));
    Border->SetBrushColor(FLinearColor(0.015f, 0.035f, 0.045f, 0.91f));
    UCanvasPanelSlot* PanelSlot = Canvas->AddChildToCanvas(Border);
    PanelSlot->SetAnchors(FAnchors(1.f, 0.f, 1.f, 0.f));
    PanelSlot->SetAlignment(FVector2D(1.f, 0.f));
    PanelSlot->SetPosition(FVector2D(-20.f, 16.f));
    PanelSlot->SetAutoSize(true);
    DisplayText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("LabInfo"));
    FSlateFontInfo Font = DisplayText->GetFont();
    Font.Size = 18;
    DisplayText->SetFont(Font);
    DisplayText->SetColorAndOpacity(FSlateColor(FLinearColor(0.88f, 0.98f, 1.f, 1.f)));
    Border->SetContent(DisplayText);
    return Super::RebuildWidget();
}

void UBossMotionLabOverlay::SetDisplayText(const FString& Value)
{
    if (DisplayText) DisplayText->SetText(FText::FromString(Value));
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
        if (Overlay) Overlay->AddToViewport(100);
    }
    PlayerActor->OnTakeAnyDamage.AddUniqueDynamic(this, &ABossMotionLabDirector::OnPlayerDamage);
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
    for (AActor* Actor : {Player, BossActor.Get()})
    {
        const float Current = ReadNumber(Actor, TEXT("CurrentHealth"));
        const float Maximum = ReadNumber(Actor, TEXT("MaxHealth"));
        if (Current >= 0.f && Maximum > Current)
            UGameplayStatics::ApplyDamage(Actor, Current - Maximum, nullptr, this, nullptr);
    }
    LastResult = FString::Printf(TEXT("Reset | %.0f cm"), Distances[DistanceIndex]);
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
    BossActor->SetActorTickEnabled(true);
    bManualActionActive = true;
    ManualActionStartTime = GetWorld()->GetTimeSeconds();
    if (FFloatProperty* Distance = FindFProperty<FFloatProperty>(BossActor->GetClass(), TEXT("UtilityDistance")))
        Distance->SetPropertyValue_InContainer(BossActor, FVector::Dist2D(BossActor->GetActorLocation(), PlayerActor->GetActorLocation()));
    if (UFunction* Fn = BossActor->FindFunction(TEXT("RequestCombatAction")))
    {
        FStructOnScope Params(Fn);
        for (TFieldIterator<FProperty> It(Fn); It; ++It)
            if ((*It)->HasAnyPropertyFlags(CPF_Parm) && !(*It)->HasAnyPropertyFlags(CPF_ReturnParm))
                if (FIntProperty* Int = CastField<FIntProperty>(*It)) { Int->SetPropertyValue_InContainer(Params.GetStructMemory(), Index); break; }
        BossActor->ProcessEvent(Fn, Params.GetStructMemory());
        LastResult = FString::Printf(TEXT("Live action %d requested"), Index + 1);
    }
    else LastResult = TEXT("RequestCombatAction missing");
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
        LastResult = FString::Printf(TEXT("Preview %s: %s | no damage notify"), Played ? TEXT("PLAYING") : TEXT("FAILED"), *Path.GetAssetName());
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

void ABossMotionLabDirector::DrawDiagnostics() const
{
    if (!bShowHitboxes || !IsValid(BossActor) || !PlayerActor.IsValid()) return;
    const ACharacter* Boss = Cast<ACharacter>(BossActor);
    const ACharacter* Player = Cast<ACharacter>(PlayerActor.Get());
    if (!Boss || !Player) return;
    const UCapsuleComponent* Capsule = Player->GetCapsuleComponent();
    DrawDebugCapsule(GetWorld(), Capsule->GetComponentLocation(), Capsule->GetScaledCapsuleHalfHeight(),
        Capsule->GetScaledCapsuleRadius(), Capsule->GetComponentQuat(), FColor::Cyan, false, 0.f, 0, 2.f);
    const bool bOpen = ReadBool(BossActor, TEXT("bPhysicalStrikeOpen"));
    for (const FName Hand : {FName(TEXT("hand_l")), FName(TEXT("hand_r"))})
    {
        const FVector Position = Boss->GetMesh()->GetSocketLocation(Hand);
        DrawDebugSphere(GetWorld(), Position, 52.f, 12, bOpen ? FColor::Red : FColor::Yellow, false, 0.f, 0, 2.f);
    }
}

void ABossMotionLabDirector::DrawOverlay() const
{
    if (!GEngine) return;
    const FString Clip = CurrentClips && CurrentClips->IsValidIndex(ClipIndex) ? (*CurrentClips)[ClipIndex].GetAssetName() : TEXT("none");
    const FStructProperty* StateProperty = IsValid(BossActor) ? FindFProperty<FStructProperty>(BossActor->GetClass(), TEXT("BossState")) : nullptr;
    const FGameplayTag* State = StateProperty ? StateProperty->ContainerPtrToValuePtr<FGameplayTag>(BossActor) : nullptr;
    const FString StateName = State ? State->ToString() : TEXT("unknown");
    const FString Text = FString::Printf(
        TEXT("MOTION LAB | 1-9 live actions | Z X V B distance | R reset\n")
        TEXT("1 Combo01  2 GutPunch  3 Combo03  4 Sweep  5 JabJabHook\n")
        TEXT("6 GuardBreak  7 Dash  8 Approach  9 Jump\n")
        TEXT("[ ] browse   O preview   C focus/all   H hitbox\n")
        TEXT("T Slow01+Recovery | Y Slow02+Recovery | U Dash HIT | I Dash MISS\n")
        TEXT("Catalog %s %d/%d: %s\n")
        TEXT("HFSM %s\n")
        TEXT("Boss HP %.0f | Player HP %.0f | hand window %s | hit %s | distance %.0f cm\n")
        TEXT("Damage events %d | total %.0f\n")
        TEXT("%s"),
        CurrentClips == &FocusClips ? TEXT("review") : TEXT("all"), ClipIndex + 1, CurrentClips ? CurrentClips->Num() : 0, *Clip,
        *StateName,
        ReadNumber(BossActor, TEXT("CurrentHealth")), ReadNumber(PlayerActor.Get(), TEXT("CurrentHealth")),
        ReadBool(BossActor, TEXT("bPhysicalStrikeOpen")) ? TEXT("OPEN") : TEXT("closed"),
        ReadBool(BossActor, TEXT("bPhysicalStrikeHit")) ? TEXT("YES") : TEXT("no"),
        IsValid(BossActor) && PlayerActor.IsValid() ? FVector::Dist2D(BossActor->GetActorLocation(), PlayerActor->GetActorLocation()) : -1.f,
        DamageEventCount, DamageTotal,
        *LastResult);
    if (Overlay) Overlay->SetDisplayText(Text);
}

void ABossMotionLabDirector::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bInitialized) return;
    SuppressAutonomousChoice();
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
            LastResult += TEXT(" | finished");
        }
    }
    else
    {
        BossActor->SetActorTickEnabled(false);
        if (FObjectProperty* Active = FindFProperty<FObjectProperty>(BossActor->GetClass(), TEXT("ActiveAction")))
            Active->SetObjectPropertyValue_InContainer(BossActor, nullptr);
    }
    if (!Chain.IsEmpty() && GetWorld()->GetTimeSeconds() >= NextChainTime) AdvanceChain();
    DrawDiagnostics();
    DrawOverlay();
}
