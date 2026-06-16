from fastapi import APIRouter, Query

from app.api.v1.deps import SessionDep
from app.core.constants import EMERGENCY_KINDS
from app.core.exceptions import UnknownStateError, ValidationError
from app.core.logging import get_logger
from app.db.repositories.emergency_repo import emergency_repo
from app.db.repositories.state_repo import state_repo
from app.domain.schemas.emergency import EmergencyContactOut, EmergencyDirectoryResponse
from app.domain.services.places_service import places_service

router = APIRouter()
log = get_logger(__name__)


@router.get("/states/{code}/emergency", response_model=EmergencyDirectoryResponse)
async def emergency_directory(
    code: str,
    db: SessionDep,
    kind: str | None = Query(None),
    city: str | None = Query(
        None, description="City for nearby facilities; defaults to the capital"
    ),
) -> EmergencyDirectoryResponse:
    code = code.strip().upper()
    state = await state_repo.get(db, code)
    if state is None:
        raise UnknownStateError(f"Unknown or unsupported state '{code}'")
    if kind is not None and kind not in EMERGENCY_KINDS:
        raise ValidationError(f"kind must be one of: {', '.join(EMERGENCY_KINDS)}")

    contacts = await emergency_repo.list_for_state(db, code, kind)
    target_city = (city or state.capital).strip()

    facilities = []
    try:
        explored = await places_service.explore(
            code, state.name, target_city, ["hospital", "police", "fire"], radius=8000
        )
        facilities = explored.places
    except Exception as exc:
        log.warning(
            "emergency facilities lookup failed for %s/%s: %s", code, target_city, exc
        )

    return EmergencyDirectoryResponse(
        state=code,
        city=target_city,
        contacts=[EmergencyContactOut.model_validate(c) for c in contacts],
        local_facilities=facilities,
    )
