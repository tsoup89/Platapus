/**
 * TypeScript surface for the WidgetBridge native module.
 *
 * On Android or Expo Go this module resolves to NativeModules.WidgetBridge
 * being undefined; callers (widgetService.ts) guard against that.
 */
export { default } from './src/WidgetBridge';
