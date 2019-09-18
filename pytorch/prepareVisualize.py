import os
import sys
import json
import time
from PIL import Image
from PIL import ImageDraw
from cam2screen import cam2screen

if len(sys.argv) > 1:
    dataPath = sys.argv[1]
else:
    dataPath = ""

if len(sys.argv) > 2:
    resultsPath = sys.argv[2]
else:
    resultsPath = "best_results.json"

if not os.path.isdir(dataPath):
    print("Invalid arguments: must pass the data directory as first argument and results file as the second argument.")
    sys.exit(-1)

if not os.path.exists(os.path.join(dataPath, "README.md")):
    print(f"{dataPath} does not look like a valid data directory, missing README.md.")
    sys.exit(-1)

if not os.path.exists(resultsPath):
    print(f"Does not look like a valid results file: {resultsPath}")
    sys.exit(-1)

# Metrics collection
resultFrames = 0
skippedFrames = 0
predictedFrames = 0
gazeSamplesCount = 0
gazeSamplesWithPredictionsCount = 0
averageGazeSamplesFrameCount = 0


resultsJson = open(resultsPath)
results = json.load(resultsJson)

# Parse the results into an array of [sampleId, frameId] containing (gazePoint: (x, y), gazePrediction: (x, y))
print("Parsing Results")
gazeSamples = {}
for result in results:
    gazeSample = gazeSamples.pop(result['frame'][0], {})
    gazeSample[result['frame'][1]] = {"gazePointCamera": result['gazePoint'], "gazePredictionCamera": result['gazePrediction']}
    gazeSamples.update({result['frame'][0]: gazeSample })
    resultFrames += 1

gazeSamplesWithPredictionsCount = len(gazeSamples)
gazeSamplesFrameCount = list(map(lambda _: len(_.keys()), gazeSamples.values()))
averageGazeSamplesFrameCount = sum(gazeSamplesFrameCount) / len(gazeSamplesFrameCount)

print("Parsing Results Finished")

