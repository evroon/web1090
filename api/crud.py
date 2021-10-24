from sqlalchemy.orm import Session
from typing import Optional, List, cast

import schemas
from models import Aircraft, Route, AircraftImage

# Aircraft
def get_aircraft(db: Session, icao: str) -> Optional[Aircraft]:
    return cast(
        Optional[Aircraft],
        db.query(Aircraft).filter(Aircraft.icao == icao).first()
    )


def get_aircraft_paginated(db: Session, skip: int = 0, limit: int = 100) -> List[Aircraft]:
    return cast(
        List[Aircraft],
        db.query(Aircraft).offset(skip).limit(limit).all()
    )


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


# AircraftImage
def get_aircraft_image(db: Session, icao: str, number: int) -> Optional[AircraftImage]:
    return cast(
        Optional[AircraftImage],
        db.query(AircraftImage) \
            .filter(AircraftImage.icao == icao) \
            .filter(AircraftImage.number == number) \
            .first()
    )


def get_images(db: Session, icao: str, skip: int = 0, limit: int = 100) -> List[AircraftImage]:
    return cast(
        List[AircraftImage],
        db.query(AircraftImage) \
            .filter(AircraftImage.icao == icao) \
            .offset(skip) \
            .limit(limit) \
            .all()
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
    return cast(
        Optional[Route],
        db.query(Route).filter(Route.icao == icao).first()
    )


def get_routes_paginated(db: Session, skip: int = 0, limit: int = 100) -> List[Route]:
    return cast(
        List[Route],
        db.query(Route).offset(skip).limit(limit).all()
    )


def get_route_count(db: Session) -> int:
    return int(db.query(Route).count())


def get_registrations_count(db: Session) -> int:
    return int(db.query(Aircraft).count())
