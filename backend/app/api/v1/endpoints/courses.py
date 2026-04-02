"""
Course marketplace API endpoints.

Endpoints for:
- Course CRUD (teacher/admin)
- Public course catalog (unauthenticated)
- Module CRUD under courses (teacher/admin)
- Module question attachment (teacher/admin)
"""

import os
import re
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.api.v1.deps import (
    get_current_user,
    get_current_teacher_or_admin,
)
from app.models.user import User
from app.models.course import (
    Course, CourseModule, ModuleQuestion,
    CourseStatus, ModuleType,
)
from app.models.document import Document
from app.models.question import Question
from app.models.subject import Subject, Topic
from app.schemas.course import (
    CourseCreate, CourseUpdate, CourseResponse, CourseSummary, CourseListResponse,
    ModuleCreate, ModuleUpdate, ModuleReorder, ModuleQuestionAdd,
    CourseModuleResponse, ModuleQuestionResponse, ModuleContentGenerateRequest,
)
from app.services.provider_service import get_provider_service

router = APIRouter()


def _slugify(text: str) -> str:
    """Generate a URL-safe slug from text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:250]


async def _unique_slug(db: AsyncSession, base_slug: str, exclude_id: Optional[str] = None) -> str:
    """Ensure slug is unique, appending a suffix if needed."""
    slug = base_slug
    counter = 1
    while True:
        query = select(Course.id).where(Course.slug == slug)
        if exclude_id:
            query = query.where(Course.id != exclude_id)
        result = await db.execute(query)
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            return slug


async def _get_course_or_404(
    db: AsyncSession, course_id: str, load_modules: bool = False
) -> Course:
    query = select(Course).where(Course.id == course_id)
    if load_modules:
        query = query.options(
            selectinload(Course.modules).selectinload(CourseModule.module_questions)
        )
    result = await db.execute(query)
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def _assert_course_owner(course: Course, user: User) -> None:
    if user.role == "admin" or user.is_superuser:
        return
    if course.teacher_id != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your course")


def _build_module_question_snapshot(question: Question) -> dict:
    options = [str(option) for option in (question.options or [])]
    correct_answer = str(question.correct_answer or "").strip()
    correct_index = None

    if options and correct_answer:
        normalized_correct = correct_answer.upper()
        for index, option in enumerate(options):
            normalized_option = option.strip().upper()
            if (
                option.strip() == correct_answer
                or normalized_option == normalized_correct
                or normalized_option.startswith(f"{normalized_correct})")
                or normalized_option.startswith(f"{normalized_correct}.")
                or normalized_option.startswith(f"{normalized_correct}:")
            ):
                correct_index = index
                break

    return {
        "question_id": str(question.id),
        "question": question.question_text,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "options": options,
        "correct": correct_index,
        "correct_answer": correct_answer,
        "sample_answer": correct_answer,
        "explanation": str(question.explanation or "").strip(),
        "difficulty_level": question.difficulty_level,
        "marks": question.marks,
    }


# ==================== Course CRUD ====================


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Create a new course (draft)."""
    slug = await _unique_slug(db, _slugify(data.title))
    course = Course(
        teacher_id=str(current_user.id),
        title=data.title,
        slug=slug,
        description=data.description,
        subject_id=data.subject_id,
        price_cents=data.price_cents,
        currency=data.currency,
        cover_image_url=data.cover_image_url,
        preview_video_url=data.preview_video_url,
        learning_outcomes=data.learning_outcomes,
        status=CourseStatus.DRAFT.value,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course, attribute_names=["modules"])
    return course


