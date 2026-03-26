// Fill out your copyright notice in the Description page of Project Settings.

#include "SkeletalExtractor.h"
#include "GameFramework/Actor.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/Skeleton.h"
#include "DrawDebugHelpers.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformFileManager.h"
#include "Serialization/Archive.h"

// Sets default values for this component's properties
USkeletalExtractor::USkeletalExtractor()
{
	// IMPORTANT: Set bCanEverTick to true so TickComponent is called every frame
	PrimaryComponentTick.bCanEverTick = true;
	BodySkeletalMesh = nullptr;
	FaceSkeletalMesh = nullptr;
	LowerLimbSkeletalMesh = nullptr; // Initialize the new pointer

	// Initialize properties for file output
	bWriteToTextFile = true;
	TextFileNameBase = "BoneLocations.txt";

	// NEW: Initialize JSON properties
	bWriteToJsonFile = true;
	JsonFileNameBase = "BoneLocations.json";
}

// Called when the game starts
void USkeletalExtractor::BeginPlay()
{
	Super::BeginPlay();

	AActor* OwnerActor = GetOwner();
	if (OwnerActor)
	{
		FString OwnerActorName = OwnerActor->GetName();
		UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor attached to Actor: %s"), *OwnerActorName);

		TArray<USkeletalMeshComponent*> SkeletalMeshComponents;
		OwnerActor->GetComponents<USkeletalMeshComponent>(SkeletalMeshComponents);

		if (SkeletalMeshComponents.Num() > 0)
		{
			UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Scanning for Skeletal Mesh Components on Actor: %s"), *OwnerActorName);

			for (USkeletalMeshComponent* MeshComp : SkeletalMeshComponents)
			{
				if (MeshComp)
				{
					FString ComponentName = MeshComp->GetName();
					FString AssetName = MeshComp->GetSkeletalMeshAsset() ? MeshComp->GetSkeletalMeshAsset()->GetName() : TEXT("N/A (No Asset)");
					UE_LOG(LogTemp, Log, TEXT("  - Found component: '%s' (Asset: '%s')"), *ComponentName, *AssetName);

					if (ComponentName == TEXT("Body"))
					{
						BodySkeletalMesh = MeshComp;
						UE_LOG(LogTemp, Display, TEXT("SkeletalExtractor: Successfully identified and stored the 'Body' USkeletalMeshComponent instance for %s."), *OwnerActorName);
					}
					else if (ComponentName == TEXT("Face"))
					{
						FaceSkeletalMesh = MeshComp;
						UE_LOG(LogTemp, Display, TEXT("SkeletalExtractor: Successfully identified and stored the 'Face' USkeletalMeshComponent instance for %s."), *OwnerActorName);
					}
					// If you have a separate "LowerLimb" component, you would add an else if here:
					// else if (ComponentName == TEXT("LowerLimb"))
					// {
					//     LowerLimbSkeletalMesh = MeshComp;
					//     UE_LOG(LogTemp, Display, TEXT("SkeletalExtractor: Successfully identified and stored the 'LowerLimb' USkeletalMeshComponent instance for %s."), *OwnerActorName);
					// }
				}
			}

			// --- Process both Body and Face meshes for initial data saving ---
			// The drawing logic will be moved to TickComponent
			if (BodySkeletalMesh)
			{
				ExtractAndSaveMeshBones(BodySkeletalMesh, TEXT("Body"));
			}
			else
			{
				UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: 'Body' USkeletalMeshComponent instance NOT FOUND on %s. Bone extraction for Body skipped."), *OwnerActorName);
			}

			if (FaceSkeletalMesh)
			{
				ExtractAndSaveMeshBones(FaceSkeletalMesh, TEXT("Face"));
			}
			else
			{
				UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: 'Face' USkeletalMeshComponent instance NOT FOUND on %s. Bone extraction for Face skipped."), *OwnerActorName);
			}
			// If you add LowerLimbSkeletalMesh:
			// if (LowerLimbSkeletalMesh)
			// {
			//     ExtractAndSaveMeshBones(LowerLimbSkeletalMesh, TEXT("LowerLimb"));
			// }
			// else
			// {
			//     UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: 'LowerLimb' USkeletalMeshComponent instance NOT FOUND on %s. Bone extraction for LowerLimb skipped."), *OwnerActorName);
			// }
			// --- End Initial Processing ---

			// Store the keypoint lists for drawing in TickComponent
			FaceKeypointsToDraw = GetFaceKeypointsToExtract();
			UpperBodyKeypointsToDraw = GetUpperBodyKeypointsToExtract();
			LowerBodyKeypointsToDraw = GetLowerBodyKeypointsToExtract(); // Assuming you want to draw these

			if (!BodySkeletalMesh && !FaceSkeletalMesh) // Add LowerLimbSkeletalMesh check here if applicable
			{
				UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Neither 'Body' nor 'Face' USkeletalMeshComponent instances were found on %s."), *OwnerActorName);
			}
		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: No SkeletalMeshComponents found on Actor: %s!"), *OwnerActorName);
		}
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Component owner is null!"));
	}
}

