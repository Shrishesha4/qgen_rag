"""
Question Generation Service - Core RAG Pipeline

This service implements:
1. Retrieval of relevant document chunks using vector similarity
2. Blacklisting of previously generated questions to avoid duplicates
3. LLM-based question generation with structured output
4. Quality validation and deduplication
5. Stateful tracking across sessions
"""

import json
from datetime import datetime, timezone
from typing import Optional, List, AsyncGenerator, Dict, Any
import uuid
import asyncio

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentChunk
from app.models.question import Question, GenerationSession
from app.models.subject import Subject
from app.schemas.question import (
    QuestionGenerationRequest,
    QuestionResponse,
    GenerationProgress,
    QuickGenerateProgress,
)
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.redis_service import RedisService
from app.services.document_service import DocumentService
from app.services.reranker_service import RerankerService
from app.core.config import settings


# System prompts for question generation
SYSTEM_PROMPT_MCQ = """You are an expert educator creating examination questions for university students.

CRITICAL RULES:
1. The question MUST be directly answerable from the provided content
2. The correct answer MUST be factually accurate based on the content
3. All 4 options must be plausible but only ONE is correct
4. Do NOT create questions about things not mentioned in the content
5. Do NOT use placeholder letters (A, B, C, D) as answers - use actual values

Output ONLY valid JSON with this exact format:
{
    "question_text": "Clear, specific question based on the content",
    "options": ["A) First option with actual value", "B) Second option with actual value", "C) Third option with actual value", "D) Fourth option with actual value"],
    "correct_answer": "The letter (A, B, C, or D) of the correct option",
    "explanation": "Why this answer is correct, referencing the source content",
    "topic_tags": ["relevant", "topics"]
}

Example for a math topic:
{
    "question_text": "What is the determinant of matrix A = [[3, 1], [2, 4]]?",
    "options": ["A) 10", "B) 14", "C) 7", "D) 5"],
    "correct_answer": "A",
    "explanation": "The determinant of a 2x2 matrix [[a,b],[c,d]] is ad-bc. So (3*4)-(1*2) = 12-2 = 10",
    "topic_tags": ["matrices", "determinants"]
}"""

SYSTEM_PROMPT_SHORT = """You are an expert educator creating examination questions for university students.

CRITICAL RULES:
1. The question MUST be directly answerable from the provided content
2. The expected answer MUST be factually accurate based on the content
3. Questions should require 2-4 sentence responses demonstrating understanding
4. Do NOT create questions about things not mentioned in the content

Output ONLY valid JSON with this exact format:
{
    "question_text": "Clear question requiring a short written response",
    "expected_answer": "Complete model answer in 2-4 sentences based on the content",
    "key_points": ["key point 1", "key point 2", "key point 3"],
    "topic_tags": ["relevant", "topics"]
}"""

SYSTEM_PROMPT_LONG = """You are an expert educator creating examination questions for university students.

CRITICAL RULES:
1. The question MUST be directly answerable from the provided content
2. The expected answer MUST cover key concepts from the content
3. Questions should require detailed responses (1-2 paragraphs)
4. Do NOT create questions about things not mentioned in the content

Output ONLY valid JSON with this exact format:
{
    "question_text": "Comprehensive question requiring detailed analysis",
    "expected_answer": "Detailed model answer outline covering main points",
    "key_points": ["main concept 1", "main concept 2", "main concept 3"],
    "rubric": {
        "Understanding": "Demonstrates clear understanding of concepts",
        "Application": "Correctly applies principles",
        "Analysis": "Shows analytical thinking"
    },
    "topic_tags": ["relevant", "topics"]
}"""

BLOOM_TAXONOMY_VERBS = {
    "remember": ["define", "list", "name", "identify", "recall", "state"],
    "understand": ["explain", "describe", "summarize", "interpret", "classify"],
    "apply": ["apply", "demonstrate", "solve", "use", "implement"],
    "analyze": ["analyze", "compare", "contrast", "examine", "differentiate"],
    "evaluate": ["evaluate", "assess", "justify", "critique", "argue"],
    "create": ["create", "design", "develop", "propose", "construct"],
}


