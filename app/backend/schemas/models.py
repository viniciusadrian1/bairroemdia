from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


Category = Literal['pothole', 'sound']


class ImageInput(StrictModel):
    image_base64: str = Field(min_length=1, max_length=7_000_000)


class AudioInput(StrictModel):
    audio_base64: str = Field(min_length=1, max_length=4_000_000)
    client_request_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_.-]+$')


class ReportInput(StrictModel):
    client_request_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.-]+$')
    description: str = Field(min_length=10, max_length=2000)
    neighborhood: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_confirmed: Literal[True]
    category: Category = 'pothole'
    image_base64: str | None = Field(default=None, max_length=7_000_000)
    sound_event_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r'^[\w.-]+$')


class ReviewInput(StrictModel):
    approved: bool
    corrected_category: Category
    note: str = Field(default='', max_length=500)


class StatusInput(StrictModel):
    status: Literal['in_progress', 'resolved']


class Message(StrictModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=3000)


class AssistantInput(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    history: list[Message] = Field(default_factory=list, max_length=10)


class Source(StrictModel):
    id: str
    title: str
    url: str
    excerpt: str


class AssistantResponse(StrictModel):
    answer: str = Field(min_length=1, max_length=6000)
    sources: list[Source]
    abstained: bool
    mode: str
    warnings: list[str] = Field(default_factory=list)


class Generation(StrictModel):
    answer: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(max_length=3)
    evidence_quotes: list[str] = Field(max_length=3)
    abstained: bool


class SoundEvent(StrictModel):
    event_id: str = Field(min_length=1, max_length=100, pattern=r'^[\w.-]+$')
    label: Literal['campainha', 'batida', 'ambiente']
    confidence: float = Field(ge=0, le=1)
    source: Literal['manual', 'edge_impulse']
    model_version: str = Field(min_length=1, max_length=100)
    observed_at: AwareDatetime
