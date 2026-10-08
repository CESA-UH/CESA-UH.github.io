from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Login(Input):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.lower()
        if "@" not in value or not value.split("@")[-1] or " " in value:
            raise ValueError("ایمیل معتبر وارد کنید.")
        return value


class Register(Login):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Literal["student", "teacher"] = "student"


class CourseInput(Input):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)


class TopicInput(Input):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)


class JoinInput(Input):
    code: str = Field(min_length=6, max_length=32)


class ReportInput(Input):
    topic_id: int = Field(gt=0)
    confidence: int = Field(ge=1, le=5)
    difficulty: Literal["none", "concept", "practice", "prerequisite", "time"]
    study_minutes: int = Field(ge=0, le=1440)
    note: str = Field(default="", max_length=2000)


class ThreadInput(Input):
    title: str = Field(default="گفت‌وگوی جدید", min_length=1, max_length=120)


class ChatInput(Input):
    message: str = Field(min_length=2, max_length=2000)
    thread_id: int | None = Field(default=None, gt=0)
    topic_id: int | None = Field(default=None, gt=0)


class TopicBatchInput(Input):
    topics: list[TopicInput] = Field(min_length=1, max_length=200)


class ReportFieldInput(Input):
    label: str = Field(min_length=1, max_length=300)
    kind: Literal['text', 'scale', 'choice'] = 'text'
    required: bool = True
    options: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('options')
    @classmethod
    def valid_options(cls, values):
        if any(not v.strip() or len(v) > 200 for v in values) or len(set(values)) != len(values):
            raise ValueError('گزینه‌ها باید غیرخالی و بدون تکرار باشند.')
        return [v.strip() for v in values]


class ReportFormInput(Input):
    title: str = Field(min_length=1, max_length=255)
    instructions: str = Field(default='', max_length=2000)
    topic_ids: list[int] = Field(min_length=1, max_length=200)
    fields: list[ReportFieldInput] = Field(default_factory=list, max_length=20)


class FormReportInput(ReportInput):
    answers: dict[str, str | int] = Field(default_factory=dict)


class QuizQuestionInput(Input):
    topic_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=5000)
    kind: Literal['choice', 'short'] = 'choice'
    options: list[str] = Field(default_factory=list, max_length=8)
    correct_choice: int | None = Field(default=None, ge=0, le=7)
    points: int = Field(default=1, ge=1, le=100)


class QuizInput(Input):
    title: str = Field(min_length=1, max_length=255)
    instructions: str = Field(default='', max_length=2000)
    starts_at: str
    ends_at: str
    duration_minutes: int = Field(ge=1, le=180)
    questions: list[QuizQuestionInput] = Field(min_length=1, max_length=100)


class QuizAnswerInput(Input):
    value: str = Field(max_length=10000)


class QuizGradeInput(Input):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    feedback: str = Field(default='', max_length=2000)
