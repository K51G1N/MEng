// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Components/SkeletalMeshComponent.h" // For USkeletalMeshComponent
#include "Dom/JsonObject.h" // Include for FJsonObject
#include "Serialization/JsonWriter.h" // Include for TJsonWriter
#include "Serialization/JsonSerializer.h" // Include for FJsonSerializer

#include "SkeletalExtractor.generated.h"

UCLASS(ClassGroup = (Custom), meta = (BlueprintSpawnableComponent))
class EXTRACTJOINTLOCATION_API USkeletalExtractor : public UActorComponent
{
	GENERATED_BODY()

public:
	// Sets default values for this component's properties
	USkeletalExtractor();

protected:
	// Called when the game starts
	virtual void BeginPlay() override;

public:
	// Called every frame
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// Function to get bone location by name in global world coordinates for a specific skeletal mesh
	UFUNCTION(BlueprintCallable, Category = "Skeletal Extraction")
	FVector GetBoneLocationForMeshByName(USkeletalMeshComponent* SkeletalMesh, FName BoneName);

private:
	// This will hold the pointer to the *specific instance* of the Body skeletal mesh component
	UPROPERTY()
	USkeletalMeshComponent* BodySkeletalMesh;

	// Pointer to the *specific instance* of the Face skeletal mesh component
	UPROPERTY()
	USkeletalMeshComponent* FaceSkeletalMesh;

	// New: Pointer to the *specific instance* of the LowerLimb skeletal mesh component
	UPROPERTY()
	USkeletalMeshComponent* LowerLimbSkeletalMesh;

	// Properties for file output configuration
	UPROPERTY(EditAnywhere, Category = "Skeletal Extraction | Output")
	bool bWriteToTextFile;

	// NEW: Property to enable JSON output
	UPROPERTY(EditAnywhere, Category = "Skeletal Extraction | Output")
	bool bWriteToJsonFile;

	UPROPERTY(EditAnywhere, Category = "Skeletal Extraction | Output",
		meta = (Tooltip = "Base name for the text file. The actor's name and mesh type will be prepended (e.g., 'BP_MetaHuman_C_0_BoneLocations.txt')."))
	FString TextFileNameBase;

	// NEW: Property for the base JSON file name
	UPROPERTY(EditAnywhere, Category = "Skeletal Extraction | Output",
		meta = (Tooltip = "Base name for the JSON file. The actor's name and mesh type will be prepended (e.g., 'BP_MetaHuman_C_0_BoneLocations.json')."))
	FString JsonFileNameBase;

	// --- NEW: Arrays to store bone names for drawing ---
	TArray<FName> FaceKeypointsToDraw;
	TArray<FName> UpperBodyKeypointsToDraw;
	TArray<FName> LowerBodyKeypointsToDraw;
	// --- END NEW ---

	// New private function for text file saving, now takes a mesh type string
	void SaveBoneDataToTextFile(const TArray<FName>& BoneNames, const TArray<FVector>& BoneLocations, const FString& MeshType, const FString& SubFolder);

	// NEW: Private function to save data to a JSON file
	void SaveBoneDataToJsonFile(const TArray<FName>& BoneNames, const TArray<FVector>& BoneLocations, const FString& MeshType, const FString& SubFolder);

	// Modified: Member function to extract and save bone data for a given skeletal mesh,
	// now accepts an optional list of specific bone names to extract.
	void ExtractAndSaveMeshBones(USkeletalMeshComponent* SkeletalMesh, const FString& MeshType);

	// Function to define the specific 17 face keypoints
	TArray<FName> GetFaceKeypointsToExtract() const;

	// Function to define the specific upper body keypoints for subset
	TArray<FName> GetUpperBodyKeypointsToExtract() const;

	TArray<FName> GetLowerBodyKeypointsToExtract() const;
};