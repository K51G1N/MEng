#include "CameraDataComponent.h"

// Core Engine/Framework Includes
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"

// Camera-Specific Includes
#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Engine/SceneCapture2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"

// File I/O Includes
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFileManager.h"

// Logging
#include "Logging/LogMacros.h"

// Define a log category for your component
DEFINE_LOG_CATEGORY_STATIC(LogCameraData, Log, All);

// Sets default values for this component's properties
UCameraDataComponent::UCameraDataComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	TargetRenderTarget = nullptr;
	CameraDataFilename = TEXT("");
	RenderTargetImageFilename = TEXT("");
}

// Called when the game starts
void UCameraDataComponent::BeginPlay()
{
	Super::BeginPlay();

	AActor* OwnerActor = GetOwner();
	if (!OwnerActor)
	{
		UE_LOG(LogCameraData, Error, TEXT("CameraDataComponent: Owner actor is null. Cannot extract camera data."));
		return;
	}

	ACineCameraActor* CineCameraActor = Cast<ACineCameraActor>(OwnerActor);
	ASceneCapture2D* SceneCaptureActor = Cast<ASceneCapture2D>(OwnerActor);

	if (!CineCameraActor && !SceneCaptureActor)
	{
		UE_LOG(LogCameraData, Warning, TEXT("CameraDataComponent: Component is not attached to a CineCameraActor or SceneCapture2D. Skipping data extraction."));
		return;
	}

	FString CameraName = OwnerActor->GetName();
	FTransform Extrinsics = GetCameraExtrinsics();
	FCameraIntrinsics Intrinsics;
	bool bIntrinsicsSuccess = GetCameraIntrinsics(Intrinsics, TargetRenderTarget);

	if (bIntrinsicsSuccess)
	{
		FString FinalCameraDataFilename = CameraDataFilename.IsEmpty() ?
			FString::Printf(TEXT("CameraData_%s.txt"), *CameraName) : CameraDataFilename;
		SaveCameraDataToFile(FinalCameraDataFilename, Extrinsics, Intrinsics, CameraName);
		SaveIntrinsicDataToJSON(FinalCameraDataFilename, Intrinsics, CameraName);
		SaveExtrinsicDataToJSON(FinalCameraDataFilename, Extrinsics, CameraName);

		if (TargetRenderTarget)
		{
			FString FinalRenderTargetFilename = RenderTargetImageFilename.IsEmpty() ?
				FString::Printf(TEXT("%s_Frame.png"), *CameraName) : RenderTargetImageFilename;

			SaveRenderTargetToDisk(TargetRenderTarget, FinalRenderTargetFilename);
		}
	}
	else
	{
		UE_LOG(LogCameraData, Error, TEXT("CameraDataComponent: Failed to get camera intrinsics for %s."), *CameraName);
	}
}

// Called every frame - kept as false in constructor for one-time operation
void UCameraDataComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
}

FTransform UCameraDataComponent::GetCameraExtrinsics()
{
	return GetOwner()->GetActorTransform();
}