// Called every frame - THIS IS WHERE THE DRAWING WILL HAPPEN
void USkeletalExtractor::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	//UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: TickComponent is ticking!"));

	// Ensure we have a valid world to draw in
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// Draw Face Keypoints (Red)
	if (FaceSkeletalMesh && FaceSkeletalMesh->GetSkeletalMeshAsset())
	{
		FColor DrawColor = FColor::Red;
		float PointSize = 3.0f;
		float Duration = 0.0f; // Draw for a single frame. Use a small positive value like 0.1f if points flicker.

		for (const FName& KeypointName : FaceKeypointsToDraw)
		{
			FVector WorldLocation = FaceSkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
			// Changed bPersistentLines to false, and Lifetime to 0.0 for single frame draw
			DrawDebugPoint(World, WorldLocation, PointSize, DrawColor, false, Duration, SDPG_Foreground);
		}
	}

	// Draw Upper Body Keypoints (Blue)
	if (BodySkeletalMesh && BodySkeletalMesh->GetSkeletalMeshAsset()) // Assuming upper body bones are on the "Body" mesh
	{
		FColor DrawColor = FColor::Blue;
		float PointSize = 3.0f;
		float Duration = 0.0f;

		for (const FName& KeypointName : UpperBodyKeypointsToDraw)
		{
			FVector WorldLocation = BodySkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
			if (WorldLocation == FVector::ZeroVector)
			{
				UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Upper Body Bone '%s' not found or returned zero location on BodySkeletalMesh!"), *KeypointName.ToString());
			}
			else
			{
				DrawDebugPoint(World, WorldLocation, PointSize, DrawColor, false, Duration, SDPG_Foreground);
				// Optional: Log successful draws too, but keep it concise for performance
				// UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Drawing Upper Body Bone '%s' at %s"), *KeypointName.ToString(), *WorldLocation.ToString());
			}
		}

		// Draw Lower Body Keypoints (Green) - assuming these are also on the "Body" mesh
		FColor LowerDrawColor = FColor::Green;
		float LowerPointSize = 3.0f;

		for (const FName& KeypointName : LowerBodyKeypointsToDraw)
		{
			FVector WorldLocation = BodySkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
			if (WorldLocation == FVector::ZeroVector)
			{
				UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Lower Body Bone '%s' NOT FOUND or returned zero location on BodySkeletalMesh at Tick!"), *KeypointName.ToString());
			}
			else
			{
				DrawDebugPoint(World, WorldLocation, LowerPointSize, LowerDrawColor, false, Duration, SDPG_Foreground);
			}
		}
	}
	// If you have a separate LowerLimbSkeletalMesh for lower body points, you'd do:
	// if (LowerLimbSkeletalMesh && LowerLimbSkeletalMesh->GetSkeletalMeshAsset())
	// {
	//     FColor LowerDrawColor = FColor::Green;
	//     float LowerPointSize = 3.0f;
	//     float Duration = 0.0f;
	//     for (const FName& KeypointName : LowerBodyKeypointsToDraw)
	//     {
	//         FVector WorldLocation = LowerLimbSkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
	//         DrawDebugPoint(World, WorldLocation, LowerPointSize, LowerDrawColor, false, Duration, SDPG_Foreground);
	//     }
	// }
}

// Full implementation of GetBoneLocationForMeshByName (Operates on instance-specific SkeletalMesh)
FVector USkeletalExtractor::GetBoneLocationForMeshByName(USkeletalMeshComponent* SkeletalMesh, FName BoneName)
{
	if (SkeletalMesh)
	{
		return SkeletalMesh->GetBoneLocation(BoneName, EBoneSpaces::WorldSpace);
	}
	UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: SkeletalMesh is NULL in GetBoneLocationForMeshByName for bone '%s'."), *BoneName.ToString());
	return FVector::ZeroVector;
}

