import json
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
import time

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

    user = relationship("User", back_populates="workspaces")
    items = relationship("WorkspaceItem", back_populates="workspace")
    notes = relationship("Note", back_populates="workspace")
    chat_messages = relationship("WorkspaceChatMessage", back_populates="workspace")


class WorkspaceChatMessage(Base):
    __tablename__ = "workspace_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
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

    user = relationship("User", back_populates="workspace_items")
    workspace = relationship("Workspace", back_populates="items")
    item = relationship("Item", back_populates="in_workspaces")
    uploaded_file = relationship("UploadedFile", back_populates="in_workspaces")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    time_uploaded: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="uploaded_files")
    in_workspaces = relationship("WorkspaceItem", back_populates="uploaded_file")

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

def setup_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Add password_hash if missing
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if 'password_hash' not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))

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

        conn.commit()

def get_or_create_user(email, platform, platform_id, *, name=None, username=None):
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
            "platform": new_user.login_platform,
            "platform_id": new_user.platform_id
        }

def get_user_by_username(username):
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.username) == username.lower()).first()

def get_user_by_email(email):
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.email) == email.lower()).first()

def get_user_by_id(user_id):
    with SessionLocal() as session:
        return session.query(User).filter_by(id=user_id).first()

def create_local_user(email, username, password_hash, name=None):
    with SessionLocal() as session:
        new_user = User(
            email=email,
            name=name,
            username=username,
            password_hash=password_hash,
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
            "platform": new_user.login_platform,
            "platform_id": new_user.platform_id
        }


def _item_to_dict(item):
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

def get_item_by_source(source_name, source_id, user_id, add_to_recent_search):
    with SessionLocal() as session:
        item = session.query(Item).filter_by(source_name=source_name, source_id=source_id).first()
        if item:
            if add_to_recent_search:
                append_to_recently_searched(user_id, item.id)
            return _item_to_dict(item)
        return None

def get_item_by_source_id(source_id, user_id, add_to_recent_search):
    """Find URL-backed items regardless of historical display-name casing."""
    with SessionLocal() as session:
        item = session.query(Item).filter_by(source_id=source_id).first()
        if not item:
            return None
        if add_to_recent_search:
            append_to_recently_searched(user_id, item.id)
        return _item_to_dict(item)

def create_item(item_data, user_id, add_to_recent_search):
    with SessionLocal() as session:
        new_item = Item(**item_data)
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        if add_to_recent_search:
            append_to_recently_searched(user_id, new_item.id)
        return _item_to_dict(new_item)

def _get_and_sync_item_by_source_id(item_data, user_id, add_to_recent_search):
    """Return an existing URL row after applying security-sensitive fields."""
    with SessionLocal() as session:
        item = session.query(Item).filter_by(source_id=item_data["source_id"]).first()
        if not item:
            return None

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

def get_or_create_item_by_source_id(item_data, user_id, add_to_recent_search):
    """Reuse URL-backed rows and recover cleanly from concurrent insert races."""
    existing = _get_and_sync_item_by_source_id(
        item_data,
        user_id,
        add_to_recent_search,
    )
    if existing:
        return existing

    try:
        return create_item(item_data, user_id, add_to_recent_search)
    except IntegrityError:
        # Another source worker may have inserted the same Serp URL first.
        existing = _get_and_sync_item_by_source_id(
            item_data,
            user_id,
            add_to_recent_search,
        )
        if existing:
            return existing
        raise

def get_saved_items(user_id):
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
            "saved_at": uts.time_inserted
        } for uts, item in saved]

def save_item(item_id, user_id):
    with SessionLocal() as session:
        existing = session.query(UserToSaved).filter_by(user_id=user_id, item_id=item_id).first()
        if existing:
            return None  # Already saved
        new_save = UserToSaved(user_id=user_id, item_id=item_id, time_inserted=int(time.time() * 1000000))
        session.add(new_save)
        session.commit()
        return "Saved"

def unsave_item(item_id, user_id):
    with SessionLocal() as session:
        save = session.query(UserToSaved).filter_by(user_id=user_id, item_id=item_id).first()
        if not save:
            return None
        session.delete(save)
        session.commit()
        return "Unsaved"

def get_recently_viewed(user_id):
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

def get_recently_searched(user_id):
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

def append_to_recently_viewed(user_id, item_id):
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

def append_to_recently_searched(user_id, item_id):
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

def get_workspace_items(user_id):
    with SessionLocal() as session:
        items = session.query(WorkspaceItem, Item).join(Item).filter(WorkspaceItem.user_id == user_id).order_by(WorkspaceItem.position).all()
        return [{
            "id": wi.id,
            "item_id": wi.item_id,
            "file_id": wi.file_id,
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
        } for wi, item in items]

