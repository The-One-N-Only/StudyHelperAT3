from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, func, text
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
    workspace_items = relationship("WorkspaceItem", back_populates="user")
    uploaded_files = relationship("UploadedFile", back_populates="user")
    notes = relationship("Note", back_populates="user")

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
    source_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)

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

class WorkspaceItem(Base):
    __tablename__ = "workspace_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    time_created: Mapped[int] = mapped_column(nullable=False)
    time_updated: Mapped[int] = mapped_column(nullable=False)

    user = relationship("User", back_populates="notes")

def setup_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if 'password_hash' not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))

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


def get_item_by_source(source_name, source_id, user_id, add_to_recent_search):
    with SessionLocal() as session:
        item = session.query(Item).filter_by(source_name=source_name, source_id=source_id).first()
        if item:
            if add_to_recent_search:
                append_to_recently_searched(user_id, item.id)
            return {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "thumb_url": item.thumb_url,
                "thumb_mime": item.thumb_mime,
                "thumb_height": item.thumb_height,
                "source_url": item.source_url,
                "source_name": item.source_name,
                "source_id": item.source_id
            }
        return None

def create_item(item_data, user_id, add_to_recent_search):
    with SessionLocal() as session:
        new_item = Item(**item_data)
        session.add(new_item)
        session.commit()
        session.refresh(new_item)
        if add_to_recent_search:
            append_to_recently_searched(user_id, new_item.id)
        return {
            "id": new_item.id,
            "title": new_item.title,
            "description": new_item.description,
            "thumb_url": new_item.thumb_url,
            "thumb_mime": new_item.thumb_mime,
            "thumb_height": new_item.thumb_height,
            "source_url": new_item.source_url,
            "source_name": new_item.source_name,
            "source_id": new_item.source_id
        }

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
            "source_id": item.source_id
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