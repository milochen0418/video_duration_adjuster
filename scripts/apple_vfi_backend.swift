#!/usr/bin/env swift
import Foundation
import AVFoundation

struct Arguments {
    let input: String
    let output: String
    let factor: Double
    let fps: Double
    let previewSeconds: Int
}

enum ArgError: Error {
    case missing(String)
    case invalid(String)
}

func parseArgs() throws -> Arguments {
    let rawArgs = Array(CommandLine.arguments.dropFirst())
    var values: [String: String] = [:]
    var index = 0

    while index < rawArgs.count {
        let key = rawArgs[index]
        guard key.hasPrefix("--") else {
            throw ArgError.invalid("Unexpected argument: \(key)")
        }
        let name = String(key.dropFirst(2))
        let valueIndex = index + 1
        guard valueIndex < rawArgs.count else {
            throw ArgError.missing("Missing value for --\(name)")
        }
        values[name] = rawArgs[valueIndex]
        index += 2
    }

    guard let input = values["input"], !input.isEmpty else {
        throw ArgError.missing("--input")
    }
    guard let output = values["output"], !output.isEmpty else {
        throw ArgError.missing("--output")
    }
    guard let factorRaw = values["factor"], let factor = Double(factorRaw), factor > 0 else {
        throw ArgError.invalid("--factor must be > 0")
    }
    guard let fpsRaw = values["fps"], let fps = Double(fpsRaw), fps > 0 else {
        throw ArgError.invalid("--fps must be > 0")
    }
    let previewSeconds = Int(values["preview-seconds"] ?? "0") ?? 0

    return Arguments(
        input: input,
        output: output,
        factor: factor,
        fps: fps,
        previewSeconds: max(0, previewSeconds)
    )
}

func renderSize(for track: AVAssetTrack) -> CGSize {
    let transformed = track.naturalSize.applying(track.preferredTransform)
    return CGSize(width: abs(transformed.width), height: abs(transformed.height))
}

func exportVideo(args: Arguments) throws {
    let inputURL = URL(fileURLWithPath: args.input)
    let outputURL = URL(fileURLWithPath: args.output)

    let inputAsset = AVURLAsset(url: inputURL)
    guard let inputVideoTrack = inputAsset.tracks(withMediaType: .video).first else {
        throw ArgError.invalid("Input file has no video track")
    }

    let composition = AVMutableComposition()
    guard let compositionVideoTrack = composition.addMutableTrack(
        withMediaType: .video,
        preferredTrackID: kCMPersistentTrackID_Invalid
    ) else {
        throw ArgError.invalid("Unable to create composition video track")
    }

    let sourceDuration = inputAsset.duration
    try compositionVideoTrack.insertTimeRange(
        CMTimeRange(start: .zero, duration: sourceDuration),
        of: inputVideoTrack,
        at: .zero
    )

    let stretchedDuration = CMTimeMultiplyByFloat64(sourceDuration, multiplier: args.factor)
    compositionVideoTrack.scaleTimeRange(
        CMTimeRange(start: .zero, duration: sourceDuration),
        toDuration: stretchedDuration
    )

    let finalDuration: CMTime
    if args.previewSeconds > 0 {
        let previewDuration = CMTime(seconds: Double(args.previewSeconds), preferredTimescale: 600)
        finalDuration = CMTimeMinimum(stretchedDuration, previewDuration)
    } else {
        finalDuration = stretchedDuration
    }

    let instruction = AVMutableVideoCompositionInstruction()
    instruction.timeRange = CMTimeRange(start: .zero, duration: finalDuration)

    let layerInstruction = AVMutableVideoCompositionLayerInstruction(assetTrack: compositionVideoTrack)
    layerInstruction.setTransform(inputVideoTrack.preferredTransform, at: .zero)
    instruction.layerInstructions = [layerInstruction]

    let videoComposition = AVMutableVideoComposition()
    videoComposition.instructions = [instruction]
    videoComposition.renderSize = renderSize(for: inputVideoTrack)

    let roundedFPS = max(1, Int32(args.fps.rounded()))
    videoComposition.frameDuration = CMTime(value: 1, timescale: roundedFPS)

    guard let exportSession = AVAssetExportSession(
        asset: composition,
        presetName: AVAssetExportPresetHighestQuality
    ) else {
        throw ArgError.invalid("Unable to create AVAssetExportSession")
    }

    if FileManager.default.fileExists(atPath: outputURL.path) {
        try FileManager.default.removeItem(at: outputURL)
    }

    exportSession.outputURL = outputURL
    exportSession.videoComposition = videoComposition
    exportSession.shouldOptimizeForNetworkUse = true
    exportSession.outputFileType = outputURL.pathExtension.lowercased() == "mov" ? .mov : .mp4
    exportSession.timeRange = CMTimeRange(start: .zero, duration: finalDuration)

    let semaphore = DispatchSemaphore(value: 0)
    exportSession.exportAsynchronously {
        semaphore.signal()
    }
    semaphore.wait()

    if exportSession.status != .completed {
        let reason = exportSession.error?.localizedDescription ?? "unknown error"
        throw ArgError.invalid("AVFoundation export failed: \(reason)")
    }
}

func run() -> Int32 {
    do {
        let args = try parseArgs()
        print("APPLE_VFI_PROGRESS=20")
        try exportVideo(args: args)
        print("APPLE_VFI_PROGRESS=70")
        return 0
    } catch {
        fputs("apple_vfi_backend error: \(error)\n", stderr)
        return 2
    }
}

exit(run())
