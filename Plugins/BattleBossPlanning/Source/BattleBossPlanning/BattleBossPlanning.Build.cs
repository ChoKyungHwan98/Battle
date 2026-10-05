using UnrealBuildTool;

public class BattleBossPlanning : ModuleRules
{
    public BattleBossPlanning(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "AssetRegistry", "GameplayTags", "UMG", "Slate", "SlateCore", "AIModule", "NavigationSystem" });
    }
}
