import { Stack } from 'expo-router';

export default function LearnLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="lesson" />
      <Stack.Screen name="result" />
      <Stack.Screen name="subject-detail" />
      <Stack.Screen name="topic-content" />
      <Stack.Screen name="pdf-viewer" />
    </Stack>
  );
}
