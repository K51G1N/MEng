#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CameraDataManager.generated.h" // THIS MUST BE THE LAST INCLUDE

// Forward declare your CameraDataComponent
class UCameraDataComponent;

UCLASS()
class EXTRACTJOINTLOCATION_API ACameraDataManager : public AActor
{
	GENERATED_BODY()

public:
	// Sets default values for this actor's properties
	ACameraDataManager();

protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;

public:
	// Called every frame
	virtual void Tick(float DeltaTime) override;

	/**
	 * Function to initiate the camera data extraction and saving.
	 * Can be called manually or from BeginPlay.
	 */
	UFUNCTION(BlueprintCallable, Category = "Camera Data Manager")
	void ExtractAndSaveAllCameraData();

protected:
	/** Optional: Delay before saving to ensure all actors are fully initialized. */
	UPROPERTY(EditAnywhere, Category = "Camera Data Manager")
	float DataExtractionDelay = 0.5f; // Small delay in seconds

private:
	FTimerHandle ExtractionTimerHandle;
};