bool UCameraDataComponent::GetCameraIntrinsics(FCameraIntrinsics& OutIntrinsics, UTextureRenderTarget2D* RenderTarget)
{
	ACineCameraActor* CineCameraActor = Cast<ACineCameraActor>(GetOwner());
	ASceneCapture2D* SceneCaptureActor = Cast<ASceneCapture2D>(GetOwner());

	if (CineCameraActor)
	{
		UCineCameraComponent* CineCameraComp = CineCameraActor->GetCineCameraComponent();
		if (CineCameraComp)
		{
			// Get focal length from the Cine Camera component
			float FocalLengthMm = CineCameraComp->CurrentFocalLength;
			// Get sensor dimensions from the Filmback settings
			float SensorWidthMm = CineCameraComp->Filmback.SensorWidth;
			float SensorHeightMm = CineCameraComp->Filmback.SensorHeight;

			if (RenderTarget)
			{
				OutIntrinsics.ImageWidth = RenderTarget->SizeX;
				OutIntrinsics.ImageHeight = RenderTarget->SizeY;
			}
			else
			{
				OutIntrinsics.ImageWidth = 1920;
				OutIntrinsics.ImageHeight = 1080;
				UE_LOG(LogCameraData, Warning, TEXT("GetCameraIntrinsics: No RenderTarget provided for CineCameraActor. Using default image dimensions (1920x1080)."));
			}

			// Perform the conversion from focal length (mm) to pixels
			if (SensorWidthMm > 0 && OutIntrinsics.ImageWidth > 0)
			{
				OutIntrinsics.FocalLengthX = (FocalLengthMm * OutIntrinsics.ImageWidth) / SensorWidthMm;
				OutIntrinsics.FocalLengthY = (FocalLengthMm * OutIntrinsics.ImageHeight) / SensorHeightMm;
			}
			else
			{
				UE_LOG(LogCameraData, Error, TEXT("GetCameraIntrinsics: Invalid sensor or image dimensions."));
				return false;
			}

			OutIntrinsics.PrincipalPointX = OutIntrinsics.ImageWidth / 2.0f;
			OutIntrinsics.PrincipalPointY = OutIntrinsics.ImageHeight / 2.0f;

			return true;
		}
	}
	else if (SceneCaptureActor)
	{
		USceneCaptureComponent2D* SceneCaptureComp = SceneCaptureActor->GetCaptureComponent2D();
		if (SceneCaptureComp && RenderTarget)
		{
			OutIntrinsics.ImageWidth = RenderTarget->SizeX;
			OutIntrinsics.ImageHeight = RenderTarget->SizeY;

			float FOVRad = FMath::DegreesToRadians(SceneCaptureComp->FOVAngle);
			OutIntrinsics.FocalLengthX = (OutIntrinsics.ImageWidth / 2.0f) / FMath::Tan(FOVRad / 2.0f);
			OutIntrinsics.FocalLengthY = (OutIntrinsics.ImageHeight / 2.0f) / FMath::Tan(FOVRad / 2.0f);

			OutIntrinsics.PrincipalPointX = OutIntrinsics.ImageWidth / 2.0f;
			OutIntrinsics.PrincipalPointY = OutIntrinsics.ImageHeight / 2.0f;
			return true;
		}
		else if (SceneCaptureComp && !RenderTarget)
		{
			UE_LOG(LogCameraData, Error, TEXT("GetCameraIntrinsics: SceneCapture2D requires a RenderTarget to calculate intrinsics. Please assign TargetRenderTarget."));
		}
	}
	return false;
}
void UCameraDataComponent::SaveIntrinsicDataToJSON(const FString& Filename, const FCameraIntrinsics& Intrinsics, const FString& CameraName) {

	// Construct the directory path using CameraName
	FString SaveDirectory = FPaths::ProjectSavedDir() + TEXT("CameraData/") + CameraName + TEXT("/");
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	// Create the directory if it doesn't exist
	if (!PlatformFile.DirectoryExists(*SaveDirectory))
	{
		PlatformFile.CreateDirectoryTree(*SaveDirectory);
	}

	// Construct the full file path for the intrinsics JSON
	FString AbsoluteFilePath = SaveDirectory + FString::Printf(TEXT("Intrinsics_%s.json"), *CameraName);

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject());
	RootObject->SetStringField(TEXT("CameraName"), CameraName);

	//Focal
	TSharedPtr<FJsonObject> FocalLengthObj = MakeShareable(new FJsonObject());
	FocalLengthObj->SetNumberField(TEXT("fx"), Intrinsics.FocalLengthX);
	FocalLengthObj->SetNumberField(TEXT("fy"), Intrinsics.FocalLengthY);

	//Principal
	TSharedPtr<FJsonObject> PrincipalPointObj = MakeShareable(new FJsonObject());
	PrincipalPointObj->SetNumberField(TEXT("cx"), Intrinsics.PrincipalPointX);
	PrincipalPointObj->SetNumberField(TEXT("cy"), Intrinsics.PrincipalPointY);

	//Image Dimensions
	TSharedPtr<FJsonObject> ImageDimensionsObj = MakeShareable(new FJsonObject());
	ImageDimensionsObj->SetNumberField(TEXT("Width"), Intrinsics.ImageWidth);
	ImageDimensionsObj->SetNumberField(TEXT("Height"), Intrinsics.ImageHeight);

	TSharedPtr<FJsonObject> IntrinsicsObj = MakeShareable(new FJsonObject());
	IntrinsicsObj->SetObjectField(TEXT("FocalLength"), FocalLengthObj);
	IntrinsicsObj->SetObjectField(TEXT("PrincipalPoint"), PrincipalPointObj);
	IntrinsicsObj->SetObjectField(TEXT("ImageDimensions"), ImageDimensionsObj);

	FMatrix IntrinsicMatrix = ConvertIntrinsicsToIntrinsicMatrix(Intrinsics);
	TArray<TSharedPtr<FJsonValue>> IntrinsicMatrixArray;
	for (int32 Row = 0; Row < 3; ++Row)
	{
		TArray<TSharedPtr<FJsonValue>> RowArray;
		for (int32 Col = 0; Col < 3; ++Col)
		{
			RowArray.Add(MakeShareable(new FJsonValueNumber(IntrinsicMatrix.M[Row][Col])));
		}
		IntrinsicMatrixArray.Add(MakeShareable(new FJsonValueArray(RowArray)));
	}
	IntrinsicsObj->SetArrayField(TEXT("IntrinsicMatrix"), IntrinsicMatrixArray);

	RootObject->SetObjectField(TEXT("Intrinsics"), IntrinsicsObj);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	// Save to file using the new AbsoluteFilePath
	if (FFileHelper::SaveStringToFile(OutputString, *AbsoluteFilePath))
	{
		UE_LOG(LogCameraData, Log, TEXT("Successfully saved intrinsic data to: %s"), *AbsoluteFilePath);
	}
	else
	{
		UE_LOG(LogCameraData, Error, TEXT("Failed to save intrinsic data to: %s"), *AbsoluteFilePath);
	}
}

