from pydantic import BaseModel, Field, field_validator, validator
# need to find new package without vulnerability:  from bson import ObjectId
from datetime import datetime
from typing import Optional, Literal
import pytz
from datetime import datetime
from pydantic import BaseModel, Field
from dateutil import parser

class PyObjectId(ObjectId):
    """ Custom Validator for reading ObjectId from MongoDB """
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, values):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid ObjectId')
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type='string')



class AppointmentCreate(BaseModel):
    patientID: str
    doctorID: Optional[str] = None
    appointmentDateTime: str
    appointmentType: str
    duration: int
    status: str
    reason: str
    appointmentRoute: str

    @field_validator('appointmentDateTime')
    @classmethod
    def parse_datetime(cls, value):
        try:
            # Parse the datetime string and set it to UTC
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=pytz.UTC)
        except ValueError:
            raise ValueError(f"Invalid datetime format: {value}. Expected format: YYYY-MM-DD HH:M:S")

    class Config:
        json_schema_extra = {
            "example": {
                "patientID": "66c3c30c6f4db7e5fdc7c8e5",
                "doctorID": "",
                "appointmentDateTime": "2024-09-05 14:00:00",
                "appointmentType": "skin peel",
                "duration": 60,
                "status": "requested",
                "reason": "I need a skin peel",
                "appointmentRoute": "Aesthetician"
            }
        }
class AppointmentRead(BaseModel):
    appointmentId: Optional[str] = Field(default_factory=str)
    patientID: str
    doctorID: str
    appointmentDateTime: datetime
    appointmentType: str
    duration: int
    status: Optional[str]
    reason: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.now)

class AppointmentUpdate(BaseModel):
    patientID: Optional[str] = None
    doctorID: Optional[str] = None
    appointmentDateTime: Optional[datetime] = None
    appointmentType: Optional[str] = None
    duration: Optional[int] = None
    status: Optional[Literal['requested', 'confirmed', 'cancelled']] = None
    reason: Optional[str] = None
    appointmentRoute: Optional[str] = None

    @validator('appointmentDateTime', pre=True)
    def parse_datetime(cls, value):
        if isinstance(value, str):
            try:
                return parser.parse(value)
            except ValueError:
                raise ValueError("Invalid datetime format. Use ISO format or human-readable format (e.g., 'October 31st 2:00pm')")
        return value
class AppointmentDelete(BaseModel):
    appointmentDateTime: Optional[datetime]
    reason: Optional[str]
    updatedAt: datetime = Field(default_factory=datetime.now)

from pydantic import BaseModel, Field
from datetime import datetime

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from datetime_helper import format_datetime_for_tts

class AppointmentResponse(BaseModel):
    _id: str
    patientID: str
    doctorID: str
    appointmentDateTime: datetime
    formattedDateTime: str = ""
    appointmentType: str
    duration: int
    status: str
    reason: str
    appointmentRoute: str
    createdAt: datetime
    updatedAt: datetime
    endDateTime: datetime
    message: str = ""

    class Config:
        allow_population_by_field_name = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.appointmentDateTime:
            self.formattedDateTime = format_datetime_for_tts(self.appointmentDateTime)