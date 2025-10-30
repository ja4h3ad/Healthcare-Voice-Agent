from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from bson import ObjectId

class Patient(BaseModel):
    firstName: str
    lastName: str
    dob: datetime
    mobileNumber: str
    accountNumber: str
    streetAddress: str
    city: str
    state: str
    postCode: str
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)

    @field_validator('dob')
    def parse_dob(cls, value, field):
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator('createdAt', 'updatedAt')
    def parse_timestamps(cls, value, field):
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return value

    class Config:
        json_encoders = {
            ObjectId: lambda oid: str(oid),  # Convert ObjectId to string for JSON serialization
        }

class DoctorBase(BaseModel):
    firstName: str
    lastName: str
    specialty: str
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)

class AestheticianBase(BaseModel):
    firstName: str
    lastName: str
    specialty: str
    qualifications: list = []
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
