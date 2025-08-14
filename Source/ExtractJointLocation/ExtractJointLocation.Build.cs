// Fill out your copyright notice in the Description page of Project Settings.

using UnrealBuildTool;

public class ExtractJointLocation : ModuleRules
{
	public ExtractJointLocation(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] { 
			"CinematicCamera",
			"Core", 
			"CoreUObject", 
			"Engine", 
			"ImageWriteQueue",
			"InputCore", 
			"Json",
            "RenderCore"      
		});
		
		PrivateDependencyModuleNames.AddRange(new string[] { 
			"Core",
			"CoreUObject",
			"Engine",
			"ImageCore",
			"ImageWriteQueue",
			"ImageWrapper",
			"Json",
			"Projects",
			"RenderCore" // May also be needed for texture resources

		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });
		
		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
