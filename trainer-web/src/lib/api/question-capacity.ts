/** Question Capacity Estimation API */
import { apiFetch } from './client';

export async function estimateQuestionCapacity(subjectId: string): Promise<{
	subject_id: string;
	primary_documents: number;
	total_chunks: number;
	estimated_capacity: number;
	recommendation: {
		suggested_count: number;
		reasoning: string;
	};
}> {
	return apiFetch(`/questions/estimate-capacity/${subjectId}`);
}
