import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';
import { ListingsScreen } from '../screens/ListingsScreen';
import { WatchlistsScreen } from '../screens/WatchlistsScreen';
import { InventoryScreen } from '../screens/InventoryScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { usePushNotifications } from '../hooks/usePushNotifications';

const Tab = createBottomTabNavigator();

function Icon({ glyph, focused }: { glyph: string; focused: boolean }) {
  return <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.45 }}>{glyph}</Text>;
}

export function TabNavigator() {
  usePushNotifications();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0d0d1a',
          borderTopColor: '#1e1e2e',
          height: 64,
          paddingBottom: 10,
        },
        tabBarActiveTintColor: '#7c3aed',
        tabBarInactiveTintColor: '#4b5563',
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600', marginTop: 2 },
      }}
    >
      <Tab.Screen
        name="Listings"
        component={ListingsScreen}
        options={{ tabBarIcon: ({ focused }) => <Icon glyph="🔥" focused={focused} /> }}
      />
      <Tab.Screen
        name="Watchlists"
        component={WatchlistsScreen}
        options={{ tabBarIcon: ({ focused }) => <Icon glyph="👁" focused={focused} /> }}
      />
      <Tab.Screen
        name="Inventory"
        component={InventoryScreen}
        options={{ tabBarIcon: ({ focused }) => <Icon glyph="📦" focused={focused} /> }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarIcon: ({ focused }) => <Icon glyph="⚙️" focused={focused} /> }}
      />
    </Tab.Navigator>
  );
}
