import json

def estimate_tokens(text: str) -> int:
    if text is None:
        return 0
    return len(text)


def estimate_message_tokens(msg:dict) -> int:
    """
    token for whole message - content + tool_calls
    """
    tokens = estimate_tokens(msg.get("content"))
    if msg.get("tool_calls"):
        tokens += sum(estimate_tokens(json.dumps(tc)) for tc in msg["tool_calls"])
    return tokens


def trim_history(
    history: list[dict],
    system_prompt: str,
    rag_context: str,
    max_tokens: int = 6000
) -> list[dict]:
    """
    Trims messages history to fit within token budget
    Always keeps most recent messages, drops oldest first.
    """

    reserved = estimate_tokens(system_prompt) + estimate_tokens(rag_context)

    budget = max_tokens - reserved

    if budget <= 0:
        last = history[-1] if history else None
        return [last] if last else []
    
    kept = []
    used = 0

    for msg in reversed(history):
        msg_tokens = estimate_message_tokens(msg)

        if used + msg_tokens > budget:
            break
        kept.append(msg)
        used += msg_tokens
    
    if not kept or kept[-1].get("role") != "user":
        last_user = next((m for m in reversed(history) if m.get("role") == "user"), None)
        if last_user and last_user not in kept:
            kept.append(last_user)
            
    kept.reverse()

    trimmed_count = len(history) - len(kept)
    if trimmed_count > 0:
        kept.insert(0, {
            "role": "system",
            "content": f"[Note: {trimmed_count} older messages were removed to fit context window]"
        })

    return kept