"""
CritiqueService — Constitutional AI filter for auto-reviewing generated questions.

Phase 2 of the Dual-Engine loop:
  Before a question reaches a human vetter, the configured LLM critiques it
  against a "Constitution" of quality rules. Low-scoring questions are
  auto-rejected or regenerated, reducing vetter workload.

Uses the configured LLM provider (Ollama, Gemini, or DeepSeek) to evaluate questions on:
  1. Solvability — Can the question actually be answered from the content?
  2. Clarity — Is the question free of ambiguity?
  3. Answer Correctness — Does the answer key match the question?
  4. Educational Value — Does it test the intended learning outcome?
  5. Formatting — Proper grammar, spelling, structure?
"""

import json
import logging
from typing import Optional
from dataclasses import dataclass

from app.services.llm_service import LLMService, LLMError
from app.core.config import settings


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# Constitution — the critique rubric
# ═══════════════════════════════════════════

CONSTITUTION_PROMPT = """You are a strict educational content reviewer. Your job is to evaluate a generated question against the following criteria. Be critical — only pass genuinely good questions.

## Evaluation Criteria (score each 1-5):

1. **Solvability**: Can this question be answered with a definite, correct response? (1=unsolvable, 5=clearly solvable)
2. **Clarity**: Is the question free from ambiguity, vagueness, or confusing phrasing? (1=very ambiguous, 5=crystal clear)
3. **Answer Correctness**: Does the provided answer key / correct answer actually match the question? (1=wrong answer, 5=definitely correct)
4. **Educational Value**: Does this question meaningfully test understanding of the topic? (1=trivial/irrelevant, 5=excellent pedagogical value)
5. **Formatting**: Is the grammar, spelling, and structure correct? Are MCQ options well-formed? (1=many errors, 5=perfect)

## Output Format (strict JSON):
{
  "scores": {
    "solvability": <1-5>,
    "clarity": <1-5>,
    "answer_correctness": <1-5>,
    "educational_value": <1-5>,
    "formatting": <1-5>
  },
  "overall_score": <1-5 average>,
  "pass": <true if overall >= 4.0, false otherwise>,
  "issues": ["list of specific issues found, empty if none"],
  "suggestion": "brief suggestion for improvement, or null if perfect"
}

Respond ONLY with the JSON object. No other text."""


CRITIQUE_USER_TEMPLATE = """## Question to Evaluate

**Type:** {question_type}
**Difficulty:** {difficulty}
**Topic:** {topic}

**Question:**
{question_text}

{options_section}

**Correct Answer:** {correct_answer}

{explanation_section}
"""


@dataclass
class CritiqueResult:
    """Result of a constitutional critique."""
    scores: dict
    overall_score: float
    passed: bool
    issues: list[str]
    suggestion: Optional[str]
    raw_response: str


class CritiqueService:
    """
    Constitutional AI filter using the configured LLM provider.

    Evaluates generated questions before they reach human vetters.
    Questions scoring below the threshold are auto-rejected.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        pass_threshold: float = 4.0,
    ):
        # Use the configured LLM provider for critique.
        # Can be overridden with a specific model (e.g. fine-tuned LoRA variant).
        self.llm = LLMService(model=model)
        self.pass_threshold = pass_threshold
        model_name = getattr(self.llm, 'model', None) or getattr(self.llm, 'model_name', 'unknown')
        logger.info(
            f"CritiqueService initialized — model={model_name}, "
            f"threshold={self.pass_threshold}"
        )

    async def critique(
        self,
        question_text: str,
        question_type: str = "unknown",
        difficulty: str = "medium",
        topic: str = "general",
        correct_answer: Optional[str] = None,
        options: Optional[list[str]] = None,
        explanation: Optional[str] = None,
    ) -> CritiqueResult:
        """
        Run constitutional critique on a single question.

        Returns a CritiqueResult with scores and pass/fail determination.
        """
        # Build options section
        options_section = ""
        if options:
            options_section = "**Options:**\n" + "\n".join(
                f"  {chr(65 + i)}) {opt}" for i, opt in enumerate(options)
            )

        explanation_section = ""
        if explanation:
            explanation_section = f"**Explanation:** {explanation}"

        user_prompt = CRITIQUE_USER_TEMPLATE.format(
            question_type=question_type,
            difficulty=difficulty,
            topic=topic,
            question_text=question_text,
            options_section=options_section,
            correct_answer=correct_answer or "Not provided",
            explanation_section=explanation_section,
        )

        try:
            raw = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=CONSTITUTION_PROMPT,
                temperature=0.1,  # Low temp for consistent scoring
                max_tokens=500,
            )

            parsed = self._parse_response(raw)
            return parsed

        except LLMError as e:
            logger.error(f"Critique LLM call failed: {e}")
            # On LLM failure, pass the question through (fail-open)
            return CritiqueResult(
                scores={},
                overall_score=5.0,
                passed=True,
                issues=["Critique service unavailable — auto-passed"],
                suggestion=None,
                raw_response=str(e),
            )

    async def critique_question_model(self, question) -> CritiqueResult:
        """
        Convenience: critique a Question ORM model directly.
        """
        topic_name = "general"
        if question.topic and hasattr(question.topic, "name"):
            topic_name = question.topic.name

        return await self.critique(
            question_text=question.question_text,
            question_type=question.question_type or "unknown",
            difficulty=question.difficulty_level or "medium",
            topic=topic_name,
            correct_answer=question.correct_answer,
            options=question.options,
            explanation=question.explanation,
        )

    def _parse_response(self, raw: str) -> CritiqueResult:
        """Parse the LLM JSON response into a CritiqueResult."""
        # Try to extract JSON from the response (handle markdown code fences)
        text = raw.strip()
        if text.startswith("```"):
            # Remove code fences
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse critique response: {raw[:200]}")
                    return CritiqueResult(
                        scores={},
                        overall_score=5.0,
                        passed=True,
                        issues=["Could not parse critique response — auto-passed"],
                        suggestion=None,
                        raw_response=raw,
                    )
            else:
                return CritiqueResult(
                    scores={},
                    overall_score=5.0,
                    passed=True,
                    issues=["No JSON in critique response — auto-passed"],
                    suggestion=None,
                    raw_response=raw,
                )

        scores = data.get("scores", {})
        overall = data.get("overall_score", 0)

        # Validate overall score is reasonable
        if isinstance(overall, (int, float)) and 1 <= overall <= 5:
            pass
        else:
            # Compute from individual scores
            score_vals = [v for v in scores.values() if isinstance(v, (int, float))]
            overall = sum(score_vals) / len(score_vals) if score_vals else 5.0

        return CritiqueResult(
            scores=scores,
            overall_score=float(overall),
            passed=float(overall) >= self.pass_threshold,
            issues=data.get("issues", []),
            suggestion=data.get("suggestion"),
            raw_response=raw,
        )
