from __future__ import annotations

import json
import time
from typing import Any, Optional

import hashlib
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, Boolean, create_engine, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

engine = create_engine("sqlite:///server.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(254), nullable=True)
    username: Mapped[str] = mapped_column(String(254), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="gentleman")
    login_platform: Mapped[str] = mapped_column(String(16), nullable=False, default='local')
    platform_id: Mapped[dict] = mapped_column(JSON, nullable=False, default={})

    # Relationships
    saved_items = relationship("UserToSaved", back_populates="user")
    recently_viewed = relationship("UserToRecentlyViewed", back_populates="user")
    recently_searched = relationship("UserToRecentlySearched", back_populates="user")
    workspaces = relationship("Workspace", back_populates="user")
    workspace_items = relationship("WorkspaceItem", back_populates="user")
    uploaded_files = relationship("UploadedFile", back_populates="user")
    notes = relationship("Note", back_populates="user")
    workspace_chat_messages = relationship("WorkspaceChatMessage", back_populates="user")

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1023), nullable=False)
    thumb_url: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_mime: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_height: Mapped[int] = mapped_column(nullable=False)
    source_url: Mapped[str] = mapped_column(String(1023), nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(1023), nullable=False, unique=True)
    # PubMed and academic metadata
    abstract: Mapped[str] = mapped_column(Text, nullable=True)
    authors: Mapped[str] = mapped_column(Text, nullable=True)
    journal: Mapped[str] = mapped_column(String(255), nullable=True)
    year: Mapped[str] = mapped_column(String(4), nullable=True)
    volume: Mapped[str] = mapped_column(String(32), nullable=True)
    issue: Mapped[str] = mapped_column(String(32), nullable=True)
    doi: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationships
    saved_by = relationship("UserToSaved", back_populates="item")
    recently_viewed_by = relationship("UserToRecentlyViewed", back_populates="item")
    recently_searched_by = relationship("UserToRecentlySearched", back_populates="item")
    in_workspaces = relationship("WorkspaceItem", back_populates="item")

class UserToSaved(Base):
    __tablename__ = "user_to_saved"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    time_inserted: Mapped[int] = mapped_column(nullable=False)
    query: Mapped[str] = mapped_column(String(1023), nullable=True)

    user = relationship("User", back_populates="saved_items")
    item = relationship("Item", back_populates="saved_by")

class UserToRecentlyViewed(Base):
    __tablename__ = "user_to_recently_viewed"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    time_inserted: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="recently_viewed")
    item = relationship("Item", back_populates="recently_viewed_by")

class UserToRecentlySearched(Base):
    __tablename__ = "user_to_recently_searched"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    time_inserted: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="recently_searched")
    item = relationship("Item", back_populates="recently_searched_by")

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    time_created: Mapped[int] = mapped_column(nullable=False)
    persona: Mapped[str] = mapped_column(String(32), nullable=False, default="formal")
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    folder_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workspace_folders.id"), nullable=True)
    archived: Mapped[bool] = mapped_column(nullable=False, default=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(nullable=True)

    user = relationship("User", back_populates="workspaces")
    items = relationship("WorkspaceItem", back_populates="workspace")
    notes = relationship("Note", back_populates="workspace")
    chat_messages = relationship("WorkspaceChatMessage", back_populates="workspace")
    parent = relationship("Workspace", remote_side="Workspace.id", backref="children")


class WorkspaceChatMessage(Base):
    __tablename__ = "workspace_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    time_created: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="workspace_chat_messages")
    workspace = relationship("Workspace", back_populates="chat_messages")

class WorkspaceItem(Base):
    __tablename__ = "workspace_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("uploaded_files.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    bullets: Mapped[str] = mapped_column(Text, nullable=False)
    relevance: Mapped[str] = mapped_column(Text, nullable=True)
    atn_used: Mapped[str] = mapped_column(Text, nullable=True)
    citation_apa: Mapped[str] = mapped_column(Text, nullable=False)
    citation_harvard: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    time_added: Mapped[int] = mapped_column(nullable=False)
    archived: Mapped[bool] = mapped_column(nullable=False, default=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(nullable=True)

    user = relationship("User", back_populates="workspace_items")
    workspace = relationship("Workspace", back_populates="items")
    item = relationship("Item", back_populates="in_workspaces")
    uploaded_file = relationship("UploadedFile", back_populates="in_workspaces")
    tags = relationship("Tag", secondary="workspace_item_tags", backref="workspace_items")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    time_uploaded: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="uploaded_files")
    in_workspaces = relationship("WorkspaceItem", back_populates="uploaded_file")

class SearchCache(Base):
    __tablename__ = "search_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_ids: Mapped[str] = mapped_column(Text, nullable=False)
    time_cached: Mapped[int] = mapped_column(nullable=False)

class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    query: Mapped[str] = mapped_column(String(1023), nullable=False)
    source_filters: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    num_results: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User")


class ExportTemplate(Base):
    __tablename__ = "export_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    time_created: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    time_created: Mapped[int] = mapped_column(nullable=False)
    time_updated: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="notes")
    workspace = relationship("Workspace", back_populates="notes")

class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workspace_folders.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    user = relationship("User")
    parent = relationship("WorkspaceFolder", remote_side="WorkspaceFolder.id", backref="sub_folders")

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0d6efd")

    user = relationship("User")