class QuestionGenerationService:
    """Service for RAG-based question generation with deduplication."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
        redis_service: Optional[RedisService] = None,
        document_service: Optional[DocumentService] = None,
        reranker_service: Optional[RerankerService] = None,
    ):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.redis_service = redis_service or RedisService()
        self.document_service = document_service or DocumentService(db, self.embedding_service)
        # Only initialize reranker if enabled
        if settings.RERANKER_ENABLED:
            self.reranker_service = reranker_service or RerankerService()
        else:
            self.reranker_service = None

    async def generate_questions(
        self,
        user_id: uuid.UUID,
        request: QuestionGenerationRequest,
    ) -> AsyncGenerator[GenerationProgress, None]:
        """
        Generate questions with streaming progress updates.
        Implements the full RAG pipeline with blacklisting.
        """
        document_id = request.document_id

        # 1. Verify document ownership
        document = await self._get_document(document_id, user_id)
        if not document:
            yield GenerationProgress(
                status="error",
                progress=0,
                message="Document not found or access denied",
            )
            return

        if document.processing_status != "completed":
            yield GenerationProgress(
                status="error",
                progress=0,
                message="Document is still processing",
            )
            return

        # 2. Acquire generation lock
        lock_acquired = await self.redis_service.acquire_generation_lock(
            str(user_id), str(document_id)
        )
        if not lock_acquired:
            yield GenerationProgress(
                status="error",
                progress=0,
                message="Another generation is in progress for this document",
            )
            return

        try:
            yield GenerationProgress(
                status="processing",
                progress=5,
                message="Initializing generation session...",
            )

            # 3. Create generation session
            session = await self._create_session(user_id, request)
            
            yield GenerationProgress(
                status="processing",
                progress=10,
                message="Building question blacklist...",
            )

            # 4. Build blacklist from existing questions
            blacklist = await self._build_blacklist(document_id, user_id, request.exclude_question_ids)
            session.blacklist_size = len(blacklist)

            yield GenerationProgress(
                status="processing",
                progress=15,
                message=f"Found {len(blacklist)} existing questions to avoid...",
            )

            # 5. Get document chunks
            chunks = await self._get_chunks(document_id)
            if not chunks:
                yield GenerationProgress(
                    status="error",
                    progress=15,
                    message="No document chunks found",
                )
                return

            session.chunks_used = len(chunks)

            yield GenerationProgress(
                status="generating",
                progress=20,
                message=f"Generating {request.count} questions from {len(chunks)} chunks...",
                total_questions=request.count,
            )

            # 6. Generate questions
            questions_generated = 0
            questions_failed = 0
            questions_duplicate = 0
            
            # Distribute question types
            type_distribution = self._distribute_types(request.count, request.types)
            
            for q_type, count in type_distribution.items():
                for i in range(count):
                    try:
                        # Select relevant chunks for this question
                        selected_chunks = await self._select_chunks(
                            chunks=chunks,
                            focus_topics=request.focus_topics,
                            blacklist_chunks=blacklist.get("chunks", set()),
                            num_chunks=3,
                            document_id=document_id,
                        )

                        # Generate question
                        question_data = await self._generate_single_question(
                            chunks=selected_chunks,
                            question_type=q_type,
                            difficulty=request.difficulty,
                            marks=request.marks,
                            bloom_levels=request.bloom_levels,
                        )

                        if not question_data:
                            questions_failed += 1
                            continue

                        # Check for duplicates using semantic similarity
                        is_duplicate = await self._check_duplicate(
                            question_text=question_data["question_text"],
                            blacklist_embeddings=blacklist.get("embeddings", []),
                            threshold=0.85,
                        )

                        if is_duplicate:
                            questions_duplicate += 1
                            continue

                        # Save question to database (includes validation)
                        question, question_response = await self._save_question(
                            document_id=document_id,
                            session_id=session.id,
                            question_data=question_data,
                            question_type=q_type,
                            marks=request.marks,
                            difficulty=request.difficulty,
                            chunk_ids=[c.id for c in selected_chunks],
                            chunks=selected_chunks,
                        )
                        
                        questions_generated += 1

                        # Update blacklist with new question
                        blacklist["embeddings"].append(question.question_embedding)

                        # Calculate progress
                        total_attempted = questions_generated + questions_failed + questions_duplicate
                        progress = 20 + int((total_attempted / request.count) * 75)

                        yield GenerationProgress(
                            status="generating",
                            progress=min(progress, 95),
                            current_question=questions_generated,
                            total_questions=request.count,
                            question=question_response,
                            message=f"Generated question {questions_generated}/{request.count}",
                        )

                    except Exception as e:
                        questions_failed += 1
                        # Continue with next question on error

            # 7. Complete session
            session.questions_generated = questions_generated
            session.questions_failed = questions_failed
            session.questions_duplicate = questions_duplicate
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            session.total_duration_seconds = (
                session.completed_at - session.started_at
            ).total_seconds()
            
            await self.db.commit()

            yield GenerationProgress(
                status="complete",
                progress=100,
                current_question=questions_generated,
                total_questions=request.count,
                message=f"Generated {questions_generated} questions ({questions_duplicate} duplicates avoided)",
            )

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            await self.db.commit()
            
            yield GenerationProgress(
                status="error",
                progress=0,
                message=f"Generation failed: {str(e)}",
            )

        finally:
            # Release lock
            await self.redis_service.release_generation_lock(
                str(user_id), str(document_id)
            )

    async def _get_document(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[Document]:
        """Get document with user ownership verification."""
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _create_session(
        self,
        user_id: uuid.UUID,
        request: QuestionGenerationRequest,
    ) -> GenerationSession:
        """Create a new generation session."""
        session = GenerationSession(
            document_id=request.document_id,
            user_id=user_id,
            requested_count=request.count,
            requested_types=request.types,
            requested_marks=request.marks,
            requested_difficulty=request.difficulty,
            focus_topics=request.focus_topics,
            status="in_progress",
            generation_config={
                "bloom_levels": request.bloom_levels,
                "exclude_ids": [str(id) for id in (request.exclude_question_ids or [])],
            },
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def _build_blacklist(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        exclude_ids: Optional[List[uuid.UUID]] = None,
    ) -> Dict[str, Any]:
        """
        Build blacklist of existing questions for deduplication.
        Includes questions from all sessions for this document.
        """
        # Get all existing questions for this document
        query = select(Question).where(
            Question.document_id == document_id,
            Question.is_archived == False,
        )
        result = await self.db.execute(query)
        existing_questions = result.scalars().all()

        blacklist = {
            "question_ids": set(),
            "embeddings": [],
            "texts": set(),
            "chunks": set(),
        }

        for q in existing_questions:
            blacklist["question_ids"].add(q.id)
            blacklist["texts"].add(q.question_text.lower().strip())
            
            # Check embedding exists (handle numpy array truth value issue)
            if q.question_embedding is not None and len(q.question_embedding) > 0:
                blacklist["embeddings"].append(q.question_embedding)
            
            if q.source_chunk_ids:
                blacklist["chunks"].update(q.source_chunk_ids)

        # Add manually excluded IDs
        if exclude_ids:
            blacklist["question_ids"].update(exclude_ids)

        return blacklist

    async def _get_chunks(self, document_id: uuid.UUID) -> List[DocumentChunk]:
        """Get all chunks for a document."""
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return result.scalars().all()

    async def _select_chunks(
        self,
        chunks: List[DocumentChunk],
        focus_topics: Optional[List[str]],
        blacklist_chunks: set,
        num_chunks: int = 3,
        document_id: Optional[uuid.UUID] = None,
    ) -> List[DocumentChunk]:
        """
        Select relevant chunks for question generation using hybrid search.
        Prioritizes chunks not heavily used in previous questions.
        """
        import random

        # Filter out heavily used chunks
        available_chunks = [c for c in chunks if c.id not in blacklist_chunks]
        
        if not available_chunks:
            # Fall back to all chunks if all are used
            available_chunks = chunks

        if focus_topics:
            # If focus topics provided, use hybrid search
            topic_query = " ".join(focus_topics)
            topic_embedding = await self.embedding_service.get_embedding(topic_query)
            
            # Use hybrid search if document_id is available
            if document_id and self.document_service:
                # Get more candidates for reranking
                candidates = await self.document_service.hybrid_search(
                    document_id=document_id,
                    query=topic_query,
                    query_embedding=topic_embedding,
                    top_k=num_chunks * 3,  # Get more for filtering and reranking
                    alpha=0.6,  # Slightly favor semantic search
                )
                # Filter out blacklisted chunks
                candidates = [c for c in candidates if c.id not in blacklist_chunks]
                
                # Rerank using cross-encoder if available
                if self.reranker_service and len(candidates) > num_chunks:
                    selected = self.reranker_service.rerank(
                        query=topic_query,
                        chunks=candidates,
                        top_k=num_chunks,
                    )
                else:
                    selected = candidates[:num_chunks]
                
                return selected
            
            # Fallback: Score chunks by relevance using only vector similarity
            scored_chunks = []
            for chunk in available_chunks:
                if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                    similarity = self.embedding_service.compute_similarity(
                        topic_embedding, chunk.chunk_embedding
                    )
                    scored_chunks.append((chunk, similarity))
            
            # Sort by similarity and take top chunks
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            candidates = [c for c, _ in scored_chunks[:num_chunks * 2]]
            
            # Rerank using cross-encoder if available
            if self.reranker_service and len(candidates) > num_chunks:
                selected = self.reranker_service.rerank(
                    query=topic_query,
                    chunks=candidates,
                    top_k=num_chunks,
                )
            else:
                selected = candidates[:num_chunks]
        else:
            # Random selection with some diversity
            selected = random.sample(
                available_chunks,
                min(num_chunks, len(available_chunks))
            )

        return selected

    async def _expand_query(
        self,
        context: str,
        num_variations: int = 3,
    ) -> List[str]:
        """
        Generate query variations using LLM for better retrieval coverage.
        
        This helps find relevant chunks that might use different terminology
        or phrasing than the original query.
        """
        prompt = f"""Given this topic/context: "{context}"

