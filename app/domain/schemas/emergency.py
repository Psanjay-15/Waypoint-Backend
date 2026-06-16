from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.domain.schemas.places import PlaceOut


class EmergencyContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_name: str
    kind: str
    phone: str
    url: str | None = None
    hours: str
    city: str | None = None


class EmergencyDirectoryResponse(BaseModel):
    state: str
    city: str
    note: str = "For immediate life-threatening emergencies, always call 911."
    contacts: list[EmergencyContactOut]
    local_facilities: list[PlaceOut] = []
