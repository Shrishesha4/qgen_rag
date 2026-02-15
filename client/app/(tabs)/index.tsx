import { Redirect } from 'expo-router';

/**
 * Index route for (tabs) group.
 * Redirects to the home tab's index screen.
 */
export default function TabsIndex() {
  return <Redirect href="/(tabs)/home" />;
}
