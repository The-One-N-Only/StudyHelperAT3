import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.db as db


@pytest.fixture
def test_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:", echo=False)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", test_session)
    return test_session


def _make_user(name="Test User", email="test@example.com", username="testuser", gender="gentleman"):
    return db.create_local_user(email=email, username=username, password_hash="hash", name=name, gender=gender)


def _make_item(source_id="src-1", source_name="Wikipedia", title="Test Item"):
    return db.get_or_create_item(
        {"title": title, "description": "desc", "thumb_url": "", "thumb_mime": "", "thumb_height": 0,
         "source_url": "https://example.com", "source_name": source_name, "source_id": source_id},
        user_id=1, add_to_recent_search=False,
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class TestUser:
    def test_create_local_user(self, test_db):
        u = _make_user()
        assert u["email"] == "test@example.com"
        assert u["username"] == "testuser"
        assert u["gender"] == "gentleman"
        assert u["platform"] == "local"
        assert "id" in u

    def test_get_user_by_id(self, test_db):
        u = _make_user()
        found = db.get_user_by_id(u["id"])
        assert found is not None
        assert found.email == "test@example.com"

    def test_get_user_by_id_not_found(self, test_db):
        assert db.get_user_by_id(99999) is None

    def test_get_user_by_username_case_insensitive(self, test_db):
        _make_user(username="CaseUser")
        assert db.get_user_by_username("caseuser") is not None
        assert db.get_user_by_username("CASEUSER") is not None
        assert db.get_user_by_username("nonexistent") is None

    def test_get_user_by_email_case_insensitive(self, test_db):
        _make_user(email="Test@Example.COM")
        assert db.get_user_by_email("test@example.com") is not None
        assert db.get_user_by_email("nobody@nowhere.com") is None

    def test_update_user(self, test_db):
        u = _make_user()
        result = db.update_user(u["id"], name="New Name", username="newuser", email="new@example.com", gender="lady")
        assert result is not None
        assert result["name"] == "New Name"
        assert result["username"] == "newuser"
        assert result["email"] == "new@example.com"
        assert result["gender"] == "lady"

    def test_update_user_not_found(self, test_db):
        assert db.update_user(99999, "x", "x", "x@x.com", "gentleman") is None

    def test_get_profile_picture_path(self, test_db):
        assert "victorian-man" in db.get_profile_picture_path("gentleman")
        assert "victorian-woman" in db.get_profile_picture_path("lady")
        assert "quill" in db.get_profile_picture_path("secret")
        assert "quill" in db.get_profile_picture_path("unknown")


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class TestItem:
    def test_get_or_create_creates_new(self, test_db):
        _make_user()
        item = db.get_or_create_item(
            {"title": "New", "description": "d", "thumb_url": "", "thumb_mime": "", "thumb_height": 0,
             "source_url": "https://x.com", "source_name": "Wiki", "source_id": "uid-1"},
            user_id=1, add_to_recent_search=False,
        )
        assert item["source_id"] == "uid-1"
        assert item["id"] is not None

    def test_get_or_create_returns_existing(self, test_db):
        _make_user()
        first = _make_item(source_id="dup-1")
        second = db.get_or_create_item(
            {"title": "Updated", "description": "d", "thumb_url": "", "thumb_mime": "", "thumb_height": 0,
             "source_url": "https://x.com", "source_name": "Wiki", "source_id": "dup-1"},
            user_id=1, add_to_recent_search=False,
        )
        assert second["id"] == first["id"]

    def test_get_item_by_id(self, test_db):
        _make_user()
        item = _make_item()
        found = db.get_item_by_id(item["id"], user_id=1, add_to_recent_search=False)
        assert found is not None
        assert found["title"] == "Test Item"

    def test_get_item_by_id_not_found(self, test_db):
        assert db.get_item_by_id(99999, user_id=1, add_to_recent_search=False) is None


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

class TestWorkspace:
    def test_create_and_list(self, test_db):
        _make_user()
        ws = db.create_workspace(user_id=1, name="My Workspace")
        assert ws["name"] == "My Workspace"
        workspaces = db.get_user_workspaces(1)
        assert len(workspaces) == 1
        assert workspaces[0]["name"] == "My Workspace"

    def test_get_single(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "Test")
        found = db.get_workspace(1, ws["id"])
        assert found is not None
        assert found["name"] == "Test"

    def test_get_workspace_wrong_owner(self, test_db):
        _make_user(email="a@a.com", username="a")
        _make_user(email="b@b.com", username="b")
        ws = db.create_workspace(1, "A's workspace")
        assert db.get_workspace(2, ws["id"]) is None

    def test_rename(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "Old")
        renamed = db.rename_workspace(ws["id"], 1, "New")
        assert renamed["name"] == "New"

    def test_rename_wrong_owner(self, test_db):
        _make_user()
        db.create_local_user(email="b@b.com", username="b", password_hash="hash")
        ws = db.create_workspace(1, "Mine")
        assert db.rename_workspace(ws["id"], 2, "Stolen") is None

    def test_delete_cascades(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "ToDelete")
        item = _make_item()
        db.add_to_workspace(1, item["id"], "summary", "[]", "relevant", None, "", "", workspace_id=ws["id"])
        db.create_workspace_note(1, ws["id"], "Note")
        db.append_workspace_chat_turn(1, ws["id"], "Q", "A")
        assert db.delete_workspace(ws["id"], 1) is True
        assert db.get_workspace(1, ws["id"]) is None

    def test_delete_wrong_owner(self, test_db):
        _make_user()
        db.create_local_user(email="b@b.com", username="b", password_hash="hash")
        ws = db.create_workspace(1, "Mine")
        assert db.delete_workspace(ws["id"], 2) is False


# ---------------------------------------------------------------------------
# Workspace items
# ---------------------------------------------------------------------------

class TestWorkspaceItems:
    def test_add_to_workspace_creates_default(self, test_db):
        _make_user()
        item = _make_item()
        result = db.add_to_workspace(1, item["id"], "summary", "[]", "relevant", None, "", "")
        assert result is not None
        assert result["item_id"] == item["id"]

    def test_add_to_specific_workspace(self, test_db):
        _make_user()
        item = _make_item()
        ws = db.create_workspace(1, "Target")
        result = db.add_to_workspace(1, item["id"], "s", "[]", "r", None, "", "", workspace_id=ws["id"])
        assert result["workspace_id"] == ws["id"]

    def test_get_workspace_items(self, test_db):
        _make_user()
        item = _make_item()
        ws = db.create_workspace(1, "WS")
        db.add_to_workspace(1, item["id"], "s1", "[]", "r1", None, "", "", workspace_id=ws["id"])
        items = db.get_workspace_items(1, ws["id"])
        assert len(items) == 1
        assert items[0]["title"] == "Test Item"

    def test_remove_from_workspace(self, test_db):
        _make_user()
        item = _make_item()
        db.add_to_workspace(1, item["id"], "s", "[]", "r", None, "", "")
        ws_items = db.get_workspace_items(1)
        assert len(ws_items) == 1
        assert db.remove_from_workspace(ws_items[0]["id"], 1) == "Removed"
        assert db.get_workspace_items(1) == []

    def test_reorder(self, test_db):
        _make_user()
        a = db.add_to_workspace(1, _make_item(source_id="a").get("id"), "a", "[]", "r", None, "", "")["id"]
        b = db.add_to_workspace(1, _make_item(source_id="b").get("id"), "b", "[]", "r", None, "", "")["id"]
        db.reorder_workspace(1, [b, a])
        items = db.get_workspace_items(1)
        assert items[0]["id"] == b
        assert items[1]["id"] == a


# ---------------------------------------------------------------------------
# Workspace chat
# ---------------------------------------------------------------------------

class TestWorkspaceChat:
    def test_append_and_retrieve(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "ChatTest")
        assert db.append_workspace_chat_turn(1, ws["id"], "Hello", "Hi there") is True
        msgs = db.get_workspace_chat_messages(ws["id"], 1)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi there"

    def test_chat_wrong_workspace_owner(self, test_db):
        _make_user()
        db.create_local_user(email="b@b.com", username="b", password_hash="hash")
        ws = db.create_workspace(1, "Mine")
        assert db.append_workspace_chat_turn(2, ws["id"], "Q", "A") is False
        assert db.get_workspace_chat_messages(ws["id"], 2) == []

    def test_chat_nonexistent_workspace(self, test_db):
        _make_user()
        assert db.append_workspace_chat_turn(1, 999, "Q", "A") is False


# ---------------------------------------------------------------------------
# Workspace notes
# ---------------------------------------------------------------------------

class TestWorkspaceNotes:
    def test_create_and_list(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "NotesWS")
        note = db.create_workspace_note(1, ws["id"], "Title", "Content")
        assert note["title"] == "Title"
        notes = db.get_workspace_notes(ws["id"], 1)
        assert len(notes) == 1

    def test_notes_isolated_by_workspace(self, test_db):
        _make_user()
        ws1 = db.create_workspace(1, "WS1")
        ws2 = db.create_workspace(1, "WS2")
        db.create_workspace_note(1, ws1["id"], "Note in WS1")
        db.create_workspace_note(1, ws2["id"], "Note in WS2")
        assert len(db.get_workspace_notes(ws1["id"], 1)) == 1
        assert len(db.get_workspace_notes(ws2["id"], 1)) == 1


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

class TestUploadedFiles:
    def test_create_and_list(self, test_db):
        _make_user()
        f = db.create_uploaded_file(1, "test.pdf", "uploads/test.pdf", "pdf", "hello world", 1024)
        assert f["filename"] == "test.pdf"
        files = db.get_uploaded_files(1)
        assert len(files) == 1

    def test_delete(self, test_db):
        _make_user()
        f = db.create_uploaded_file(1, "del.pdf", "uploads/del.pdf", "pdf", "x", 100)
        assert db.delete_uploaded_file(f["id"], 1) == "Deleted"
        assert db.get_uploaded_files(1) == []

    def test_delete_wrong_owner(self, test_db):
        _make_user()
        db.create_local_user(email="b@b.com", username="b", password_hash="hash")
        f = db.create_uploaded_file(1, "mine.pdf", "u/m.pdf", "pdf", "x", 100)
        assert db.delete_uploaded_file(f["id"], 2) is None

    def test_search(self, test_db):
        _make_user()
        db.create_uploaded_file(1, "a.pdf", "u/a.pdf", "pdf", "the quick brown fox", 100)
        db.create_uploaded_file(1, "b.pdf", "u/b.pdf", "pdf", "hello world", 100)
        results = db.search_uploaded_files(1, "brown fox")
        assert len(results) == 1
        assert results[0]["filename"] == "a.pdf"

    def test_add_file_to_workspace(self, test_db):
        _make_user()
        ws = db.create_workspace(1, "FilesWS")
        f = db.create_uploaded_file(1, "notes.pdf", "u/notes.pdf", "pdf", "content", 500)
        result = db.add_file_to_workspace(1, f["id"], workspace_id=ws["id"])
        assert result["file_id"] == f["id"]
        assert result["workspace_id"] == ws["id"]


# ---------------------------------------------------------------------------
# Save / unsave
# ---------------------------------------------------------------------------

class TestSave:
    def test_save_and_list(self, test_db):
        _make_user()
        item = _make_item()
        assert db.save_item(item["id"], 1, "test query") == "Saved"
        saved = db.get_saved_items(1)
        assert len(saved) == 1
        assert saved[0]["query"] == "test query"

    def test_save_twice_is_noop(self, test_db):
        _make_user()
        item = _make_item()
        db.save_item(item["id"], 1)
        assert db.save_item(item["id"], 1) is None

    def test_unsave(self, test_db):
        _make_user()
        item = _make_item()
        db.save_item(item["id"], 1)
        assert db.unsave_item(item["id"], 1) == "Unsaved"
        assert db.get_saved_items(1) is None

    def test_grouped(self, test_db):
        _make_user()
        a = _make_item(source_id="a")
        b = _make_item(source_id="b")
        db.save_item(a["id"], 1, "Query A")
        db.save_item(b["id"], 1, "Query B")
        groups = db.get_saved_items_grouped(1)
        assert len(groups) == 2
        titles = {g["items"][0]["title"] for g in groups}
        assert titles == {"Test Item"}


# ---------------------------------------------------------------------------
# Recently viewed / searched
# ---------------------------------------------------------------------------

class TestRecentlyViewed:
    def test_append_and_get(self, test_db):
        _make_user()
        item = _make_item()
        db.append_to_recently_viewed(1, item["id"])
        viewed = db.get_recently_viewed(1)
        assert viewed is not None
        assert len(viewed) == 1


class TestRecentlySearched:
    def test_append_and_get(self, test_db):
        _make_user()
        item = _make_item()
        db.append_to_recently_searched(1, item["id"])
        searched = db.get_recently_searched(1)
        assert searched is not None
        assert len(searched) == 1


# ---------------------------------------------------------------------------
# Search cache
# ---------------------------------------------------------------------------

class TestSearchCache:
    def test_set_and_get(self, test_db):
        db.set_search_cache("key1", "1,2,3")
        cached = db.get_search_cache("key1")
        assert cached is not None
        assert cached["item_ids"] == "1,2,3"

    def test_miss(self, test_db):
        assert db.get_search_cache("no-such-key") is None

    def test_overwrite(self, test_db):
        db.set_search_cache("key", "old")
        db.set_search_cache("key", "new")
        assert db.get_search_cache("key")["item_ids"] == "new"


# ---------------------------------------------------------------------------
# Standalone notes
# ---------------------------------------------------------------------------

class TestNotes:
    def test_create_and_get(self, test_db):
        _make_user()
        n = db.create_note(1, "Title", "Content")
        assert n["title"] == "Title"
        found = db.get_note(n["id"], 1)
        assert found is not None
        assert found["content"] == "Content"

    def test_update(self, test_db):
        _make_user()
        n = db.create_note(1, "Old", "Old content")
        updated = db.update_note(n["id"], 1, title="New", content="New content")
        assert updated["title"] == "New"
        assert updated["content"] == "New content"

    def test_delete(self, test_db):
        _make_user()
        n = db.create_note(1, "Del", "x")
        assert db.delete_note(n["id"], 1) is True
        assert db.get_note(n["id"], 1) is None

    def test_list(self, test_db):
        _make_user()
        db.create_note(1, "A", "A")
        db.create_note(1, "B", "B")
        notes = db.get_notes(1)
        assert len(notes) == 2
