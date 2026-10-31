import FamilyControls
import ManagedSettings
import SwiftUI

@MainActor
final class BlockModel: ObservableObject {
    @Published var selection: FamilyActivitySelection {
        didSet { save(selection) }
    }
    @Published private(set) var isBlocking: Bool
    @Published private(set) var tagID: String?
    @Published var message: String?

    private let shield = ManagedSettingsStore()
    private let reader = NFCReader()
    private let defaults = UserDefaults.standard

    private enum Key {
        static let selection = "selection", blocking = "blocking", tag = "tagID"
    }

    init() {
        if let data = defaults.data(forKey: Key.selection),
           let saved = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data) {
            selection = saved
        } else {
            selection = FamilyActivitySelection()
        }
        isBlocking = defaults.bool(forKey: Key.blocking)
        tagID = defaults.string(forKey: Key.tag)
    }

    var hasApps: Bool {
        !selection.applicationTokens.isEmpty
            || !selection.categoryTokens.isEmpty
            || !selection.webDomainTokens.isEmpty
    }

    // MARK: Actions

    func authorize() async {
        do {
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
        } catch {
            message = "Screen Time permission is required."
        }
    }

    func pairTag() {
        message = nil
        reader.scan(prompt: "Hold your tag near the top of your iPhone.") { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let id):
                tagID = id
                defaults.set(id, forKey: Key.tag)
            case .failure(let error):
                if case NFCReader.ReadError.cancelled = error { return }
                message = error.localizedDescription
            }
        }
    }

    func tap() {
        message = nil
        let prompt = isBlocking ? "Tap your tag to unblock." : "Tap your tag to block."
        reader.scan(prompt: prompt) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let id) where id == tagID:
                isBlocking ? unblock() : block()
            case .success:
                message = "That's not your tag."
            case .failure(let error):
                if case NFCReader.ReadError.cancelled = error { return }
                message = error.localizedDescription
            }
        }
    }

    // MARK: Shielding

    private func block() {
        shield.shield.applications = selection.applicationTokens.isEmpty ? nil : selection.applicationTokens
        shield.shield.applicationCategories = selection.categoryTokens.isEmpty
            ? nil : .specific(selection.categoryTokens)
        shield.shield.webDomains = selection.webDomainTokens.isEmpty ? nil : selection.webDomainTokens
        setBlocking(true)
    }

    private func unblock() {
        shield.clearAllSettings()
        setBlocking(false)
    }

    private func setBlocking(_ value: Bool) {
        isBlocking = value
        defaults.set(value, forKey: Key.blocking)
    }

    private func save(_ selection: FamilyActivitySelection) {
        if let data = try? JSONEncoder().encode(selection) {
            defaults.set(data, forKey: Key.selection)
        }
    }
}
