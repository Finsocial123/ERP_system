from app.core.config import settings

from app.client import client
from app.models.lesson import LessonChunk  

import os
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.models.lesson import LessonChunk


splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " "]
)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenRouter embedding model"""
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,  
        input=texts
    )
    return [item.embedding for item in response.data]



def _group_segments_into_chunks(
    segments: list[dict],
    max_chars: int = 500    
) -> list[dict]:
    chunks = []
    current_text = ""
    current_start = None
    current_end = None

    for seg in segments:
        if current_start is None:
            current_start = seg["start"]

        if len(current_text) + len(seg["text"]) > max_chars and current_text:
            chunks.append({
                "text": current_text.strip(),
                "start": current_start,
                "end": current_end
            })
            current_text = seg["text"]
            current_start = seg["start"]
        else:
            current_text += " " + seg["text"]

        current_end = seg["end"]  

    if current_text:
        chunks.append({
            "text": current_text.strip(),
            "start": current_start,
            "end": current_end
        })

    return chunks


async def chunk_and_embed_lesson(
    lesson_id: int, 
    text: str, 
    source: str, 
    db: AsyncSession,
    segments: list[dict] | None = None
    ) -> int:
    await db.execute(                                 
        delete(LessonChunk).where(                   
            LessonChunk.lesson_id == lesson_id,
            LessonChunk.source == source
        )
    )
    await db.commit()

    if segments:
        chunks_data = _group_segments_into_chunks(segments)
    else:
            # PDF / notes — no timestamps
            raw_chunks = splitter.split_text(text)
            chunks_data = [
                {"text": c, "start": None, "end": None}
                for c in raw_chunks
            ]

    if not chunks_data:
        return 0

    texts = [c["text"] for c in chunks_data]
    embeddings = await embed_texts(texts)

    db_chunks = [
        LessonChunk(
            lesson_id=lesson_id,
            content=c["text"],
            source=source,
            chunk_index=i,
            embedding=embedding,
            start_time=c["start"],   # None for PDF
            end_time=c["end"]        # None for PDF
        )
        for i, (c, embedding) in enumerate(zip(chunks_data, embeddings))
    ]

    db.add_all(db_chunks)
    await db.commit()

    return len(db_chunks)


async def embed_visual_frames(
    lesson_id: int,
    frames: list[dict],
    db: AsyncSession
) -> int:
    # Delete existing visual chunks for this lesson
    await db.execute(
        delete(LessonChunk).where(
            LessonChunk.lesson_id == lesson_id,
            LessonChunk.source == "visual"
        )
    )
    await db.commit()

    if not frames:
        return 0

    # Embed all frame descriptions
    descriptions = [frame["description"] for frame in frames]
    embeddings = await embed_texts(descriptions)

    db_chunks = [
        LessonChunk(
            lesson_id=lesson_id,
            content=frame["description"],
            source="visual",
            chunk_index=i,
            embedding=embedding,
            start_time=frame["start"],
            end_time=frame["end"]
        )
        for i, (frame, embedding) in enumerate(zip(frames, embeddings))
    ]

    db.add_all(db_chunks)
    await db.commit()

    return len(db_chunks)