def add_to_workspace(user_id, item_id, summary, bullets, relevance, atn_used, citation_apa, citation_harvard):
    with SessionLocal() as session:
        max_pos = session.query(func.max(WorkspaceItem.position)).filter_by(user_id=user_id).scalar() or 0
        new_item = WorkspaceItem(
            user_id=user_id,
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
            "summary": new_item.summary,
            "bullets": new_item.bullets,
            "relevance": new_item.relevance,
            "atn_used": new_item.atn_used,
            "citation_apa": new_item.citation_apa,
            "citation_harvard": new_item.citation_harvard,
            "position": new_item.position,
            "time_added": new_item.time_added
        }

def remove_from_workspace(workspace_item_id, user_id):
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

def reorder_workspace(user_id, ordered_ids):
    with SessionLocal() as session:
        for pos, wid in enumerate(ordered_ids):
            wi = session.query(WorkspaceItem).filter_by(id=wid, user_id=user_id).first()
            if wi:
                wi.position = pos
        session.commit()

def get_uploaded_files(user_id):
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

def create_uploaded_file(user_id, filename, stored_path, file_type, extracted_text, file_size):
    with SessionLocal() as session:
        new_file = UploadedFile(
            user_id=user_id,
            filename=filename,
            stored_path=stored_path,
            file_type=file_type,
            extracted_text=extracted_text,
            file_size=file_size,
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
            "time_uploaded": new_file.time_uploaded
        }

def delete_uploaded_file(file_id, user_id):
    with SessionLocal() as session:
        file = session.query(UploadedFile).filter_by(id=file_id, user_id=user_id).first()
        if not file:
            return None
        session.delete(file)
        session.commit()
        return "Deleted"

def search_uploaded_files(user_id, query):
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
def create_note(user_id, title, content):
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

def get_notes(user_id):
    with SessionLocal() as session:
        notes = session.query(Note).filter_by(user_id=user_id).order_by(Note.time_updated.desc()).all()
        return [{
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "time_created": n.time_created,
            "time_updated": n.time_updated
        } for n in notes]

def get_note(note_id, user_id):
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

def update_note(note_id, user_id, title=None, content=None):
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

def delete_note(note_id, user_id):
    with SessionLocal() as session:
        note = session.query(Note).filter_by(id=note_id, user_id=user_id).first()
        if not note:
            return False
        session.delete(note)
        session.commit()
        return True

# ========== Workspace Management Functions ==========

def get_user_workspaces(user_id):
    """Get all workspaces for a user"""
    with SessionLocal() as session:
        workspaces = session.query(Workspace).filter_by(user_id=user_id).order_by(Workspace.time_created.desc()).all()
        return [{
            "id": w.id,
            "name": w.name,
            "time_created": w.time_created,
            "item_count": len(w.items) if w.items else 0,
            "note_count": len(w.notes) if w.notes else 0
        } for w in workspaces]

def get_workspace(user_id, workspace_id):
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
            "note_count": len(workspace.notes) if workspace.notes else 0
        }

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
            "time_created": message.time_created,
        } for message in messages]

def append_workspace_chat_turn(
    user_id: int,
    workspace_id: int,
    user_content: str,
    assistant_content: str,
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
                time_created=created_at,
            ),
        ])
        session.commit()
        return True

def create_workspace(user_id, name):
    """Create a new workspace"""
    with SessionLocal() as session:
        new_workspace = Workspace(
            user_id=user_id,
            name=name,
            time_created=int(time.time())
        )
        session.add(new_workspace)
        session.commit()
        session.refresh(new_workspace)
        return {
            "id": new_workspace.id,
            "name": new_workspace.name,
            "time_created": new_workspace.time_created
        }

def rename_workspace(workspace_id, user_id, new_name):
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

def delete_workspace(workspace_id, user_id):
    """Delete a workspace and its owned items, notes, and chat history."""
    with SessionLocal() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id, user_id=user_id).first()
        if not workspace:
            return False
        session.query(WorkspaceItem).filter_by(workspace_id=workspace_id).delete()
        session.query(Note).filter_by(workspace_id=workspace_id).delete()
        session.query(WorkspaceChatMessage).filter_by(workspace_id=workspace_id).delete()
        session.delete(workspace)
        session.commit()
        return True

def get_workspace_items(user_id, workspace_id=None):
    """Get items from a workspace, or default workspace if workspace_id is None"""
    with SessionLocal() as session:
        query = session.query(WorkspaceItem, Item).join(Item).filter(WorkspaceItem.user_id == user_id)
        if workspace_id:
            query = query.filter(WorkspaceItem.workspace_id == workspace_id)
        items = query.order_by(WorkspaceItem.position).all()
        return [{
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
        } for wi, item in items]

def add_to_workspace(user_id, item_id, summary, bullets, relevance, atn_used, citation_apa, citation_harvard, workspace_id=None):
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

def get_workspace_notes(workspace_id, user_id):
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

def create_workspace_note(user_id, workspace_id, title, content=""):
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

        return True
