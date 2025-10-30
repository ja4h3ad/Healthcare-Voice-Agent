# app/entities/physician.py

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class DoctorBase(BaseModel):
    firstName: str
    lastName: str
    specialty: str
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
