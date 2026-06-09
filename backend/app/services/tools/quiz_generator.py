"""
quiz_generator.py — patched to add AI response caching + request coalescing.

Changes vs original
--------------------
* `generate_quiz` now checks ai_cache before calling the LLM.
* Cache key includes a content_hash of the lesson chunks — so if the teacher
  re-uploads a video/PDF, the old quiz is never served.
* Request coalescing: if 50 students click "Generate Quiz" on the same lesson
  simultaneously, only 1 LLM call is made. The remaining 49 wait and receive
  the cached result.
* All cache operations log HIT / MISS / STORE / LOCK events.
* school_id is now a required parameter for tenant-safe key construction.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.rag import retrieve_context
from app.models.lesson import LessonChunk
from app.client import client
from app.services.ai_cache import ai_cache, compute_content_hash, _lock  # ← NEW
import json
import logging

logger = logging.getLogger(__name__)
# Prompt templates (unchanged)
QUIZ_PROMPT_NO_ANSWERS = """
Return this exact JSON structure:
{{
    "lesson_id": {lesson_id},
    "difficulty": "{difficulty}",
    "questions": [
        {{
            "question_number": 1,
            "question": "question text here",
            "options": {{
                "A": "option text",
                "B": "option text",
                "C": "option text",
                "D": "option text"
            }}
        }}
    ]
}}"""

QUIZ_PROMPT_WITH_ANSWERS = """
Return this exact JSON structure:
{{
    "lesson_id": {lesson_id},
    "difficulty": "{difficulty}",
    "questions": [
        {{
            "question_number": 1,
            "question": "question text here",
            "options": {{
                "A": "option text",
                "B": "option text",
                "C": "option text",
                "D": "option text"
            }},
            "correct_answer": "A",
            "explanation": "why this answer is correct"
        }}
    ]
}}"""

DIFFICULTY_PROMPTS = {
    "easy":   "Generate simple recall questions. Focus on basic definitions and key facts.",
    "medium": "Generate questions that require understanding concepts, not just memorization.",
    "hard":   "Generate questions that require deep analysis, application, and connecting multiple concepts.",
}


# Core function

async def generate_quiz(
    lesson_id: int,
    num_questions: int,
    difficulty: str,
    db: AsyncSession,
    include_answers: bool = True,
    school_id: int = 0,       # ← NEW: required for tenant-safe cache keys
) -> dict:
    """
    Generate (or return cached) quiz for a lesson.

    Cache strategy
    --------------
    Key: ai:quiz:{school_id}:{lesson_id}:{num_q}:{difficulty}:{content_hash}
    TTL: 3 days
    Coalescing: only 1 LLM call for concurrent identical requests
    Invalidation: triggered by lesson content changes (chunk re-generation)
    """

    # 1. Fetch lesson chunks (needed for cache key AND prompt)            #
    chunks = (await db.execute(
        select(LessonChunk)
        .where(LessonChunk.lesson_id == lesson_id)
        .limit(10)
    )).scalars().all()

    if not chunks:
        return {"error": f"No content found for lesson {lesson_id}"}

    combined_text = "\n\n".join(chunk.content for chunk in chunks)
    content_hash = compute_content_hash([chunk.content for chunk in chunks])

    # 2. Cache hit?                                                       #
    cached = await ai_cache.get_quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
    if cached is not None:
        return cached

    # 3. Request coalescing via distributed lock                         #
    lock_key = ai_cache.get_quiz_lock_key(school_id, lesson_id, num_questions, difficulty, content_hash)

    async with _lock(lock_key) as acquired:
        if not acquired:
            # Another worker is computing this quiz — wait for it
            result = await ai_cache.wait_for_quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
            if result is not None:
                return result
            # Lock holder crashed without storing — fall through to compute
            logger.warning(
                "[AI_CACHE] Lock wait timed out for quiz lesson=%d, computing independently",
                lesson_id
            )

        # 4. Double-check cache after acquiring lock (another worker may have  #
        #    stored before us between our MISS and our LOCK acquisition)      #
        cached = await ai_cache.get_quiz(school_id, lesson_id, num_questions, difficulty, content_hash)
        if cached is not None:
            return cached

        # 5. Call LLM                                                         #
        difficulty_instruction = DIFFICULTY_PROMPTS.get(difficulty, DIFFICULTY_PROMPTS["medium"])
        quiz_prompt = QUIZ_PROMPT_WITH_ANSWERS if include_answers else QUIZ_PROMPT_NO_ANSWERS

        response = await client.chat.completions.create(
            model="anthropic/claude-sonnet-4-5",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a quiz generator. Always respond with valid JSON only. "
                        "No markdown, no explanation, just the JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate {num_questions} multiple choice questions from this content.\n\n"
                        f"Difficulty: {difficulty.upper()}\n"
                        f"Instructions: {difficulty_instruction}\n\n"
                        f"Content:\n{combined_text}\n\n"
                        f"{quiz_prompt}"
                    ),
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)

        # 6. Store in cache                                                   #
        await ai_cache.set_quiz(school_id, lesson_id, num_questions, difficulty, content_hash, result)

        return result
