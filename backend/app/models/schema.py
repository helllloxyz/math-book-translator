from sqlalchemy import Column, Float, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid
from .base import Base
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, List, Any

class BookStatus(enum.Enum):
    loaded = "loaded"
    translating = "translating"
    translated = "translated"
    generating = "generating"
    generating_guides = "generating_guides"
    failed = "failed"

class AgentStage(enum.Enum):
    init = "init"
    architecting = "architecting"
    reviewing = "reviewing"
    confirmed = "confirmed"
    writing = "writing"
    ready = "ready"

class BookType(enum.Enum):
    uploaded = "uploaded"
    generated = "generated"

class NoteType(enum.Enum):
    translation = "translation"
    explanation = "explanation"
    custom_note = "custom_note"
    chapter_chat = "chapter_chat"
    selection_chat = "selection_chat"
    quiz_chat = "quiz_chat"
    annotation = "annotation"

# --- SQLAlchemy Models ---

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, index=True)
    original_filename = Column(String)
    status = Column(SAEnum(BookStatus), default=BookStatus.loaded)
    translation_total = Column(Integer, default=0)
    translation_completed = Column(Integer, default=0)
    translation_failed = Column(Integer, default=0)
    type = Column(SAEnum(BookType), default=BookType.uploaded)
    agent_stage = Column(SAEnum(AgentStage), default=AgentStage.init)
    vision = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    chapters = relationship("Chapter", back_populates="book")

class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"))
    chapter_index = Column(String) # e.g., "17.1"
    title_en = Column(String)
    title_zh = Column(String, nullable=True)
    content_type = Column(String, default="main_text")
    # Content is now stored in files
    order = Column(Integer)

    book = relationship("Book", back_populates="chapters")
    notes = relationship("UserNote", back_populates="chapter")

class UserNote(Base):
    __tablename__ = "user_notes"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    source_type = Column(String, nullable=True, index=True)
    source_id = Column(String, nullable=True, index=True)
    source_title = Column(String, nullable=True)
    selected_text = Column(Text)
    title = Column(String, nullable=True)
    start_index = Column(Integer, default=0)
    note_content = Column(Text)
    type = Column(SAEnum(NoteType))
    created_at = Column(DateTime, default=datetime.utcnow)

    chapter = relationship("Chapter", back_populates="notes")

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True, index=True)
    quiz_mode = Column(String, default="chapter", server_default="chapter", nullable=False, index=True)
    source = Column(String, default="generated", index=True)
    question_type = Column(String, nullable=False, index=True)
    difficulty = Column(String, default="medium", index=True)
    target_concepts = Column(JSON, default=list)
    question_text = Column(Text, nullable=False)
    expected_points = Column(JSON, default=list)
    common_mistakes = Column(JSON, default=list)
    context_refs = Column(JSON, default=list)
    evaluation_rubric = Column(JSON, default=dict)
    followup_strategy = Column(Text, nullable=True)
    times_seen = Column(Integer, default=0)
    attempts_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    book = relationship("Book")
    chapter = relationship("Chapter")
    attempts = relationship("QuizAttempt", back_populates="question")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True, index=True)
    answer_text = Column(Text, nullable=False)
    evaluation_status = Column(String, nullable=False, index=True)
    score = Column(Float, nullable=True)
    missing_points = Column(JSON, default=list)
    feedback_text = Column(Text, nullable=True)
    followup_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("QuizQuestion", back_populates="attempts")
    book = relationship("Book")
    chapter = relationship("Chapter")

# --- Pydantic Schemas ---

class AskLLMRequest(BaseModel):
    context: str
    prompt: str

class ChatRequest(BaseModel):
    context: str
    messages: List[Dict]
    mode: str = "chat"

class QuizNextRequest(BaseModel):
    quiz_mode: str = "chapter"
    question_type: Optional[str] = None
    personalization_context: Optional[str] = None
    count: int = Field(default=1, ge=1, le=3)
    previous_questions: List[str] = Field(default_factory=list, max_length=30)

class QuizAttemptRequest(BaseModel):
    answer_text: str
    conversation_history: List[Dict] = Field(default_factory=list)

class QuizSelectTargetRequest(BaseModel):
    personalization_context: Optional[str] = None

class QuizQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    chapter_id: Optional[int] = None
    quiz_mode: str = "chapter"
    source: str
    question_type: str
    question_type_label: str = ""
    difficulty: str
    target_concepts: List[str] = []
    question_text: str
    expected_points: List[str] = []
    common_mistakes: List[str] = []
    context_refs: List[Dict[str, Any]] = []
    evaluation_rubric: Dict[str, Any] = {}
    followup_strategy: Optional[str] = None
    answer_guidance: str = ""


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    note_content: Optional[str] = None

class GenerateTitleRequest(BaseModel):
    context: str
    prompt: str

class CreateNoteRequest(BaseModel):
    book_id: Optional[int] = None
    chapter_id: Optional[int] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_title: Optional[str] = None
    selected_text: Optional[str] = None
    start_index: int = 0
    note_content: str
    title: Optional[str] = None
    type: str  # NoteType value, including chat, quiz, and reader annotation records.

class ImportBookRequest(BaseModel):
    file_path: str
    force: bool = False
    preflight: bool = True
    outline_selection: Optional[List[str]] = None
    outline_plan: Optional[Dict[str, Any]] = None

class LLMProfile(BaseModel):
    provider_id: Optional[str] = None
    provider_type: str = "openai_compatible"
    credential_id: Optional[str] = None
    model: Optional[str] = None

class SettingsRequest(BaseModel):
    storage_path: Optional[str] = None
    llm_profile: Optional[LLMProfile] = None
    llm_profiles: Optional[Dict[str, LLMProfile]] = None
    learning_profile_enabled: Optional[bool] = None


class ChapterReadingStatusRequest(BaseModel):
    chapter_id: int
    progress: str = "unread"
    difficulty: str = "unmarked"


class LearningProfileCheckRequest(BaseModel):
    reading_statuses: List[ChapterReadingStatusRequest] = Field(default_factory=list)
    current_chapter_id: Optional[int] = None

class CredentialWriteRequest(BaseModel):
    credential_id: str
    provider_type: str = "openai_compatible"
    provider_id: Optional[str] = None
    api_key: str
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    models: Optional[List[str]] = []
    headers: Optional[Dict[str, str]] = {}

class CredentialUpdateRequest(BaseModel):
    credential_id: Optional[str] = None
    provider_type: Optional[str] = None
    provider_id: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    models: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None

class RenameBookRequest(BaseModel):
    title: str

class LatexRepairSuggestRequest(BaseModel):
    selected_text: str
    content_target: str = "translated"
    failed_candidates: List[str] = Field(default_factory=list)

class LatexRepairApplyRequest(BaseModel):
    original_text: str
    replacement_text: str
    content_target: str = "translated"

class AgentInitRequest(BaseModel):
    domain: str

class AgentInteractRequest(BaseModel):
    message: str

class BuildStructureRequest(BaseModel):
    book_id: int

class ConfirmStructureRequest(BaseModel):
    book_id: int
    manifest: Dict[str, Any]

class RegenerateNodeRequest(BaseModel):
    book_id: int
    node_id: str
    instruction: Optional[str] = None
