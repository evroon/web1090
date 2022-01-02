import os
from logging import Logger

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

load_dotenv()


# Dependency
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Database:
    PSQL_DB = os.getenv('PSQL_DB')
    PSQL_PORT = os.getenv('PSQL_PORT')
    PSQL_USER = os.getenv('PSQL_USER')
    PSQL_PASSWORD = os.getenv('PSQL_PASSWORD')

    PSQL_DB = os.getenv('PSQL_DB')
    PSQL_PORT = os.getenv('PSQL_PORT')
    PSQL_USER = os.getenv('PSQL_USER')
    PSQL_PASSWORD = os.getenv('PSQL_PASSWORD')
    DUMP1090_ADDRESS = os.getenv('DUMP1090_ADDRESS')
    VIRTUALRADAR_SQLITE_DB_PATH = 'data/StandingData.sqb'

    ROUTESDATA_DB = 'routesdata'
    FLIGHTDATA_DB = 'flightdata'
    AIRCRAFTDATA_DB = 'aircraftdata'
    AIRCRAFT_IMAGES_DB = 'aircraftimages'
    AIRPORTDATA_DB = 'airportdata'
    REALTIMEDATA_DB = 'realtimedata'

    logger = Logger('web1090')

    SQLALCHEMY_DATABASE_URL = (
        f"postgresql://{PSQL_USER}:{PSQL_PASSWORD}@localhost:{PSQL_PORT}/{PSQL_DB}"
    )


engine = create_engine(Database.SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
