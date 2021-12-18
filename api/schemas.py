from pydantic import BaseModel


class AircraftImageBase(BaseModel):
    pass


class AircraftImage(AircraftImageBase):
    pass

    class Config:
        orm_mode = True


class AircraftBase(BaseModel):
    icao: str


class AircraftCreate(AircraftBase):
    registration: str


class Aircraft(AircraftBase):
    class Config:
        orm_mode = True


class RouteBase(BaseModel):
    icao: str


class RouteCreate(RouteBase):
    registration: str


class Route(RouteBase):
    class Config:
        orm_mode = True
