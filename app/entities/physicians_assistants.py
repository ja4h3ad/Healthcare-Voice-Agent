# app/entities/physicians_assistants.py

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
class PhysicianAssistantBase(BaseModel):
    firstName: str
    lastName: str
    specialty: str
    qualifications: list = []
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
