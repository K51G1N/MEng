#include "CameraDataManager.h"
#include "Kismet/GameplayStatics.h"
#include "CameraDataComponent.h"
#include "Engine/SceneCapture2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "CineCameraActor.h"
#include "Engine/Texture2DDynamic.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "TimerManager.h"

// Define a log category for your manager
DEFINE_LOG_CATEGORY_STATIC(LogCameraDataManager, Log, All);

// Sets default values for this actor's properties
ACameraDataManager::ACameraDataManager()
{
	PrimaryActorTick.bCanEverTick = false;

	// Set a reasonable default delay to allow other actors to initialize.
	DataExtractionDelay = 1.0f;
}

// Called when the game starts or when spawned
void ACameraDataManager::BeginPlay()
{
	Super::BeginPlay();

	// Set a timer to call our extraction function after a brief delay.
	// This ensures all actors have had their BeginPlay() called.
	GetWorldTimerManager().SetTimer(ExtractionTimerHandle, this, &ACameraDataManager::ExtractAndSaveAllCameraData, DataExtractionDelay, false);
}

// Called every frame
void ACameraDataManager::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void ACameraDataManager::ExtractAndSaveAllCameraData()
{
	UE_LOG(LogCameraDataManager, Log, TEXT("ACameraDataManager: Starting synchronized camera data extraction."));

	TArray<AActor*> FoundCameraActors;
	// Use GetAllActorsOfClass to find all actors of a certain class.
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), ACineCameraActor::StaticClass(), FoundCameraActors);

	TArray<AActor*> FoundSceneCaptureActors;
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), ASceneCapture2D::StaticClass(), FoundSceneCaptureActors);
	FoundCameraActors.Append(FoundSceneCaptureActors);

	UE_LOG(LogCameraDataManager, Log, TEXT("ACameraDataManager: Found %d candidate camera actors."), FoundCameraActors.Num());

	if (FoundCameraActors.Num() == 0)
	{
		UE_LOG(LogCameraDataManager, Warning, TEXT("No CineCameraActor or ASceneCapture2D actors found in the scene to process."));
		return;
	}

	for (AActor* CameraActor : FoundCameraActors)
	{
		if (CameraActor)
		{
			// Get the camera name once at the start of the loop
			FString CameraName = CameraActor->GetActorLabel();
			if (CameraName.IsEmpty())
			{
				CameraName = CameraActor->GetName();
			}

			// Check if the camera actor has our custom component
			UCameraDataComponent* CameraDataComponent = CameraActor->FindComponentByClass<UCameraDataComponent>();

			if (CameraDataComponent)
			{
				USceneCaptureComponent2D* SceneCaptureComp = CameraActor->FindComponentByClass<USceneCaptureComponent2D>();
				UTextureRenderTarget2D* RenderTarget = SceneCaptureComp ? SceneCaptureComp->TextureTarget : nullptr;

				if (RenderTarget)
				{
					// Set the capture source back to LDR for a standard tone-mapped image
					// This ensures the image looks like what you see in the viewport.
					SceneCaptureComp->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;

					// Force an immediate render
					SceneCaptureComp->CaptureScene();

					FTransform Extrinsics = CameraDataComponent->GetCameraExtrinsics();
					FCameraIntrinsics Intrinsics;

					if (CameraDataComponent->GetCameraIntrinsics(Intrinsics, RenderTarget))
					{
						FString FilenamePrefix = CameraName;

						// Save camera matrices
						CameraDataComponent->SaveCameraDataToFile(FilenamePrefix + TEXT("_Matrices.txt"), Extrinsics, Intrinsics, CameraName);

						// Save rendered frame as a standard PNG
						CameraDataComponent->SaveRenderTargetToDisk(RenderTarget, FilenamePrefix + TEXT("_Frame.png"));
						UE_LOG(LogCameraDataManager, Log, TEXT("Saved synchronized data for: %s"), *CameraName);
					}
					else
					{
						UE_LOG(LogCameraDataManager, Error, TEXT("Failed to get intrinsics for actor: %s"), *CameraName);
					}
				}
				else
				{
					UE_LOG(LogCameraDataManager, Warning, TEXT("RenderTarget is invalid for actor: %s. Skipping data save."), *CameraName);
				}
			}
			else
			{
				UE_LOG(LogCameraDataManager, Warning, TEXT("Camera actor %s does not have a CameraDataComponent. Skipping data save."), *CameraName);
			}
		}
	}
	UE_LOG(LogCameraDataManager, Log, TEXT("ACameraDataManager: Finished synchronized camera data extraction."));
}
