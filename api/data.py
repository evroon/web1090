import psycopg2
import psycopg2.extras
import os
import requests
import json
import pycountry


PSQL_DB=os.getenv('PSQL_DB')
PSQL_USER=os.getenv('PSQL_USER')
PSQL_PASSWORD=os.getenv('PSQL_PASSWORD')

class ADSBData:
    def __init__(self) -> None:
        self.con = psycopg2.connect(
            database=PSQL_DB,
            user=PSQL_USER,
            password=PSQL_PASSWORD,
            host="127.0.0.1",
            port="5432"
        )
        self.cur = self.con.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        self.cached_routes = {}
        self.cached_aircraft = {}

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

        self.country_ids = {}

    def get_statistics(self) -> dict:
        live_flights = self.get_live_flights()
        flights = self.get_flights()
        aircrafttypes = self.get_aircrafttypes()
        registrations = self.get_registrations()
        signal_count = self.get_signal_count()
        return {
            'live_flight_count': len(live_flights),
            'flight_count': len(flights['data']),
            'aircrafttypes_count': len(aircrafttypes['data']),
            'registrations_count': len(registrations['data']),
            'signals_count': signal_count,
        }

    def get_live_flights(self) -> dict:
        response = requests.get('http://localhost:8080/data/aircraft.json')
        if not response.ok:
            raise ConnectionError('Could not connect to dump1090')

        response_json = response.json()
        for ac in response_json['aircraft']:
            ac['hex'] = ac['hex'].upper().strip()
            if 'flight' in ac:
                ac['flight'] = ac['flight'].strip()
                ac['route'] = self.get_route(ac['flight'])

            ac_type = self.get_aircraft(ac['hex'])
            if ac_type is not None:
                ac['registration'] = ac_type['registration']
                ac['aircrafttype'] = ac_type['aircrafttype']

        return response_json

    def get_signal_count(self) -> int:
        self.cur.execute(f"select count(*) from flightdata")
        return self.cur.fetchone()['count']

    def get_flights(self) -> dict:
        columns = [
            'flight',
            'dep_airport',
            'arr_airport'
        ]

        self.cur.execute(f"select distinct {','.join(columns)}, count(*) from flightdata INNER JOIN routesdata ON (flightdata.flight = routesdata.icao) group by {','.join(columns)}")
        flights = {}
        # for x in self.cur.fetchall():
        #     flights[x[0]] = x[1:]

        return {
            'data': self.cur.fetchall(),
        }

    def get_aircrafttypes(self) -> dict:
        self.cur.execute("select distinct aircrafttype, count(*) from flightdata where aircrafttype != '' group by aircrafttype")
        aircrafttypes = {}
        for x in self.cur.fetchall():
            aircrafttypes[x['aircrafttype']] = x['count']

        return {
            'data': aircrafttypes,
        }

    def get_registrations(self) -> dict:
        self.cur.execute("select distinct registration, count(*) from flightdata where registration != '' group by registration")
        registrations = {}

        for x in self.cur.fetchall():
            registrations[x['registration']] = x['count']

        return {
            'data': registrations,
        }

    def get_route(self, icao: str) -> dict:
        icao = icao.upper()
        if icao in self.cached_routes:
            return self.cached_routes[icao]

        self.cur.execute("select * from routesdata where icao=%(icao)s", {'icao': icao})
        route = self.cur.fetchone()
        self.cached_routes[icao] = route
        return route

    def get_aircraft(self, icao: str) -> dict:
        icao = icao.upper()
        if icao in self.cached_aircraft:
            return self.cached_aircraft[icao]

        self.cur.execute("select * from aircraftdata where icao=%(icao)s", {'icao': icao})
        aircraft = self.cur.fetchone()
        print(icao, aircraft)
        self.cached_aircraft[icao] = aircraft
        return aircraft

    def get_icon(self, category: str, color: str) -> str:
        with open('data/ac_icons.json', 'r') as f:
            icons = json.load(f)

            if category not in icons:
                raise ValueError(f'Category {category} does not exist.')

            icon = icons[category]['svg']
            icon = icon.replace('aircraft_color_fill', color)
            icon = icon.replace('aircraft_color_stroke', '"#FFFFFF"')
            icon = icon.replace('add_stroke_selected', '')
            return icon

    def get_category(self, ac_type_icao: str) -> str:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.ac_categories:
            return 'unknown'

        return self.ac_categories[ac_type_icao]

    def get_family(self, ac_type_icao: str) -> str:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.ac_families:
            return 'Other'

        return self.ac_families[ac_type_icao]

    def get_country_id(self, name: str) -> str:
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

        self.country_ids[name] = country.alpha_2
        return country.alpha_2

    def get_country(self, ac_icao: str) -> str:
        icao_code_hex = int(ac_icao, 16)

        for range in self.ac_countries:
            if icao_code_hex >= int(range['start'], 16) and icao_code_hex <= int(range['end'], 16):
                return self.get_country_id(range['country'])

        print(f'Error: icao code {ac_icao} is not in the range of ac_countries.json.')
        return None
