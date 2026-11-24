import Foundation
import Vision
import AppKit

// Local-only OCR: text and normalized top-left coordinates, one JSON result per image.
for path in CommandLine.arguments.dropFirst() {
    do {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:])
        try handler.perform([request])
        let rows: [[String: Any]] = (request.results ?? []).compactMap { result in
            guard let candidate = result.topCandidates(1).first else { return nil }
            let box = result.boundingBox
            return ["text": candidate.string, "confidence": candidate.confidence,
                    "x0": box.minX, "y0": 1 - box.maxY,
                    "x1": box.maxX, "y1": 1 - box.minY, "method": "vision"]
        }
        let data = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
        print(String(data: data, encoding: .utf8)!)
    } catch {
        fputs("OCR failed: \(error)\n", stderr)
        exit(1)
    }
}
