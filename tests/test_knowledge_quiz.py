"""Tests for Knowledge Base & AI Quiz Engine."""
import pytest

from src.services.ai.knowledge_quiz import (
    QuizQuestion,
    QuizSubmission,
    KnowledgeQuizEngine,
    QuizGradingResult,
)


def test_built_in_quiz_questions_exist():
    engine = KnowledgeQuizEngine()
    questions = engine.get_questions()
    assert len(questions) >= 6
    categories = set(q.category for q in questions)
    assert "objections" in categories
    assert "qualification" in categories
    assert "pricing" in categories


def test_quiz_grading_passed():
    engine = KnowledgeQuizEngine()
    questions = engine.get_questions()
    
    # Answer all correctly
    answers = {q.question_id: q.correct_option for q in questions}
    submission = QuizSubmission(user_id="usr_1", answers=answers)
    result = engine.grade_quiz(submission)

    assert result.score_pct == 100.0
    assert result.passed is True
    assert result.correct_count == len(questions)
    assert result.total_count == len(questions)
    assert len(result.feedback) > 0


def test_quiz_grading_failed():
    engine = KnowledgeQuizEngine()
    questions = engine.get_questions()
    
    # Answer all wrong
    answers = {q.question_id: "WRONG" for q in questions}
    submission = QuizSubmission(user_id="usr_2", answers=answers)
    result = engine.grade_quiz(submission)

    assert result.score_pct == 0.0
    assert result.passed is False
    assert result.correct_count == 0
    assert "qayta oʻqib chiqish" in result.feedback.lower()
