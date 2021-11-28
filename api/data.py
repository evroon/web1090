import os
import requests
import pycountry

from typing import Optional, Dict, Any, Iterator

from sqlalchemy.schema import CreateTable
from sqlalchemy.orm.session import Session
from responses import DUMP1090Response
from models import Airline
from collector import Collector
from config import Config
import crud


PSQL_DB=os.getenv('PSQL_DB')
PSQL_PORT=os.getenv('PSQL_PORT')
PSQL_USER=os.getenv('PSQL_USER')
PSQL_PASSWORD=os.getenv('PSQL_PASSWORD')

class ADSBData:
    def __init__(self, db: Any, config: Config) -> None:
        self.db = db
        self.config = config
        self.collector = Collector(self)

    def get_db(self) -> Session:
        return self.db

    def get_statistics(self) -> dict:
        live_flights = self.get_live_flights()
        routes = crud.get_route_count(self.get_db())
        registrations = crud.get_registrations_count(self.get_db())

        return {
            'live_flight_count': len(list(live_flights)),
            'routes_count': routes,
            'registrations_count': registrations,
        }

    def get_live_flights(self) -> Dict[str, Any]:
        response = requests.get('http://localhost:8080/data/aircraft.json')
        if not response.ok:
            raise ConnectionError('Could not connect to dump1090')

        response_json: DUMP1090Response = DUMP1090Response.parse_obj(response.json())

        for ac in response_json:
            ac.hex = ac.hex.upper().strip()
            icao = ac.hex

            if ac.flight:
                ac.flight = ac.flight.strip()
                route = crud.get_route(self.get_db(), ac.flight)
                ac.route = route

                if route is not None:
                    iata = route.airline_iata

                    if self.get_airline_icon(iata) is not None:
                        ac.airline_icon = f"airline_icon.svg?iata={iata}"
                else:
                    self.get_route_details(ac.flight)


            ac_type = crud.get_aircraft(self.get_db(), icao)
            if ac_type is not None:
                ac.registration = ac_type.registration
                ac.aircrafttype = ac_type.aircrafttype
                ac.icon_category = ac_type.category
                ac.country = ac_type.country

                images = self.collector.get_aircraft_image_data(ac_type, icao)
                ac.images = []

                for i, _ in enumerate(images):
                    ac.images.append({
                        'thumbnail_endpoint': f'image?icao={icao}&i={i}&as_thumbnail=true',
                        'image_endpoint': f'image?icao={icao}&i={i}&as_thumbnail=false',
                    })

        return response_json

    def get_route_details(self, flight: str):
        with open('data/to_update.csv', 'r') as f:
            if not flight in f.read():
                print(f'get_route_details {flight}')
                with open('data/to_update.csv', 'a') as f:
                    f.write(flight + '\n')

    def get_ac_icon(self,
        category: Optional[str],
        adsb_category: Optional[str],
        color: Optional[str] = None,
        is_selected: bool = False
    ) -> str:
        if category not in self.config.ac_icons or category == 'unknown':
            if adsb_category in self.config.ac_categories['adsb_categories']:
                category = self.config.ac_categories['adsb_categories'][adsb_category]
            else:
                category = 'unknown'

        if color is None:
            if 'color' in self.config.ac_icons[category]:
                color = self.config.ac_icons[category]['color']
            else:
                color = '#f2ff00'

        icon = str(self.config.ac_icons[category]['svg'])
        icon = icon.replace('aircraft_color_fill', color)
        icon = icon.replace('aircraft_color_stroke', '"#FFFFFF"')
        icon = icon.replace('add_stroke_selected', ' stroke="black" stroke-width="1px"' if is_selected else '')
        return icon

    def get_airline_icon(self, iata: str) -> Optional[str]:
        iata = iata.upper()

        if len(iata) != 2:
            print(f'IATA Code {iata} is invalid. IATA codes consist of two letters (e.g. KL).')
            return None

        size = 64
        cache_root = 'data/logos'
        cache_path = f'{cache_root}/{iata}-{size}.png'
        cache_path_404 = f'{cache_path}.404'

        if not os.path.exists(cache_root):
            os.mkdir(cache_root)

        if os.path.exists(cache_path_404):
            return None

        if not os.path.exists(cache_path):
            response = requests.get(f'https://images.kiwi.com/airlines/{size}/{iata}.png', stream=True)

            if response.ok:
                with open(cache_path, 'wb') as f:
                    for chunk in response:
                        f.write(chunk)
            else:
                print(f'Could not retrieve logo for airline: {iata}')
                with open(cache_path_404, 'wb') as f:
                    f.write(response.content)

        return cache_path

    def get_aircraft_image_cache_path(self, icao: str, i: int, as_thumbnail: bool = False) -> str:
        cache_root = 'data/images'
        type = 't' if as_thumbnail else 'i'
        cache_path = f'{cache_root}/{icao}-{i}-{type}.png'
        return cache_path

    def get_aircraft_image(self, icao: str, i: int, as_thumbnail: bool = False) -> Optional[str]:
        icao = icao.upper()

        if len(icao) != 6:
            print(f'ICAO Code {icao} is invalid. ICAO codes consist of six hexadecimal characters.')
            return None

        if i < 0:
            raise ValueError('Invalid index.')

        cache_root = 'data/images'
        cache_path = self.get_aircraft_image_cache_path(icao, i, as_thumbnail)

        if not os.path.exists(cache_root):
            os.mkdir(cache_root)

        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 128:
            return cache_path

        return None

    def stream_aircraft_image(self, icao: str, i: int, as_thumbnail: bool = False) -> Iterator[bytes]:
        cache_path = self.get_aircraft_image_cache_path(icao, i, as_thumbnail)
        images = crud.get_images(self.get_db(), icao)
        aircraft = crud.get_aircraft(self.get_db(), icao)

        if len(images) < 1 and aircraft is not None:
            images = self.collector.get_aircraft_image_data(aircraft, icao)

        if i >= len(images):
            raise ValueError(f'Invalid index {i} in range of {len(images)}.')

        image = images[i]
        image_property = image.thumbnail_url if as_thumbnail else image.image_url
        response = requests.get(image_property, stream=True)

        if response.ok:
            try:
                with open(cache_path, 'wb') as f:
                    for chunk in response:
                        f.write(chunk)
                        yield chunk
            finally:
                if 'Content-Length' in response.headers and int(response.headers['Content-Length']) > os.path.getsize(cache_path):
                    os.remove(cache_path)
        else:
            print(f'Could not retrieve image for aircraft: {icao}')

    def get_category(self, ac_type_icao: str) -> Optional[str]:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.config.ac_categories['ac_types']:
            return 'unknown'

        return str(self.config.ac_categories['ac_types'][ac_type_icao])

    def get_family(self, ac_type_icao: str) -> Optional[str]:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.config.ac_families:
            return 'Other'

        return str(self.config.ac_families[ac_type_icao])

    def get_country_id(self, name: str) -> Optional[str]:
        if name in self.config.country_aliases.keys():
            name = self.config.country_aliases[name]

        # Retrieve from cache.
        if name in self.config.country_ids:
            return self.config.country_ids[name]

        country = pycountry.countries.get(name=name)

        if country is None:
            country = pycountry.countries.get(official_name=name)
        if country is None:
            try:
                country = pycountry.countries.search_fuzzy(name)[0]
            except LookupError:
                pass

        if country is None:
            print(f'Error: Could not resolve country "{name}"')
            return None

        self.config.country_ids[name] = str(country.alpha_2)
        return str(country.alpha_2)

    def get_country(self, ac_icao: str) -> Optional[str]:
        try:
            icao_code_hex = int(ac_icao, 16)
        except ValueError:
            print(f'Error: "{ac_icao}" is not a valid hex code.')
            return None

        for range in self.config.ac_countries:
            if icao_code_hex >= int(range['start'], 16) and icao_code_hex <= int(range['end'], 16):
                return self.get_country_id(range['country'])

        print(f'Error: icao code {ac_icao} is not in the range of ac_countries.json.')
        return None
