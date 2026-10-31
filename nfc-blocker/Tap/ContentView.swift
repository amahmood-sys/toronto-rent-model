import FamilyControls
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: BlockModel
    @State private var picking = false

    var body: some View {
        VStack(spacing: 16) {
            Spacer()

            Image(systemName: model.isBlocking ? "lock.fill" : "lock.open")
                .font(.system(size: 56, weight: .light))
                .contentTransition(.symbolEffect(.replace))
            Text(model.isBlocking ? "Blocked" : "Unblocked")
                .font(.largeTitle.weight(.semibold))
            Text(summary)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Spacer()

            if let message = model.message {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            if model.tagID == nil {
                PrimaryButton("Pair NFC tag") { model.pairTag() }
            } else {
                PrimaryButton(model.isBlocking ? "Tap tag to unblock" : "Tap tag to block") {
                    model.tap()
                }
                .disabled(!model.isBlocking && !model.hasApps)
            }

            HStack(spacing: 24) {
                Button("Choose apps") { picking = true }
                if model.tagID != nil {
                    Button("Re-pair tag") { model.pairTag() }
                }
            }
            .font(.subheadline)
            .tint(.secondary)
            .disabled(model.isBlocking) // no cheating while blocked
        }
        .padding(24)
        .animation(.default, value: model.isBlocking)
        .familyActivityPicker(isPresented: $picking, selection: $model.selection)
        .task { await model.authorize() }
    }

    private var summary: String {
        let s = model.selection
        let count = s.applicationTokens.count + s.categoryTokens.count + s.webDomainTokens.count
        return count == 0 ? "No apps selected" : "\(count) item\(count == 1 ? "" : "s") selected"
    }
}

private struct PrimaryButton: View {
    let title: String
    let action: () -> Void

    init(_ title: String, action: @escaping () -> Void) {
        self.title = title
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
        }
        .buttonStyle(.borderedProminent)
        .buttonBorderShape(.capsule)
        .tint(.primary)
        .foregroundStyle(Color(uiColor: .systemBackground))
    }
}
