# Tap — minimal NFC app blocker (iOS)

One screen. Pick apps, tap your NFC tag to block them, tap it again to unblock.
Leave the tag somewhere inconvenient (another room, the office) and the only way
back into your apps is walking to it.

## How it works
- **Blocking:** Apple's Screen Time APIs (`FamilyControls` + `ManagedSettings`).
  Blocked apps show the system shield screen and won't open.
- **NFC:** `CoreNFC` reads the tag's hardware ID. Only the paired tag toggles the block.
- While blocked, "Choose apps" and "Re-pair tag" are disabled so you can't cheat.
- Any cheap NFC sticker works (NTAG213/215/216, ~$0.50 each).

## Run it
Needs a Mac with Xcode 15+, a real iPhone (no NFC in the simulator), iOS 17+.

```sh
brew install xcodegen
cd nfc-blocker
xcodegen            # creates Tap.xcodeproj
open Tap.xcodeproj
```

1. In `project.yml` set `PRODUCT_BUNDLE_IDENTIFIER` and `DEVELOPMENT_TEAM` (or set them
   in Xcode → Signing & Capabilities).
2. Requires a paid Apple Developer account (for the NFC and Family Controls capabilities).
3. Run on your iPhone → allow Screen Time → Pair NFC tag → Choose apps → Tap tag to block.

**App Store note:** Family Controls works in development builds right away. To ship on
TestFlight or the App Store, request the distribution entitlement from Apple:
https://developer.apple.com/contact/request/family-controls-distribution

## Escape hatch
Lost the tag? Deleting the app removes all shields.

## Files
| File | What |
|---|---|
| `Tap/ContentView.swift` | The single screen |
| `Tap/BlockModel.swift` | State, persistence, block/unblock |
| `Tap/NFCReader.swift` | Reads a tag's ID |
| `project.yml` | XcodeGen spec (entitlements + Info.plist) |
