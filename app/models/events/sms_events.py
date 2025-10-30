# app/models/events/sms_event.py
from pydantic import BaseModel, Field
from typing import Optional, Dict

class InboundSMSEvent(BaseModel):  # More descriptive name
    channel: str
    message_uuid: str
    to: str
    from_: str = Field(alias="from")
    timestamp: str
    text: str
    sms: Optional[Dict[str, str]] = None
    usage: Optional[Dict[str, str]] = None
    origin: Optional[Dict[str, str]] = None

    model_config = {"populate_by_name": True}





