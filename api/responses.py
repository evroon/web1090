from typing import Iterator, List, Optional

from pydantic import BaseModel

from models import Aircraft, Airline, Route


class AircraftImagePayload(BaseModel):
    thumbnail_endpoint: str
    image_endpoint: str


class DUMP1090Signal(BaseModel):
    hex: str
    flight: Optional[str]
    route: Optional[Route]
    airline_icon: Optional[str]
    alt_baro: Optional[float]
    alt_geom: Optional[float]
    lat: Optional[float]
    lon: Optional[float]
    gs: Optional[float]
    ias: Optional[int]
    tas: Optional[int]
    mach: Optional[float]
    track: Optional[float]
    track_rate: Optional[float]
    roll: Optional[float]
    mag_heading: Optional[float]
    baro_rate: Optional[int]
    geom_rate: Optional[int]
    squawk: Optional[str]
    nav_qnh: Optional[int]
    nav_altitude_mcp: Optional[int]
    nav_altitude_fms: Optional[int]
    nav_modes: Optional[List[str]]
    version: Optional[int]
    nic_baro: Optional[int]
    nac_p: Optional[int]
    nac_v: Optional[int]
    sil: Optional[int]
    sil_type: Optional[str]
    gva: Optional[int]
    sda: Optional[int]
    modea: Optional[bool]
    messages: Optional[int]
    seen: Optional[float]
    rssi: Optional[float]
    registration: Optional[str]
    aircrafttype: Optional[str]
    icon_category: Optional[str]
    country: Optional[str]
    images: Optional[List[AircraftImagePayload]]

    class Config:
        arbitrary_types_allowed = True


class DUMP1090Response(BaseModel):
    aircraft: List[DUMP1090Signal]

    def __iter__(self) -> Iterator[DUMP1090Signal]:  # type: ignore
        return iter(self.aircraft)


class AviationStackPagination(BaseModel):
    limit: int
    offset: int
    count: int
    total: int


class AviationStackAirline(BaseModel):
    id: int
    airline_name: Optional[str]
    iata_code: Optional[str]
    iata_prefix_accounting: Optional[str]
    icao_code: Optional[str]
    callsign: Optional[str]
    type: Optional[str]
    status: str
    fleet_size: Optional[str]
    fleet_average_age: Optional[str]
    date_founded: Optional[str]
    hub_code: Optional[str]
    country_name: Optional[str]
    country_iso2: Optional[str]


class AviationStackAirlineResponse(BaseModel):
    data: List[AviationStackAirline]
    pagination: AviationStackPagination

    def __iter__(self) -> Iterator[AviationStackAirline]:  # type: ignore
        return iter(self.data)


class AviationStackAirport(BaseModel):
    airport: Optional[str]
    timezone: Optional[str]
    iata: Optional[str]
    icao: Optional[str]


class AviationStackFlightAirline(BaseModel):
    name: Optional[str]
    iata: Optional[str]
    icao: Optional[str]


class AviationStackFlight(BaseModel):
    number: Optional[str]
    iata: Optional[str]
    icao: Optional[str]


class AviationStackAircraft(BaseModel):
    registration: Optional[str]
    iata: Optional[str]
    icao: Optional[str]
    icao24: Optional[str]


class AviationStackRealTimeFlight(BaseModel):
    departure: AviationStackAirport
    arrival: AviationStackAirport
    airline: AviationStackFlightAirline
    flight: AviationStackFlight
    aircraft: AviationStackAircraft


class AviationStackFlightResponse(BaseModel):
    data: List[AviationStackRealTimeFlight]
    pagination: AviationStackPagination

    def __iter__(self) -> Iterator[AviationStackRealTimeFlight]:  # type: ignore[override]
        return iter(self.data)  #  # type: ignore[arg-type]
