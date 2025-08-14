// CameraDataComponent.h
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/TextureRenderTarget2D.h"
#include "ImageWriteBlueprintLibrary.h"
#include "CameraDataComponent.generated.h"


// Struct to hold camera intrinsic data
USTRUCT(BlueprintType)
struct FCameraIntrinsics
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	float FocalLengthX; // fx
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	float FocalLengthY; // fy (often same as fx for square pixels)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	float PrincipalPointX; // cx
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	float PrincipalPointY; // cy
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	int32 ImageWidth;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	int32 ImageHeight;
};

UCLASS(ClassGroup = (Custom), meta = (BlueprintSpawnableComponent))
class EXTRACTJOINTLOCATION_API UCameraDataComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	// Sets default values for this component's properties
	UCameraDataComponent();

protected:
	// Called when the game starts
	virtual void BeginPlay() override;

public:
	// Called every frame
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/**
	 * Optional: Render target to use for image dimensions and saving.
	 * Assign this in the editor if your camera is a SceneCapture2D and you want to save its output.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	UTextureRenderTarget2D* TargetRenderTarget;

	/**
	 * Optional: Filename for saving camera data (e.g., "CameraData_MyCamera.txt").
	 * If empty, a default name will be generated.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	FString CameraDataFilename;

	/**
	 * Optional: Filename for saving the render target image (e.g., "Frame_001.png").
	 * Only used if TargetRenderTarget is assigned. If empty, a default name will be generated.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Data")
	FString RenderTargetImageFilename;

	/**
	 * Extracts the extrinsic properties (world transform) of the attached camera.
	 * @return A transform representing the camera's pose in world space.
	 */
	UFUNCTION(BlueprintCallable, Category = "Camera Data")
	FTransform GetCameraExtrinsics();

	/**
	 * Extracts the intrinsic properties of the attached camera.
	 * @param OutIntrinsics The intrinsic data struct to fill.
	 * @param RenderTarget If the camera is a SceneCapture2D, provide its RenderTarget for dimensions.
	 * @return True if successful, false otherwise.
	 */
	UFUNCTION(BlueprintCallable, Category = "Camera Data")
	bool GetCameraIntrinsics(FCameraIntrinsics& OutIntrinsics, UTextureRenderTarget2D* RenderTarget = nullptr);

	/**
	 * Saves camera data to a text file.
	 * @param Filename The name of the file to save to (e.g., "CameraData.txt").
	 * @param Extrinsics The extrinsic data to save.
	 * @param Intrinsics The intrinsic data to save.
	 * @param CameraName The name of the camera actor.
	 */
	UFUNCTION(BlueprintCallable, Category = "Camera Data")
	void SaveCameraDataToFile(const FString& Filename, const FTransform& Extrinsics, const FCameraIntrinsics& Intrinsics, const FString& CameraName);

	/**
	 * Saves a UTextureRenderTarget2D to a PNG file on disk.
	 * @param RenderTarget The render target to save.
	 * @param Filename The name of the file (e.g., "Frame_001.png").
	 */
	UFUNCTION(BlueprintCallable, Category = "Camera Data")
	void SaveRenderTargetToDisk(UTextureRenderTarget2D* RenderTarget, const FString& Filename);


	/**
	 * Converts a FTransform (location and rotation) to a 4x4 extrinsic matrix.
	 * @param Transform The FTransform to convert.
	 * @return A 4x4 FMatrix representing the extrinsic matrix.
	 */
	UFUNCTION(BlueprintPure, Category = "Camera Data")
	FMatrix ConvertTransformToExtrinsicMatrix(const FTransform& Transform);

	/**
	 * Converts FCameraIntrinsics to a 3x3 intrinsic matrix.
	 * @param Intrinsics The FCameraIntrinsics struct.
	 * @return A 3x3 FMatrix representing the intrinsic matrix.
	 */
	UFUNCTION(BlueprintPure, Category = "Camera Data")
	FMatrix ConvertIntrinsicsToIntrinsicMatrix(const FCameraIntrinsics& Intrinsics);

	UFUNCTION(BluePrintCallable, Category = "Camera Data")
	void SaveExtrinsicDataToJSON(const FString& Filename, const FTransform& Extrinsics, const FString& CameraName);

	UFUNCTION(BluePrintCallable, Category = "Camera Data")
	void SaveIntrinsicDataToJSON(const FString& Filename, const FCameraIntrinsics& Intrinsics, const FString& CameraName);
};
