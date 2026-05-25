#import <React/RCTBridgeModule.h>

/**
 * Objective-C bridge header — exposes the Swift WidgetBridge class
 * to the React Native bridge.
 */
@interface RCT_EXTERN_MODULE(WidgetBridge, NSObject)

RCT_EXTERN_METHOD(
  updateWidgetData:(NSString *)jsonString
  resolve:(RCTPromiseResolveBlock)resolve
  reject:(RCTPromiseRejectBlock)reject
)

@end
