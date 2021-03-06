from database import Base
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import DateTime, Float, Time


class AircraftImage(Base):
    __tablename__ = "aircraft_image"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer)
    icao = Column(String, index=True)
    image_url = Column(String)
    thumbnail_url = Column(String)
    photographer = Column(String)


class Aircraft(Base):
    __tablename__ = "aircraftdata"

    icao = Column(String, primary_key=True, index=True)
    registration = Column(String, index=True)
    aircrafttype = Column(String)
    category = Column(String)
    country = Column(String)
    family = Column(String)
    airline_iata = Column(String)
    plane_owner = Column(String)
    model_name = Column(String)
    model_code = Column(String)
    production_line = Column(String)
    delivery_date = Column(Time)
    first_flight_date = Column(Time)
    registration_date = Column(Time)
    rollout_date = Column(Time)
    last_seen_date = Column(Time)
    aviationstack_id = Column(Integer)
    has_no_images = Column(Boolean, default=False)
    active = Column(Boolean, default=False)
    favorite = Column(Boolean, default=False)
    needs_update = Column(Boolean, default=False)


class Route(Base):
    __tablename__ = "routesdata"

    icao = Column(String, primary_key=True, index=True)
    iata = Column(String)
    number = Column(String)
    airline_name = Column(String)
    airline_iata = Column(String)
    airline_icao = Column(String)

    dep_airport = Column(String)
    dep_icao = Column(String)
    dep_iata = Column(String)
    dep_lat = Column(Float)
    dep_lon = Column(Float)
    dep_alt = Column(Float)
    dep_loc = Column(String)
    dep_country = Column(String)
    dep_country_id = Column(String)

    arr_airport = Column(String)
    arr_icao = Column(String)
    arr_iata = Column(String)
    arr_lat = Column(Float)
    arr_lon = Column(Float)
    arr_alt = Column(Float)
    arr_loc = Column(String)
    arr_country = Column(String)
    arr_country_id = Column(String)


class Airline(Base):
    __tablename__ = "airlinedata"

    iata_code = Column(String, primary_key=True, index=True)
    iata_prefix_accounting = Column(Integer)
    icao_code = Column(String)
    aviationstack_id = Column(Integer)
    airline_name = Column(String)
    callsign = Column(String)
    type = Column(String)
    status = Column(String)
    fleet_size = Column(Integer)
    fleet_average_age = Column(Float)
    date_founded = Column(Integer)
    hub_code = Column(String)
    country_name = Column(String)
    country_iso2 = Column(String)


class Realtime(Base):
    __tablename__ = "realtimedata"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    data = Column(JSONB, nullable=False)
