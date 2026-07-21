from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    student_answer: str | None = None
    correct_answer: str | None = None
    knowledge_point: str | None = Field(default=None, max_length=128)

    @field_validator("content", "knowledge_point", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: object):
        return value.strip() if isinstance(value, str) else value


class ModelQuestion(BaseModel):
    question_number: str
    question_text: str = Field(min_length=1)
    student_answer: str | None = None
    correct_answer: str | None = None
    question_type: str | None = None
    knowledge_point: str | None = None
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    is_correct: bool
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def score_must_not_exceed_max_score(self):
        if self.score > self.max_score:
            raise ValueError("question score cannot exceed max_score")
        return self


class ModelGradePayload(BaseModel):
    subject: str
    questions: list[ModelQuestion] = Field(min_length=1)
    total_score: float = Field(ge=0)
    student_score: float = Field(ge=0)
    overall_comment: str = Field(min_length=1)
    weak_points: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def total_score_must_be_valid(self):
        if self.student_score > self.total_score:
            raise ValueError("assignment score cannot exceed total_score")
        return self