// Implementation of the new member function to extract and save bone data
void USkeletalExtractor::ExtractAndSaveMeshBones(USkeletalMeshComponent* SkeletalMesh, const FString& MeshType)
{
	if (!SkeletalMesh)
	{
		UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor: Cannot extract bones for '%s' mesh, component is NULL."), *MeshType);
		return;
	}

	FString OwnerActorName = GetOwner() ? GetOwner()->GetName() : TEXT("UnknownActor");
	USkeletalMesh* SkeletalMeshAsset = SkeletalMesh->GetSkeletalMeshAsset();
	if (SkeletalMeshAsset)
	{
		USkeleton* SkeletonAsset = SkeletalMeshAsset->GetSkeleton();
		if (SkeletonAsset)
		{
			// --- BEGIN MODIFIED LOGIC FOR MULTIPLE FILES AND SELECTIVE DRAWING ---

			// 1. Process and save ALL bones for the current MeshType (e.g., Body or Face - all bones)
			TArray<FName> AllBoneNamesInMesh;
			TArray<FVector> AllBoneLocationsInMesh;

			const FReferenceSkeleton& RefSkeleton = SkeletonAsset->GetReferenceSkeleton();
			int32 NumBones = RefSkeleton.GetRawBoneNum();

			for (int32 i = 0; i < NumBones; ++i)
			{
				FName CurrentBoneName = RefSkeleton.GetBoneName(i);
				AllBoneNamesInMesh.Add(CurrentBoneName);
				FVector WorldLocation = SkeletalMesh->GetBoneLocation(CurrentBoneName, EBoneSpaces::WorldSpace);
				AllBoneLocationsInMesh.Add(WorldLocation);
			}

			UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Listing ALL bone names AND World Locations from '%s' (%s) (Skeleton: %s) on Actor: %s (Total Bones: %d)"),
				*SkeletalMesh->GetName(), *MeshType, *SkeletonAsset->GetName(), *OwnerActorName, AllBoneNamesInMesh.Num());

			// Save ALL bones to a text file. Use the default TextFileNameBase for all bones.
			if (bWriteToTextFile)
			{
				FString CurrentMeshSaveSubFolder = TEXT(""); // No subfolder for all bones
				SaveBoneDataToTextFile(AllBoneNamesInMesh, AllBoneLocationsInMesh, MeshType, CurrentMeshSaveSubFolder);
			}

			// NEW: Save ALL bones to a JSON file.
			if (bWriteToJsonFile)
			{
				FString CurrentMeshSaveSubFolder = TEXT("");
				SaveBoneDataToJsonFile(AllBoneNamesInMesh, AllBoneLocationsInMesh, MeshType, CurrentMeshSaveSubFolder);
			}

			// --- Handle Face Mesh Specifics (Subset File) ---
			// Drawing is now in TickComponent
			if (MeshType == TEXT("Face"))
			{
				TArray<FName> FaceKeypointsLocal = GetFaceKeypointsToExtract(); // Use a local variable
				TArray<FVector> FaceKeypointLocations;

				for (const FName& KeypointName : FaceKeypointsLocal)
				{
					FVector WorldLocation = SkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
					FaceKeypointLocations.Add(WorldLocation);
				}

				UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Extracting ONLY specified Face Keypoints for '%s' (%s) on Actor: %s (Total Keypoints: %d)"),
					*SkeletalMesh->GetName(), *MeshType, *OwnerActorName, FaceKeypointsLocal.Num());

				// Save the subset of face keypoints to the "FaceSubset" folder (Text)
				if (bWriteToTextFile)
				{
					FString FaceSubsetSubFolder = TEXT("FaceSubset");
					FString SubsetFileContent = FString::Printf(TEXT("%s YoloPose Keypoint Locations:\n\n"), *MeshType);
					for (int32 i = 0; i < FaceKeypointsLocal.Num(); ++i)
					{
						SubsetFileContent += FString::Printf(TEXT("Bone Name: %s, World Location: X=%.4f, Y=%.4f, Z=%.4f\n"),
							*FaceKeypointsLocal[i].ToString(), FaceKeypointLocations[i].X, FaceKeypointLocations[i].Y, FaceKeypointLocations[i].Z);
					}
					FString ActorNameForSubset = GetOwner() ? GetOwner()->GetName() : TEXT("UnknownActor");
					FString MeshTypeForSubsetFilename = MeshType.Replace(TEXT("Face"), TEXT("FaceSubset.txt"));
					FString GeneratedSubsetFileName = FString::Printf(TEXT("%s_%s"), *ActorNameForSubset, *MeshTypeForSubsetFilename);

					FString SaveDirectory = FPaths::ProjectSavedDir();
					FString AbsoluteSubsetFilePath = FPaths::Combine(SaveDirectory, FaceSubsetSubFolder, GeneratedSubsetFileName);

					IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
					FString DirectoryPath = FPaths::GetPath(AbsoluteSubsetFilePath);
					if (!PlatformFile.DirectoryExists(*DirectoryPath))
					{
						UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor: Creating directory tree for face subset text file: %s"), *DirectoryPath);
						PlatformFile.CreateDirectoryTree(*DirectoryPath);
					}

					if (FFileHelper::SaveStringToFile(SubsetFileContent, *AbsoluteSubsetFilePath))
					{
						UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Successfully saved %s YoloPose keypoint data to text file: %s"), *MeshType, *AbsoluteSubsetFilePath);
					}
					else
					{
						UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Failed to save %s YoloPose keypoint data to text file: %s. Check permissions or path validity."), *MeshType, *AbsoluteSubsetFilePath);
					}
				}
				// NEW: Save the subset of face keypoints to the "FaceSubset" folder (JSON)
				if (bWriteToJsonFile)
				{
					FString FaceSubsetSubFolder = TEXT("FaceSubset");
					SaveBoneDataToJsonFile(FaceKeypointsLocal, FaceKeypointLocations, TEXT("FaceSubset"), FaceSubsetSubFolder);
				}
			}
			// --- Handle Upper Body Mesh Specifics (Subset File) ---
			// Drawing is now in TickComponent
			else if (MeshType == TEXT("Body")) // Still tied to "Body" mesh component name
			{
				TArray<FName> UpperBodyKeypointsLocal = GetUpperBodyKeypointsToExtract(); // Use a local variable
				TArray<FVector> UpperBodyKeypointLocations;

				TArray<FName> LowerBodyKeypointsLocal = GetLowerBodyKeypointsToExtract(); // Use a local variable
				TArray<FVector> LowerBodyKeypointLocations;

				for (const FName& KeypointName : UpperBodyKeypointsLocal)
				{
					FVector WorldLocation = SkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
					UpperBodyKeypointLocations.Add(WorldLocation);
				}

				for (const FName& KeypointName : LowerBodyKeypointsLocal)
				{
					FVector WorldLocation = SkeletalMesh->GetBoneLocation(KeypointName, EBoneSpaces::WorldSpace);
					LowerBodyKeypointLocations.Add(WorldLocation);
				}

				UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Extracting ONLY specified Upper Body Keypoints for '%s' (%s) on Actor: %s (Total Keypoints: %d)"),
					*SkeletalMesh->GetName(), *MeshType, *OwnerActorName, UpperBodyKeypointsLocal.Num());

				UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Extracting ONLY specified Lower Body Keypoints for '%s' (%s) on Actor: %s (Total Keypoints: %d"),
					*SkeletalMesh->GetName(), *MeshType, *OwnerActorName, LowerBodyKeypointsLocal.Num());

				// Save the subset of upper body keypoints to the "UpperBodySubset" folder (Text)
				if (bWriteToTextFile)
				{
					FString UpperBodySubsetSubFolder = TEXT("UpperBodySubset"); // Renamed subfolder
					FString SubsetTextFileNameBase = "UpperBodyKeypoints.txt"; // Renamed file suffix

					FString SubsetFileContent = FString::Printf(TEXT("%s YoloPose Upper Body Keypoint Locations:\n\n"), *MeshType);
					for (int32 i = 0; i < UpperBodyKeypointsLocal.Num(); ++i)
					{
						SubsetFileContent += FString::Printf(TEXT("Bone Name: %s, World Location: X=%.4f, Y=%.4f, Z=%.4f\n"),
							*UpperBodyKeypointsLocal[i].ToString(), UpperBodyKeypointLocations[i].X, UpperBodyKeypointLocations[i].Y, UpperBodyKeypointLocations[i].Z);
					}

					AActor* OwnerActorForSubset = GetOwner();
					FString ActorNameForSubset = OwnerActorForSubset ? OwnerActorForSubset->GetName() : TEXT("UnknownActor");

					// Adjust filename to reflect UpperBodySubset
					FString MeshTypeForSubsetFilename = MeshType.Replace(TEXT("Body"), TEXT("UpperBodySubset"));
					FString GeneratedSubsetFileName = FString::Printf(TEXT("%s_%s_%s"), *ActorNameForSubset, *MeshTypeForSubsetFilename, *SubsetTextFileNameBase);

					FString SaveDirectory = FPaths::ProjectSavedDir();
					FString AbsoluteSubsetFilePath = FPaths::Combine(SaveDirectory, UpperBodySubsetSubFolder, GeneratedSubsetFileName);

					IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
					FString DirectoryPath = FPaths::GetPath(AbsoluteSubsetFilePath);
					if (!PlatformFile.DirectoryExists(*DirectoryPath))
					{
						UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor: Creating directory tree for upper body subset text file: %s"), *DirectoryPath);
						PlatformFile.CreateDirectoryTree(*DirectoryPath);
					}

					if (FFileHelper::SaveStringToFile(SubsetFileContent, *AbsoluteSubsetFilePath))
					{
						UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Successfully saved %s YoloPose upper body keypoint data to text file: %s"), *MeshType, *AbsoluteSubsetFilePath);
					}
					else
					{
						UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Failed to save %s YoloPose upper body keypoint data to text file: %s. Check permissions or path validity."), *MeshType, *AbsoluteSubsetFilePath);
					}

					// Also save lower body keypoints if they are intended to be saved in a separate file (Text)
					FString LowerBodySubsetSubFolder = TEXT("LowerBodySubset");
					FString LowerBodySubsetTextFileNameBase = "LowerBodyKeypoints.txt";
					FString LowerBodySubsetFileContent = FString::Printf(TEXT("%s YoloPose Lower Body Keypoint Locations:\n\n"), *MeshType);
					for (int32 i = 0; i < LowerBodyKeypointsLocal.Num(); ++i)
					{
						LowerBodySubsetFileContent += FString::Printf(TEXT("Bone Name: %s, World Location: X=%.4f, Y=%.4f, Z=%.4f\n"),
							*LowerBodyKeypointsLocal[i].ToString(), LowerBodyKeypointLocations[i].X, LowerBodyKeypointLocations[i].Y, LowerBodyKeypointLocations[i].Z);
					}
					FString LowerBodyMeshTypeForSubsetFilename = MeshType.Replace(TEXT("Body"), TEXT("LowerBodySubset"));
					FString LowerBodyGeneratedSubsetFileName = FString::Printf(TEXT("%s_%s_%s"), *ActorNameForSubset, *LowerBodyMeshTypeForSubsetFilename, *LowerBodySubsetTextFileNameBase);
					FString AbsoluteLowerBodySubsetFilePath = FPaths::Combine(SaveDirectory, LowerBodySubsetSubFolder, LowerBodyGeneratedSubsetFileName);

					if (!PlatformFile.DirectoryExists(*FPaths::GetPath(AbsoluteLowerBodySubsetFilePath)))
					{
						UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor: Creating directory tree for lower body subset text file: %s"), *FPaths::GetPath(AbsoluteLowerBodySubsetFilePath));
						PlatformFile.CreateDirectoryTree(*FPaths::GetPath(AbsoluteLowerBodySubsetFilePath));
					}

					if (FFileHelper::SaveStringToFile(LowerBodySubsetFileContent, *AbsoluteLowerBodySubsetFilePath))
					{
						UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Successfully saved %s YoloPose lower body keypoint data to text file: %s"), *MeshType, *AbsoluteLowerBodySubsetFilePath);
					}
					else
					{
						UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Failed to save %s YoloPose lower body keypoint data to text file: %s. Check permissions or path validity."), *MeshType, *AbsoluteLowerBodySubsetFilePath);
					}
				}
				else
				{
					UE_LOG(LogTemp, Warning, TEXT("SkeletalExtractor: bWriteToTextFile is FALSE. Skipping YoloPose upper/lower body keypoint file save for %s."), *MeshType);
				}

				// NEW: Save the subset of upper and lower body keypoints to a JSON file
				if (bWriteToJsonFile)
				{
					// Upper Body JSON
					FString UpperBodySubsetSubFolder = TEXT("UpperBodySubset");
					SaveBoneDataToJsonFile(UpperBodyKeypointsLocal, UpperBodyKeypointLocations, TEXT("UpperBodySubset"), UpperBodySubsetSubFolder);

					// Lower Body JSON
					FString LowerBodySubsetSubFolder = TEXT("LowerBodySubset");
					SaveBoneDataToJsonFile(LowerBodyKeypointsLocal, LowerBodyKeypointLocations, TEXT("LowerBodySubset"), LowerBodySubsetSubFolder);
				}
			}
			// --- END MODIFIED LOGIC ---

		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: USkeleton asset is NULL for SkeletalMesh '%s' (%s) on %s."),
				*SkeletalMeshAsset->GetName(), *MeshType, *OwnerActorName);
		}
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: USkeletalMesh asset is NULL for '%s' component on %s."),
			*MeshType, *OwnerActorName);
	}
}