class ItemTag(Base):
    __tablename__ = "item_tags"

    item_id: Mapped[int] = mapped_column(ForeignKey("workspace_items.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)

class WorkspaceItemTag(Base):
    __tablename__ = "workspace_item_tags"

    workspace_item_id: Mapped[int] = mapped_column(ForeignKey("workspace_items.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)

class NoteVersion(Base):
    __tablename__ = "note_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(nullable=False)

    note = relationship("Note")

def setup_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Add password_hash if missing
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if 'password_hash' not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))

        # Add gender if missing (default 'gentleman' for existing users)
        if 'gender' not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN gender VARCHAR(16) NOT NULL DEFAULT 'gentleman'"))

        # Add PubMed metadata columns if missing
        result = conn.execute(text("PRAGMA table_info(items)"))
        columns = [row[1] for row in result]

        new_columns = {
            'abstract': 'TEXT',
            'authors': 'TEXT',
            'journal': 'VARCHAR(255)',
            'year': 'VARCHAR(4)',
            'volume': 'VARCHAR(32)',
            'issue': 'VARCHAR(32)',
            'doi': 'VARCHAR(255)'
        }

        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                conn.execute(text(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}"))

        # Add workspace_id to workspace_items if missing
        result = conn.execute(text("PRAGMA table_info(workspace_items)"))
        columns = [row[1] for row in result]
        if 'workspace_id' not in columns:
            conn.execute(text("ALTER TABLE workspace_items ADD COLUMN workspace_id INTEGER"))

        # Add workspace_id to notes if missing
        result = conn.execute(text("PRAGMA table_info(notes)"))
        columns = [row[1] for row in result]
        if 'workspace_id' not in columns:
            conn.execute(text("ALTER TABLE notes ADD COLUMN workspace_id INTEGER"))

        # Add query column to user_to_saved if missing
        result = conn.execute(text("PRAGMA table_info(user_to_saved)"))
        columns = [row[1] for row in result]
        if 'query' not in columns:
            conn.execute(text("ALTER TABLE user_to_saved ADD COLUMN query VARCHAR(1023)"))

        # Add search_cache table if missing
        result = conn.execute(text("PRAGMA table_info(search_cache)"))
        columns = [row[1] for row in result]
        if not columns:
            conn.execute(text("""
                CREATE TABLE search_cache (
                    cache_key VARCHAR(64) PRIMARY KEY,
                    item_ids TEXT NOT NULL,
                    time_cached INTEGER NOT NULL
                )
            """))

        # Add search_history table if missing
        result = conn.execute(text("PRAGMA table_info(search_history)"))
        columns = [row[1] for row in result]
        if not columns:
            conn.execute(text("""
                CREATE TABLE search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query VARCHAR(1023) NOT NULL,
                    source_filters TEXT NOT NULL DEFAULT '[]',
                    num_results INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """))

        # Add persona to workspaces if missing
        result = conn.execute(text("PRAGMA table_info(workspaces)"))
        columns = [row[1] for row in result]
        if 'persona' not in columns:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN persona VARCHAR(32) NOT NULL DEFAULT 'formal'"))

        # Add citations to workspace_chat_messages if missing
        result = conn.execute(text("PRAGMA table_info(workspace_chat_messages)"))
        columns = [row[1] for row in result]
        if 'citations' not in columns:
            conn.execute(text("ALTER TABLE workspace_chat_messages ADD COLUMN citations JSON"))

        # Add parent_id/archived/deleted_at to workspaces if missing
        result = conn.execute(text("PRAGMA table_info(workspaces)"))
        columns = [row[1] for row in result]
        if 'parent_id' not in columns:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN parent_id INTEGER REFERENCES workspaces(id)"))
        if 'archived' not in columns:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"))
        if 'deleted_at' not in columns:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN deleted_at INTEGER"))
        if 'folder_id' not in columns:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN folder_id INTEGER REFERENCES workspace_folders(id)"))

        # Add archived/deleted_at to workspace_items if missing
        result = conn.execute(text("PRAGMA table_info(workspace_items)"))
        columns = [row[1] for row in result]
        if 'archived' not in columns:
            conn.execute(text("ALTER TABLE workspace_items ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"))
        if 'deleted_at' not in columns:
            conn.execute(text("ALTER TABLE workspace_items ADD COLUMN deleted_at INTEGER"))

        # Add file_hash to uploaded_files if missing
        result = conn.execute(text("PRAGMA table_info(uploaded_files)"))
        columns = [row[1] for row in result]
        if 'file_hash' not in columns:
            conn.execute(text("ALTER TABLE uploaded_files ADD COLUMN file_hash VARCHAR(64) NOT NULL DEFAULT ''"))

        conn.commit()

def get_or_create_user(email: str, platform: str, platform_id: dict, *, name: Optional[str] = None, username: Optional[str] = None) -> dict:
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "username": user.username,
                "platform": user.login_platform,
                "platform_id": user.platform_id
            }
        new_user = User(
            email=email,
            name=name,
            username=username,
            login_platform=platform,
            platform_id=platform_id
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "username": new_user.username,
            "gender": new_user.gender,
            "platform": new_user.login_platform,
            "platform_id": new_user.platform_id
        }


def update_user(user_id: int, name: str, username: str, email: str, gender: str, password_hash: Optional[str] = None) -> Optional[dict]:
    with SessionLocal() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None
        user.name = name
        user.username = username
        user.email = email
        user.gender = gender
        if password_hash:
            user.password_hash = password_hash
        session.commit()
        session.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "username": user.username,
            "gender": user.gender,
            "platform": user.login_platform,
        }

def get_user_by_username(username: str) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.username) == username.lower()).first()

def get_user_by_email(email: str) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.email) == email.lower()).first()

def get_user_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter_by(id=user_id).first()

GENDER_PROFILE_PICTURES = {
    'gentleman': '/static/img/profilePictures/victorian-man.jpg',
    'lady': '/static/img/profilePictures/victorian-woman.jpg',
    'secret': '/static/img/profilePictures/quill.jpg',
}

def get_profile_picture_path(gender: str) -> str:
    return GENDER_PROFILE_PICTURES.get(gender, GENDER_PROFILE_PICTURES['secret'])

def create_local_user(email: str, username: str, password_hash: str, name: Optional[str] = None, gender: str = "gentleman") -> dict:
    with SessionLocal() as session:
        new_user = User(
            email=email,
            name=name,
            username=username,
            password_hash=password_hash,
            gender=gender,
            login_platform='local',
            platform_id={}
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "username": new_user.username,
            "gender": new_user.gender,
            "platform": new_user.login_platform,
            "platform_id": new_user.platform_id
        }


def _item_to_dict(item: Item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "thumb_url": item.thumb_url,
        "thumb_mime": item.thumb_mime,
        "thumb_height": item.thumb_height,
        "source_url": item.source_url,
        "source_name": item.source_name,
        "source_id": item.source_id,
        "abstract": item.abstract,
        "authors": item.authors,
        "journal": item.journal,
        "year": item.year,
        "volume": item.volume,
        "issue": item.issue,
        "doi": item.doi,
    }

def create_item(item_data: dict, user_id: int, add_to_recent_search: bool) -> dict:
    with SessionLocal() as session:
        new_item = Item(**item_data)
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        if add_to_recent_search:
            append_to_recently_searched(user_id, new_item.id)
        return _item_to_dict(new_item)

