from typing import List, Optional, cast

import schemas
from models import Aircraft, AircraftImage, Airline, Realtime, Route
from sqlalchemy.orm import Session


# Aircraft
def get_aircraft(db: Session, icao: str) -> Optional[Aircraft]:
    return cast(Optional[Aircraft], db.query(Aircraft).filter(Aircraft.icao == icao).first())


def get_aircraft_paginated(db: Session, skip: int = 0, limit: int = 100) -> List[Aircraft]:
    return cast(List[Aircraft], db.query(Aircraft).offset(skip).limit(limit).all())


def create_aircraft(db: Session, db_aircraft: Aircraft) -> Aircraft:
    db.add(db_aircraft)
    db.commit()
    db.refresh(db_aircraft)
    return cast(Aircraft, db_aircraft)


def update_aircraft(db: Session, db_aircraft: Aircraft) -> bool:
    if get_aircraft(db, db_aircraft.icao) is None:
        create_aircraft(db, db_aircraft)
        return True

    db.merge(db_aircraft)
    db.commit()
    return False


def get_registrations_count(db: Session) -> int:
    return int(db.query(Aircraft).count())


# AircraftImage
def get_aircraft_image(db: Session, icao: str, number: int) -> Optional[AircraftImage]:
    return cast(
        Optional[AircraftImage],
        db.query(AircraftImage)
        .filter(AircraftImage.icao == icao)
        .filter(AircraftImage.number == number)
        .first(),
    )


def get_images(db: Session, icao: str, skip: int = 0, limit: int = 100) -> List[AircraftImage]:
    return cast(
        List[AircraftImage],
        db.query(AircraftImage).filter(AircraftImage.icao == icao).offset(skip).limit(limit).all(),
    )


def create_aircraft_image(db: Session, db_image: AircraftImage) -> AircraftImage:
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return cast(AircraftImage, db_image)


def set_aircraft_has_no_images(db: Session, aircraft: Aircraft) -> None:
    aircraft.has_no_images = True
    db.commit()


# Route
def get_route(db: Session, icao: str) -> Optional[Route]:
    return cast(Optional[Route], db.query(Route).filter(Route.icao == icao).first())


def get_route_by_dep_iata(db: Session, dep_iata: str) -> Optional[Route]:
    return cast(
        Optional[Route],
        db.query(Route)
        .filter(Route.dep_iata == dep_iata)
        .filter(Route.dep_icao.isnot(None))
        .first(),
    )


def get_route_by_arr_iata(db: Session, arr_iata: str) -> Optional[Route]:
    return cast(
        Optional[Route],
        db.query(Route)
        .filter(Route.arr_iata == arr_iata)
        .filter(Route.arr_icao.isnot(None))
        .first(),
    )


def get_routes_paginated(db: Session, skip: int = 0, limit: int = 100) -> List[Route]:
    return cast(List[Route], db.query(Route).offset(skip).limit(limit).all())


def create_route(db: Session, db_route: Route) -> Route:
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    return cast(Route, db_route)


def update_route(db: Session, db_route: Route) -> None:
    if get_route(db, db_route.icao) is None:
        create_airline(db, db_route)

    db.merge(db_route)
    db.commit()


def get_route_count(db: Session) -> int:
    return int(db.query(Route).count())


# Airline
def get_airline(db: Session, iata: str) -> Optional[Airline]:
    return cast(Optional[Airline], db.query(Airline).filter(Airline.iata_code == iata).first())


def create_airline(db: Session, db_airline: Airline) -> Airline:
    db.add(db_airline)
    db.commit()
    db.refresh(db_airline)
    return cast(Airline, db_airline)


def update_airline(db: Session, db_airline: Airline) -> None:
    if get_airline(db, db_airline.iata_code) is None:
        create_airline(db, db_airline)

    db.merge(db_airline)
    db.commit()


def update_route_airport_data(db: Session, db_route: Route) -> None:
    dep_airport: Route = get_route_by_dep_iata(db, db_route.dep_iata)
    arr_airport: Route = get_route_by_arr_iata(db, db_route.arr_iata)

    db_route.dep_airport = dep_airport.dep_airport
    db_route.dep_icao = dep_airport.dep_icao
    db_route.dep_country = dep_airport.dep_country
    db_route.dep_country_id = dep_airport.dep_country_id
    db_route.dep_lat = dep_airport.dep_lat
    db_route.dep_lon = dep_airport.dep_lon
    db_route.dep_alt = dep_airport.dep_alt

    db_route.arr_airport = arr_airport.arr_airport
    db_route.arr_icao = arr_airport.arr_icao
    db_route.arr_country = arr_airport.arr_country
    db_route.arr_country_id = arr_airport.arr_country_id
    db_route.arr_lat = arr_airport.arr_lat
    db_route.arr_lon = arr_airport.arr_lon
    db_route.arr_alt = arr_airport.arr_alt

    update_route(db, db_route)


# Realtime
def create_realtime_entry(db: Session, db_realtime: Realtime) -> Realtime:
    db.add(db_realtime)
    db.commit()
    db.refresh(db_realtime)
    return cast(Airline, db_realtime)