// This function is now specifically for saving a generic set of bone data,
// with filename control happening in ExtractAndSaveMeshBones for distinct files.
void USkeletalExtractor::SaveBoneDataToTextFile(const TArray<FName>& BoneNames, const TArray<FVector>& BoneLocations, const FString& MeshType, const FString& SubFolder)
{
	if (BoneNames.Num() != BoneLocations.Num())
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: BoneNames and BoneLocations arrays do not match in size for text file export for %s mesh."), *MeshType);
		return;
	}

	FString FileContent = FString::Printf(TEXT("%s Bone Locations:\n\n"), *MeshType);

	for (int32 i = 0; i < BoneNames.Num(); ++i)
	{
		FileContent += FString::Printf(TEXT("Bone Name: %s, World Location: X=%.4f, Y=%.4f, Z=%.4f\n"),
			*BoneNames[i].ToString(), BoneLocations[i].X, BoneLocations[i].Y, BoneLocations[i].Z);
	}

	AActor* OwnerActor = GetOwner();
	FString ActorName = OwnerActor ? OwnerActor->GetName() : TEXT("UnknownActor");

	// Use TextFileNameBase for general bone locations
	FString GeneratedFileName = FString::Printf(TEXT("%s_%s_%s"), *ActorName, *MeshType, *TextFileNameBase);

	FString SaveDirectory = FPaths::ProjectSavedDir();

	// Construct the full path, including the subfolder if provided
	FString AbsoluteFilePath;
	if (!SubFolder.IsEmpty())
	{
		AbsoluteFilePath = FPaths::Combine(SaveDirectory, SubFolder, GeneratedFileName);
	}
	else
	{
		AbsoluteFilePath = FPaths::Combine(SaveDirectory, GeneratedFileName);
	}

	// Ensure the directory exists
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
	FString DirectoryPath = FPaths::GetPath(AbsoluteFilePath);
	if (!PlatformFile.DirectoryExists(*DirectoryPath))
	{
		PlatformFile.CreateDirectoryTree(*DirectoryPath);
	}

	if (FFileHelper::SaveStringToFile(FileContent, *AbsoluteFilePath))
	{
		UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Successfully saved %s bone data to text file: %s"), *MeshType, *AbsoluteFilePath);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Failed to save %s bone data to text file: %s"), *MeshType, *AbsoluteFilePath);
	}
}

