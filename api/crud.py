from sqlalchemy.orm import Session
from typing import Optional, List, cast

import schemas
from models import Aircraft, Airline, Route, AircraftImage

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


def update_aircraft(db: Session, db_aircraft: Aircraft) -> None:
    if get_aircraft(db, db_aircraft.icao) is None:
        create_aircraft(db, db_aircraft)

    db.merge(db_aircraft)
    db.commit()


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