void UCameraDataComponent::SaveExtrinsicDataToJSON(const FString& Filename, const FTransform& Extrinsics, const FString& CameraName) {
	FString SaveDirectory = FPaths::ProjectSavedDir() + TEXT("CameraData/") + CameraName + TEXT("/");
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	// Create the directory if it doesn't exist
	if (!PlatformFile.DirectoryExists(*SaveDirectory))
	{
		PlatformFile.CreateDirectoryTree(*SaveDirectory);
	}

	// Construct the full file path for the intrinsics JSON
	FString AbsoluteFilePath = SaveDirectory + FString::Printf(TEXT("Extrinsics_%s.json"), *CameraName);

	TSharedPtr<FJsonObject> RootObject = MakeShareable(new FJsonObject());
	RootObject->SetStringField(TEXT("CameraName"), CameraName);

	// Location
	TSharedPtr<FJsonObject> LocationObj = MakeShareable(new FJsonObject());
	LocationObj->SetNumberField(TEXT("X"), Extrinsics.GetLocation().X);
	LocationObj->SetNumberField(TEXT("Y"), Extrinsics.GetLocation().Y);;
	LocationObj->SetNumberField(TEXT("Z"), Extrinsics.GetLocation().Z);;

	// Rotation
	TSharedPtr<FJsonObject> RotationObj = MakeShareable(new FJsonObject());
	RotationObj->SetNumberField(TEXT("Pitch"), Extrinsics.GetRotation().Rotator().Pitch);
	RotationObj->SetNumberField(TEXT("Yaw"), Extrinsics.GetRotation().Rotator().Yaw);
	RotationObj->SetNumberField(TEXT("Roll"), Extrinsics.GetRotation().Rotator().Roll);

	// Scale
	TSharedPtr<FJsonObject> ScaleObj = MakeShareable(new FJsonObject());
	ScaleObj->SetNumberField(TEXT("X"), Extrinsics.GetScale3D().X);
	ScaleObj->SetNumberField(TEXT("Y"), Extrinsics.GetScale3D().Y);
	ScaleObj->SetNumberField(TEXT("Z"), Extrinsics.GetScale3D().Z);

	// Add them to the root object
	TSharedPtr<FJsonObject> ExtrinsicsObj = MakeShareable(new FJsonObject());
	ExtrinsicsObj->SetObjectField(TEXT("Location"), LocationObj);
	ExtrinsicsObj->SetObjectField(TEXT("Rotation"), RotationObj);
	ExtrinsicsObj->SetObjectField(TEXT("Scale"), ScaleObj);

	FMatrix WorldToCameraMatrix = Extrinsics.ToInverseMatrixWithScale();
	TArray<TSharedPtr<FJsonValue>> ExtrinsicMatrixArray;
	for (int32 Row = 0; Row < 4; ++Row)
	{
		TArray<TSharedPtr<FJsonValue>> RowArray;
		for (int32 Col = 0; Col < 4; ++Col)
		{
			RowArray.Add(MakeShareable(new FJsonValueNumber(WorldToCameraMatrix.M[Row][Col])));
		}
		ExtrinsicMatrixArray.Add(MakeShareable(new FJsonValueArray(RowArray)));
	}
	ExtrinsicsObj->SetArrayField(TEXT("ExtrinsicMatrix"), ExtrinsicMatrixArray);

	RootObject->SetObjectField(TEXT("Extrinsics"), ExtrinsicsObj);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObject.ToSharedRef(), Writer);

	// Save to file using the new AbsoluteFilePath
	if (FFileHelper::SaveStringToFile(OutputString, *AbsoluteFilePath))
	{
		UE_LOG(LogCameraData, Log, TEXT("Successfully saved extrinsic data to: %s"), *AbsoluteFilePath);
	}
	else
	{
		UE_LOG(LogCameraData, Error, TEXT("Failed to save extrinsic data to: %s"), *AbsoluteFilePath);
	}
}

