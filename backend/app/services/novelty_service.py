"""
Novelty Validation Service

This service implements the novelty validation pipeline for generated questions:
1. Compute novelty score by comparing against existing questions
2. Enforce novelty threshold from user profile
3. Trigger intelligent regeneration when threshold not met
4. Use reference materials as fallback for regeneration

Novelty Score = 1 - max_similarity
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import uuid

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.services.embedding_service import EmbeddingService
from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass
class NoveltyResult:
    """Result of novelty computation."""
    novelty_score: float
    max_similarity: float
    similarity_source: str  # approved, pending, template, reference
    similarity_breakdown: Dict[str, float]


@dataclass
class RegenerationContext:
    """Context for intelligent regeneration."""
    question_type: str
    difficulty: str
    bloom_level: Optional[str]
    learning_outcome: Optional[str]
    topic_tags: Optional[List[str]]
    original_chunks: List[DocumentChunk]
    reference_chunks: List[DocumentChunk]
    attempt_number: int
    diversity_instructions: str


class NoveltyService:
    """
    Service for novelty validation and intelligent regeneration.
    
    Responsibilities:
    1. Compute novelty scores for generated questions
    2. Compare against approved, pending, template, and reference questions
    3. Provide context for intelligent regeneration
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        auth_db: Optional[AsyncSession] = None,
    ):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()
        self._auth_db = auth_db

    async def compute_novelty(
        self,
        question_text: str,
        question_embedding: List[float],
        user_id: str,
        subject_id: Optional[str] = None,
        exclude_question_ids: Optional[List[str]] = None,
    ) -> NoveltyResult:
        """
        Compute novelty score for a question by comparing against:
        1. Existing approved questions
        2. Pending questions
        3. Template paper questions (from reference documents)
        4. Reference book content
        
        Returns NoveltyResult with detailed breakdown.
        """
        exclude_ids = set(exclude_question_ids or [])
        
        # Get similarity against each source
        approved_sim = await self._compute_max_similarity_against_questions(
            question_embedding=question_embedding,
            user_id=user_id,
            subject_id=subject_id,
            vetting_status="approved",
            exclude_ids=exclude_ids,
        )
        
        pending_sim = await self._compute_max_similarity_against_questions(
            question_embedding=question_embedding,
            user_id=user_id,
            subject_id=subject_id,
            vetting_status="pending",
            exclude_ids=exclude_ids,
        )
        
        template_sim = await self._compute_max_similarity_against_reference(
            question_embedding=question_embedding,
            user_id=user_id,
            subject_id=subject_id,
            index_type="template_paper",
        )
        
        reference_sim = await self._compute_max_similarity_against_reference(
            question_embedding=question_embedding,
            user_id=user_id,
            subject_id=subject_id,
            index_type="reference_book",
        )

        # Find maximum similarity and its source
        similarities = {
            "approved": approved_sim,
            "pending": pending_sim,
            "template": template_sim,
            "reference": reference_sim,
        }
        
        max_similarity = max(similarities.values())
        similarity_source = max(similarities.keys(), key=lambda k: similarities[k])
        
        # Compute novelty score
        novelty_score = 1.0 - max_similarity
        
        return NoveltyResult(
            novelty_score=novelty_score,
            max_similarity=max_similarity,
            similarity_source=similarity_source,
            similarity_breakdown=similarities,
        )

    async def _compute_max_similarity_against_questions(
        self,
        question_embedding: List[float],
        user_id: str,
        subject_id: Optional[str],
        vetting_status: str,
        exclude_ids: set,
    ) -> float:
        """Compute maximum similarity against existing questions."""
        # Build query for existing questions
        query = (
            select(Question)
            .outerjoin(Document, Question.document_id == Document.id)
            .where(
                or_(
                    Document.user_id == user_id,
                    Question.subject_id.isnot(None),  # Include rubric-based questions
                ),
                Question.vetting_status == vetting_status,
                Question.generation_status == "accepted",  # Only compare against accepted questions
                Question.is_archived == False,
            )
        )
        
        if subject_id:
            query = query.where(Question.subject_id == subject_id)
        
        result = await self.db.execute(query)
        existing_questions = result.scalars().all()
        
        if not existing_questions:
            return 0.0
        
        # Compute similarities
        embeddings = []
        for q in existing_questions:
            if q.id not in exclude_ids and q.question_embedding is not None and len(q.question_embedding) > 0:
                embeddings.append(q.question_embedding)
        
        if not embeddings:
            return 0.0
        
        similarities = self.embedding_service.compute_similarity_batch(
            question_embedding, embeddings
        )
        
        return max(similarities) if similarities else 0.0

    async def _compute_max_similarity_against_reference(
        self,
        question_embedding: List[float],
        user_id: str,
        subject_id: Optional[str],
        index_type: str,  # reference_book or template_paper
    ) -> float:
        """Compute maximum similarity against reference document chunks."""
        # Get reference documents
        query = select(Document).where(
            Document.user_id == user_id,
            Document.index_type == index_type,
            Document.processing_status == "completed",
        )
        
        if subject_id:
            query = query.where(Document.subject_id == subject_id)
        
        result = await self.db.execute(query)
        reference_docs = result.scalars().all()
        
        if not reference_docs:
            return 0.0
        
        doc_ids = [doc.id for doc in reference_docs]
        
        # Get chunks from reference documents
        chunk_result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
        )
        chunks = chunk_result.scalars().all()
        
        if not chunks:
            return 0.0
        
        # Compute similarities
        embeddings = [c.chunk_embedding for c in chunks if c.chunk_embedding is not None and len(c.chunk_embedding) > 0]
        
        if not embeddings:
            return 0.0
        
        similarities = self.embedding_service.compute_similarity_batch(
            question_embedding, embeddings
        )
        
        return max(similarities) if similarities else 0.0

    async def _get_user(self, user_id) -> Optional[User]:
        """Get user by ID from auth database."""
        if self._auth_db:
            result = await self._auth_db.execute(
                select(User).where(User.id == str(user_id))
            )
            return result.scalar_one_or_none()
        # Fallback: create a new auth session
        from app.core.auth_database import AuthSessionLocal
        async with AuthSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == str(user_id))
            )
            return result.scalar_one_or_none()

    async def get_user_novelty_settings(
        self,
        user_id,
    ) -> Dict[str, Any]:
        """Get user's novelty settings."""
        user = await self._get_user(user_id)
        if not user:
            return {
                "max_regeneration_attempts": 5,
            }

        preferences = getattr(user, "preferences", {}) or {}

        return {
            "max_regeneration_attempts": preferences.get("max_regeneration_attempts", 5),
        }

    async def prepare_regeneration_context(
        self,
        question_data: Dict[str, Any],
        original_chunks: List[DocumentChunk],
        user_id: str,
        subject_id: Optional[str],
        attempt_number: int,
        use_reference: bool = False,
    ) -> RegenerationContext:
        """
        Prepare context for intelligent regeneration.
        
        Strategy:
        1. First attempts: Use alternative chunks from primary index
        2. Later attempts: Add reference chunks for context variation
        3. Build diversity instructions based on previous failures
        """
        reference_chunks = []
        
        if use_reference and subject_id:
            reference_chunks = await self._get_reference_chunks(
                user_id=user_id,
                subject_id=subject_id,
                focus_topics=question_data.get("topic_tags"),
                num_chunks=3,
            )
        
        # Build diversity instructions based on attempt number
        diversity_instructions = self._build_diversity_instructions(attempt_number, use_reference)
        
        return RegenerationContext(
            question_type=question_data.get("question_type", "mcq"),
            difficulty=question_data.get("difficulty_level", "medium"),
            bloom_level=question_data.get("bloom_taxonomy_level"),
            learning_outcome=question_data.get("learning_outcome_id"),
            topic_tags=question_data.get("topic_tags"),
            original_chunks=original_chunks,
            reference_chunks=reference_chunks,
            attempt_number=attempt_number,
            diversity_instructions=diversity_instructions,
        )

    async def _get_reference_chunks(
        self,
        user_id: str,
        subject_id: str,
        focus_topics: Optional[List[str]],
        num_chunks: int = 3,
    ) -> List[DocumentChunk]:
        """Get reference chunks aligned with the focus topics."""
        # Get reference documents for this subject
        doc_query = select(Document).where(
            Document.user_id == user_id,
            Document.subject_id == subject_id,
            Document.index_type.in_(["reference_book", "template_paper"]),
            Document.processing_status == "completed",
        )
        
        doc_result = await self.db.execute(doc_query)
        reference_docs = doc_result.scalars().all()
        
        if not reference_docs:
            return []
        
        doc_ids = [doc.id for doc in reference_docs]
        
        # Get all chunks from reference documents
        chunk_result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
        )
        all_chunks = chunk_result.scalars().all()
        
        if not all_chunks:
            return []
        
        # If focus topics provided, find relevant chunks
        if focus_topics:
            topic_query = " ".join(focus_topics)
            topic_embedding = await self.embedding_service.get_embedding(topic_query)
            
            # Score chunks by relevance
            scored_chunks = []
            for chunk in all_chunks:
                if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                    similarity = self.embedding_service.compute_similarity(
                        topic_embedding, chunk.chunk_embedding
                    )
                    scored_chunks.append((chunk, similarity))
            
            # Sort by similarity and take top chunks
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            return [c for c, _ in scored_chunks[:num_chunks]]
        else:
            # Random selection
            import random
            return random.sample(all_chunks, min(num_chunks, len(all_chunks)))

    def _build_diversity_instructions(
        self,
        attempt_number: int,
        use_reference: bool,
    ) -> str:
        """Build diversity instructions based on regeneration attempt."""
        base_instruction = "Generate a question that is semantically distinct from previous questions."
        
        instructions = [base_instruction]
        
        if attempt_number >= 2:
            instructions.append("Use different phrasing and problem framing.")
            instructions.append("Focus on a different aspect of the concept.")
        
        if attempt_number >= 3:
            instructions.append("Consider alternative contexts or scenarios.")
            instructions.append("Use different examples or applications.")
        
        if use_reference:
            instructions.append("Use reference materials only for conceptual inspiration.")
            instructions.append("Do NOT copy or paraphrase reference content directly.")
            instructions.append("Create an original question that tests similar concepts differently.")
        
        return "\n- ".join(["DIVERSITY REQUIREMENTS:"] + instructions)

    async def get_reference_documents_for_subject(
        self,
        user_id: str,
        subject_id: str,
    ) -> Dict[str, List[Document]]:
        """Get reference books and template papers for a subject."""
        result = await self.db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.subject_id == subject_id,
                Document.index_type.in_(["reference_book", "template_paper"]),
                Document.processing_status == "completed",
            )
        )
        documents = result.scalars().all()
        
        return {
            "reference_books": [d for d in documents if d.index_type == "reference_book"],
            "template_papers": [d for d in documents if d.index_type == "template_paper"],
        }

    async def validate_and_store_novelty(
        self,
        question: Question,
        novelty_result: NoveltyResult,
        attempt_count: int,
        used_reference: bool,
    ) -> Question:
        """Store novelty validation results on the question."""
        question.novelty_score = novelty_result.novelty_score
        question.max_similarity = novelty_result.max_similarity
        question.similarity_source = novelty_result.similarity_source
        question.generation_attempt_count = attempt_count
        question.used_reference_materials = used_reference
        question.novelty_metadata = novelty_result.similarity_breakdown
        question.generation_status = "accepted"
        
        return question

    async def should_use_reference(
        self,
        attempt_number: int,
        max_attempts: int,
    ) -> bool:
        """
        Determine if reference materials should be used for regeneration.
        
        Strategy:
        - First half of attempts: Use only primary index
        - Second half: Use reference materials as fallback
        """
        threshold_attempt = max(1, max_attempts // 2)
        return attempt_number > threshold_attempt

    async def get_existing_question_embeddings(
        self,
        user_id: str,
        subject_id: Optional[str] = None,
        document_id: Optional[str] = None,
        include_pending: bool = True,
    ) -> List[List[float]]:
        """
        Get embeddings of existing questions for batch deduplication.
        Used during generation to build a blacklist.
        """
        query = (
            select(Question)
            .outerjoin(Document, Question.document_id == Document.id)
            .where(
                or_(
                    Document.user_id == user_id,
                    Question.subject_id.isnot(None),
                ),
                Question.generation_status == "accepted",
                Question.is_archived == False,
            )
        )
        
        if subject_id:
            query = query.where(Question.subject_id == subject_id)
        
        if document_id:
            query = query.where(Question.document_id == document_id)
        
        if not include_pending:
            query = query.where(Question.vetting_status == "approved")
        
        result = await self.db.execute(query)
        questions = result.scalars().all()
        
        embeddings = []
        for q in questions:
            if q.question_embedding is not None and len(q.question_embedding) > 0:
                embeddings.append(q.question_embedding)
        
        return embeddings
