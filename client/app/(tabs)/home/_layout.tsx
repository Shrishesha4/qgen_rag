import { Stack } from 'expo-router';
import { TouchableOpacity } from 'react-native';
import { router } from 'expo-router';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';

export default function HomeStackLayout() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];

  const ProfileButton = () => (
    <TouchableOpacity
      onPress={() => router.push('/(tabs)/home/profile')}
      style={{ 
        marginRight: 12,
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.primary + '10',
      }}
      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
    >
      <IconSymbol name="person.circle.fill" size={28} color={colors.primary} />
    </TouchableOpacity>
  );

  return (
    <Stack
      screenOptions={{
        headerShown: true,
        headerStyle: {
          backgroundColor: colors.background,
        },
        headerTintColor: colors.primary,
        headerTitleStyle: {
          fontWeight: '600',
          color: colors.text,
        },
        headerShadowVisible: false,
        headerBackTitle: 'Back',
        contentStyle: {
          backgroundColor: colors.background,
        },
      }}
    >
      <Stack.Screen
        name="index"
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="subjects"
        options={{
          title: 'Subjects',
        }}
      />
      <Stack.Screen
        name="subject-detail"
        options={{
          title: 'Subject Details',
        }}
      />
      <Stack.Screen
        name="generate"
        options={{
          title: 'Rubric Generator',
        }}
      />
      <Stack.Screen
        name="vetting"
        options={{
          title: 'Question Vetting',
        }}
      />
      <Stack.Screen
        name="reports"
        options={{
          title: 'Reports',
        }}
      />
      <Stack.Screen
        name="questions"
        options={{
          title: 'Questions',
        }}
      />
      <Stack.Screen
        name="profile"
        options={{
          title: 'Profile',
          presentation: 'modal',
          headerShown: true,
          headerBackTitle: 'Back',
        }}
      />
    </Stack>
  );
}
