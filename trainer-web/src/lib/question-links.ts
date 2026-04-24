export type QuestionStatusFilter = 'pending' | 'approved' | 'rejected';

type TeacherQuestionLinkParams = {
	groupId?: string;
	groupName?: string;
	subjectId?: string;
	subjectName?: string;
	subjectCode?: string;
	topicId?: string;
	topicName?: string;
	status?: QuestionStatusFilter;
	search?: string;
};

type AdminQuestionLinkParams = {
	groupId?: string;
	subjectId?: string;
	topicId?: string;
	status?: QuestionStatusFilter;
};

export function buildTeacherQuestionsUrl(params: TeacherQuestionLinkParams = {}): string {
	const searchParams = new URLSearchParams();
	if (params.groupId) searchParams.set('group_id', params.groupId);
	if (params.groupName) searchParams.set('group_name', params.groupName);
	if (params.subjectId) searchParams.set('subject_id', params.subjectId);
	if (params.subjectName) searchParams.set('subject_name', params.subjectName);
	if (params.subjectCode) searchParams.set('subject_code', params.subjectCode);
	if (params.topicId) searchParams.set('topic_id', params.topicId);
	if (params.topicName) searchParams.set('topic_name', params.topicName);
	if (params.status) searchParams.set('vetting_status', params.status);
	if (params.search) searchParams.set('search', params.search);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	return `/teacher/questions${suffix}`;
}

export function buildAdminQuestionsUrl(params: AdminQuestionLinkParams = {}): string {
	const searchParams = new URLSearchParams();
	if (params.groupId) searchParams.set('group_id', params.groupId);
	if (params.subjectId) searchParams.set('subject_id', params.subjectId);
	if (params.topicId) searchParams.set('topic_id', params.topicId);
	if (params.status) searchParams.set('vetting_status', params.status);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	return `/admin/questions${suffix}`;
}