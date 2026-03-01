import { Redirect } from 'expo-router';
import { useAuthStore } from '@/stores/authStore';

/**
 * Index route for (tabs) group.
 * Redirects based on user role.
 */
export default function TabsIndex() {
  const { user } = useAuthStore();
  const isTeacher = user?.role === 'teacher' || user?.role === 'admin';
  
  if (isTeacher) {
    return <Redirect href="/(tabs)/home" />;
  }
  return <Redirect href="/(tabs)/learn" />;
}
