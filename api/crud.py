from sqlalchemy.orm import Session
from typing import Optional

import models, schemas

# Aircraft
def get_aircraft(db: Session, icao: str) -> Optional[models.Aircraft]:
    return db.query(models.Aircraft).filter(models.Aircraft.icao == icao).first()


def get_aircraft_paginated(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Aircraft).offset(skip).limit(limit).all()


def create_aircraft(db: Session, aircraft: schemas.AircraftCreate):
    db_aircraft = models.Aircraft(**aircraft.dict())
    db.add(db_aircraft)
    db.commit()
    db.refresh(db_aircraft)
    return db_aircraft


# AircraftImage
def get_aircraft_image(db: Session, icao: str, number: int):
    return db.query(models.AircraftImage) \
        .filter(models.AircraftImage.icao == icao) \
        .filter(models.AircraftImage.number == number) \
        .first()


def get_images(db: Session, icao: str, skip: int = 0, limit: int = 100):
    return db.query(models.AircraftImage) \
        .filter(models.AircraftImage.icao == icao) \
        .offset(skip) \
        .limit(limit) \
        .all()


def create_aircraft_image(db: Session, db_image: models.AircraftImage):
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def set_aircraft_has_no_images(db: Session, aircraft: models.Aircraft):
    aircraft.has_no_images = True
    db.commit()


# Route
def get_route(db: Session, icao: str):
    return db.query(models.Route).filter(models.Route.icao == icao).first()


def get_route_count(db: Session) -> int:
    return db.query(models.Route).count()


def get_registrations_count(db: Session) -> int:
    return db.query(models.Aircraft).count()
