import type { SubjectGroupTreeNode } from '$lib/api/subjects';

export interface SubjectGroupMeta {
	groupId: string;
	groupPath: string;
}

export interface SubjectSearchable {
	id: string;
	name: string;
	code: string;
	description: string | null;
}

export function buildSubjectGroupMetaById(groups: SubjectGroupTreeNode[]): Map<string, SubjectGroupMeta> {
	const groupMetaById = new Map<string, SubjectGroupMeta>();

	function walk(group: SubjectGroupTreeNode, parentNames: string[]) {
		const pathNames = [...parentNames, group.name];
		const groupPath = pathNames.join(' / ');

		for (const subject of group.subjects) {
			groupMetaById.set(subject.id, {
				groupId: group.id,
				groupPath,
			});
		}

		for (const child of group.children) {
			walk(child, pathNames);
		}
	}

	for (const group of groups) {
		walk(group, []);
	}

	return groupMetaById;
}

export function matchesSubjectSearch(
	subject: SubjectSearchable,
	normalizedQuery: string,
	groupMetaById: Map<string, SubjectGroupMeta>
): boolean {
	if (!normalizedQuery) return true;

	const groupPath = groupMetaById.get(subject.id)?.groupPath ?? '';
	return [subject.name, subject.code, subject.description ?? '', groupPath].some((value) =>
		value.toLowerCase().includes(normalizedQuery)
	);
}

export function getSubjectGroupPath(
	subjectId: string,
	groupMetaById: Map<string, SubjectGroupMeta>
): string | null {
	return groupMetaById.get(subjectId)?.groupPath ?? null;
}