// NEW: This function saves a generic set of bone data to a JSON file.
void USkeletalExtractor::SaveBoneDataToJsonFile(const TArray<FName>& BoneNames, const TArray<FVector>& BoneLocations, const FString& MeshType, const FString& SubFolder)
{
	if (BoneNames.Num() != BoneLocations.Num())
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: BoneNames and BoneLocations arrays do not match in size for JSON export for %s mesh."), *MeshType);
		return;
	}

	// Create the main JSON object
	TSharedPtr<FJsonObject> RootJsonObject = MakeShareable(new FJsonObject);

	// Add a top-level string for the mesh type
	RootJsonObject->SetStringField(TEXT("MeshType"), MeshType);

	// Create a JSON array to hold all the bone data
	TArray<TSharedPtr<FJsonValue>> KeypointArray;
	for (int32 i = 0; i < BoneNames.Num(); ++i)
	{
		// Create a JSON object for each bone
		TSharedPtr<FJsonObject> BoneObject = MakeShareable(new FJsonObject);
		BoneObject->SetStringField(TEXT("BoneName"), BoneNames[i].ToString());

		// Create a JSON object for the location vector
		TSharedPtr<FJsonObject> LocationObject = MakeShareable(new FJsonObject);
		LocationObject->SetNumberField(TEXT("X"), BoneLocations[i].X);
		LocationObject->SetNumberField(TEXT("Y"), BoneLocations[i].Y);
		LocationObject->SetNumberField(TEXT("Z"), BoneLocations[i].Z);

		BoneObject->SetObjectField(TEXT("WorldLocation"), LocationObject);

		// Add the bone object to the array
		KeypointArray.Add(MakeShareable(new FJsonValueObject(BoneObject)));
	}

	// Add the array of bones to the root object
	RootJsonObject->SetArrayField(TEXT("Keypoints"), KeypointArray);

	FString OutputString;
	TSharedRef<TJsonWriter<TCHAR>> JsonWriter = TJsonWriterFactory<TCHAR>::Create(&OutputString);
	FJsonSerializer::Serialize(RootJsonObject.ToSharedRef(), JsonWriter);

	// Construct the file path and save the file
	AActor* OwnerActor = GetOwner();
	FString ActorName = OwnerActor ? OwnerActor->GetName() : TEXT("UnknownActor");

	// Use JsonFileNameBase for general bone locations
	FString GeneratedFileName = FString::Printf(TEXT("%s_%s_%s"), *ActorName, *MeshType, *JsonFileNameBase);

	FString SaveDirectory = FPaths::ProjectSavedDir();
	FString AbsoluteFilePath;

	if (!SubFolder.IsEmpty())
	{
		AbsoluteFilePath = FPaths::Combine(SaveDirectory, SubFolder, GeneratedFileName);
	}
	else
	{
		AbsoluteFilePath = FPaths::Combine(SaveDirectory, GeneratedFileName);
	}

	// Ensure the directory exists
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
	FString DirectoryPath = FPaths::GetPath(AbsoluteFilePath);
	if (!PlatformFile.DirectoryExists(*DirectoryPath))
	{
		PlatformFile.CreateDirectoryTree(*DirectoryPath);
	}

	if (FFileHelper::SaveStringToFile(OutputString, *AbsoluteFilePath))
	{
		UE_LOG(LogTemp, Log, TEXT("SkeletalExtractor: Successfully saved %s bone data to JSON file: %s"), *MeshType, *AbsoluteFilePath);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("SkeletalExtractor: Failed to save %s bone data to JSON file: %s"), *MeshType, *AbsoluteFilePath);
	}
}


