"""Tests for tenant-scoped conversation filtering and first-message titles."""

import pytest

import app.api.conversation_routes as conversation_routes
from app.auth.middleware import AuthUser
from app.auth.roles import UserRole
from app.db.models import Conversation
from app.db.repositories import ConversationRepository


@pytest.mark.asyncio
async def test_list_conversations_passes_all_filters_and_returns_total(monkeypatch):
    seen = {}

    async def _list_page(self, **kwargs):
        seen.update(kwargs)
        return ([{"id": "visible"}], 7)

    monkeypatch.setattr(ConversationRepository, "list_for_user_page", _list_page)
    body = await conversation_routes.list_conversations(
        user_id="query-user",
        limit=2,
        agent_id="agent-b",
        q="Alpha",
        status="active",
        offset=4,
        session=object(),
        user=AuthUser(id="user-a", role=UserRole.OPERATOR),
    )

    assert seen == {
        "user_id": "user-a",
        "limit": 2,
        "agent_id": "agent-b",
        "q": "Alpha",
        "status": "active",
        "offset": 4,
    }
    assert body == {"conversations": [{"id": "visible"}], "total": 7}


class _Result:
    def __init__(self, conversation):
        self.conversation = conversation

    def scalar_one_or_none(self):
        return self.conversation


class _MessageSession:
    def __init__(self, conversation):
        self.conversation = conversation
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def execute(self, _statement):
        return _Result(self.conversation)

    async def flush(self):
        return None

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_first_user_message_sets_trimmed_sixty_character_title_once():
    conversation = Conversation(id="conversation-1", title=None)
    session = _MessageSession(conversation)
    repo = ConversationRepository(session)
    content = "  " + ("A very long first question " * 5) + "  "

    await repo.add_message(conversation.id, {"role": "user", "content": content})
    assert conversation.title == content.strip()[:60]
    assert len(conversation.title) == 60

    await repo.add_message(conversation.id, {"role": "user", "content": "second question"})
    assert conversation.title == content.strip()[:60]


@pytest.mark.asyncio
async def test_blank_first_user_message_does_not_create_a_title():
    conversation = Conversation(id="conversation-2", title=None)
    repo = ConversationRepository(_MessageSession(conversation))

    await repo.add_message(conversation.id, {"role": "user", "content": "   "})

    assert conversation.title is None
