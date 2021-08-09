import io

from data import ADSBData
from fastapi import FastAPI, Response
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from fastapi_cache.backends.inmemory import InMemoryBackend
from starlette.middleware.cors import CORSMiddleware

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

data = ADSBData()


@cache()
async def get_cache():
    return 1

@app.get(
    '/liveflights',
    summary="Get currently detected flights",
)
async def flights():
    return data.get_live_flights()


@app.get(
    '/statistics',
    summary="Get flight data",
)
@cache(expire=60)
async def statistics():
    return data.get_statistics()


@app.get(
    '/flights',
    summary="Get flight data",
)
@cache(expire=60)
async def flights():
    return data.get_flights()


@app.get(
    '/aircrafttypes',
    summary="Get aircrafttypes",
)
@cache(expire=60)
async def aircrafttypes():
    return data.get_aircrafttypes()


@app.get(
    '/registrations',
    summary="Get registrations",
)
@cache(expire=60)
async def registrations():
    return data.get_registrations()


@app.get(
    '/icon.svg',
    summary="Get icons of aircraft",
)
async def icons(category: str = 'airliner', color: str = '#a434eb'):
    icon_svg = data.get_icon(category, color)
    return Response(content=icon_svg, media_type="image/svg+xml")
    # return FileResponse(icon_svg, media_type="image/svg")



@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