// Function to define the specific 17 face keypoints (from previous request)
TArray<FName> USkeletalExtractor::GetFaceKeypointsToExtract() const
{
	TArray<FName> Keypoints;

	// Left Ear
	Keypoints.Add(FName(TEXT("FACIAL_L_Ear1")));
	Keypoints.Add(FName(TEXT("FACIAL_L_Ear2")));
	Keypoints.Add(FName(TEXT("FACIAL_L_Ear3")));
	Keypoints.Add(FName(TEXT("FACIAL_L_Ear4")));

	// Right Ear
	Keypoints.Add(FName(TEXT("FACIAL_R_Ear1")));
	Keypoints.Add(FName(TEXT("FACIAL_R_Ear2")));
	Keypoints.Add(FName(TEXT("FACIAL_R_Ear3")));
	Keypoints.Add(FName(TEXT("FACIAL_R_Ear4")));

	// Eyes
	Keypoints.Add(FName(TEXT("FACIAL_L_EyeParallel")));
	Keypoints.Add(FName(TEXT("FACIAL_R_EyeParallel")));

	// Nose Tip
	Keypoints.Add(FName(TEXT("FACIAL_C_12IPV_NoseTip1")));
	Keypoints.Add(FName(TEXT("FACIAL_C_12IPV_NoseTip2")));
	Keypoints.Add(FName(TEXT("FACIAL_C_12IPV_NoseTip3")));
	Keypoints.Add(FName(TEXT("FACIAL_L_12IPV_NoseTip1")));
	Keypoints.Add(FName(TEXT("FACIAL_L_12IPV_NoseTip2")));
	Keypoints.Add(FName(TEXT("FACIAL_L_12IPV_NoseTip3")));
	Keypoints.Add(FName(TEXT("FACIAL_R_12IPV_NoseTip1")));
	Keypoints.Add(FName(TEXT("FACIAL_R_12IPV_NoseTip2")));
	Keypoints.Add(FName(TEXT("FACIAL_R_12IPV_NoseTip3")));

	return Keypoints;
}

