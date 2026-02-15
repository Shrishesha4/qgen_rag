"""
Reranker service for improving retrieval quality using cross-encoder models.

Cross-encoders are more accurate than bi-encoders for ranking because they
jointly process the query and document together, allowing for more nuanced
similarity assessment.
"""

from typing import List, Optional, Tuple
from sentence_transformers import CrossEncoder

from app.models.document import DocumentChunk
from app.core.config import settings


class RerankerService:
    """
    Service for reranking retrieved chunks using cross-encoder models.
    
    Cross-encoders provide more accurate relevance scores than embedding
    similarity but are slower, so they're best used as a second stage
    after initial retrieval.
    """

    _instance: Optional["RerankerService"] = None
    _model: Optional[CrossEncoder] = None

    def __new__(cls):
        """Singleton pattern for model reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            # ms-marco-MiniLM-L-6-v2 is a fast, effective model for reranking
            # It was trained on MS MARCO passage ranking dataset
            self._model = CrossEncoder(
                settings.RERANKER_MODEL if hasattr(settings, 'RERANKER_MODEL') 
                else 'cross-encoder/ms-marco-MiniLM-L-6-v2',
                max_length=512
            )

    def rerank(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: Optional[int] = None,
    ) -> List[DocumentChunk]:
        """
        Rerank chunks by relevance to query using cross-encoder.
        
        Args:
            query: The search query or context
            chunks: List of document chunks to rerank
            top_k: Number of top results to return (None = return all)
        
        Returns:
            List of chunks sorted by relevance (highest first)
        """
        if not chunks:
            return []
        
        if len(chunks) == 1:
            return chunks
        
        # Create query-document pairs for cross-encoder
        pairs = [(query, chunk.chunk_text) for chunk in chunks]
        
        # Get relevance scores
        scores = self._model.predict(pairs)
        
        # Combine chunks with scores and sort by score (descending)
        ranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return top-k if specified, otherwise return all
        result_chunks = [chunk for chunk, _ in ranked]
        if top_k is not None:
            return result_chunks[:top_k]
        
        return result_chunks

    def rerank_with_scores(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: Optional[int] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Rerank chunks and return both chunks and their scores.
        
        Args:
            query: The search query or context
            chunks: List of document chunks to rerank
            top_k: Number of top results to return (None = return all)
        
        Returns:
            List of (chunk, score) tuples sorted by relevance
        """
        if not chunks:
            return []
        
        if len(chunks) == 1:
            # Still compute score for the single chunk
            score = self._model.predict([(query, chunks[0].chunk_text)])[0]
            return [(chunks[0], float(score))]
        
        # Create query-document pairs for cross-encoder
        pairs = [(query, chunk.chunk_text) for chunk in chunks]
        
        # Get relevance scores
        scores = self._model.predict(pairs)
        
        # Combine chunks with scores and sort by score (descending)
        ranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Convert to list of tuples with float scores
        result = [(chunk, float(score)) for chunk, score in ranked]
        
        if top_k is not None:
            return result[:top_k]
        
        return result

    def rerank_texts(
        self,
        query: str,
        texts: List[str],
        top_k: Optional[int] = None,
    ) -> List[Tuple[str, float, int]]:
        """
        Rerank raw text strings (not DocumentChunk objects).
        
        Args:
            query: The search query or context
            texts: List of text strings to rerank
            top_k: Number of top results to return (None = return all)
        
        Returns:
            List of (text, score, original_index) tuples sorted by relevance
        """
        if not texts:
            return []
        
        # Create query-document pairs
        pairs = [(query, text) for text in texts]
        
        # Get relevance scores
        scores = self._model.predict(pairs)
        
        # Combine texts with scores and original indices
        indexed_results = [
            (texts[i], float(scores[i]), i)
            for i in range(len(texts))
        ]
        
        # Sort by score (descending)
        ranked = sorted(indexed_results, key=lambda x: x[1], reverse=True)
        
        if top_k is not None:
            return ranked[:top_k]
        
        return ranked

    def filter_by_threshold(
        self,
        query: str,
        chunks: List[DocumentChunk],
        threshold: float = 0.0,
    ) -> List[DocumentChunk]:
        """
        Filter chunks by minimum relevance score.
        
        Args:
            query: The search query or context
            chunks: List of document chunks to filter
            threshold: Minimum score to include (cross-encoder scores typically range -10 to 10)
        
        Returns:
            List of chunks with scores above threshold, sorted by relevance
        """
        if not chunks:
            return []
        
        ranked_with_scores = self.rerank_with_scores(query, chunks)
        return [chunk for chunk, score in ranked_with_scores if score >= threshold]

    def warmup(self) -> None:
        """
        Warmup the model by running a dummy inference.
        
        This ensures the model is fully loaded and ready before the first
        real request, avoiding cold start latency for users.
        """
        dummy_query = "What is the main topic?"
        dummy_text = "This is a warmup text for model initialization."
        _ = self._model.predict([(dummy_query, dummy_text)])
        print(f"✅ Reranker model warmed up: {settings.RERANKER_MODEL}")


# Module-level function for easy import
def warmup_reranker_service() -> None:
    """Warmup the reranker service singleton."""
    service = RerankerService()
    service.warmup()
