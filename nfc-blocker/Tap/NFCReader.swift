import CoreNFC

/// Reads the hardware ID of any NFC tag (NTAG stickers, cards, key fobs).
final class NFCReader: NSObject, NFCTagReaderSessionDelegate {
    enum ReadError: LocalizedError {
        case unavailable, cancelled
        var errorDescription: String? {
            switch self {
            case .unavailable: return "NFC isn't available on this device."
            case .cancelled: return nil
            }
        }
    }

    private var session: NFCTagReaderSession?
    private var completion: ((Result<String, Error>) -> Void)?

    func scan(prompt: String, completion: @escaping (Result<String, Error>) -> Void) {
        guard NFCTagReaderSession.readingAvailable else {
            completion(.failure(ReadError.unavailable))
            return
        }
        self.completion = completion
        session = NFCTagReaderSession(pollingOption: [.iso14443, .iso15693], delegate: self, queue: nil)
        session?.alertMessage = prompt
        session?.begin()
    }

    // MARK: NFCTagReaderSessionDelegate

    func tagReaderSessionDidBecomeActive(_ session: NFCTagReaderSession) {}

    func tagReaderSession(_ session: NFCTagReaderSession, didInvalidateWithError error: Error) {
        let code = (error as? NFCReaderError)?.code
        let userCancelled = code == .readerSessionInvalidationErrorUserCanceled
            || code == .readerSessionInvalidationErrorFirstNDEFTagRead
        finish(.failure(userCancelled ? ReadError.cancelled : error))
    }

    func tagReaderSession(_ session: NFCTagReaderSession, didDetect tags: [NFCTag]) {
        guard let tag = tags.first else { return }
        session.connect(to: tag) { [weak self] error in
            guard error == nil, let id = Self.identifier(of: tag) else {
                session.invalidate(errorMessage: "Couldn't read that tag. Try again.")
                return
            }
            session.alertMessage = "Got it"
            self?.finish(.success(id))
            session.invalidate()
        }
    }

    // MARK: Helpers

    private func finish(_ result: Result<String, Error>) {
        guard let completion else { return }
        self.completion = nil
        session = nil
        DispatchQueue.main.async { completion(result) }
    }

    private static func identifier(of tag: NFCTag) -> String? {
        let data: Data
        switch tag {
        case .miFare(let t): data = t.identifier
        case .iso7816(let t): data = t.identifier
        case .iso15693(let t): data = t.identifier
        case .feliCa(let t): data = t.currentIDm
        @unknown default: return nil
        }
        return data.map { String(format: "%02x", $0) }.joined()
    }
}
