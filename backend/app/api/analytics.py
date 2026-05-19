from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.analytics_service import (
    get_overview, get_workload_list, get_completion_buckets, get_delegation_flow,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_overview(db)


@router.get("/workload")
def workload(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_workload_list(db)


@router.get("/completion")
def completion(
    period: str = Query("month", pattern="^(year|quarter|month|week)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_completion_buckets(db, period)


@router.get("/delegation-flow")
def delegation_flow(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_delegation_flow(db)
