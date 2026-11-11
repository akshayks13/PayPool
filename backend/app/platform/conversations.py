"""Buyer-owned current-task history; estimates are deliberately not persisted."""

from fastapi import HTTPException

from app.platform.store import now


def current(tx, user):
    return tx.get("procurement_conversations", user["id"]) or {
        "id": user["id"],
        "version": 0,
        "message": "",
        "intent": None,
        "history": [],
        "engine": None,
        "updated_at": None,
    }


def check(tx, user, expected):
    record = current(tx, user)
    if record["version"] != expected:
        raise HTTPException(
            409,
            "This conversation changed on another tab or device. Reload before continuing.",
        )
    return record


def save(store, user, data, intent, engine):
    if data.conversation_version is None:
        return None  # Stateless API consumers do not modify the saved task.
    with store.transaction() as tx:
        previous = check(tx, user, data.conversation_version)
        history = (
            previous["history"]
            if (previous.get("intent") or {}).get("clarification_questions")
            else []
        )
        history = [
            *history,
            {
                "message": data.message,
                "questions": list(intent.clarification_questions),
                "at": now(),
            },
        ][-10:]
        return tx.put(
            "procurement_conversations",
            {
                "id": user["id"],
                "version": previous["version"] + 1,
                "message": data.message,
                "intent": intent.model_dump(mode="json"),
                "history": history,
                "engine": engine,
                "updated_at": now(),
            },
        )
