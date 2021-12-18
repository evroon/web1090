import models
from collector import DataSource
from config import Config
from data import ADSBData
from database import SessionLocal, engine
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)


# Dependency
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


config = Config()


with SessionLocal() as db:
    data = ADSBData(db, config)
    print(data.collector.load_data(DataSource.aviationstack_missing_routes))
