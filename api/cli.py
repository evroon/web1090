import sys
import time

import click
import models
from collector import DataSource
from config import Config
from data import ADSBData
from database import SessionLocal, engine
from logger import get_logger

models.Base.metadata.create_all(bind=engine)


config = Config()
logger = get_logger('cli')


@click.group()
def cli() -> None:
    pass


@click.command()
def track_aircraft() -> None:
    while True:
        with SessionLocal() as db:
            data = ADSBData(db, config)
            task = data.collector.load_data(DataSource.schiphol_missing_routes)
            logger.info(task)

        time.sleep(60)


@click.command()
@click.option(
    "--source",
    default='schiphol.missing_routes',
    help="Source to get information of.",
)
def load_data_source(source: str) -> None:
    with SessionLocal() as db:
        data = ADSBData(db, config)
        data.collector.load_data(DataSource(source))


if __name__ == "__main__":
    cli.add_command(track_aircraft)
    cli.add_command(load_data_source)
    cli()