// New: Function to define the specific upper body keypoints for subset
TArray<FName> USkeletalExtractor::GetLowerBodyKeypointsToExtract() const {
	TArray<FName> Keypoints;

	Keypoints.Add(FName(TEXT("thigh_r")));

	Keypoints.Add(FName(TEXT("bigtoe_01_r")));
	Keypoints.Add(FName(TEXT("bigtoe_01_l")));
	Keypoints.Add(FName(TEXT("bigtoe_02_r")));
	Keypoints.Add(FName(TEXT("bigtoe_02_l")));

	Keypoints.Add(FName(TEXT("calf_r")));
	Keypoints.Add(FName(TEXT("foot_r")));
	Keypoints.Add(FName(TEXT("ankle_bck_r")));
	Keypoints.Add(FName(TEXT("ankle_fwd_r")));
	Keypoints.Add(FName(TEXT("calf_twist_02_r")));
	Keypoints.Add(FName(TEXT("calf_twist_01_r")));
	Keypoints.Add(FName(TEXT("calf_correctiveRoot_r")));
	Keypoints.Add(FName(TEXT("calf_kneeBack_r")));
	Keypoints.Add(FName(TEXT("calf_knee_r")));
	Keypoints.Add(FName(TEXT("thigh_twist_01_r")));
	Keypoints.Add(FName(TEXT("thigh_twistCor_01_r")));
	Keypoints.Add(FName(TEXT("thigh_twist_02_r")));
	Keypoints.Add(FName(TEXT("thigh_twistCor_02_r")));
	Keypoints.Add(FName(TEXT("thigh_correctiveRoot_r")));
	Keypoints.Add(FName(TEXT("thigh_fwd_r")));
	Keypoints.Add(FName(TEXT("thigh_bck_r")));
	Keypoints.Add(FName(TEXT("thigh_out_r")));
	Keypoints.Add(FName(TEXT("thigh_in_r")));
	Keypoints.Add(FName(TEXT("thigh_bck_lwr_r")));
	Keypoints.Add(FName(TEXT("thigh_fwd_lwr_r")));
	Keypoints.Add(FName(TEXT("thigh_l")));
	Keypoints.Add(FName(TEXT("calf_l")));
	Keypoints.Add(FName(TEXT("foot_l")));
	Keypoints.Add(FName(TEXT("ankle_bck_l")));
	Keypoints.Add(FName(TEXT("ankle_fwd_l")));
	Keypoints.Add(FName(TEXT("calf_twist_02_l")));
	Keypoints.Add(FName(TEXT("calf_twistCor_02_l")));
	Keypoints.Add(FName(TEXT("calf_twist_01_l")));
	Keypoints.Add(FName(TEXT("calf_correctiveRoot_l")));
	Keypoints.Add(FName(TEXT("calf_kneeBack_l")));
	Keypoints.Add(FName(TEXT("calf_knee_l")));
	Keypoints.Add(FName(TEXT("thigh_twist_01_l")));
	Keypoints.Add(FName(TEXT("thigh_twistCor_01_l")));
	Keypoints.Add(FName(TEXT("thigh_twist_02_l")));
	Keypoints.Add(FName(TEXT("thigh_twistCor_02_l")));
	Keypoints.Add(FName(TEXT("thigh_correctiveRoot_l")));
	Keypoints.Add(FName(TEXT("thigh_bck_l")));
	Keypoints.Add(FName(TEXT("thigh_fwd_l")));
	Keypoints.Add(FName(TEXT("thigh_out_l")));
	Keypoints.Add(FName(TEXT("thigh_bck_lwr_l")));
	Keypoints.Add(FName(TEXT("thigh_in_l")));
	Keypoints.Add(FName(TEXT("thigh_fwd_lwr_l")));

	return Keypoints;
}

