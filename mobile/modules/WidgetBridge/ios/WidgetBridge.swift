import Foundation
import WidgetKit

/**
 * WidgetBridge
 *
 * Writes serialised WidgetData JSON into the shared App Group
 * UserDefaults container and triggers a WidgetKit timeline reload
 * so the home-screen widget refreshes immediately.
 *
 * App Group identifier: group.com.gamgee.app
 * This must be enabled in both the main app target and the widget
 * extension target in Xcode / provisioning profiles.
 */
@objc(WidgetBridge)
class WidgetBridge: NSObject {

  private let appGroup = "group.com.gamgee.app"
  private let dataKey  = "gamgeeWidgetData"

  @objc(updateWidgetData:resolve:reject:)
  func updateWidgetData(
    _ jsonString: String,
    resolve: @escaping RCTPromiseResolveBlock,
    reject:  @escaping RCTPromiseRejectBlock
  ) {
    guard let defaults = UserDefaults(suiteName: appGroup) else {
      reject(
        "NO_APP_GROUP",
        "App Group '\(appGroup)' is not configured. " +
        "Enable it in Xcode under Signing & Capabilities for both targets.",
        nil
      )
      return
    }

    defaults.set(jsonString, forKey: dataKey)
    defaults.synchronize()

    if #available(iOS 14.0, *) {
      WidgetCenter.shared.reloadAllTimelines()
    }

    resolve(nil)
  }

  @objc static func requiresMainQueueSetup() -> Bool {
    return false
  }
}