with os.scandir(dataPath) as sampleDirEntries:

    for sampleDirEntry in sampleDirEntries:

        if sampleDirEntry.is_dir():  

            gazeSamplesCount += 1
            sampleId = sampleDirEntry.name
            sampleIndex = int(sampleId)

            framesPath = os.path.join(sampleDirEntry.path, "frames")

            screenJson = open(f'{sampleDirEntry.path}/screen.json')
            screen = json.load(screenJson)
            dotInfoJson = open(f'{sampleDirEntry.path}/dotInfo.json')
            dotInfo = json.load(dotInfoJson)
            infoJson = open(f'{sampleDirEntry.path}/info.json')
            info = json.load(infoJson)

            with os.scandir(framesPath) as framesDirEntries:

                for frameDirEntry in framesDirEntries:

                    frameId = os.path.splitext(frameDirEntry.name)[0]
                    frameIndex = int(frameId)

                    framePrediction = gazeSamples.get(sampleIndex, {}).get(frameIndex)
                    if framePrediction is None:
                        skippedFrames += 1
                        continue
                    else:
                        predictedFrames += 1

                    framePredictionJson = json.dumps(gazeSamples[int(sampleId)][int(frameId)])

                    # Check for existence of frame.input.json, don't regenerate if present
                    if os.path.isfile(f'{sampleDirEntry.path}/frames/{frameId}.input.json'):
                        continue

                    frameImage = Image.open(f'{sampleDirEntry.path}/frames/{frameId}.jpg')
                    frameImageSize = frameImage.size

                    frameInput = {
                        "image": {
                            "width": frameImageSize[0],
                            "height": frameImageSize[1]
                        },
                        "screen": {
                            "width": screen['W'][frameIndex],
                            "height": screen['H'][frameIndex],
                            "orientation": screen["Orientation"][frameIndex]
                        },
                        "gazePoint": {
                            "xpts": dotInfo["XPts"][frameIndex],
                            "ypts": dotInfo["YPts"][frameIndex],
                            "xcam": dotInfo["XCam"][frameIndex],
                            "ycam": dotInfo["YCam"][frameIndex]
                        }
                    }

                    frameInputJson = json.dumps(frameInput)

                    # Skip frames that aren't portrait
                    if frameInput['screen']['orientation'] != 1:
                        continue

                    xScaleScreenToImage = frameInput["image"]["width"] / frameInput["screen"]["width"]
                    yScaleScreenToImage = frameInput["image"]["height"] / frameInput["screen"]["height"]

                    # print(frameInputJson)
                    # print(framePredictionJson)
                    # print(frameOutput)

                    gazeTargetScreenPixelTuple = cam2screen(framePrediction["gazePointCamera"][0], framePrediction["gazePointCamera"][1], frameInput['screen']['orientation'], info['DeviceName'], frameInput["screen"]["width"], frameInput["screen"]["height"])
                    # Skip datasets for which we don't have device information yet
                    if gazeTargetScreenPixelTuple is None:
                        continue

                    (gazeTargetScreenPixelXFromCamera, gazeTargetScreenPixelYFromCamera) = gazeTargetScreenPixelTuple
                    (gazePredictionScreenPixelXFromCamera, gazePredictionScreenPixelYFromCamera) = cam2screen(framePrediction["gazePredictionCamera"][0], framePrediction["gazePredictionCamera"][1], frameInput['screen']['orientation'], info['DeviceName'], frameInput["screen"]["width"], frameInput["screen"]["height"])

                    # Invert the X Axis (camera vs screen), don't need to do this for screen prediction
                    gazeTargetXScreenPixel = frameInput["screen"]["width"] - frameInput["gazePoint"]["xpts"]
                    gazeTargetScreenPixelXFromCamera = frameInput["screen"]["width"] - gazeTargetScreenPixelXFromCamera
                    gazePredictionScreenPixelXFromCamera = frameInput["screen"]["width"] - gazePredictionScreenPixelXFromCamera

                    gazeTargetYScreenPixel = frameInput["gazePoint"]["ypts"]

                    # Scale the data to fit on the camera image rather than the screen, don't need to do this for screen prediction
                    gazeTargetImagePixelX = gazeTargetXScreenPixel * xScaleScreenToImage
                    gazeTargetImagePixelY = gazeTargetYScreenPixel * yScaleScreenToImage
                    gazeTargetImagePixelXFromCamera = gazeTargetScreenPixelXFromCamera * xScaleScreenToImage
                    gazeTargetImagePixelYFromCamera = gazeTargetScreenPixelYFromCamera * yScaleScreenToImage
                    gazePredictionImagePixelXFromCamera = gazePredictionScreenPixelXFromCamera * xScaleScreenToImage
                    gazePredictionImagePixelYFromCamera = gazePredictionScreenPixelYFromCamera * yScaleScreenToImage

                    draw = ImageDraw.Draw(frameImage)

                    draw.line( (gazeTargetImagePixelX, gazeTargetImagePixelY-25) + (gazeTargetImagePixelX, gazeTargetImagePixelY+25), fill=(0, 160, 0), width=5)
                    draw.line( (gazeTargetImagePixelX-25, gazeTargetImagePixelY) + (gazeTargetImagePixelX+25, gazeTargetImagePixelY), fill=(0, 160, 0), width=5)

                    # This confirms that our camera space to point space conversion is working, because the two crosses (green from points and red from camera space) overlay
                    draw.line( (gazeTargetImagePixelXFromCamera, gazeTargetImagePixelYFromCamera-25) + (gazeTargetImagePixelXFromCamera, gazeTargetImagePixelYFromCamera+25), fill=(160, 0, 0), width=3)
                    draw.line( (gazeTargetImagePixelXFromCamera-25, gazeTargetImagePixelYFromCamera) + (gazeTargetImagePixelXFromCamera+25, gazeTargetImagePixelYFromCamera), fill=(160, 0, 0), width=3)

                    draw.arc( (gazePredictionImagePixelXFromCamera-25, gazePredictionImagePixelYFromCamera-25) + (gazePredictionImagePixelXFromCamera+25, gazePredictionImagePixelYFromCamera+25), 0, 360, fill=(00, 128, 00), width=3)
                    draw.arc( (gazePredictionImagePixelXFromCamera-3, gazePredictionImagePixelYFromCamera-3) + (gazePredictionImagePixelXFromCamera+3, gazePredictionImagePixelYFromCamera+3), 0, 360, fill=(00, 128, 00), width=2)

                    filename = f"/data/gc-output/deepthink/2019-01-01.01/{sampleId}/{frameId}_overlay.jpg"

                    directory = os.path.dirname(filename)
                    if not os.path.exists(directory):
                        os.makedirs(directory)

                    frameImage.save(filename)

print(f"Total Samples: {gazeSamplesCount}")
print(f"Samples with Predictions: {gazeSamplesWithPredictionsCount}")
print(f"Result Frames: {resultFrames}")
print(f"Predicted Frames: {predictedFrames}")
print(f"Skipped Frames: {skippedFrames}")
print(f"Result Average Frames per Sample: {averageGazeSamplesFrameCount}")