def get_or_create_item(item_data: dict, user_id: int, add_to_recent_search: bool) -> dict:
    """Find an existing item by source_id (or source_name+source_id fallback),
    sync thumb metadata, create a row if needed, and recover from insert races."""
    source_id = item_data.get("source_id", "")
    source_name = item_data.get("source_name", "")

    with SessionLocal() as session:
        item = None
        if source_id:
            item = session.query(Item).filter_by(source_id=source_id).first()
        if not item and source_name and source_id:
            item = session.query(Item).filter_by(source_name=source_name, source_id=source_id).first()

        if item:
            expected_thumb_url = item_data.get("thumb_url")
            if expected_thumb_url is not None and item.thumb_url != expected_thumb_url:
                item.thumb_url = expected_thumb_url
                item.thumb_mime = item_data.get("thumb_mime", item.thumb_mime)
                item.thumb_height = item_data.get("thumb_height", item.thumb_height)
                session.commit()
                session.refresh(item)
            result = _item_to_dict(item)
        else:
            try:
                new_item = Item(**item_data)
                session.add(new_item)
                session.commit()
                session.refresh(new_item)
                result = _item_to_dict(new_item)
            except IntegrityError:
                session.rollback()
                if source_id:
                    item = session.query(Item).filter_by(source_id=source_id).first()
                if not item and source_name and source_id:
                    item = session.query(Item).filter_by(source_name=source_name, source_id=source_id).first()
                if not item:
                    raise
                expected_thumb_url = item_data.get("thumb_url")
                if expected_thumb_url is not None and item.thumb_url != expected_thumb_url:
                    item.thumb_url = expected_thumb_url
                    item.thumb_mime = item_data.get("thumb_mime", item.thumb_mime)
                    item.thumb_height = item_data.get("thumb_height", item.thumb_height)
                    session.commit()
                    session.refresh(item)
                result = _item_to_dict(item)

    if add_to_recent_search:
        append_to_recently_searched(user_id, result["id"])
    return result

def get_item_by_id(item_id: int, user_id: int, add_to_recent_search: bool) -> Optional[dict]:
    with SessionLocal() as session:
        item = session.query(Item).filter_by(id=item_id).first()
        if not item:
            return None
        if add_to_recent_search:
            append_to_recently_searched(user_id, item.id)
        return _item_to_dict(item)

