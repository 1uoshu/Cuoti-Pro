from typing import Literal

from pydantic import BaseModel, Field, field_validator


PracticeDifficulty = Literal["基础补漏", "同类变式", "综合提升", "高考真题"]


class PracticeCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=32)
    knowledge_point: str = Field(min_length=1, max_length=128)
    difficulty: PracticeDifficulty
    question_count: int = Field(default=5, ge=1, le=10)

    @field_validator("subject", "knowledge_point", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object):
        return value.strip() if isinstance(value, str) else value


class PracticeAnswerInput(BaseModel):
    question_id: int
    answer: str = Field(min_length=1, max_length=5000)


class PracticeSubmitRequest(BaseModel):
    answers: list[PracticeAnswerInput] = Field(min_length=1)


class ModelPracticeQuestion(BaseModel):
    content: str = Field(min_length=1)
    standard_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    knowledge_point: str = Field(min_length=1, max_length=128)
    confidence: float = Field(default=0, ge=0, le=1)
    confidence_warning: str | None = None


class ModelPracticePayload(BaseModel):
    questions: list[ModelPracticeQuestion] = Field(min_length=1)

    @field_validator("questions")
    @classmethod
    def no_duplicate_questions(cls, questions: list[ModelPracticeQuestion]):
        normalized = [item.content.strip() for item in questions]
        if len(normalized) != len(set(normalized)):
            raise ValueError("practice generation returned duplicate questions")
        return questions