void UCameraDataComponent::SaveCameraDataToFile(const FString& Filename, const FTransform& Extrinsics, const FCameraIntrinsics& Intrinsics, const FString& CameraName)
{
	FString SaveDirectory = FPaths::ProjectSavedDir() + TEXT("CameraData/");
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	if (!PlatformFile.DirectoryExists(*SaveDirectory))
	{
		PlatformFile.CreateDirectoryTree(*SaveDirectory);
	}

	FString AbsoluteFilePath = SaveDirectory + Filename;
	FVector Location = Extrinsics.GetLocation();
	FRotator Rotation = Extrinsics.GetRotation().Rotator();
	FVector Scale = Extrinsics.GetScale3D();

	FString ExtrinsicString = FString::Printf(TEXT("Extrinsics:\n  Location: X=%.6f, Y=%.6f, Z=%.6f\n  Rotation: Pitch=%.6f, Yaw=%.6f, Roll=%.6f\n  Scale: X=%.6f, Y=%.6f, Z=%.6f"),
		Location.X, Location.Y, Location.Z,
		Rotation.Pitch, Rotation.Yaw, Rotation.Roll,
		Scale.X, Scale.Y, Scale.Z);

	FMatrix WorldToCameraMatrix = Extrinsics.ToInverseMatrixWithScale();
	FString ExtrinsicMatrixString = TEXT("Extrinsic Matrix (World to Camera, 4x4 homogenous):\n");

	for (int32 Row = 0; Row < 4; ++Row)
	{
		ExtrinsicMatrixString += FString::Printf(TEXT("  %.6f %.6f %.6f %.6f\n"),
			WorldToCameraMatrix.M[Row][0], WorldToCameraMatrix.M[Row][1], WorldToCameraMatrix.M[Row][2], WorldToCameraMatrix.M[Row][3]);
	}

	FString IntrinsicString = FString::Printf(TEXT("Intrinsics:\n  Focal Length (fx, fy): %.6f, %.6f\n  Principal Point (cx, cy): %.6f, %.6f\n  Image Dimensions: Width=%d, Height=%d"),
		Intrinsics.FocalLengthX, Intrinsics.FocalLengthY,
		Intrinsics.PrincipalPointX, Intrinsics.PrincipalPointY,
		Intrinsics.ImageWidth, Intrinsics.ImageHeight);

	FMatrix IntrinsicMatrix = ConvertIntrinsicsToIntrinsicMatrix(Intrinsics);
	FString IntrinsicMatrixString = TEXT("Intrinsic Matrix (3x3):\n");
	for (int32 Row = 0; Row < 3; ++Row)
	{
		IntrinsicMatrixString += FString::Printf(TEXT("  %.6f %.6f %.6f\n"),
			IntrinsicMatrix.M[Row][0], IntrinsicMatrix.M[Row][1], IntrinsicMatrix.M[Row][2]);
	}

	FString OutputContent = FString::Printf(TEXT("Camera Name: %s\n\n%s\n\n%s\n\n%s\n\n%s"),
		*CameraName,
		*ExtrinsicString,
		*ExtrinsicMatrixString,
		*IntrinsicString,
		*IntrinsicMatrixString);

	if (FFileHelper::SaveStringToFile(OutputContent, *AbsoluteFilePath))
	{
		UE_LOG(LogCameraData, Log, TEXT("Successfully saved camera data to: %s"), *AbsoluteFilePath);
	}
	else
	{
		UE_LOG(LogCameraData, Error, TEXT("Failed to save camera data to: %s"), *AbsoluteFilePath);
	}
}

void UCameraDataComponent::SaveRenderTargetToDisk(UTextureRenderTarget2D* RenderTarget, const FString& Filename)
{
	if (!RenderTarget)
	{
		UE_LOG(LogCameraData, Error, TEXT("SaveRenderTargetToDisk: RenderTarget is invalid."));
		return;
	}

	FString SaveDirectory = FPaths::ProjectSavedDir() + TEXT("CameraFrames/");
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	if (!PlatformFile.DirectoryExists(*SaveDirectory))
	{
		PlatformFile.CreateDirectoryTree(*SaveDirectory);
	}

	UKismetRenderingLibrary::ExportRenderTarget(GetWorld(), RenderTarget, SaveDirectory, Filename);

	UE_LOG(LogCameraData, Log, TEXT("Exporting RenderTarget to: %s%s"), *SaveDirectory, *Filename);
}

FMatrix UCameraDataComponent::ConvertTransformToExtrinsicMatrix(const FTransform& Transform)
{
	return Transform.ToInverseMatrixWithScale();
}

FMatrix UCameraDataComponent::ConvertIntrinsicsToIntrinsicMatrix(const FCameraIntrinsics& Intrinsics)
{
	FMatrix K = FMatrix::Identity;
	K.M[0][0] = Intrinsics.FocalLengthX;
	K.M[1][1] = Intrinsics.FocalLengthY;
	K.M[0][2] = Intrinsics.PrincipalPointX;
	K.M[1][2] = Intrinsics.PrincipalPointY;
	K.M[2][2] = 1.0f;
	return K;
}