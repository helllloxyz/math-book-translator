from app.models.schema import NoteType


def test_learning_note_types_exist():
    assert NoteType.chapter_chat.value == "chapter_chat"
    assert NoteType.selection_chat.value == "selection_chat"
    assert NoteType.quiz_chat.value == "quiz_chat"
    assert NoteType.custom_note.value == "custom_note"
    assert NoteType.annotation.value == "annotation"