Generate {num_variations} alternative search queries that would help find relevant educational content about this topic.
Each query should use different terminology or focus on different aspects of the topic.

Output as a JSON array of strings: ["query1", "query2", "query3"]

Output JSON only, no explanation."""

        try:
            response = await self.llm_service.generate_json(
                prompt=prompt,
                temperature=0.7,
            )
            
            if isinstance(response, list):
                # Ensure all items are strings
                queries = [str(q) for q in response if q][:num_variations]
            else:
                queries = []
            
            # Always include the original context as the first query
            return [context] + queries
            
        except Exception:
            # On any error, just return the original context
            return [context]

    async def _select_chunks_with_expansion(
        self,
        chunks: List[DocumentChunk],
        context: str,
        blacklist_chunks: set,
        num_chunks: int = 3,
        document_id: Optional[uuid.UUID] = None,
        expand_queries: bool = True,
    ) -> List[DocumentChunk]:
        """
        Select chunks using query expansion for better coverage.
        
        This generates multiple query variations and combines results
        for more comprehensive chunk selection.
        """
        from collections import defaultdict
        
        # Filter out heavily used chunks
        available_chunks = [c for c in chunks if c.id not in blacklist_chunks]
        
        if not available_chunks:
            available_chunks = chunks
        
        # Get query variations
        if expand_queries:
            queries = await self._expand_query(context, num_variations=2)
        else:
            queries = [context]
        
        # Score each chunk across all queries (take max score for each chunk)
        chunk_scores = defaultdict(float)
        
        for query in queries:
            query_embedding = await self.embedding_service.get_embedding(query)
            
            # Use hybrid search if available
            if document_id and self.document_service:
                candidates = await self.document_service.hybrid_search(
                    document_id=document_id,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=num_chunks * 2,
                    alpha=0.6,
                )
                # Filter and score by rank
                for rank, chunk in enumerate(candidates):
                    if chunk.id not in blacklist_chunks:
                        # Higher rank = lower score index, invert for max
                        score = 1.0 / (rank + 1)
                        chunk_scores[chunk.id] = max(chunk_scores[chunk.id], score)
            else:
                # Fallback to embedding similarity
                for chunk in available_chunks:
                    # Check embedding exists (handle numpy array truth value issue)
                    if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                        sim = self.embedding_service.compute_similarity(
                            query_embedding, chunk.chunk_embedding
                        )
                        chunk_scores[chunk.id] = max(chunk_scores[chunk.id], sim)
        
        # Sort chunks by combined score
        chunk_map = {c.id: c for c in available_chunks}
        sorted_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)
        candidates = [chunk_map[cid] for cid in sorted_ids if cid in chunk_map]
        
        # Rerank if available
        if self.reranker_service and len(candidates) > num_chunks:
            return self.reranker_service.rerank(
                query=context,  # Use original context for reranking
                chunks=candidates,
                top_k=num_chunks,
            )
        
        return candidates[:num_chunks]

    async def _generate_single_question(
        self,
        chunks: List[DocumentChunk],
        question_type: str,
        difficulty: str,
        marks: Optional[int],
        bloom_levels: Optional[List[str]],
    ) -> Optional[Dict[str, Any]]:
        """Generate a single question using LLM."""
        # Build context from chunks
        context = "\n\n---\n\n".join([c.chunk_text for c in chunks])
        
        # Select system prompt based on type
        if question_type == "mcq":
            system_prompt = SYSTEM_PROMPT_MCQ
        elif question_type == "short_answer":
            system_prompt = SYSTEM_PROMPT_SHORT
        else:
            system_prompt = SYSTEM_PROMPT_LONG

        # Select Bloom's level
        bloom_level = None
        if bloom_levels:
            import random
            bloom_level = random.choice(bloom_levels)
        else:
            # Default based on question type
            bloom_defaults = {
                "mcq": "understand",
                "short_answer": "apply",
                "long_answer": "analyze",
            }
            bloom_level = bloom_defaults.get(question_type, "understand")

        # Build prompt
        prompt = f"""Context from the document:
{context}

