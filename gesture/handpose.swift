// friday · gesture/handpose.swift
//
// G0/G1/G2 native tracker: capture the camera, run Apple Vision hand-pose on up
// to TWO hands per frame, and emit one JSON line per frame:
//   {"hands":[{"chirality":"right","landmarks":{"wrist":[x,y],...}}, ...]}
// (normalized coords, origin bottom-left). Optionally, an argv frame path makes
// it also write the raw camera frame as a JPEG there (the /gesture live feed).
// No Mac control here — the Python side owns cursor/click. Build: `make gesture`.
// Run from a terminal so macOS can prompt for Camera access.

import AVFoundation
import CoreImage
import Foundation
import Vision

let framePath = CommandLine.arguments.dropFirst().first  // optional: write JPEG frames here
let ciContext = CIContext()
let rgb = CGColorSpaceCreateDeviceRGB()

let handRequest: VNDetectHumanHandPoseRequest = {
    let r = VNDetectHumanHandPoseRequest()
    r.maximumHandCount = 2
    return r
}()

// All 21 joints -> the snake_case names gesture/classifier.py expects.
let jointMap: [VNHumanHandPoseObservation.JointName: String] = [
    .wrist: "wrist",
    .thumbCMC: "thumb_cmc", .thumbMP: "thumb_mp", .thumbIP: "thumb_ip", .thumbTip: "thumb_tip",
    .indexMCP: "index_mcp", .indexPIP: "index_pip", .indexDIP: "index_dip", .indexTip: "index_tip",
    .middleMCP: "middle_mcp", .middlePIP: "middle_pip", .middleDIP: "middle_dip", .middleTip: "middle_tip",
    .ringMCP: "ring_mcp", .ringPIP: "ring_pip", .ringDIP: "ring_dip", .ringTip: "ring_tip",
    .littleMCP: "little_mcp", .littlePIP: "little_pip", .littleDIP: "little_dip", .littleTip: "little_tip",
]

func err(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }

func chirality(_ obs: VNHumanHandPoseObservation) -> String {
    switch obs.chirality {
    case .left: return "left"
    case .right: return "right"
    default: return "unknown"
    }
}

final class Cam: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()

    func start() {
        session.sessionPreset = .medium
        guard let device = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else { err("gesture: no camera available"); exit(1) }
        session.addInput(input)
        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: DispatchQueue(label: "gesture.cam"))
        guard session.canAddOutput(output) else { err("gesture: cannot add output"); exit(1) }
        session.addOutput(output)
        session.startRunning()
        err("gesture: camera running — show your hand(s)")
    }

    func captureOutput(_ o: AVCaptureOutput, didOutput sb: CMSampleBuffer,
                       from c: AVCaptureConnection) {
        guard let pixel = CMSampleBufferGetImageBuffer(sb) else { return }
        let handler = VNImageRequestHandler(cvPixelBuffer: pixel, orientation: .up)
        try? handler.perform([handRequest])
        var hands: [[String: Any]] = []
        for obs in handRequest.results ?? [] {
            guard let points = try? obs.recognizedPoints(.all) else { continue }
            var lm: [String: [Double]] = [:]
            for (vn, name) in jointMap where (points[vn]?.confidence ?? 0) > 0.3 {
                let p = points[vn]!
                lm[name] = [Double(p.location.x), Double(p.location.y)]
            }
            if !lm.isEmpty { hands.append(["chirality": chirality(obs), "landmarks": lm]) }
        }
        if let data = try? JSONSerialization.data(withJSONObject: ["hands": hands]),
           let line = String(data: data, encoding: .utf8) {
            print(line)
            fflush(stdout)
        }
        if let path = framePath {  // the live-feed frame (raw pixels stay local)
            let ci = CIImage(cvPixelBuffer: pixel)
            if let jpeg = ciContext.jpegRepresentation(of: ci, colorSpace: rgb) {
                try? jpeg.write(to: URL(fileURLWithPath: path), options: .atomic)
            }
        }
    }
}

let cam = Cam()
AVCaptureDevice.requestAccess(for: .video) { granted in
    if granted { cam.start() } else { err("gesture: Camera access denied"); exit(1) }
}
RunLoop.main.run()
