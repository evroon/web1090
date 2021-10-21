import io

from starlette.responses import FileResponse

from data import ADSBData
from fastapi import FastAPI, Response, Query, BackgroundTasks
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from fastapi_cache.backends.inmemory import InMemoryBackend
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

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
async def flights(background_tasks: BackgroundTasks):
    data.background_tasks = background_tasks
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
async def aircrafttypes(by_family: bool = True):
    return data.get_aircrafttypes(by_family)


@app.get(
    '/registrations',
    summary="Get registrations",
)
@cache(expire=60)
async def registrations():
    return data.get_registrations()


@app.get(
    '/ac_icon.svg',
    summary="Get icons of an aircraft category",
)
async def icons(category: str = None, adsb_category: str = None, color: str = None, is_selected: bool = False):
    icon_svg = data.get_ac_icon(category, adsb_category, color, is_selected)
    return Response(content=icon_svg, media_type="image/svg+xml")


@app.get(
    '/airline_icon.svg',
    summary="Get icon of an airline",
)
async def icons(iata: str = 'KL'):
    icon_png = data.get_airline_icon(iata)
    return FileResponse(icon_png)


@app.get(
    '/image',
    summary="Get aircraft image",
)
async def image(
    icao: str = Query(None, title='test', description='ICAO hex code of aircraft'),
    i: int = Query(0, description='index of the image'),
    as_thumbnail: bool = Query(False, description='Load as thumbnail or as full image')
):
    image_png = data.get_aircraft_image(icao, i, as_thumbnail)
    return FileResponse(image_png)


@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
