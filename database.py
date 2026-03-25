"""
VaultFetch — Phase 3
Database Module
SQLite + SQLAlchemy for user history, stats, preferences
"""

import os
import logging
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    DateTime, BigInteger, Text, Float, Boolean, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import contextmanager

logger = logging.getLogger("VaultFetch.DB")

# ─── Database Setup ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "vaultfetch.db")
engine   = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
Base     = declarative_base()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id   = Column(BigInteger, unique=True, nullable=False, index=True)
    username      = Column(String(100), nullable=True)
    full_name     = Column(String(200), nullable=True)
    joined_at     = Column(DateTime, default=datetime.utcnow)
    last_active   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_downloads = Column(Integer, default=0)
    is_banned     = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User {self.telegram_id} @{self.username}>"


class Download(Base):
    __tablename__ = "downloads"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id   = Column(BigInteger, nullable=False, index=True)
    url           = Column(Text, nullable=False)
    platform      = Column(String(100), nullable=True)
    content_type  = Column(String(50), nullable=True)   # video/audio/article
    action        = Column(String(50), nullable=True)   # video_best/720p/audio/article
    title         = Column(Text, nullable=True)
    uploader      = Column(String(200), nullable=True)
    filesize      = Column(BigInteger, default=0)
    duration      = Column(Integer, default=0)          # seconds
    success       = Column(Boolean, default=True)
    error_msg     = Column(Text, nullable=True)
    ai_confidence = Column(Float, default=0.0)
    downloaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Download {self.platform} | {self.title[:30]}>"


class Summary(Base):
    __tablename__ = "summaries"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id  = Column(BigInteger, nullable=False, index=True)
    url          = Column(Text, nullable=False)
    title        = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Summary {self.title[:30]}>"


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id     = Column(BigInteger, unique=True, nullable=False, index=True)
    default_quality = Column(String(20), default="best")     # best/1080p/720p/480p/360p
    default_format  = Column(String(20), default="video")    # video/audio
    auto_download   = Column(Boolean, default=True)          # auto-trigger on high confidence
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Create Tables ─────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info(f"✅ Database initialized at: {DB_PATH}")


# ─── Context Manager ───────────────────────────────────────────────────────────
@contextmanager
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB Error: {e}")
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  USER OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_user(telegram_id: int, username: str = None, full_name: str = None) -> User:
    """Create or update user record"""
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.last_active = datetime.utcnow()
            if username:
                user.username = username
            if full_name:
                user.full_name = full_name
        else:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
            )
            db.add(user)
        return user


def get_user(telegram_id: int) -> User | None:
    with get_db() as db:
        return db.query(User).filter(User.telegram_id == telegram_id).first()


def get_total_users() -> int:
    with get_db() as db:
        return db.query(func.count(User.id)).scalar()


# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOAD OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def log_download(
    telegram_id: int,
    url: str,
    platform: str,
    content_type: str,
    action: str,
    title: str = None,
    uploader: str = None,
    filesize: int = 0,
    duration: int = 0,
    success: bool = True,
    error_msg: str = None,
    ai_confidence: float = 0.0,
) -> Download:
    """Log a download attempt to the database"""
    with get_db() as db:
        # Log download
        dl = Download(
            telegram_id=telegram_id,
            url=url,
            platform=platform,
            content_type=content_type,
            action=action,
            title=title,
            uploader=uploader,
            filesize=filesize,
            duration=duration,
            success=success,
            error_msg=error_msg,
            ai_confidence=ai_confidence,
        )
        db.add(dl)

        # Increment user total
        if success:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.total_downloads += 1

        return dl


def get_user_history(telegram_id: int, limit: int = 10) -> list[Download]:
    """Get last N downloads for a user"""
    with get_db() as db:
        return (
            db.query(Download)
            .filter(Download.telegram_id == telegram_id, Download.success == True)
            .order_by(Download.downloaded_at.desc())
            .limit(limit)
            .all()
        )


def get_user_stats(telegram_id: int) -> dict:
    """Get download statistics for a user"""
    with get_db() as db:
        total = db.query(func.count(Download.id)).filter(
            Download.telegram_id == telegram_id,
            Download.success == True,
        ).scalar()

        # By content type
        by_type = db.query(
            Download.content_type,
            func.count(Download.id).label("count"),
        ).filter(
            Download.telegram_id == telegram_id,
            Download.success == True,
        ).group_by(Download.content_type).all()

        # Top platform
        top_platform = db.query(
            Download.platform,
            func.count(Download.id).label("count"),
        ).filter(
            Download.telegram_id == telegram_id,
            Download.success == True,
        ).group_by(Download.platform).order_by(func.count(Download.id).desc()).first()

        # Total data downloaded
        total_bytes = db.query(func.sum(Download.filesize)).filter(
            Download.telegram_id == telegram_id,
            Download.success == True,
        ).scalar() or 0

        return {
            "total": total,
            "by_type": {row.content_type: row.count for row in by_type},
            "top_platform": top_platform.platform if top_platform else "N/A",
            "top_platform_count": top_platform.count if top_platform else 0,
            "total_bytes": total_bytes,
        }


def get_global_stats() -> dict:
    """Bot-wide statistics"""
    with get_db() as db:
        total_dl   = db.query(func.count(Download.id)).filter(Download.success == True).scalar()
        total_users = db.query(func.count(User.id)).scalar()
        total_bytes = db.query(func.sum(Download.filesize)).filter(Download.success == True).scalar() or 0

        top_platforms = db.query(
            Download.platform,
            func.count(Download.id).label("count"),
        ).filter(Download.success == True).group_by(Download.platform)\
         .order_by(func.count(Download.id).desc()).limit(5).all()

        return {
            "total_downloads": total_dl,
            "total_users": total_users,
            "total_bytes": total_bytes,
            "top_platforms": [(r.platform, r.count) for r in top_platforms],
        }


# ══════════════════════════════════════════════════════════════════════════════
#  SUMMARY OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def save_summary(telegram_id: int, url: str, title: str, summary_text: str) -> Summary:
    with get_db() as db:
        s = Summary(
            telegram_id=telegram_id,
            url=url,
            title=title,
            summary_text=summary_text,
        )
        db.add(s)
        return s


def get_cached_summary(url: str) -> Summary | None:
    """Return cached summary if exists"""
    with get_db() as db:
        return db.query(Summary).filter(Summary.url == url).first()


# ══════════════════════════════════════════════════════════════════════════════
#  USER PREFERENCES
# ══════════════════════════════════════════════════════════════════════════════

def get_preferences(telegram_id: int) -> UserPreference:
    with get_db() as db:
        pref = db.query(UserPreference).filter(UserPreference.telegram_id == telegram_id).first()
        if not pref:
            pref = UserPreference(telegram_id=telegram_id)
            db.add(pref)
        return pref


def update_preference(telegram_id: int, **kwargs) -> UserPreference:
    with get_db() as db:
        pref = db.query(UserPreference).filter(UserPreference.telegram_id == telegram_id).first()
        if not pref:
            pref = UserPreference(telegram_id=telegram_id)
            db.add(pref)
        for key, val in kwargs.items():
            if hasattr(pref, key):
                setattr(pref, key, val)
        return pref
