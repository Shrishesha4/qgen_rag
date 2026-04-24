from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject, SubjectGroup


async def get_descendant_group_ids(db: AsyncSession, root_group_id: str) -> list[str]:
	"""Return the requested group id plus all nested descendant group ids."""
	clean_group_id = (root_group_id or "").strip()
	if not clean_group_id:
		return []

	result = await db.execute(select(SubjectGroup.id, SubjectGroup.parent_id))
	rows = result.all()
	if not rows:
		return []

	children_by_parent: dict[Optional[str], list[str]] = {}
	all_group_ids = set()
	for group_id, parent_id in rows:
		group_id_str = str(group_id)
		parent_id_str = str(parent_id) if parent_id else None
		all_group_ids.add(group_id_str)
		children_by_parent.setdefault(parent_id_str, []).append(group_id_str)

	if clean_group_id not in all_group_ids:
		return []

	descendant_ids: list[str] = []
	stack = [clean_group_id]
	seen = set()
	while stack:
		group_id = stack.pop()
		if group_id in seen:
			continue
		seen.add(group_id)
		descendant_ids.append(group_id)
		stack.extend(children_by_parent.get(group_id, []))

	return descendant_ids


async def get_subject_ids_for_group(
	db: AsyncSession,
	group_id: str,
	*,
	owner_id: Optional[str] = None,
) -> list[str]:
	"""Return all subject ids that belong to the group or any nested descendant group."""
	group_ids = await get_descendant_group_ids(db, group_id)
	if not group_ids:
		return []

	query = select(Subject.id).where(Subject.group_id.in_(group_ids))
	if owner_id:
		query = query.where(Subject.user_id == owner_id)

	result = await db.execute(query)
	return [str(subject_id) for subject_id in result.scalars().all()]