TArray<FName> USkeletalExtractor::GetUpperBodyKeypointsToExtract() const
{
	TArray<FName> Keypoints;

	// Spine
	Keypoints.Add(FName(TEXT("spine_01")));
	Keypoints.Add(FName(TEXT("spine_02")));
	Keypoints.Add(FName(TEXT("spine_03")));
	Keypoints.Add(FName(TEXT("spine_04")));
	Keypoints.Add(FName(TEXT("spine_05")));

	// Left Arm

	Keypoints.Add(FName(TEXT("wrist_inner_l")));
	Keypoints.Add(FName(TEXT("wrist_outer_l")));
	Keypoints.Add(FName(TEXT("hand_l")));
	Keypoints.Add(FName(TEXT("middle_01_mcp_l")));

	Keypoints.Add(FName(TEXT("clavicle_l")));
	Keypoints.Add(FName(TEXT("upperarm_l")));
	Keypoints.Add(FName(TEXT("upperarm_correctiveRoot_l")));
	Keypoints.Add(FName(TEXT("upperarm_bck_l")));
	Keypoints.Add(FName(TEXT("upperarm_fwd_l")));
	Keypoints.Add(FName(TEXT("upperarm_in_l")));
	Keypoints.Add(FName(TEXT("upperarm_out_l")));
	Keypoints.Add(FName(TEXT("lowerarm_l")));
	Keypoints.Add(FName(TEXT("hand_l")));
	Keypoints.Add(FName(TEXT("lowerarm_twist_02_l")));
	Keypoints.Add(FName(TEXT("lowerarm_twist_01_l")));
	Keypoints.Add(FName(TEXT("lowerarm_correctiveRoot_l")));
	Keypoints.Add(FName(TEXT("lowerarm_in_l")));
	Keypoints.Add(FName(TEXT("lowerarm_out_l")));
	Keypoints.Add(FName(TEXT("lowerarm_fwd_l")));
	Keypoints.Add(FName(TEXT("lowerarm_bck_l")));
	Keypoints.Add(FName(TEXT("upperarm_twist_01_l")));
	Keypoints.Add(FName(TEXT("upperarm_twistCor_01_l")));
	Keypoints.Add(FName(TEXT("upperarm_twist_02_l")));
	Keypoints.Add(FName(TEXT("upperarm_tricep_l")));
	Keypoints.Add(FName(TEXT("upperarm_bicep_l")));
	Keypoints.Add(FName(TEXT("upperarm_twistCor_02_l")));
	Keypoints.Add(FName(TEXT("clavicle_out_l")));
	Keypoints.Add(FName(TEXT("clavicle_scap_l")));

	// Right Arm (mirror of left arm)
	Keypoints.Add(FName(TEXT("wrist_inner_r")));
	Keypoints.Add(FName(TEXT("wrist_outer_r")));
	Keypoints.Add(FName(TEXT("hand_r")));
	Keypoints.Add(FName(TEXT("middle_01_mcp_r")));

	Keypoints.Add(FName(TEXT("clavicle_r")));
	Keypoints.Add(FName(TEXT("upperarm_r")));
	Keypoints.Add(FName(TEXT("upperarm_correctiveRoot_r")));
	Keypoints.Add(FName(TEXT("upperarm_bck_r")));
	Keypoints.Add(FName(TEXT("upperarm_in_r")));
	Keypoints.Add(FName(TEXT("upperarm_fwd_r")));
	Keypoints.Add(FName(TEXT("upperarm_out_r")));
	Keypoints.Add(FName(TEXT("lowerarm_r")));
	Keypoints.Add(FName(TEXT("hand_r")));
	Keypoints.Add(FName(TEXT("lowerarm_twist_02_r")));
	Keypoints.Add(FName(TEXT("lowerarm_twist_01_r")));
	Keypoints.Add(FName(TEXT("lowerarm_correctiveRoot_r")));
	Keypoints.Add(FName(TEXT("lowerarm_out_r")));
	Keypoints.Add(FName(TEXT("lowerarm_in_r")));
	Keypoints.Add(FName(TEXT("lowerarm_fwd_r")));
	Keypoints.Add(FName(TEXT("lowerarm_bck_r")));
	Keypoints.Add(FName(TEXT("upperarm_twist_01_r")));
	Keypoints.Add(FName(TEXT("upperarm_twistCor_01_r")));
	Keypoints.Add(FName(TEXT("upperarm_twist_02_r")));
	Keypoints.Add(FName(TEXT("upperarm_tricep_r")));
	Keypoints.Add(FName(TEXT("upperarm_bicep_r")));
	Keypoints.Add(FName(TEXT("upperarm_twistCor_02_r")));
	Keypoints.Add(FName(TEXT("clavicle_out_r")));
	Keypoints.Add(FName(TEXT("clavicle_scap_r")));

	return Keypoints;
}