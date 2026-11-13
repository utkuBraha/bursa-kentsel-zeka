from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import demo_models as inventory
from .coverage import router as coverage_router
from .dashboard import router as dashboard_router
from .db import get_db
from .geography import router as geography_router
from .inventory import router as inventory_router
from .models import DataSource, District, Neighborhood
from .routing import router as routing_router
from .schemas import DistrictPage, SystemOut

app = FastAPI(
    title="Bursa Kentsel Zekâ API",
    version="0.4.0",
    description="Bursa 17 ilçe yerel çalışma alanı. Sentetik demo envanteri.",
)

for router in (
    geography_router,
    inventory_router,
    coverage_router,
    dashboard_router,
    routing_router,
):
    app.include_router(router)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Veri altyapısına erişilemiyor. Lütfen yeniden deneyin."},
    )


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def ready(db: Session = Depends(get_db)):
    version = db.scalar(text("SELECT postgis_lib_version()"))
    revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != "0004":
        raise HTTPException(503, "Veritabanı şeması hazır değil.")
    return {"status": "ready", "postgis": version, "migration": revision}


@app.get("/api/v1/system", response_model=SystemOut, tags=["System"])
def system(db: Session = Depends(get_db)):
    return dict(
        status="ready",
        phase=5,
        district_count=db.scalar(select(func.count()).select_from(District)),
        active_district_count=db.scalar(
            select(func.count()).select_from(District).where(District.active.is_(True))
        ),
        geometry_count=db.scalar(
            select(func.count()).select_from(District).where(District.geom.is_not(None))
        ),
        household_count=db.scalar(
            select(func.count()).select_from(inventory.households)
        ),
        service_count=db.scalar(
            select(func.count()).select_from(inventory.service_points)
        ),
        neighborhood_count=db.scalar(select(func.count()).select_from(Neighborhood)),
        source_count=db.scalar(select(func.count()).select_from(DataSource)),
        postgis_version=db.scalar(text("SELECT postgis_lib_version()")),
        data_notice="İlçe ve mahalle sınırları resmî kaynaklardan alınmıştır. Demo haneleri ve hizmetleri sentetik, doğrulanmış yerleşke noktası gerçek kaynaklıdır.",
    )


@app.get("/api/v1/geography/districts", response_model=DistrictPage, tags=["Geography"])
def districts(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
):
    statement = select(District)
    if q:
        statement = statement.where(District.name.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.scalars(
        statement.order_by(District.name).limit(limit).offset(offset)
    ).all()
    return dict(items=rows, total=total, limit=limit, offset=offset)
