import { NativeModules } from 'react-native';

const { WidgetBridge } = NativeModules;
export default WidgetBridge as {
  updateWidgetData(jsonString: string): Promise<void>;
} | null;
