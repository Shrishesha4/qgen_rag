/** Question Capacity Estimation API */
import { apiFetch } from './client';

export async function estimateQuestionCapacity(subjectId: string): Promise<{
	subject_id: string;
	primary_documents: number;
	completed_documents: number;
	reference_documents: number;
	template_documents: number;
	total_chunks: number;
	discovery_strategy: string;
}> {
	return apiFetch(`/questions/estimate-capacity/${subjectId}`);
}
