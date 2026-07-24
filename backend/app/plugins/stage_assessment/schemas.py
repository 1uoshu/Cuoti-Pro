from typing import Literal

from pydantic import BaseModel, Field, field_validator


ExamType = Literal["专项小测", "单元卷", "模拟卷", "高考专题卷"]
ExamDifficulty = Literal["基础", "中等", "较难", "混合难度"]


class ExamCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=32)
    exam_type: ExamType = "单元卷"
    knowledge_points: list[str] = Field(default_factory=list, max_length=20)
    difficulty: ExamDifficulty = "混合难度"
    question_count: int = Field(default=20, ge=5, le=50)

    @field_validator("subject", mode="before")
    @classmethod
    def normalize_subject(cls, value: object):
        return value.strip() if isinstance(value, str) else value

    @field_validator("knowledge_points")
    @classmethod
    def normalize_knowledge_points(cls, values: list[str]):
        normalized = list(dict.fromkeys(item.strip() for item in values if item.strip()))
        if "all" in normalized and len(normalized) > 1:
            raise ValueError('"all" 不能与具体知识点同时提交')
        if any(len(item) > 128 for item in normalized):
            raise ValueError("知识点名称不能超过 128 个字符")
        return normalized


class ModelExamQuestion(BaseModel):
    content: str = Field(min_length=1)
    standard_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    knowledge_point: str = Field(min_length=1, max_length=128)
    confidence: float = Field(default=0, ge=0, le=1)
    confidence_warning: str | None = None

    @field_validator("content", "standard_answer", "explanation", "knowledge_point", mode="before")
    @classmethod
    def normalize_text(cls, value: object):
        return value.strip() if isinstance(value, str) else value


class ModelExamPayload(BaseModel):
    questions: list[ModelExamQuestion] = Field(min_length=1)

    @field_validator("questions")
    @classmethod
    def no_duplicate_questions(cls, questions: list[ModelExamQuestion]):
        contents = [item.content for item in questions]
        if len(contents) != len(set(contents)):
            raise ValueError("exam generation returned duplicate questions")
        return questions
