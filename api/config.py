import json
from datetime import datetime
from logging import Logger
from typing import Any, Dict


class Config:
    def __init__(self) -> None:
        self.cached_routes: Dict[str, Any] = {}
        self.cached_aircraft: Dict[str, Any] = {}
        self.country_ids: Dict[str, str] = {}
        self.ac_logos_path = 'data/logos'
        self.aircraft_to_update_path = 'data/aircraft_to_update.csv'
        self.routes_to_update_path = 'data/routes_to_update.csv'
        self.opensky_csv_path = 'data/opensky.csv'
        self.piaware_ac_db_path = '/usr/share/dump1090-fa/html/db/'

        with open('data/country_aliases.json', 'r') as f:
            self.country_aliases = json.load(f)

        with open('data/ac_icons.json', 'r') as f:
            self.ac_icons = json.load(f)

        with open('data/ac_families.json', 'r') as f:
            self.ac_families = json.load(f)

        with open('data/ac_categories.json', 'r') as f:
            self.ac_categories = json.load(f)

        with open('data/ac_countries.json', 'r') as f:
            self.ac_countries = json.load(f)

    def set_airport_data_window(self, unix_time: int) -> None:
        self.airport_data_window = datetime.utcfromtimestamp(float(unix_time))
        self.logger = Logger('config')
        self.logger.info(self.airport_data_window)