@router.get("", response_model=CourseListResponse)
async def list_courses(
    subject_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    price_max: Optional[int] = Query(None, ge=0),
    featured: Optional[bool] = Query(None),
    teacher_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Public catalog: list published courses (paginated, filterable)."""
    filters = [Course.status == CourseStatus.PUBLISHED.value]

    if subject_id:
        filters.append(Course.subject_id == subject_id)
    if price_max is not None:
        filters.append(Course.price_cents <= price_max)
    if featured is not None:
        filters.append(Course.is_featured == featured)
    if teacher_id:
        filters.append(Course.teacher_id == teacher_id)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Course.title.ilike(pattern),
                Course.description.ilike(pattern),
            )
        )

    where = and_(*filters)

    # Count
    count_q = select(func.count()).select_from(Course).where(where)
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch
    offset = (page - 1) * page_size
    query = (
        select(Course)
        .where(where)
        .order_by(Course.is_featured.desc(), Course.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .options(selectinload(Course.modules), selectinload(Course.enrollments))
    )
    rows = (await db.execute(query)).scalars().all()

    items = [
        CourseSummary(
            id=c.id,
            teacher_id=c.teacher_id,
            title=c.title,
            slug=c.slug,
            description=c.description,
            cover_image_url=c.cover_image_url,
            price_cents=c.price_cents,
            currency=c.currency,
            status=c.status,
            is_featured=c.is_featured,
            module_count=len(c.modules),
            enrolled_count=len(c.enrollments),
            created_at=c.created_at,
        )
        for c in rows
    ]

    return CourseListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/thumbnails/{filename}")
async def get_course_thumbnail(filename: str):
    """Serve locally uploaded course thumbnails."""
    thumbnails_dir = os.path.join(settings.UPLOAD_DIR, "course-thumbnails")
    file_path = os.path.join(thumbnails_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")

    return FileResponse(file_path)


@router.get("/my", response_model=CourseListResponse)
async def list_my_courses(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """List courses owned by the current teacher."""
    filters = [Course.teacher_id == str(current_user.id)]
    if status_filter:
        filters.append(Course.status == status_filter)

    where = and_(*filters)
    count_q = select(func.count()).select_from(Course).where(where)
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = (
        select(Course)
        .where(where)
        .order_by(Course.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .options(selectinload(Course.modules), selectinload(Course.enrollments))
    )
    rows = (await db.execute(query)).scalars().all()

    items = [
        CourseSummary(
            id=c.id,
            teacher_id=c.teacher_id,
            title=c.title,
            slug=c.slug,
            description=c.description,
            cover_image_url=c.cover_image_url,
            price_cents=c.price_cents,
            currency=c.currency,
            status=c.status,
            is_featured=c.is_featured,
            module_count=len(c.modules),
            enrolled_count=len(c.enrollments),
            created_at=c.created_at,
        )
        for c in rows
    ]

    return CourseListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response_model=CourseResponse)
async def get_course_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: get course detail by slug (published courses show all modules; draft only for owner)."""
    query = (
        select(Course)
        .where(Course.slug == slug)
        .options(
            selectinload(Course.modules).selectinload(CourseModule.module_questions)
        )
    )
    result = await db.execute(query)
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.status != CourseStatus.PUBLISHED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.get("/id/{course_id}", response_model=CourseResponse)
async def get_course_by_id(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get course by ID (owner/admin can see any status)."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    if course.status != CourseStatus.PUBLISHED.value:
        _assert_course_owner(course, current_user)
    return course


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    data: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Update a course (owner or admin)."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    _assert_course_owner(course, current_user)

    update_data = data.model_dump(exclude_unset=True)

    if "title" in update_data and update_data["title"]:
        new_slug = _slugify(update_data["title"])
        update_data["slug"] = await _unique_slug(db, new_slug, exclude_id=course_id)

    for field, value in update_data.items():
        setattr(course, field, value)

    await db.commit()
    await db.refresh(course, attribute_names=["modules"])
    return course


@router.post("/{course_id}/thumbnail", response_model=CourseResponse)
async def upload_course_thumbnail(
    course_id: str,
    file: UploadFile = File(..., description="Course thumbnail image (JPEG, PNG, or WebP)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Upload and store a course thumbnail locally on the server."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    _assert_course_owner(course, current_user)

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed types: JPEG, PNG, WebP",
        )

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5MB",
        )

    thumbnails_dir = os.path.join(settings.UPLOAD_DIR, "course-thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)

    extension = allowed_types[file.content_type]
    filename = f"{course.id}_{uuid.uuid4().hex[:8]}{extension}"
    file_path = os.path.join(thumbnails_dir, filename)

    local_prefix = f"{settings.API_PREFIX}/courses/thumbnails/"
    if course.cover_image_url and course.cover_image_url.startswith(local_prefix):
        old_filename = course.cover_image_url.removeprefix(local_prefix)
        old_path = os.path.join(thumbnails_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    with open(file_path, "wb") as output_file:
        output_file.write(content)

    course.cover_image_url = f"{local_prefix}{filename}"
    await db.commit()
    await db.refresh(course, attribute_names=["modules"])
    return course


@router.post("/{course_id}/publish", response_model=CourseResponse)
async def publish_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Transition course from draft to published (validates completeness)."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    _assert_course_owner(course, current_user)

    if course.status == CourseStatus.PUBLISHED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course already published")
    if course.status == CourseStatus.ARCHIVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot publish an archived course")

    # Basic completeness check
    if not course.title or not course.description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course needs a title and description")
    if not course.modules:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course needs at least one module")

    course.status = CourseStatus.PUBLISHED.value
    await db.commit()
    await db.refresh(course, attribute_names=["modules"])
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Soft-delete: archive a course."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)
    course.status = CourseStatus.ARCHIVED.value
    await db.commit()


# ==================== Module CRUD ====================


@router.post("/{course_id}/modules", response_model=CourseModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    course_id: str,
    data: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Add a module to a course."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    _assert_course_owner(course, current_user)

    # Auto-assign order_index to end
    max_order = max((m.order_index for m in course.modules), default=-1)

    module = CourseModule(
        course_id=course_id,
        title=data.title,
        description=data.description,
        order_index=max_order + 1,
        module_type=data.module_type,
        content_data=data.content_data,
        duration_minutes=data.duration_minutes,
        is_preview=data.is_preview,
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


@router.post("/{course_id}/modules/{module_id}/generate-content", response_model=CourseModuleResponse)
async def generate_module_content(
    course_id: str,
    module_id: str,
    data: ModuleContentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Generate a lesson or assignment draft for a module using the linked subject topic."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)

    result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    if not course.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assign a subject to this course before generating module content",
        )

    content_data = dict(module.content_data or {})
    topic_id = data.topic_id or content_data.get("topic_id")
    if not topic_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a topic before generating module content",
        )

    topic_result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == course.subject_id,
        )
    )
    topic = topic_result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found for this course subject")

    subject_result = await db.execute(select(Subject).where(Subject.id == course.subject_id))
    subject = subject_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    provider_service = get_provider_service()
    enabled_providers = await provider_service.get_enabled_providers()
    if not enabled_providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No enabled API providers are configured in Admin Settings.",
        )

    llm_service, _ = provider_service.create_llm_service(enabled_providers[0])
    source_parts = [
        f"Course: {course.title}",
        f"Subject: {subject.name} ({subject.code})",
        f"Topic: {topic.name}",
        f"Module title: {module.title}",
        f"Module type: {module.module_type}",
    ]
    if topic.description:
        source_parts.append(f"Topic description:\n{topic.description}")
    if topic.syllabus_content:
        source_parts.append(f"Topic syllabus:\n{topic.syllabus_content[:6000]}")
    if module.description:
        source_parts.append(f"Existing module brief:\n{module.description}")
    if data.focus:
        source_parts.append(f"Teacher focus:\n{data.focus}")

    system_prompt = (
        "You are an expert instructional designer helping a teacher build course modules. "
        "Return only JSON with these keys: summary, learning_objectives, body_markdown, assignment_prompt, video_url, suggested_duration_minutes. "
        "learning_objectives must be an array of short strings. body_markdown must be detailed and classroom-ready. "
        "If the module type is assignment, make assignment_prompt specific and actionable."
    )
    prompt = (
        "Create a teaching draft for this module based on the source material below. "
        "Use the topic syllabus when available, keep the lesson structured, and avoid inventing facts not supported by the source.\n\n"
        + "\n\n".join(source_parts)
    )

    try:
        generated = await llm_service.generate_json(prompt=prompt, system_prompt=system_prompt, temperature=0.3)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate module content: {exc}",
        ) from exc

    if not isinstance(generated, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider returned invalid content payload",
        )

    learning_objectives = generated.get("learning_objectives") or []
    if not isinstance(learning_objectives, list):
        learning_objectives = [str(learning_objectives)]

    content_data.update(
        {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "summary": str(generated.get("summary") or "").strip(),
            "learning_objectives": [str(item).strip() for item in learning_objectives if str(item).strip()],
            "body_markdown": str(generated.get("body_markdown") or "").strip(),
            "markdown": str(generated.get("body_markdown") or "").strip(),
            "assignment_prompt": str(generated.get("assignment_prompt") or "").strip(),
            "video_url": str(generated.get("video_url") or "").strip(),
        }
    )
    module.content_data = content_data

    if not module.description and content_data.get("summary"):
        module.description = str(content_data["summary"])[:500]

    suggested_duration = generated.get("suggested_duration_minutes")
    if isinstance(suggested_duration, int) and suggested_duration >= 0:
        module.duration_minutes = suggested_duration

    await db.commit()
    await db.refresh(module)
    return module


@router.patch("/{course_id}/modules/{module_id}", response_model=CourseModuleResponse)
async def update_module(
    course_id: str,
    module_id: str,
    data: ModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Update a module."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)

    result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(module, field, value)

    await db.commit()
    await db.refresh(module)
    return module


@router.delete("/{course_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    course_id: str,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Remove a module."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)

    result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    await db.delete(module)
    await db.commit()


@router.post("/{course_id}/modules/reorder", status_code=status.HTTP_200_OK)
async def reorder_modules(
    course_id: str,
    data: ModuleReorder,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Reorder modules by providing ordered list of module IDs."""
    course = await _get_course_or_404(db, course_id, load_modules=True)
    _assert_course_owner(course, current_user)

    module_map = {m.id: m for m in course.modules}
    for idx, mid in enumerate(data.module_ids):
        if mid not in module_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module {mid} not found in course",
            )
        module_map[mid].order_index = idx

    await db.commit()
    return {"ok": True}


# ==================== Module Questions ====================


@router.post(
    "/{course_id}/modules/{module_id}/questions",
    response_model=List[ModuleQuestionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_questions_to_module(
    course_id: str,
    module_id: str,
    data: ModuleQuestionAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Attach approved questions to a quiz module."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)

    result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    question_filters = [
        Question.id.in_(data.question_ids),
        Question.is_archived.is_(False),
    ]

    if not (current_user.role == "admin" or current_user.is_superuser):
        question_filters.append(
            or_(
                Question.vetting_status == "approved",
                Document.user_id == str(current_user.id),
                Subject.user_id == str(current_user.id),
            )
        )

    q_result = await db.execute(
        select(Question.id)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(*question_filters)
    )
    accessible_ids = set(q_result.scalars().all())
    missing = set(data.question_ids) - accessible_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Questions not found or not accessible for this teacher: {list(missing)}",
        )

    question_result = await db.execute(
        select(Question).where(Question.id.in_(data.question_ids))
    )
    questions_by_id = {str(question.id): question for question in question_result.scalars().all()}

    content_data = dict(module.content_data or {})
    existing_snapshots = [
        item
        for item in (content_data.get("questions") or [])
        if isinstance(item, dict)
    ]
    existing_snapshot_ids = {
        str(item.get("question_id") or item.get("id") or item.get("questionId"))
        for item in existing_snapshots
        if item.get("question_id") or item.get("id") or item.get("questionId")
    }

    # Get current max sequence
    seq_result = await db.execute(
        select(func.coalesce(func.max(ModuleQuestion.sequence), -1)).where(
            ModuleQuestion.module_id == module_id,
        )
    )
    max_seq = seq_result.scalar() or -1

    created = []
    for i, qid in enumerate(data.question_ids):
        # Skip duplicates
        exists = await db.execute(
            select(ModuleQuestion.id).where(
                ModuleQuestion.module_id == module_id,
                ModuleQuestion.question_id == qid,
            )
        )
        if exists.scalar_one_or_none():
            continue

        mq = ModuleQuestion(
            module_id=module_id,
            question_id=qid,
            sequence=max_seq + 1 + i,
        )
        db.add(mq)
        created.append(mq)

        question = questions_by_id.get(str(qid))
        if question and str(qid) not in existing_snapshot_ids:
            existing_snapshots.append(_build_module_question_snapshot(question))
            existing_snapshot_ids.add(str(qid))

    content_data["questions"] = existing_snapshots
    module.content_data = content_data

    await db.commit()
    for mq in created:
        await db.refresh(mq)
    return created


@router.get(
    "/{course_id}/modules/{module_id}/questions",
    response_model=List[ModuleQuestionResponse],
)
async def list_module_questions(
    course_id: str,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List questions attached to a module."""
    # Verify course and module exist
    course = await _get_course_or_404(db, course_id)
    result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    q = (
        select(ModuleQuestion)
        .where(ModuleQuestion.module_id == module_id)
        .order_by(ModuleQuestion.sequence)
    )
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.delete(
    "/{course_id}/modules/{module_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_question_from_module(
    course_id: str,
    module_id: str,
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Detach a question from a module."""
    course = await _get_course_or_404(db, course_id)
    _assert_course_owner(course, current_user)

    module_result = await db.execute(
        select(CourseModule).where(
            CourseModule.id == module_id,
            CourseModule.course_id == course_id,
        )
    )
    module = module_result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    result = await db.execute(
        select(ModuleQuestion).where(
            ModuleQuestion.module_id == module_id,
            ModuleQuestion.question_id == question_id,
        )
    )
    mq = result.scalar_one_or_none()
    if not mq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not attached to module")

    content_data = dict(module.content_data or {})
    if isinstance(content_data.get("questions"), list):
        content_data["questions"] = [
            item
            for item in content_data["questions"]
            if not isinstance(item, dict)
            or str(item.get("question_id") or item.get("id") or item.get("questionId")) != question_id
        ]
        module.content_data = content_data

    await db.delete(mq)
    await db.commit()
