from typing import Any, Dict, List, Optional, Union

import crud
import models
from config import Config
from data import ADSBData
from database import SessionLocal, engine
from fastapi import FastAPI, Query, Response
from fastapi.params import Depends
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from responses import DUMP1090Response
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, StreamingResponse

models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="DUMP1090 PSQL API",
    description='<b>DUMP1090 PSQL API</b><br>',
    docs_url="/",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@cache()
async def get_cache() -> int:
    return 1


config = Config()


@app.get(
    '/liveflights',
    summary="Get currently detected flights",
)
async def liveflights(db: Session = Depends(get_db)) -> DUMP1090Response:
    data = ADSBData(db, config)
    return data.get_live_flights()


@app.get(
    '/statistics',
    summary="Get flight data",
)
@cache(expire=60)
async def statistics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    data = ADSBData(db, config)
    return data.get_statistics()


@app.get(
    '/routes',
    summary="Get route data",
)
@cache(expire=60)
async def routes(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> List[models.Route]:
    return crud.get_routes_paginated(db, skip, limit)


@app.get(
    '/aircraft',
    summary="Get aircraft",
)
@cache(expire=60)
async def aircraft(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> List[models.Aircraft]:
    return crud.get_aircraft_paginated(db, skip, limit)


@app.get(
    '/ac_icon.svg',
    summary="Get icons of an aircraft category",
)
async def ac_icon(
    category: str = None,
    adsb_category: str = None,
    color: str = None,
    is_selected: bool = False,
    db: Session = Depends(get_db),
) -> Response:
    data = ADSBData(db, config)
    icon_svg = data.get_ac_icon(category, adsb_category, color, is_selected)
    return Response(content=icon_svg, media_type="image/svg+xml")


@app.get(
    '/airline_icon.svg',
    summary="Get icon of an airline",
)
async def airline_icon(iata: str = 'KL', db: Session = Depends(get_db)) -> Optional[FileResponse]:
    data = ADSBData(db, config)
    icon_png = data.get_airline_icon(iata)
    if icon_png is not None:
        return FileResponse(icon_png)

    return None


@app.get(
    '/image',
    summary="Get aircraft image",
)
async def image(
    icao: str = Query(None, title='test', description='ICAO hex code of aircraft'),
    i: int = Query(0, description='index of the image'),
    as_thumbnail: bool = Query(False, description='Load as thumbnail or as full image'),
    db: Session = Depends(get_db),
) -> Union[FileResponse, StreamingResponse]:
    data = ADSBData(db, config)
    image_png = data.get_aircraft_image(icao, i, as_thumbnail)

    if image_png is not None:
        return FileResponse(image_png)

    return StreamingResponse(
        data.stream_aircraft_image(icao, i, as_thumbnail), media_type="image/png"
    )


@app.on_event("startup")
async def startup() -> None:
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
