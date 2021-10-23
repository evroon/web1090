import json
from datetime import datetime
from typing import Dict, Any

class Config:
    def __init__(self) -> None:
        self.cached_routes: Dict[str, Any] = {}
        self.cached_aircraft: Dict[str, Any] = {}
        self.country_ids: Dict[str, str] = {}

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
        self.airport_data_window = datetime.fromtimestamp(int)
        print(self.airport_data_window)
