from typing import Iterator
from typing_extensions import final
import psycopg2
import psycopg2.extras
import os
import requests
import json
import pycountry
import time

from typing import Optional, Dict, Any
from collector import Collector


PSQL_DB=os.getenv('PSQL_DB')
PSQL_PORT=os.getenv('PSQL_PORT')
PSQL_USER=os.getenv('PSQL_USER')
PSQL_PASSWORD=os.getenv('PSQL_PASSWORD')

class ADSBData:
    def __init__(self) -> None:
        self.collector = Collector(self)

        self.con = psycopg2.connect(
            database=PSQL_DB,
            user=PSQL_USER,
            password=PSQL_PASSWORD,
            host="127.0.0.1",
            port=PSQL_PORT
        )
        self.cur = self.con.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
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


    def get_cursor(self) -> psycopg2.cursor:
        return self.con.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    def get_statistics(self) -> dict:
        live_flights = self.get_live_flights()
        flights = self.get_flights()
        aircrafttypes = self.get_aircrafttypes()
        registrations = self.get_registrations()
        signal_count = self.get_signal_count()
        return {
            'live_flight_count': len(live_flights['aircraft']),
            'routes_count': len(flights['data']),
            'registrations_count': len(registrations['data']),
        }

    def get_live_flights(self) -> Dict[str, Any]:
        response = requests.get('http://localhost:8080/data/aircraft.json')
        if not response.ok:
            raise ConnectionError('Could not connect to dump1090')

        response_json: Dict[str, Any] = response.json()
        for ac in response_json['aircraft']:
            ac['hex'] = ac['hex'].upper().strip()
            if 'flight' in ac:
                ac['flight'] = ac['flight'].strip()
                ac['route'] = self.get_route(ac['flight'])

                if ac['route'] is not None:
                    iata = ac['route']['airline_iata']

                    if self.get_airline_icon(iata) is not None:
                        ac['airline_icon'] = f"airline_icon.svg?iata={iata}"

            ac_type = self.get_aircraft(ac['hex'])
            if ac_type is not None:
                ac['registration'] = ac_type['registration']
                ac['aircrafttype'] = ac_type['aircrafttype']
                ac['icon_category'] = ac_type['category']
                ac['country'] = ac_type['country']

            images = self.collector.get_aircraft_image_data(ac['hex'])
            ac['images'] = []
            icao = ac['hex']

            for i, _ in enumerate(images):
                ac['images'].append({
                    'thumbnail_endpoint': f'image?icao={icao}&i={i}&as_thumbnail=true',
                    'image_endpoint': f'image?icao={icao}&i={i}&as_thumbnail=false',
                })

        return response_json

    def get_signal_count(self) -> int:
        cur = self.get_cursor()
        cur.execute(f"select count(*) from flightdata")
        return int(cur.fetchone()['count'])

    def get_flights(self) -> dict:
        cur = self.get_cursor()
        columns = [
            'flight',
            'dep_airport',
            'arr_airport'
        ]

        cur.execute(f"select distinct {','.join(columns)}, count(*) from flightdata INNER JOIN routesdata ON (flightdata.flight = routesdata.icao) group by {','.join(columns)}")
        # flights = {}
        # for x in self.cur.fetchall():
        #     flights[x[0]] = x[1:]

        return {
            'data': cur.fetchall(),
        }

    def get_aircrafttypes(self, by_family: bool = False) -> dict:
        cur = self.get_cursor()
        aircrafttypes = {}

        if not by_family:
            cur.execute("select distinct aircrafttype, count(*) from flightdata where aircrafttype != '' group by aircrafttype")

            for x in cur.fetchall():
                aircrafttypes[x['aircrafttype']] = x['count']
        else:
            cur.execute("select aircrafttype, count(*) from flightdata where aircrafttype != '' group by aircrafttype")

            for x in cur.fetchall():
                if x['aircrafttype'] in self.ac_families:
                    family_name = self.ac_families[x['aircrafttype']]
                else:
                    family_name = 'Other'

                if family_name not in aircrafttypes:
                    aircrafttypes[family_name] = 0

                aircrafttypes[family_name] += x['count']

        return {
            'data': aircrafttypes,
        }

    def get_registrations(self) -> dict:
        cur = self.get_cursor()
        cur.execute("select distinct registration, count(*) from flightdata where registration != '' group by registration")
        # cur.execute("select * from aircraftdata where registration != ''")
        registrations = {}

        for x in cur.fetchall():
            registrations[x['registration']] = x['count']

        return {
            'data': registrations,
        }

    def get_route(self, icao: str) -> dict:
        icao = icao.upper()
        if icao in self.cached_routes:
            return dict(self.cached_routes[icao])

        route = self.collector.check_route(icao)
        self.cached_routes[icao] = route
        return route

    def get_aircraft(self, icao: str) -> dict:
        icao = icao.upper()
        if icao in self.cached_aircraft:
            return dict(self.cached_aircraft[icao])

        aircraft = self.collector.check_aircraft(icao)
        self.cached_aircraft[icao] = aircraft
        return aircraft

    def get_ac_icon(self,
        category: Optional[str],
        adsb_category: Optional[str],
        color: Optional[str] = None,
        is_selected: bool = False
    ) -> str:
        if category not in self.ac_icons or category == 'unknown':
            if adsb_category in self.ac_categories['adsb_categories']:
                category = self.ac_categories['adsb_categories'][adsb_category]
            else:
                category = 'unknown'

        if color is None:
            if 'color' in self.ac_icons[category]:
                color = self.ac_icons[category]['color']
            else:
                color = '#f2ff00'

        icon = str(self.ac_icons[category]['svg'])
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

        cur = self.get_cursor()
        cur.execute("select * from aircraftimages where icao=%(icao)s", {'icao': icao})
        images = cur.fetchall()

        if len(images) < 1:
            images = self.collector.get_aircraft_image_data(icao)

        if i >= len(images):
            raise ValueError(f'Invalid index {i} in range of {len(images)}.')

        image = images[i]
        image_property = 'thumbnail_url' if as_thumbnail else 'image_url'
        response = requests.get(image[image_property], stream=True)

        if response.ok:
            try:
                with open(cache_path, 'wb') as f:
                    for chunk in response:
                        f.write(chunk)
                        yield chunk
            finally:
                if int(response.headers['Content-Length']) > os.path.getsize(cache_path):
                    os.remove(cache_path)
        else:
            print(f'Could not retrieve image for aircraft: {icao}')

    def get_category(self, ac_type_icao: str) -> Optional[str]:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.ac_categories['ac_types']:
            return 'unknown'

        return str(self.ac_categories['ac_types'][ac_type_icao])

    def get_family(self, ac_type_icao: str) -> Optional[str]:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.ac_families:
            return 'Other'

        return str(self.ac_families[ac_type_icao])

    def get_country_id(self, name: str) -> Optional[str]:
        if name in self.country_aliases.keys():
            name = self.country_aliases[name]

        # Retrieve from cache.
        if name in self.country_ids:
            return self.country_ids[name]

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

        self.country_ids[name] = str(country.alpha_2)
        return str(country.alpha_2)

    def get_country(self, ac_icao: str) -> Optional[str]:
        try:
            icao_code_hex = int(ac_icao, 16)
        except ValueError:
            print(f'Error: "{ac_icao}" is not a valid hex code.')
            return None

        for range in self.ac_countries:
            if icao_code_hex >= int(range['start'], 16) and icao_code_hex <= int(range['end'], 16):
                return self.get_country_id(range['country'])

        print(f'Error: icao code {ac_icao} is not in the range of ac_countries.json.')
        return None
