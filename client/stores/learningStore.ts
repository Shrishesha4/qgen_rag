/**
 * Learning & Gamification state store (Zustand)
 */
import { create } from 'zustand';
import learnService, {
  SubjectStudent,
  Enrollment,
  LessonData,
  LessonResult,
  StudentProgress,
  GamificationProfile,
  LeaderboardData,
  TestHistoryEntry,
  DailyActivityEntry,
  AnswerSubmission,
} from '../services/learn';

interface LearningState {
  // State
  profile: GamificationProfile | null;
  subjects: SubjectStudent[];
  enrollments: Enrollment[];
  currentLesson: LessonData | null;
  lessonResult: LessonResult | null;
  progress: StudentProgress[];
  leaderboard: LeaderboardData | null;
  testHistory: TestHistoryEntry[];
  dailyActivity: DailyActivityEntry[];
  isLoading: boolean;
  error: string | null;

  // Actions
  loadProfile: () => Promise<void>;
  loadSubjects: () => Promise<void>;
  loadEnrollments: () => Promise<void>;
  enrollInSubject: (subjectId: string) => Promise<boolean>;
  startLesson: (subjectId: string, topicId?: string, count?: number) => Promise<boolean>;
  submitLesson: (subjectId: string, topicId: string | undefined, answers: AnswerSubmission[], totalTime?: number) => Promise<boolean>;
  loadProgress: (subjectId: string) => Promise<void>;
  loadLeaderboard: (limit?: number) => Promise<void>;
  loadTestHistory: (subjectId?: string, limit?: number) => Promise<void>;
  loadDailyActivity: (days?: number) => Promise<void>;
  clearLesson: () => void;
  clearError: () => void;
}

export const useLearningStore = create<LearningState>((set, get) => ({
  profile: null,
  subjects: [],
  enrollments: [],
  currentLesson: null,
  lessonResult: null,
  progress: [],
  leaderboard: null,
  testHistory: [],
  dailyActivity: [],
  isLoading: false,
  error: null,

  loadProfile: async () => {
    try {
      set({ isLoading: true, error: null });
      const profile = await learnService.getProfile();
      set({ profile, isLoading: false });
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to load profile' });
    }
  },

  loadSubjects: async () => {
    try {
      set({ isLoading: true, error: null });
      const subjects = await learnService.getAvailableSubjects();
      set({ subjects, isLoading: false });
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to load subjects' });
    }
  },

  loadEnrollments: async () => {
    try {
      const enrollments = await learnService.getEnrollments();
      set({ enrollments });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load enrollments' });
    }
  },

  enrollInSubject: async (subjectId: string) => {
    try {
      set({ isLoading: true, error: null });
      await learnService.enrollInSubject(subjectId);
      // Reload subjects and enrollments
      const [subjects, enrollments] = await Promise.all([
        learnService.getAvailableSubjects(),
        learnService.getEnrollments(),
      ]);
      set({ subjects, enrollments, isLoading: false });
      return true;
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to enroll' });
      return false;
    }
  },

  startLesson: async (subjectId: string, topicId?: string, count: number = 10) => {
    try {
      set({ isLoading: true, error: null, lessonResult: null });
      const lesson = await learnService.getLesson(subjectId, topicId, count);
      set({ currentLesson: lesson, isLoading: false });
      return true;
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to start lesson' });
      return false;
    }
  },

  submitLesson: async (subjectId: string, topicId: string | undefined, answers: AnswerSubmission[], totalTime?: number) => {
    try {
      set({ isLoading: true, error: null });
      const result = await learnService.submitLesson({
        subject_id: subjectId,
        topic_id: topicId,
        answers,
        total_time_seconds: totalTime,
      });
      set({ lessonResult: result, currentLesson: null, isLoading: false });
      return true;
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to submit lesson' });
      return false;
    }
  },

  loadProgress: async (subjectId: string) => {
    try {
      const progress = await learnService.getSubjectProgress(subjectId);
      set({ progress });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load progress' });
    }
  },

  loadLeaderboard: async (limit: number = 20) => {
    try {
      set({ isLoading: true, error: null });
      const leaderboard = await learnService.getLeaderboard(limit);
      set({ leaderboard, isLoading: false });
    } catch (e: any) {
      set({ isLoading: false, error: e?.message || 'Failed to load leaderboard' });
    }
  },

  loadTestHistory: async (subjectId?: string, limit?: number) => {
    try {
      const testHistory = await learnService.getTestHistory(subjectId, limit);
      set({ testHistory });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load test history' });
    }
  },

  loadDailyActivity: async (days: number = 30) => {
    try {
      const dailyActivity = await learnService.getDailyActivity(days);
      set({ dailyActivity });
    } catch (e: any) {
      set({ error: e?.message || 'Failed to load daily activity' });
    }
  },

  clearLesson: () => set({ currentLesson: null, lessonResult: null }),

  clearError: () => set({ error: null }),
}));
