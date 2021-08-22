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

                if ac['route'] is not None:
                    iata = ac['route']['airline_iata']

                    if self.get_airline_icon(iata) is not None:
                        ac['airline_icon'] = self.base_url + f"airline_icon.svg?iata={iata}"

            ac_type = self.get_aircraft(ac['hex'])
            if ac_type is not None:
                ac['registration'] = ac_type['registration']
                ac['aircrafttype'] = ac_type['aircrafttype']
                ac['icon_category'] = ac_type['category']
                ac['country'] = ac_type['country']

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

    def get_aircrafttypes(self, by_family: bool = False) -> dict:
        aircrafttypes = {}
        if not by_family:
            self.cur.execute("select distinct aircrafttype, count(*) from flightdata where aircrafttype != '' group by aircrafttype")

            for x in self.cur.fetchall():
                aircrafttypes[x['aircrafttype']] = x['count']
        else:
            self.cur.execute("select aircrafttype, count(*) from flightdata where aircrafttype != '' group by aircrafttype")

            for x in self.cur.fetchall():
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
        self.cached_aircraft[icao] = aircraft
        return aircraft

    def get_ac_icon(self, category: str, adsb_category: str, color: str = None) -> str:
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

        icon = self.ac_icons[category]['svg']
        icon = icon.replace('aircraft_color_fill', color)
        icon = icon.replace('aircraft_color_stroke', '"#FFFFFF"')
        icon = icon.replace('add_stroke_selected', '')
        return icon

    def get_airline_icon(self, iata: str) -> str:
        iata = iata.upper()

        if len(iata) != 2:
            print(f'IATA Code {iata} is invalid. IATA codes consist of two letters (e.g. KL).')
            return None

        size = 64
        cache_path = f'data/logos/{iata}-{size}.png'
        cache_path_404 = f'{cache_path}.404'

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
                with open(cache_path_404, 'w') as f:
                    f.write(response.content)

        return cache_path

    def get_category(self, ac_type_icao: str) -> str:
        if ac_type_icao == '':
            return None

        if ac_type_icao not in self.ac_categories['ac_types']:
            return 'unknown'

        return self.ac_categories['ac_types'][ac_type_icao]

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