def get_search_cache(cache_key: str) -> Optional[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            row = session.query(SearchCache).filter_by(cache_key=cache_key).first()
            if row:
                return {"cache_key": row.cache_key, "item_ids": row.item_ids, "time_cached": row.time_cached}
            return None
    except OperationalError:
        return None

def set_search_cache(cache_key: str, item_ids: str) -> None:
    try:
        with SessionLocal() as session:
            existing = session.query(SearchCache).filter_by(cache_key=cache_key).first()
            if existing:
                existing.item_ids = item_ids
                existing.time_cached = int(time.time())
            else:
                row = SearchCache(cache_key=cache_key, item_ids=item_ids, time_cached=int(time.time()))
                session.add(row)
            session.commit()
    except OperationalError:
        pass

def get_saved_items(user_id: int) -> Optional[list[dict[str, Any]]]:
    with SessionLocal() as session:
        saved = session.query(UserToSaved, Item).join(Item).filter(UserToSaved.user_id == user_id).order_by(UserToSaved.time_inserted.desc()).all()
        if not saved:
            return None
        return [{
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "thumb_url": item.thumb_url,
            "thumb_mime": item.thumb_mime,
            "thumb_height": item.thumb_height,
            "source_url": item.source_url,
            "source_name": item.source_name,
            "source_id": item.source_id,
            "abstract": item.abstract,
            "authors": item.authors,
            "journal": item.journal,
            "year": item.year,
            "volume": item.volume,
            "issue": item.issue,
            "doi": item.doi,
            "saved_at": uts.time_inserted,
            "query": uts.query
        } for uts, item in saved]

def get_saved_items_grouped(user_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        saved = session.query(UserToSaved, Item).join(Item).filter(UserToSaved.user_id == user_id).order_by(UserToSaved.time_inserted.desc()).all()
        if not saved:
            return []

        groups = {}
        for uts, item in saved:
            query = (uts.query or '').strip() or 'Unsorted'
            if query not in groups:
                groups[query] = []
            groups[query].append({
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "thumb_url": item.thumb_url,
                "thumb_mime": item.thumb_mime,
                "thumb_height": item.thumb_height,
                "source_url": item.source_url,
                "source_name": item.source_name,
                "source_id": item.source_id,
                "abstract": item.abstract,
                "authors": item.authors,
                "journal": item.journal,
                "year": item.year,
                "volume": item.volume,
                "issue": item.issue,
                "doi": item.doi,
                "saved_at": uts.time_inserted,
                "query": query,
                "saved": True
            })

        return [{"query": q, "items": items} for q, items in groups.items()]

def save_item(item_id: int, user_id: int, query: str = '') -> Optional[str]:
    with SessionLocal() as session:
        existing = session.query(UserToSaved).filter_by(user_id=user_id, item_id=item_id).first()
        if existing:
            return None  # Already saved
        new_save = UserToSaved(user_id=user_id, item_id=item_id, time_inserted=int(time.time() * 1000000), query=query)
        session.add(new_save)
        session.commit()
        return "Saved"

def unsave_item(item_id: int, user_id: int) -> Optional[str]:
    with SessionLocal() as session:
        save = session.query(UserToSaved).filter_by(user_id=user_id, item_id=item_id).first()
        if not save:
            return None
        session.delete(save)
        session.commit()
        return "Unsaved"

def get_recently_viewed(user_id: int) -> Optional[list[dict[str, Any]]]:
    with SessionLocal() as session:
        viewed = session.query(UserToRecentlyViewed, Item).join(Item).filter(UserToRecentlyViewed.user_id == user_id).order_by(UserToRecentlyViewed.time_inserted.desc()).limit(10).all()
        if not viewed:
            return None
        return [{
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "thumb_url": item.thumb_url,
            "thumb_mime": item.thumb_mime,
            "thumb_height": item.thumb_height,
            "source_url": item.source_url,
            "source_name": item.source_name,
            "source_id": item.source_id,
            "abstract": item.abstract,
            "authors": item.authors,
            "journal": item.journal,
            "year": item.year,
            "volume": item.volume,
            "issue": item.issue,
            "doi": item.doi,
            "viewed_at": rtv.time_inserted
        } for rtv, item in viewed]

def get_recently_searched(user_id: int) -> Optional[list[dict[str, Any]]]:
    with SessionLocal() as session:
        searched = session.query(UserToRecentlySearched, Item).join(Item).filter(UserToRecentlySearched.user_id == user_id).order_by(UserToRecentlySearched.time_inserted.desc()).limit(10).all()
        if not searched:
            return None
        return [{
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "thumb_url": item.thumb_url,
            "thumb_mime": item.thumb_mime,
            "thumb_height": item.thumb_height,
            "source_url": item.source_url,
            "source_name": item.source_name,
            "source_id": item.source_id,
            "abstract": item.abstract,
            "authors": item.authors,
            "journal": item.journal,
            "year": item.year,
            "volume": item.volume,
            "issue": item.issue,
            "doi": item.doi,
            "searched_at": rts.time_inserted
        } for rts, item in searched]

def append_to_recently_viewed(user_id: int, item_id: int) -> Optional[str]:
    if not user_id:
        return None
    with SessionLocal() as session:
        # Remove if exists
        session.query(UserToRecentlyViewed).filter_by(user_id=user_id, item_id=item_id).delete()
        # Add new
        new_view = UserToRecentlyViewed(user_id=user_id, item_id=item_id, time_inserted=int(time.time() * 1000000))
        session.add(new_view)
        # Keep only 10
        subq = session.query(UserToRecentlyViewed.time_inserted).filter_by(user_id=user_id).order_by(UserToRecentlyViewed.time_inserted.desc()).offset(10).subquery()
        session.query(UserToRecentlyViewed).filter(UserToRecentlyViewed.user_id == user_id, UserToRecentlyViewed.time_inserted.in_(subq)).delete()
        session.commit()
        return "Added"

def append_to_recently_searched(user_id: int, item_id: int) -> Optional[str]:
    if not user_id:
        return None
    with SessionLocal() as session:
        # Remove if exists
        session.query(UserToRecentlySearched).filter_by(user_id=user_id, item_id=item_id).delete()
        # Add new
        new_search = UserToRecentlySearched(user_id=user_id, item_id=item_id, time_inserted=int(time.time() * 1000000))
        session.add(new_search)
        # Keep only 10
        subq = session.query(UserToRecentlySearched.time_inserted).filter_by(user_id=user_id).order_by(UserToRecentlySearched.time_inserted.desc()).offset(10).subquery()
        session.query(UserToRecentlySearched).filter(UserToRecentlySearched.user_id == user_id, UserToRecentlySearched.time_inserted.in_(subq)).delete()
        session.commit()
        return "Added"

def remove_from_workspace(workspace_item_id: int, user_id: int) -> Optional[str]:
    with SessionLocal() as session:
        item = session.query(WorkspaceItem).filter_by(id=workspace_item_id, user_id=user_id).first()
        if not item:
            return None
        session.delete(item)
        # Reorder positions
        remaining = session.query(WorkspaceItem).filter_by(user_id=user_id).order_by(WorkspaceItem.position).all()
        for i, wi in enumerate(remaining):
            wi.position = i
        session.commit()
        return "Removed"

def reorder_workspace(user_id: int, ordered_ids: list[int]) -> None:
    with SessionLocal() as session:
        for pos, wid in enumerate(ordered_ids):
            wi = session.query(WorkspaceItem).filter_by(id=wid, user_id=user_id).first()
            if wi:
                wi.position = pos
        session.commit()

def get_uploaded_files(user_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        files = session.query(UploadedFile).filter_by(user_id=user_id).order_by(UploadedFile.time_uploaded.desc()).all()
        return [{
            "id": f.id,
            "filename": f.filename,
            "stored_path": f.stored_path,
            "file_type": f.file_type,
            "extracted_text": f.extracted_text,
            "file_size": f.file_size,
            "time_uploaded": f.time_uploaded
        } for f in files]


def get_workspace_uploaded_files(workspace_id: int, user_id: int) -> list[dict[str, Any]]:
    """Get uploaded files that belong to a specific workspace."""
    with SessionLocal() as session:
        files = (
            session.query(UploadedFile)
            .join(WorkspaceItem, WorkspaceItem.file_id == UploadedFile.id)
            .filter(
                WorkspaceItem.workspace_id == workspace_id,
                WorkspaceItem.user_id == user_id,
                WorkspaceItem.file_id.isnot(None),
            )
            .order_by(UploadedFile.time_uploaded.desc())
            .all()
        )
        return [{
            "id": f.id,
            "filename": f.filename,
            "stored_path": f.stored_path,
            "file_type": f.file_type,
            "extracted_text": f.extracted_text,
            "file_size": f.file_size,
            "time_uploaded": f.time_uploaded
        } for f in files]

def create_uploaded_file(user_id: int, filename: str, stored_path: str, file_type: str, extracted_text: str, file_size: int, file_hash: str = "") -> dict:
    with SessionLocal() as session:
        new_file = UploadedFile(
            user_id=user_id,
            filename=filename,
            stored_path=stored_path,
            file_type=file_type,
            extracted_text=extracted_text,
            file_size=file_size,
            file_hash=file_hash,
            time_uploaded=int(time.time())
        )
        session.add(new_file)
        session.commit()
        session.refresh(new_file)
        return {
            "id": new_file.id,
            "filename": new_file.filename,
            "stored_path": new_file.stored_path,
            "file_type": new_file.file_type,
            "extracted_text": new_file.extracted_text,
            "file_size": new_file.file_size,
            "file_hash": new_file.file_hash,
            "time_uploaded": new_file.time_uploaded
        }

def hash_file(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def check_duplicate_file(user_id: int, file_hash: str) -> Optional[dict]:
    with SessionLocal() as session:
        existing = session.query(UploadedFile).filter_by(user_id=user_id, file_hash=file_hash).first()
        if existing:
            return {
                "id": existing.id,
                "filename": existing.filename,
                "file_type": existing.file_type,
                "file_size": existing.file_size,
                "time_uploaded": existing.time_uploaded
            }
        return None

def delete_uploaded_file(file_id: int, user_id: int) -> Optional[str]:
    with SessionLocal() as session:
        file = session.query(UploadedFile).filter_by(id=file_id, user_id=user_id).first()
        if not file:
            return None
        session.delete(file)
        session.commit()
        return "Deleted"

def search_uploaded_files(user_id: int, query: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        files = session.query(UploadedFile).filter(UploadedFile.user_id == user_id, UploadedFile.extracted_text.contains(query)).all()
        results = []
        for f in files:
            text = f.extracted_text
            idx = text.lower().find(query.lower())
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(text), idx + len(query) + 100)
                excerpt = text[start:end]
                results.append({
                    "file_id": f.id,
                    "filename": f.filename,
                    "excerpt": excerpt,
                    "page": 1  # Assuming single page for simplicity
                })
        return results

# Note functions
def create_note(user_id: int, title: str, content: str) -> dict:
    with SessionLocal() as session:
        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            time_created=int(time.time()),
            time_updated=int(time.time())
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "time_created": note.time_created,
            "time_updated": note.time_updated
        }

def get_notes(user_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        notes = session.query(Note).filter_by(user_id=user_id).order_by(Note.time_updated.desc()).all()
        return [{
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "time_created": n.time_created,
            "time_updated": n.time_updated
        } for n in notes]

def get_note(note_id: int, user_id: int) -> Optional[dict[str, Any]]:
    with SessionLocal() as session:
        note = session.query(Note).filter_by(id=note_id, user_id=user_id).first()
        if note:
            return {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "time_created": note.time_created,
                "time_updated": note.time_updated
            }
        return None

def update_note(note_id: int, user_id: int, title: Optional[str] = None, content: Optional[str] = None) -> Optional[dict[str, Any]]:
    with SessionLocal() as session:
        note = session.query(Note).filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return None
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        note.time_updated = int(time.time())
        session.commit()
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "time_created": note.time_created,
            "time_updated": note.time_updated
        }

def delete_note(note_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        note = session.query(Note).filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return False
        session.delete(note)
        session.commit()
        return True

# ========== Workspace Management Functions ==========

def get_user_workspaces(user_id: int) -> list[dict[str, Any]]:
    """Get all workspaces for a user (excluding soft-deleted)"""
    with SessionLocal() as session:
        workspaces = session.query(Workspace).filter_by(user_id=user_id, deleted_at=None).order_by(Workspace.time_created.desc()).all()
        return [{
            "id": w.id,
            "name": w.name,
            "time_created": w.time_created,
            "item_count": len(w.items) if w.items else 0,
            "note_count": len(w.notes) if w.notes else 0,
            "archived": w.archived,
            "parent_id": w.parent_id,
            "folder_id": w.folder_id
        } for w in workspaces]

def get_workspace(user_id: int, workspace_id: int) -> Optional[dict[str, Any]]:
    """Get a single workspace for a user"""
    with SessionLocal() as session:
        workspace = session.query(Workspace).filter_by(user_id=user_id, id=workspace_id).first()
        if not workspace:
            return None
        return {
            "id": workspace.id,
            "name": workspace.name,
            "time_created": workspace.time_created,
            "item_count": len(workspace.items) if workspace.items else 0,
            "note_count": len(workspace.notes) if workspace.notes else 0,
            "archived": workspace.archived,
            "parent_id": workspace.parent_id,
            "folder_id": workspace.folder_id
        }


def set_workspace_persona(workspace_id: int, user_id: int, persona: str) -> Optional[dict]:
    """Set the AI persona for a workspace."""
    valid_personas = {"formal", "casual", "socratic", "tutor"}
    if persona not in valid_personas:
        return None
    with SessionLocal() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return None
        workspace.persona = persona
        session.commit()
        return {"id": workspace.id, "persona": workspace.persona}

def get_workspace_chat_messages(workspace_id: int, user_id: int) -> list[dict]:
    """Return oldest-first chat messages for a workspace owned by the user."""
    with SessionLocal() as session:
        workspace_exists = session.query(Workspace.id).filter_by(
            id=workspace_id,
            user_id=user_id,
        ).first()
        if not workspace_exists:
            return []

        messages = session.query(WorkspaceChatMessage).filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
        ).order_by(
            WorkspaceChatMessage.time_created.asc(),
            WorkspaceChatMessage.id.asc(),
        ).all()
        return [{
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "citations": json.loads(message.citations) if message.citations else None,
            "time_created": message.time_created,
        } for message in messages]

def append_workspace_chat_turn(
    user_id: int,
    workspace_id: int,
    user_content: str,
    assistant_content: str,
    citations: Optional[list] = None,
) -> bool:
    """Atomically persist one user/assistant turn for an owned workspace."""
    with SessionLocal() as session:
        workspace_exists = session.query(Workspace.id).filter_by(
            id=workspace_id,
            user_id=user_id,
        ).first()
        if not workspace_exists:
            return False

        created_at = int(time.time())
        session.add_all([
            WorkspaceChatMessage(
                user_id=user_id,
                workspace_id=workspace_id,
                role="user",
                content=user_content,
                time_created=created_at,
            ),
            WorkspaceChatMessage(
                user_id=user_id,
                workspace_id=workspace_id,
                role="assistant",
                content=assistant_content,
                citations=json.dumps(citations) if citations else None,
                time_created=created_at,
            ),
        ])
        session.commit()
        return True

def create_workspace(user_id: int, name: str, parent_id: Optional[int] = None, folder_id: Optional[int] = None) -> dict:
    """Create a new workspace"""
    with SessionLocal() as session:
        new_workspace = Workspace(
            user_id=user_id,
            name=name,
            parent_id=parent_id,
            folder_id=folder_id,
            time_created=int(time.time())
        )
        session.add(new_workspace)
        session.commit()
        session.refresh(new_workspace)
        return {
            "id": new_workspace.id,
            "name": new_workspace.name,
            "time_created": new_workspace.time_created,
            "parent_id": new_workspace.parent_id,
            "folder_id": new_workspace.folder_id
        }

def rename_workspace(workspace_id: int, user_id: int, new_name: str) -> Optional[dict]:
    """Rename a workspace"""
    with SessionLocal() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return None
        workspace.name = new_name
        session.commit()
        return {
            "id": workspace.id,
            "name": workspace.name,
            "time_created": workspace.time_created
        }

def delete_workspace(workspace_id: int, user_id: int) -> bool:
    """Soft-delete a workspace (set deleted_at)"""
    with SessionLocal() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return False
        workspace.deleted_at = int(time.time())
        session.commit()
        return True

def get_workspace_items(user_id: int, workspace_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Get items from a workspace, or default workspace if workspace_id is None"""
    with SessionLocal() as session:
        query = session.query(WorkspaceItem, Item, UploadedFile).outerjoin(Item).outerjoin(UploadedFile).filter(WorkspaceItem.user_id == user_id)
        if workspace_id:
            query = query.filter(WorkspaceItem.workspace_id == workspace_id)
        rows = query.order_by(WorkspaceItem.position).all()
        items = []
        for wi, item, file_ in rows:
            if file_:
                items.append({
                    "id": wi.id,
                    "item_id": wi.item_id,
                    "file_id": wi.file_id,
                    "workspace_id": wi.workspace_id,
                    "summary": wi.summary,
                    "bullets": json.loads(wi.bullets) if wi.bullets else [],
                    "relevance": wi.relevance,
                    "atn_used": wi.atn_used,
                    "citation_apa": wi.citation_apa,
                    "citation_harvard": wi.citation_harvard,
                    "position": wi.position,
                    "time_added": wi.time_added,
                    "title": file_.filename,
                    "description": "",
                    "thumb_url": "",
                    "thumb_mime": "",
                    "thumb_height": None,
                    "source_url": f"/{file_.stored_path}",
                    "source_name": f"Uploaded {file_.file_type.upper()}",
                    "source_id": "",
                    "abstract": (file_.extracted_text or "")[:200],
                    "authors": "",
                    "journal": "",
                    "year": None,
                    "volume": "",
                    "issue": "",
                    "doi": ""
                })
            elif item:
                items.append({
                    "id": wi.id,
                    "item_id": wi.item_id,
                    "file_id": wi.file_id,
                    "workspace_id": wi.workspace_id,
                    "summary": wi.summary,
                    "bullets": json.loads(wi.bullets) if wi.bullets else [],
                    "relevance": wi.relevance,
                    "atn_used": wi.atn_used,
                    "citation_apa": wi.citation_apa,
                    "citation_harvard": wi.citation_harvard,
                    "position": wi.position,
                    "time_added": wi.time_added,
                    "title": item.title,
                    "description": item.description,
                    "thumb_url": item.thumb_url,
                    "thumb_mime": item.thumb_mime,
                    "thumb_height": item.thumb_height,
                    "source_url": item.source_url,
                    "source_name": item.source_name,
                    "source_id": item.source_id,
                    "abstract": item.abstract,
                    "authors": item.authors,
                    "journal": item.journal,
                    "year": item.year,
                    "volume": item.volume,
                    "issue": item.issue,
                    "doi": item.doi
                })
        return items

def add_to_workspace(user_id: int, item_id: int, summary: str, bullets: str, relevance: str, atn_used: str, citation_apa: str, citation_harvard: str, workspace_id: Optional[int] = None) -> dict:
    """Add an item to workspace"""
    with SessionLocal() as session:
        # If no workspace_id, get or create the default workspace
        if workspace_id is None:
            default = session.query(Workspace).filter_by(user_id=user_id).first()
            if not default:
                default = Workspace(user_id=user_id, name="My Collection", time_created=int(time.time()))
                session.add(default)
                session.flush()
            workspace_id = default.id
        
        existing = session.query(WorkspaceItem).filter_by(
            workspace_id=workspace_id, item_id=item_id, user_id=user_id
        ).first()
        if existing:
            return {"duplicate": True}

        max_pos = session.query(func.max(WorkspaceItem.position)).filter_by(workspace_id=workspace_id).scalar() or 0
        new_item = WorkspaceItem(
            user_id=user_id,
            workspace_id=workspace_id,
            item_id=item_id,
            summary=summary,
            bullets=bullets,
            relevance=relevance,
            atn_used=atn_used,
            citation_apa=citation_apa,
            citation_harvard=citation_harvard,
            position=max_pos + 1,
            time_added=int(time.time())
        )
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        return {
            "id": new_item.id,
            "item_id": new_item.item_id,
            "workspace_id": new_item.workspace_id,
            "summary": new_item.summary,
            "bullets": new_item.bullets,
            "relevance": new_item.relevance,
            "atn_used": new_item.atn_used,
            "citation_apa": new_item.citation_apa,
            "citation_harvard": new_item.citation_harvard,
            "position": new_item.position,
            "time_added": new_item.time_added
        }

def add_file_to_workspace(user_id: int, file_id: int, workspace_id: Optional[int] = None) -> dict:
    """Add an uploaded file to a workspace"""
    with SessionLocal() as session:
        if workspace_id is None:
            default = session.query(Workspace).filter_by(user_id=user_id).first()
            if not default:
                default = Workspace(user_id=user_id, name="My Collection", time_created=int(time.time()))
                session.add(default)
                session.flush()
            workspace_id = default.id

        existing = session.query(WorkspaceItem).filter_by(
            workspace_id=workspace_id, file_id=file_id, user_id=user_id
        ).first()
        if existing:
            return {"duplicate": True}

        max_pos = session.query(func.max(WorkspaceItem.position)).filter_by(workspace_id=workspace_id).scalar() or 0
        new_item = WorkspaceItem(
            user_id=user_id,
            workspace_id=workspace_id,
            file_id=file_id,
            summary="",
            bullets="[]",
            citation_apa="",
            citation_harvard="",
            position=max_pos + 1,
            time_added=int(time.time())
        )
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        return {
            "id": new_item.id,
            "file_id": new_item.file_id,
            "workspace_id": new_item.workspace_id,
            "position": new_item.position,
            "time_added": new_item.time_added
        }

def get_workspace_notes(workspace_id: int, user_id: int) -> list[dict[str, Any]]:
    """Get notes for a specific workspace"""
    with SessionLocal() as session:
        notes = session.query(Note).filter_by(workspace_id=workspace_id, user_id=user_id).order_by(Note.time_updated.desc()).all()
        return [{
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "time_created": n.time_created,
            "time_updated": n.time_updated
        } for n in notes]

# ========== Search History Functions ==========

def add_search_history(user_id: int, query: str, source_filters: list, num_results: int) -> dict:
    with SessionLocal() as session:
        entry = SearchHistory(
            user_id=user_id,
            query=query,
            source_filters=json.dumps(source_filters),
            num_results=num_results,
            created_at=int(time.time())
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return {
            "id": entry.id,
            "query": entry.query,
            "source_filters": json.loads(entry.source_filters),
            "num_results": entry.num_results,
            "created_at": entry.created_at
        }


def get_search_history(user_id: int, limit: int = 20) -> list[dict]:
    with SessionLocal() as session:
        entries = (
            session.query(SearchHistory)
            .filter_by(user_id=user_id)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [{
            "id": e.id,
            "query": e.query,
            "source_filters": json.loads(e.source_filters),
            "num_results": e.num_results,
            "created_at": e.created_at
        } for e in entries]


def clear_search_history(user_id: int) -> bool:
    with SessionLocal() as session:
        session.query(SearchHistory).filter_by(user_id=user_id).delete()
        session.commit()
        return True


def get_search_history_entry(entry_id: int, user_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        entry = session.query(SearchHistory).filter_by(id=entry_id, user_id=user_id).first()
        if not entry:
            return None
        return {
            "id": entry.id,
            "query": entry.query,
            "source_filters": json.loads(entry.source_filters),
            "num_results": entry.num_results,
            "created_at": entry.created_at
        }


# ========== Export Template Functions ==========

def get_export_templates(user_id: int) -> list[dict]:
    with SessionLocal() as session:
        templates = session.query(ExportTemplate).filter(
            (ExportTemplate.user_id == user_id) | (ExportTemplate.is_public == True)
        ).order_by(ExportTemplate.name).all()
        return [{
            "id": t.id,
            "user_id": t.user_id,
            "name": t.name,
            "template_content": t.template_content,
            "is_public": t.is_public,
            "time_created": t.time_created,
        } for t in templates]


def create_export_template(user_id: int, name: str, template_content: str, is_public: bool = False) -> dict:
    with SessionLocal() as session:
        tmpl = ExportTemplate(
            user_id=user_id,
            name=name,
            template_content=template_content,
            is_public=is_public,
            time_created=int(time.time()),
        )
        session.add(tmpl)
        session.commit()
        session.refresh(tmpl)
        return {
            "id": tmpl.id,
            "user_id": tmpl.user_id,
            "name": tmpl.name,
            "template_content": tmpl.template_content,
            "is_public": tmpl.is_public,
            "time_created": tmpl.time_created,
        }


def update_export_template(template_id: int, user_id: int, name: str = None, template_content: str = None, is_public: bool = None) -> Optional[dict]:
    with SessionLocal() as session:
        tmpl = session.query(ExportTemplate).filter_by(id=template_id, user_id=user_id).first()
        if not tmpl:
            return None
        if name is not None:
            tmpl.name = name
        if template_content is not None:
            tmpl.template_content = template_content
        if is_public is not None:
            tmpl.is_public = is_public
        session.commit()
        session.refresh(tmpl)
        return {
            "id": tmpl.id,
            "user_id": tmpl.user_id,
            "name": tmpl.name,
            "template_content": tmpl.template_content,
            "is_public": tmpl.is_public,
            "time_created": tmpl.time_created,
        }


def delete_export_template(template_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        tmpl = session.query(ExportTemplate).filter_by(id=template_id, user_id=user_id).first()
        if not tmpl:
            return False
        session.delete(tmpl)
        session.commit()
        return True


def create_workspace_note(user_id: int, workspace_id: int, title: str, content: str = "") -> dict:
    """Create a note in a specific workspace"""
    with SessionLocal() as session:
        new_note = Note(
            user_id=user_id,
            workspace_id=workspace_id,
            title=title,
            content=content,
            time_created=int(time.time()),
            time_updated=int(time.time())
        )
        session.add(new_note)
        session.commit()
        session.refresh(new_note)
        return {
            "id": new_note.id,
            "title": new_note.title,
            "content": new_note.content,
            "time_created": new_note.time_created,
            "time_updated": new_note.time_updated
        }


# ========== Workspace Tree / Sub-Workspaces ==========

def get_workspace_tree(user_id: int) -> list[dict]:
    """Returns nested tree structure of workspaces"""
    with SessionLocal() as session:
        workspaces = session.query(Workspace).filter_by(user_id=user_id, deleted_at=None).order_by(Workspace.time_created.desc()).all()
        roots = []
        child_map = {}
        for w in workspaces:
            item = {
                "id": w.id,
                "name": w.name,
                "time_created": w.time_created,
                "item_count": len(w.items) if w.items else 0,
                "note_count": len(w.notes) if w.notes else 0,
                "archived": w.archived,
                "children": []
            }
            if w.parent_id is None:
                roots.append(item)
            else:
                if w.parent_id not in child_map:
                    child_map[w.parent_id] = []
                child_map[w.parent_id].append(item)
        def attach_children(node):
            node["children"] = child_map.get(node["id"], [])
            for c in node["children"]:
                attach_children(c)
        for r in roots:
            attach_children(r)
        return roots


def move_workspace(workspace_id: int, new_parent_id: Optional[int], user_id: int) -> bool:
    """Move workspace under new parent, validates no circular refs"""
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        if new_parent_id is not None:
            parent = session.query(Workspace).filter_by(id=new_parent_id, user_id=user_id).first()
            if not parent:
                return False
            # Check circular
            current = parent
            while current:
                if current.id == workspace_id:
                    return False
                current = session.query(Workspace).filter_by(id=current.parent_id, user_id=user_id).first()
        ws.parent_id = new_parent_id
        session.commit()
        return True


# ========== WorkspaceFolder CRUD ==========

def create_folder(name: str, user_id: int, parent_id: Optional[int] = None) -> dict:
    with SessionLocal() as session:
        max_order = session.query(func.max(WorkspaceFolder.sort_order)).filter_by(user_id=user_id, parent_id=parent_id).scalar() or 0
        folder = WorkspaceFolder(name=name, user_id=user_id, parent_id=parent_id, sort_order=max_order + 1)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id, "sort_order": folder.sort_order}


def get_folder_tree(user_id: int) -> dict:
    """Returns nested dict of folders and workspaces"""
    with SessionLocal() as session:
        folders = session.query(WorkspaceFolder).filter_by(user_id=user_id).order_by(WorkspaceFolder.sort_order).all()
        workspaces = session.query(Workspace).filter_by(user_id=user_id, deleted_at=None).order_by(Workspace.time_created.desc()).all()
        folder_map = {}
        for f in folders:
            folder_map[f.id] = {
                "id": f.id,
                "name": f.name,
                "parent_id": f.parent_id,
                "sort_order": f.sort_order,
                "folders": [],
                "workspaces": []
            }
        roots = []
        for fid, node in folder_map.items():
            if node["parent_id"] is None:
                roots.append(node)
            elif node["parent_id"] in folder_map:
                folder_map[node["parent_id"]]["folders"].append(node)
        for ws in workspaces:
            w_node = {
                "id": ws.id,
                "name": ws.name,
                "time_created": ws.time_created,
                "item_count": len(ws.items) if ws.items else 0,
                "note_count": len(ws.notes) if ws.notes else 0,
                "archived": ws.archived,
                "folder_id": ws.folder_id
            }
            if ws.folder_id and ws.folder_id in folder_map:
                folder_map[ws.folder_id]["workspaces"].append(w_node)
        return {"folders": roots, "root_workspaces": [w for w in workspaces if w.folder_id is None and not w.archived and w.deleted_at is None]}


def rename_folder(folder_id: int, new_name: str, user_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        folder = session.query(WorkspaceFolder).filter_by(id=folder_id, user_id=user_id).first()
        if not folder:
            return None
        folder.name = new_name
        session.commit()
        return {"id": folder.id, "name": folder.name}


def delete_folder(folder_id: int, user_id: int) -> bool:
    """Moves children to parent, then deletes folder"""
    with SessionLocal() as session:
        folder = session.query(WorkspaceFolder).filter_by(id=folder_id, user_id=user_id).first()
        if not folder:
            return False
        parent_id = folder.parent_id
        # Move sub-folders to parent
        session.query(WorkspaceFolder).filter_by(parent_id=folder_id, user_id=user_id).update({"parent_id": parent_id})
        # Move workspaces in folder to parent (or root)
        session.query(Workspace).filter(Workspace.folder_id == folder_id, Workspace.user_id == user_id).update({"folder_id": parent_id})
        session.delete(folder)
        session.commit()
        return True


def move_to_folder(workspace_id: int, folder_id: Optional[int], user_id: int) -> bool:
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        ws.folder_id = folder_id
        session.commit()
        return True


# ========== Tag CRUD ==========

def create_tag(name: str, color: str, user_id: int) -> dict:
    with SessionLocal() as session:
        tag = Tag(name=name, color=color, user_id=user_id)
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return {"id": tag.id, "name": tag.name, "color": tag.color, "user_id": tag.user_id}


def get_user_tags(user_id: int) -> list[dict]:
    with SessionLocal() as session:
        tags = session.query(Tag).filter_by(user_id=user_id).order_by(Tag.name).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]


def add_tag_to_workspace_item(workspace_item_id: int, tag_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        existing = session.query(WorkspaceItemTag).filter_by(workspace_item_id=workspace_item_id, tag_id=tag_id).first()
        if existing:
            return None
        link = WorkspaceItemTag(workspace_item_id=workspace_item_id, tag_id=tag_id)
        session.add(link)
        session.commit()
        return {"workspace_item_id": workspace_item_id, "tag_id": tag_id}


def remove_tag_from_workspace_item(workspace_item_id: int, tag_id: int) -> bool:
    with SessionLocal() as session:
        link = session.query(WorkspaceItemTag).filter_by(workspace_item_id=workspace_item_id, tag_id=tag_id).first()
        if not link:
            return False
        session.delete(link)
        session.commit()
        return True


def get_workspace_items_by_tag(tag_id: int, workspace_id: int, user_id: int) -> list[dict]:
    with SessionLocal() as session:
        items = session.query(WorkspaceItem).join(WorkspaceItemTag).filter(
            WorkspaceItemTag.tag_id == tag_id,
            WorkspaceItem.workspace_id == workspace_id,
            WorkspaceItem.user_id == user_id,
            WorkspaceItem.deleted_at.is_(None)
        ).all()
        return [{"id": wi.id, "workspace_item_id": wi.id} for wi in items]


def delete_tag(tag_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        tag = session.query(Tag).filter_by(id=tag_id, user_id=user_id).first()
        if not tag:
            return False
        session.query(WorkspaceItemTag).filter_by(tag_id=tag_id).delete()
        session.delete(tag)
        session.commit()
        return True


# ========== Note Version History ==========

def save_note_version(note_id: int, content: str, title: str) -> dict:
    with SessionLocal() as session:
        version = NoteVersion(note_id=note_id, content=content, title=title, created_at=int(time.time()))
        session.add(version)
        session.commit()
        session.refresh(version)
        return {"id": version.id, "note_id": version.note_id, "content": version.content, "title": version.title, "created_at": version.created_at}


def get_note_versions(note_id: int, limit: int = 20) -> list[dict]:
    with SessionLocal() as session:
        versions = session.query(NoteVersion).filter_by(note_id=note_id).order_by(NoteVersion.created_at.desc()).limit(limit).all()
        return [{"id": v.id, "title": v.title, "content": v.content[:200], "created_at": v.created_at} for v in versions]


def restore_note_version(note_id: int, version_id: int, user_id: int) -> Optional[dict]:
    with SessionLocal() as session:
        note = session.query(Note).filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return None
        version = session.query(NoteVersion).filter_by(id=version_id, note_id=note_id).first()
        if not version:
            return None
        note.content = version.content
        note.title = version.title
        note.time_updated = int(time.time())
        session.commit()
        return {"id": note.id, "title": note.title, "content": note.content, "time_updated": note.time_updated}


# ========== Archive / Soft-Delete / Trash ==========

def archive_workspace(workspace_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        ws.archived = True
        session.commit()
        return True


def unarchive_workspace(workspace_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        ws.archived = False
        session.commit()
        return True


def get_archived_workspaces(user_id: int) -> list[dict]:
    with SessionLocal() as session:
        workspaces = session.query(Workspace).filter_by(user_id=user_id, archived=True, deleted_at=None).order_by(Workspace.time_created.desc()).all()
        return [{
            "id": w.id, "name": w.name, "time_created": w.time_created,
            "item_count": len(w.items) if w.items else 0,
            "note_count": len(w.notes) if w.notes else 0
        } for w in workspaces]


def get_trash(user_id: int) -> list[dict]:
    with SessionLocal() as session:
        workspaces = session.query(Workspace).filter_by(user_id=user_id).filter(Workspace.deleted_at.isnot(None)).order_by(Workspace.deleted_at.desc()).all()
        return [{
            "id": w.id, "name": w.name, "time_created": w.time_created,
            "deleted_at": w.deleted_at,
            "item_count": len(w.items) if w.items else 0,
            "note_count": len(w.notes) if w.notes else 0
        } for w in workspaces]


def restore_from_trash(workspace_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        ws.deleted_at = None
        session.commit()
        return True


def permanently_delete_workspace(workspace_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        ws = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not ws:
            return False
        session.query(WorkspaceItem).filter_by(workspace_id=workspace_id).delete()
        session.query(Note).filter_by(workspace_id=workspace_id).delete()
        session.query(WorkspaceChatMessage).filter_by(workspace_id=workspace_id).delete()
        session.delete(ws)
        session.commit()
        return True