Generate a {question_type.replace('_', ' ')} question with the following requirements:
- Difficulty: {difficulty}
- Bloom's Taxonomy Level: {bloom_level}
- Marks: {marks or 'appropriate for the question type'}

The question should be based directly on the provided context.
Ensure the question is clear, specific, and examines understanding of the material.

Output valid JSON only."""

        try:
            response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            
            response["bloom_taxonomy_level"] = bloom_level
            return response
            
        except Exception as e:
            return None

    async def _check_duplicate(
        self,
        question_text: str,
        blacklist_embeddings: List[List[float]],
        threshold: float = 0.85,
    ) -> bool:
        """Check if question is semantically similar to existing questions."""
        if not blacklist_embeddings:
            return False

        # Get embedding for new question
        new_embedding = await self.embedding_service.get_embedding(question_text)
        
        # Check similarity against all blacklisted embeddings
        similarities = self.embedding_service.compute_similarity_batch(
            new_embedding, blacklist_embeddings
        )
        
        # If any similarity is above threshold, it's a duplicate
        return any(s > threshold for s in similarities)

    async def _validate_question_quality(
        self,
        question_data: Dict[str, Any],
        question_type: str,
        chunks: List[DocumentChunk],
    ) -> tuple[bool, str, float]:
        """
        Validate the quality of a generated question.
        
        Returns:
            Tuple of (is_valid, reason, confidence_score)
        """
        import re
        
        q_text = question_data.get("question_text", "")
        
        # Basic length checks
        if len(q_text) < 15:
            return False, "Question too short", 0.0
        if len(q_text) > 1000:
            return False, "Question too long", 0.0
        
        # Check question has interrogative structure
        question_patterns = [
            r'\?$',  # Ends with question mark
            r'^(what|which|who|whom|whose|when|where|why|how|is|are|was|were|do|does|did|can|could|will|would|should|shall)\s',
            r'^(explain|describe|define|compare|contrast|analyze|evaluate|discuss|identify|list|name|state)\s',
            # Math/engineering imperative patterns (common in exam questions)
            r'^(find|calculate|determine|solve|compute|derive|prove|show|simplify|verify|express|convert|obtain)\s',
            r'^(given|consider|let|suppose|assume|if)\s',  # Conditional/setup patterns
            r'(find|calculate|determine|solve|compute)\s+(the|a|an)\s',  # Mid-sentence imperatives
        ]
        has_question_structure = any(
            re.search(pattern, q_text, re.IGNORECASE) for pattern in question_patterns
        )
        if not has_question_structure:
            return False, "Question lacks proper interrogative structure", 0.3
        
        # Combine chunk text for grounding check
        chunk_text = " ".join([c.chunk_text.lower() for c in chunks])
        chunk_words = set(chunk_text.split())
        
        # Remove common stop words from question for meaningful overlap check
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                      'should', 'may', 'might', 'must', 'shall', 'can', 'of', 'in', 'to',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                      'and', 'or', 'but', 'if', 'then', 'else', 'when', 'up', 'out',
                      'what', 'which', 'who', 'how', 'why', 'where', 'this', 'that',
                      'these', 'those', 'it', 'its'}
        
        q_words = set(w.lower().strip('.,?!;:') for w in q_text.split() if len(w) > 2)
        q_meaningful_words = q_words - stop_words
        
        if q_meaningful_words:
            overlap = len(q_meaningful_words & chunk_words) / len(q_meaningful_words)
            if overlap < 0.2:
                return False, "Question may not be grounded in the source content", 0.4
        
        # MCQ-specific validation
        if question_type == "mcq":
            options = question_data.get("options", [])
            correct_answer = question_data.get("correct_answer", "")
            
            if not options:
                return False, "MCQ missing options", 0.0
            if len(options) < 3:
                return False, f"MCQ has only {len(options)} options, needs at least 3", 0.3
            if len(options) > 6:
                return False, "MCQ has too many options", 0.5
            
            # Check for unique options
            option_texts = [self._extract_option_text(opt) for opt in options]
            if len(set(option_texts)) != len(option_texts):
                return False, "MCQ options are not unique", 0.3
            
            # Check correct answer is provided
            if not correct_answer:
                return False, "MCQ missing correct answer", 0.0
            
            # Check options are not too similar
            if await self._check_options_too_similar(options):
                return False, "MCQ options are too similar to each other", 0.4
        
        # Short answer validation
        elif question_type == "short_answer":
            expected_answer = question_data.get("expected_answer") or question_data.get("correct_answer")
            if not expected_answer:
                return False, "Short answer missing expected answer", 0.0
            if len(str(expected_answer)) < 10:
                return False, "Expected answer too brief", 0.5
        
        # Long answer validation
        elif question_type == "long_answer":
            key_points = question_data.get("key_points", [])
            if not key_points or len(key_points) < 2:
                return False, "Long answer should have at least 2 key points", 0.5
        
        # Calculate confidence score based on various factors
        confidence = 0.7  # Base confidence
        
        # Boost for good grounding
        if q_meaningful_words:
            overlap = len(q_meaningful_words & chunk_words) / len(q_meaningful_words)
            confidence += min(overlap * 0.2, 0.15)
        
        # Boost for having proper structure
        if has_question_structure:
            confidence += 0.1
        
        # Cap at 0.95
        confidence = min(confidence, 0.95)
        
        return True, "Valid", confidence

    def _extract_option_text(self, option: str) -> str:
        """Extract the text portion of an option, removing the label."""
        import re
        # Remove labels like "A)", "1.", "a." etc.
        cleaned = re.sub(r'^[A-Za-z0-9][).:\s]+', '', str(option).strip())
        return cleaned.lower().strip()

    async def _check_options_too_similar(
        self,
        options: List[str],
        similarity_threshold: float = 0.9,
    ) -> bool:
        """Check if any options are too similar to each other."""
        if len(options) < 2:
            return False
        
        option_texts = [self._extract_option_text(opt) for opt in options]
        embeddings = await self.embedding_service.get_embeddings(option_texts)
        
        # Check pairwise similarities
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarity = self.embedding_service.compute_similarity(
                    embeddings[i], embeddings[j]
                )
                if similarity > similarity_threshold:
                    return True
        
        return False

    async def _save_question(
        self,
        document_id: uuid.UUID,
        session_id: uuid.UUID,
        question_data: Dict[str, Any],
        question_type: str,
        marks: Optional[int],
        difficulty: str,
        chunk_ids: List[uuid.UUID],
        chunks: Optional[List[DocumentChunk]] = None,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
    ) -> tuple[Question, QuestionResponse]:
        """
        Save generated question to database after validation.
        
        Returns both the ORM object (for embedding access) and the 
        QuestionResponse (for SSE serialization without lazy loading issues).
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Validate question quality if chunks provided
        confidence_score = 0.8  # Default confidence
        if chunks:
            is_valid, reason, confidence_score = await self._validate_question_quality(
                question_data, question_type, chunks
            )
            if not is_valid:
                logger.warning(f"Question validation failed: {reason}")
                raise ValueError(f"Question validation failed: {reason}")
        
        # Generate embedding for the question
        question_embedding = await self.embedding_service.get_embedding(
            question_data["question_text"]
        )
        
        # Normalize options - LLM may return different formats
        raw_options = question_data.get("options")
        normalized_options = None
        if raw_options:
            normalized_options = self._normalize_options(raw_options)
        
        # Normalize correct answer
        correct_answer = question_data.get("correct_answer") or question_data.get("expected_answer") or question_data.get("answer")
        if isinstance(correct_answer, dict):
            correct_answer = correct_answer.get("option") or correct_answer.get("value") or str(correct_answer)

        question = Question(
            document_id=document_id,
            session_id=session_id,
            subject_id=subject_id,
            topic_id=topic_id,
            question_text=question_data["question_text"],
            question_embedding=question_embedding,
            question_type=question_type,
            marks=marks,
            difficulty_level=difficulty,
            bloom_taxonomy_level=question_data.get("bloom_taxonomy_level"),
            correct_answer=str(correct_answer) if correct_answer else None,
            options=normalized_options,
            topic_tags=question_data.get("topic_tags"),
            source_chunk_ids=chunk_ids,
            generation_confidence=confidence_score,  # Calculated from validation
            generation_metadata={
                "raw_response": question_data,
            },
        )
        
        self.db.add(question)
        await self.db.commit()
        await self.db.refresh(question)
        
        # Convert to QuestionResponse immediately while in async context
        # This avoids SQLAlchemy lazy-loading issues when serializing later
        question_response = QuestionResponse(
            id=question.id,
            document_id=question.document_id,
            subject_id=question.subject_id,
            topic_id=question.topic_id,
            session_id=question.session_id,
            question_text=question.question_text,
            question_type=question.question_type,
            marks=question.marks,
            difficulty_level=question.difficulty_level,
            bloom_taxonomy_level=question.bloom_taxonomy_level,
            options=question.options,
            correct_answer=question.correct_answer,
            topic_tags=question.topic_tags,
            source_chunk_ids=question.source_chunk_ids,
            course_outcome_mapping=question.course_outcome_mapping,
            learning_outcome_id=question.learning_outcome_id,
            vetting_status=question.vetting_status,
            vetted_at=question.vetted_at,
            vetting_notes=question.vetting_notes,
            answerability_score=question.answerability_score,
            specificity_score=question.specificity_score,
            generation_confidence=question.generation_confidence,
            generated_at=question.generated_at,
            times_shown=question.times_shown,
            user_rating=question.user_rating,
            is_archived=question.is_archived,
        )
        
        return question, question_response
    
    def _normalize_options(self, options: List[Any]) -> List[str]:
        """Normalize options to list of strings in format 'A) text'."""
        if not options:
            return []
        
        normalized = []
        labels = ['A', 'B', 'C', 'D', 'E', 'F']
        
        for i, opt in enumerate(options):
            label = labels[i] if i < len(labels) else str(i + 1)
            
            if isinstance(opt, str):
                # Already a string - check if it has a label prefix
                if opt.strip() and opt[0].isalpha() and len(opt) > 1 and opt[1] in ').:':
                    normalized.append(opt)
                else:
                    normalized.append(f"{label}) {opt}")
            elif isinstance(opt, dict):
                # Handle dict format: {"option": "value", "description": "text"}
                text = opt.get("description") or opt.get("text") or opt.get("option") or opt.get("value") or str(opt)
                option_val = opt.get("option") or opt.get("value")
                if option_val and text != option_val:
                    normalized.append(f"{label}) {option_val} - {text}")
                else:
                    normalized.append(f"{label}) {text}")
            else:
                normalized.append(f"{label}) {str(opt)}")
        
        return normalized

    def _distribute_types(
        self,
        total_count: int,
        types: Optional[List[str]],
    ) -> Dict[str, int]:
        """Distribute question count across types."""
        if not types:
            types = ["mcq", "short_answer"]
        
        per_type = total_count // len(types)
        remainder = total_count % len(types)
        
        distribution = {}
        for i, q_type in enumerate(types):
            distribution[q_type] = per_type + (1 if i < remainder else 0)
        
        return distribution

    async def get_questions(
        self,
        user_id: uuid.UUID,
        document_id: Optional[uuid.UUID] = None,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        vetting_status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        question_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        show_archived: bool = False,
    ) -> tuple[List[Question], Dict[str, Any]]:
        """Get questions with pagination and flexible filtering."""
        # Build base query - support both document-based and rubric-based questions
        # Questions can be owned via Document OR via Subject
        query = (
            select(Question)
            .outerjoin(Document, Question.document_id == Document.id)
            .outerjoin(Subject, Question.subject_id == Subject.id)
            .where(
                or_(
                    Document.user_id == user_id,  # Document-based questions
                    Subject.user_id == user_id,   # Rubric-based questions
                )
            )
        )
        
        # Filter archived questions unless explicitly requested
        if not show_archived:
            query = query.where(Question.is_archived == False)
        else:
            # If show_archived is True, only show archived questions
            query = query.where(Question.is_archived == True)

        # Apply optional filters
        if document_id:
            query = query.where(Question.document_id == document_id)
        if subject_id:
            query = query.where(Question.subject_id == subject_id)
        if topic_id:
            query = query.where(Question.topic_id == topic_id)
        if vetting_status:
            query = query.where(Question.vetting_status == vetting_status)
        if question_type:
            query = query.where(Question.question_type == question_type)
        if difficulty:
            query = query.where(Question.difficulty_level == difficulty)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Question.generated_at.desc())
        
        result = await self.db.execute(query)
        questions = result.scalars().all()

        pagination = {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }

        return questions, pagination

    async def rate_question(
        self,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
        rating: int,
        difficulty_rating: Optional[str] = None,
    ) -> Question:
        """Rate a question."""
        # Get question and verify ownership through document
        result = await self.db.execute(
            select(Question)
            .join(Document)
            .where(
                Question.id == question_id,
                Document.user_id == user_id,
            )
        )
        question = result.scalar_one_or_none()
        
        if not question:
            raise ValueError("Question not found")

        question.user_rating = rating
        question.user_difficulty_rating = difficulty_rating
        question.times_shown += 1
        question.last_shown_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(question)
        
        return question

    async def archive_question(
        self,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Archive a question."""
        result = await self.db.execute(
            select(Question)
            .join(Document)
            .where(
                Question.id == question_id,
                Document.user_id == user_id,
            )
        )
        question = result.scalar_one_or_none()
        
        if not question:
            return False

        question.is_archived = True
        await self.db.commit()
        return True
    
    async def unarchive_question(
        self,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Unarchive a question (restore it)."""
        from sqlalchemy import or_
        # Get question and verify ownership through document or subject
        result = await self.db.execute(
            select(Question)
            .outerjoin(Document, Question.document_id == Document.id)
            .outerjoin(Subject, Question.subject_id == Subject.id)
            .where(
                Question.id == question_id,
                or_(
                    Document.user_id == user_id,
                    Subject.user_id == user_id,
                ),
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            return False
        
        question.is_archived = False
        await self.db.commit()
        return True

    async def get_generation_sessions(
        self,
        user_id: uuid.UUID,
        document_id: Optional[uuid.UUID] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[GenerationSession], Dict[str, Any]]:
        """Get generation sessions for a user."""
        query = select(GenerationSession).where(GenerationSession.user_id == user_id)
        
        if document_id:
            query = query.where(GenerationSession.document_id == document_id)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(GenerationSession.started_at.desc())
        
        result = await self.db.execute(query)
        sessions = result.scalars().all()

        pagination = {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }

        return sessions, pagination

    async def quick_generate(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        context: str,
        count: int = 5,
        types: Optional[List[str]] = None,
        difficulty: str = "medium",
        bloom_levels: Optional[List[str]] = None,
        use_query_expansion: bool = False,
        marks_by_type: Optional[dict] = None,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
    ) -> AsyncGenerator[QuickGenerateProgress, None]:
        """
        Generate questions from an already-processed document with minimal configuration.
        This is the simplified RAG pipeline for quick generation.
        
        Args:
            user_id: User ID
            document_id: Document ID (using ID instead of object to avoid SQLAlchemy session issues)
            context: Context/title provided by user (e.g., "Chapter 5: Data Structures")
            count: Number of questions to generate
            types: Question types to generate
            difficulty: Difficulty level
            bloom_levels: Target Bloom's taxonomy levels
            marks_by_type: Dict mapping question type to marks (e.g., {"mcq": 1, "short_answer": 2, "long_answer": 5})
            subject_id: Subject ID to link questions to
            topic_id: Topic/Chapter ID to link questions to
        """
        if types is None:
            types = ["mcq", "short_answer"]
        
        # Default marks by type if not provided
        if marks_by_type is None:
            marks_by_type = {"mcq": 1, "short_answer": 2, "long_answer": 5}

        # 1. Acquire generation lock
        lock_acquired = await self.redis_service.acquire_generation_lock(
            str(user_id), str(document_id)
        )
        if not lock_acquired:
            yield QuickGenerateProgress(
                status="error",
                progress=0,
                message="Another generation is in progress",
            )
            return

        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"quick_generate: Starting for user {user_id}, context: {context}, count: {count}, types: {types}")
            
            yield QuickGenerateProgress(
                status="generating",
                progress=10,
                message="Preparing content for question generation...",
                document_id=document_id,
            )

            # 2. Get document chunks
            chunks = await self._get_chunks(document_id)
            logger.info(f"quick_generate: Got {len(chunks) if chunks else 0} chunks")
            if not chunks:
                yield QuickGenerateProgress(
                    status="error",
                    progress=10,
                    message="No document content found for generation",
                    document_id=document_id,
                )
                return

            yield QuickGenerateProgress(
                status="generating",
                progress=20,
                message=f"Generating {count} questions from {len(chunks)} content sections...",
                total_questions=count,
                document_id=document_id,
            )

            # 3. Create a simple session for tracking
            session = GenerationSession(
                document_id=document_id,
                user_id=user_id,
                requested_count=count,
                requested_types=types,
                requested_difficulty=difficulty,
                focus_topics=[context],  # Use context as focus topic
                status="in_progress",
                generation_config={
                    "mode": "quick_generate",
                    "context": context,
                    "bloom_levels": bloom_levels,
                },
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            
            # Extract session_id immediately to avoid SQLAlchemy lazy-loading issues after rollback
            session_id = session.id

            # 4. Generate questions
            questions_generated = 0
            questions_failed = 0
            generated_embeddings = []  # Track embeddings for deduplication within session
            
            # Distribute question types
            type_distribution = self._distribute_types(count, types)
            logger.info(f"Type distribution: {type_distribution}")
            
            for q_type, type_count in type_distribution.items():
                logger.info(f"Generating {type_count} questions of type {q_type}")
                for i in range(type_count):
                    try:
                        logger.info(f"Starting generation {i+1}/{type_count} for {q_type}")
                        
                        # Select relevant chunks using hybrid search (semantic + BM25)
                        context_embedding = await self.embedding_service.get_embedding(context)
                        
                        # Use hybrid search for better chunk selection - get more for reranking
                        candidates = await self.document_service.hybrid_search(
                            document_id=document_id,
                            query=context,
                            query_embedding=context_embedding,
                            top_k=6,  # Get more candidates for reranking
                            alpha=0.6,  # Slightly favor semantic search
                        )
                        
                        # Rerank using cross-encoder if available
                        if self.reranker_service and len(candidates) > 3:
                            selected_chunks = self.reranker_service.rerank(
                                query=context,
                                chunks=candidates,
                                top_k=3,
                            )
                        else:
                            selected_chunks = candidates[:3]
                        
                        logger.info(f"Hybrid search returned {len(selected_chunks)} chunks")
                        
                        if not selected_chunks:
                            logger.warning("No chunks from hybrid search, falling back to random selection")
                            import random
                            selected_chunks = random.sample(chunks, min(3, len(chunks)))

                        logger.info(f"Selected {len(selected_chunks)} chunks for generation")

                        # Generate question with context-aware prompt
                        question_data = await self._generate_quick_question(
                            chunks=selected_chunks,
                            question_type=q_type,
                            difficulty=difficulty,
                            context=context,
                            bloom_levels=bloom_levels,
                        )

                        if not question_data:
                            logger.warning(f"Question generation returned None for {q_type}")
                            questions_failed += 1
                            continue
                        
                        q_text = question_data.get('question_text', '')
                        logger.info(f"Question generated: {q_text[:100] if q_text else 'empty'}")

                        # Check for duplicates within this session
                        if generated_embeddings:
                            new_embedding = await self.embedding_service.get_embedding(
                                question_data["question_text"]
                            )
                            similarities = self.embedding_service.compute_similarity_batch(
                                new_embedding, generated_embeddings
                            )
                            if any(s > 0.85 for s in similarities):
                                logger.warning("Question rejected as duplicate")
                                questions_failed += 1
                                continue

                        # Save question to database (includes validation)
                        try:
                            # Get marks for this question type
                            type_marks = marks_by_type.get(q_type, 1)
                            
                            question, question_response = await self._save_question(
                                document_id=document_id,
                                session_id=session_id,
                                question_data=question_data,
                                question_type=q_type,
                                marks=type_marks,
                                difficulty=difficulty,
                                chunk_ids=[c.id for c in selected_chunks],
                                chunks=selected_chunks,
                                subject_id=subject_id,
                                topic_id=topic_id,
                            )
                            
                            questions_generated += 1
                            generated_embeddings.append(question.question_embedding)
                            logger.info(f"Successfully saved question {question.id} with vetting_status: {question.vetting_status}")

                            # Calculate progress
                            total_attempted = questions_generated + questions_failed
                            progress = 20 + int((total_attempted / count) * 75)

                            yield QuickGenerateProgress(
                                status="generating",
                                progress=min(progress, 95),
                                current_question=questions_generated,
                                total_questions=count,
                                question=question_response,
                                message=f"Generated question {questions_generated}/{count}",
                                document_id=document_id,
                            )
                        except Exception as save_error:
                            # Rollback this transaction and continue
                            await self.db.rollback()
                            logger.exception(f"Failed to save question: {save_error}")
                            questions_failed += 1
                            continue

                    except Exception as e:
                        logger.exception(f"Exception during question generation: {e}")
                        questions_failed += 1
                        # Continue with next question on error

            # 5. Backfill: try to generate more if we didn't reach the target
            backfill_attempts = 0
            max_backfill = min(questions_failed, 3)  # Try up to 3 backfill attempts
            
            while questions_generated < count and backfill_attempts < max_backfill:
                backfill_attempts += 1
                logger.info(f"Backfill attempt {backfill_attempts}: need {count - questions_generated} more questions")
                
                # Pick a random type to backfill with
                import random
                q_type = random.choice(types)
                
                try:
                    # Use hybrid search with modified context for variety
                    modified_context = f"{context} variation {backfill_attempts}"
                    context_embedding = await self.embedding_service.get_embedding(modified_context)
                    
                    # Get more chunks and offset for variety
                    all_chunks = await self.document_service.hybrid_search(
                        document_id=document_id,
                        query=modified_context,
                        query_embedding=context_embedding,
                        top_k=6,
                        alpha=0.5,  # Balance semantic and keyword search
                    )
                    
                    # Use different chunks for variety by offsetting
                    offset = backfill_attempts * 2
                    selected_chunks = all_chunks[offset:offset+3] if len(all_chunks) > offset else all_chunks[:3]
                    
                    if not selected_chunks:
                        selected_chunks = random.sample(chunks, min(3, len(chunks)))
                    
                    question_data = await self._generate_quick_question(
                        chunks=selected_chunks,
                        question_type=q_type,
                        difficulty=difficulty,
                        context=context,
                        bloom_levels=bloom_levels,
                    )
                    
                    if question_data:
                        # Check for duplicates
                        is_duplicate = False
                        if generated_embeddings:
                            new_embedding = await self.embedding_service.get_embedding(
                                question_data["question_text"]
                            )
                            similarities = self.embedding_service.compute_similarity_batch(
                                new_embedding, generated_embeddings
                            )
                            is_duplicate = any(s > 0.85 for s in similarities)
                        
                        if not is_duplicate:
                            try:
                                question, question_response = await self._save_question(
                                    document_id=document_id,
                                    session_id=session_id,
                                    question_data=question_data,
                                    question_type=q_type,
                                    marks=None,
                                    difficulty=difficulty,
                                    chunk_ids=[c.id for c in selected_chunks],
                                    chunks=selected_chunks,
                                )
                                questions_generated += 1
                                generated_embeddings.append(question.question_embedding)
                                logger.info(f"Backfill successful: {questions_generated}/{count} questions")
                                
                                yield QuickGenerateProgress(
                                    status="generating",
                                    progress=min(95, 20 + int((questions_generated / count) * 75)),
                                    current_question=questions_generated,
                                    total_questions=count,
                                    question=question_response,
                                    message=f"Generated question {questions_generated}/{count}",
                                    document_id=document_id,
                                )
                            except Exception as save_error:
                                await self.db.rollback()
                                logger.warning(f"Backfill save failed: {save_error}")
                except Exception as e:
                    logger.warning(f"Backfill attempt {backfill_attempts} failed: {e}")

            # 6. Complete session - re-fetch to avoid expired state after rollbacks
            logger.info(f"Generation complete: {questions_generated} generated, {questions_failed} failed")
            
            # Re-fetch session to ensure we have fresh state after any rollbacks
            session_result = await self.db.execute(
                select(GenerationSession).where(GenerationSession.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            
            if session:
                session.questions_generated = questions_generated
                session.questions_failed = questions_failed
                session.questions_duplicate = 0
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)
                if session.started_at:
                    session.total_duration_seconds = (
                        session.completed_at - session.started_at
                    ).total_seconds()
                
                await self.db.commit()

            yield QuickGenerateProgress(
                status="complete",
                progress=100,
                current_question=questions_generated,
                total_questions=count,
                message=f"Successfully generated {questions_generated} questions",
                document_id=document_id,
            )

        except Exception as e:
            # Rollback the session on error
            await self.db.rollback()
            logger.exception(f"Error in quick_generate: {e}")
            
            yield QuickGenerateProgress(
                status="error",
                progress=0,
                message=f"Generation failed: {str(e)}",
                document_id=document_id,
            )

        finally:
            # Release lock
            await self.redis_service.release_generation_lock(
                str(user_id), str(document_id)
            )

    async def _generate_quick_question(
        self,
        chunks: List[DocumentChunk],
        question_type: str,
        difficulty: str,
        context: str,
        bloom_levels: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a single question for quick generation with context awareness."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Build context from chunks
        doc_content = "\n\n---\n\n".join([c.chunk_text for c in chunks])
        logger.info(f"Generating {question_type} question, context length: {len(doc_content)}")
        
        # Select system prompt based on type
        if question_type == "mcq":
            system_prompt = SYSTEM_PROMPT_MCQ
        elif question_type == "short_answer":
            system_prompt = SYSTEM_PROMPT_SHORT
        else:
            system_prompt = SYSTEM_PROMPT_LONG

        # Select Bloom's level
        bloom_level = None
        if bloom_levels:
            import random
            bloom_level = random.choice(bloom_levels)
        else:
            bloom_defaults = {
                "mcq": "understand",
                "short_answer": "apply",
                "long_answer": "analyze",
            }
            bloom_level = bloom_defaults.get(question_type, "understand")

        # Build enhanced prompt with user context
        prompt = f"""Topic/Context: {context}

Content from the document:
{doc_content}

Generate a {question_type.replace('_', ' ')} question with the following requirements:
- The question should be relevant to the topic: "{context}"
- Difficulty: {difficulty}
- Bloom's Taxonomy Level: {bloom_level}
- The question must be directly answerable from the provided content
- Ensure the question is clear, specific, and tests understanding of the material

Output valid JSON only."""

        try:
            logger.info(f"Calling LLM for {question_type} question...")
            response = await self._generate_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                question_type=question_type,
            )
            
            if not response:
                return None
            
            logger.info(f"LLM response received: {str(response)[:200]}")
            
            # Normalize response keys - LLM might use different key names
            if "question" in response and "question_text" not in response:
                response["question_text"] = response.pop("question")
            if "text" in response and "question_text" not in response:
                response["question_text"] = response.pop("text")
            
            # Validate required field
            if "question_text" not in response:
                logger.warning(f"Response missing question_text: {response.keys()}")
                return None
            
            response["bloom_taxonomy_level"] = bloom_level
            return response
            
        except Exception as e:
            logger.exception(f"Failed to generate question: {e}")
            return None
    
    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: str,
        question_type: str,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON with retry on parse errors."""
        import logging
        logger = logging.getLogger(__name__)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} for {question_type}")
                    # Use lower temperature on retry for more predictable output
                    temperature = max(0.1, 0.7 - (attempt * 0.2))
                else:
                    temperature = 0.7
                
                response = await self.llm_service.generate_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {question_type}: {str(e)[:100]}")
        
        # All retries exhausted - log and return None instead of raising
        logger.error(f"All {max_retries} attempts failed for {question_type}: {last_error}")
        return None