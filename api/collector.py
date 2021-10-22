import psycopg2
import datetime
import requests
import json
import time
import csv
import argparse
import sqlite3
import pycountry
import os

PSQL_DB=os.getenv('PSQL_DB')
PSQL_PORT=os.getenv('PSQL_PORT')
PSQL_USER=os.getenv('PSQL_USER')
PSQL_PASSWORD=os.getenv('PSQL_PASSWORD')
DUMP1090_ADDRESS=os.getenv('DUMP1090_ADDRESS')
AVIATIONSTACK_KEY = os.getenv('AVIATIONSTACK_KEY')
VIRTUALRADAR_SQLITE_DB_PATH = 'data/StandingData.sqb'

ROUTESDATA_DB='routesdata'
FLIGHTDATA_DB='flightdata'
AIRCRAFTDATA_DB='aircraftdata'
AIRCRAFT_IMAGES_DB='aircraftimages'
AIRPORTDATA_DB='airportdata'


class Collector:
    def __init__(self, adsbdata) -> None:
        self.adsbdata = adsbdata
        self.con = psycopg2.connect(database=PSQL_DB, user=PSQL_USER, password=PSQL_PASSWORD, host="127.0.0.1", port=PSQL_PORT)
        print("Database opened successfully")

        with open('data/db.json', 'r') as f:
            db = json.load(f)

        self.flightdata_columns = db['flightdata_columns']
        self.aircraft_image_columns = db['aircraft_image_columns']
        self.aircraftdata_columns = db['aircraftdata_columns']
        self.airportdata_columns = db['airportdata_columns']
        self.routesdata_columns = db['routesdata_columns']

        if not self.table_exists(AIRCRAFTDATA_DB):
            self.create_table(AIRCRAFTDATA_DB, self.aircraftdata_columns)
            self.store_aircraftdata_flightaware()
            self.store_aircraftdata_aviationstack()

        if not self.table_exists(ROUTESDATA_DB):
            self.create_table(ROUTESDATA_DB, self.routesdata_columns)
            self.store_routedata_virtualradar()

        if not self.table_exists(AIRCRAFT_IMAGES_DB):
            self.create_table(AIRCRAFT_IMAGES_DB, self.aircraft_image_columns)

        if not self.table_exists(FLIGHTDATA_DB):
            self.create_table(FLIGHTDATA_DB, self.flightdata_columns)

        # self.con.close()

    def get_cursor(self):
        return self.con.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    def insert_in_table(self, cur, columns, aggregated_data, table_name, id=None) -> None:
        if len(aggregated_data) < 1:
            return

        data_values = ','.join([f'%({x})s' for x in columns.keys()])
        columns_keys = ','.join(columns.keys())
        args_str = ','.join(['(' + cur.mogrify(data_values, x).decode("utf-8") + ')' for x in aggregated_data])
        on_conflict = ''

        # Overwrite columns if key already exists in table.
        if id is not None:
            args = []
            for col in columns:
                if col != 'id':
                    args.append(f'{col} = excluded.{col}')

            on_conflict = f"ON CONFLICT ({id}) DO UPDATE SET {', '.join(args)}"

        print(f'Adding {len(aggregated_data)} entries in {table_name}.')
        cur.execute(f"INSERT INTO {table_name} ({columns_keys}) VALUES {args_str} {on_conflict}")
        self.con.commit()


    def store_routedata_virtualradar(self) -> None:
        print('Storing routes...')
        conn = sqlite3.connect(VIRTUALRADAR_SQLITE_DB_PATH)
        cur_in = conn.execute('select * from RouteView')
        cur = self.con.cursor()
        aggregated_route_data = []
        routes = cur_in.fetchall()
        batch_size = 10000

        for i, route in enumerate(routes):
            if i % int(len(routes) / 10) == 0:
                print(f'Progress: {i} / {len(routes)} ({i/len(routes)*100:.0f}%)')

            aggregated_route_data.append({
                'icao': route[1],
                'airline_icao': route[3],
                'airline_iata': route[4],
                'airline_name': route[5],
                'number': route[6],

                'dep_icao': route[8],
                'dep_iata': route[9],
                'dep_airport': route[10],
                'dep_lat': route[11],
                'dep_lon': route[12],
                'dep_alt': route[13],
                'dep_loc': route[14],
                'dep_country': route[16],
                'dep_country_id': self.adsbdata.get_country_id(route[16]),

                'arr_icao': route[18],
                'arr_iata': route[19],
                'arr_airport': route[20],
                'arr_lat': route[21],
                'arr_lon': route[22],
                'arr_alt': route[23],
                'arr_loc': route[24],
                'arr_country': route[26],
                'arr_country_id': self.adsbdata.get_country_id(route[26]),
            })

        for i in range(0, len(aggregated_route_data), batch_size):
            self.insert_in_table(cur, self.routesdata_columns, aggregated_route_data[i:i+batch_size], ROUTESDATA_DB, 'icao')

        print('Finished loading routes.')
        conn.close()


    def store_airportdata(self) -> None:
        print('Storing airports...')
        total = 1e8
        pagination = 100
        cur = self.con.cursor()
        i = 0

        while i < total:
            params = {
                'access_key': AVIATIONSTACK_KEY,
                'offset': i,
            }
            api_result = requests.get('http://api.aviationstack.com/v1/airports', params)

            if not api_result.ok:
                print(api_result.content)
                return

            api_response = api_result.json()
            total = api_response['pagination']['total']

            aggregated_data = []

            for airport in api_response['data']:
                aggregated_data.append({
                    'name': airport['airport_name'],
                    'iata': airport['iata_code'],
                    'icao': airport['icao_code'],
                    'lat': airport['latitude'],
                    'lon': airport['longitude'],
                    'geoname_id': airport['geoname_id'],
                    'timezone': airport['timezone'],
                    'gmt': airport['gmt'],
                    'country_name': airport['country_name'],
                    'country_iso2': airport['country_iso2'],
                    'city_iata_code': airport['city_iata_code'],
                })

            self.insert_in_table(cur, self.airportdata_columns, aggregated_data, AIRPORTDATA_DB, 'icao')

            i += pagination
            break

        print('Airport data is stored.')


    def store_aircraftdata_flightaware(self) -> None:
        print('Storing aircraft data in postgres...')
        cur = self.con.cursor()
        batch_size = 10000

        with open('data/flightaware.csv', 'r') as f:
            reader = csv.reader(f, delimiter=',')
            aggregated_data = []

            # Skip header
            next(reader, None)

            for i, aircraft in enumerate(reader):
                if i % 10000 == 0:
                    print(f'Progress: {i}')

                icao = aircraft[0].upper()
                reg = aircraft[1]
                ac_type = aircraft[2]

                country = self.adsbdata.get_country(icao)
                category = self.adsbdata.get_category(ac_type)
                family = self.adsbdata.get_family(ac_type)

                aggregated_data.append({
                    'icao': icao,
                    'registration': reg,
                    'aircrafttype': ac_type,
                    'country': country,
                    'category': category,
                    'family': family,
                    'favorite': False,
                    'needs_update': False,
                    'airline_iata': None,
                    'plane_owner': None,
                    'model_name': None,
                    'model_code': None,
                    'production_line': None,
                    'delivery_date': None,
                    'first_flight_date': None,
                    'registration_date': None,
                    'rollout_date': None,
                    'active': None,
                })

            for i in range(0, len(aggregated_data), batch_size):
                self.insert_in_table(cur, self.aircraftdata_columns, aggregated_data[i:i+batch_size], AIRCRAFTDATA_DB, 'icao')

            print('Aircraft data is stored.')


    def store_aircraftdata_aviationstack(self) -> None:
        print('Storing aircraft from aviationstack...')
        total = 1e8
        pagination = 100
        cur = self.get_cursor()
        i = 0

        while i < total:
            params = {
                'access_key': AVIATIONSTACK_KEY,
                'offset': i,
            }
            api_result = requests.get('http://api.aviationstack.com/v1/airplanes', params)

            if not api_result.ok:
                print('Error:', api_result.content)
                return

            api_response = api_result.json()
            total = api_response['pagination']['total']
            print(f'Aviationstack aircraft: {i} / {total}')

            aggregated_data = []

            for aircraft in api_response['data']:
                if aircraft['icao_code_hex'] is None:
                    continue

                icao = aircraft['icao_code_hex'].upper()
                ac_type = aircraft['iata_code_long']

                # One aircraft in aviationstack has an invalid hex code with O instead of 0.
                icao = icao.replace('O', '0')

                delivery_date = aircraft['delivery_date'] if aircraft['delivery_date'] != '0000-00-00' else None
                first_flight_date = aircraft['first_flight_date'] if aircraft['first_flight_date'] != '0000-00-00' else None
                registration_date = aircraft['registration_date'] if aircraft['registration_date'] != '0000-00-00' else None
                rollout_date = aircraft['rollout_date'] if aircraft['rollout_date'] != '0000-00-00' else None

                aggregated_data.append({
                    'aviationstack_id': aircraft['id'],
                    'icao': icao,
                    'registration': aircraft['registration_number'],
                    'aircrafttype': ac_type,
                    'country': self.adsbdata.get_country(icao),
                    'category': self.adsbdata.get_category(ac_type),
                    'family': self.adsbdata.get_family(ac_type),
                    'airline_iata': aircraft['airline_iata_code'],
                    'plane_owner': aircraft['plane_owner'],
                    'model_name': aircraft['model_name'],
                    'model_code': aircraft['model_code'],
                    'production_line': aircraft['production_line'],
                    'delivery_date': delivery_date,
                    'first_flight_date': first_flight_date,
                    'registration_date': registration_date,
                    'rollout_date': rollout_date,
                    'active': aircraft['plane_status'] == 'active',
                    'favorite': False,
                    'needs_update': False,
                })

            self.insert_in_table(cur, self.aircraftdata_columns, aggregated_data, AIRCRAFTDATA_DB, 'icao')

            i += pagination

        print('Aircraft data from aviationstack is stored.')

    def update_route(self, icao: str) -> dict:
        print('update route...', icao)
        params = {
            'access_key': AVIATIONSTACK_KEY,
            'flight_icao': icao,
        }
        # api_result = requests.get('http://api.aviationstack.com/v1/flights', params)
        return {}
        if not api_result.ok:
            print(api_result.content)
            return {}

        response = api_result.json()['data']

        if len(response) < 1:
            print('no response:', response)
            return {}

        route = response[0]
        aggregated_data = [
            {
                'icao': route['flight']['icao'],
                'number': route['flight']['number'],

                'airline_icao': route['airline']['icao'],
                'airline_iata': route['airline']['iata'],
                'airline_name': route['airline']['name'],

                'dep_icao': route['departure']['icao'],
                'dep_iata': route['departure']['iata'],
                'dep_airport': route['departure']['airport'],

                'arr_icao': route['arrival']['icao'],
                'arr_iata': route['arrival']['iata'],
                'arr_airport': route['arrival']['airport'],
            }
        ]
        cur = self.get_cursor()
        self.insert_in_table(cur, self.routesdata_columns, aggregated_data, ROUTESDATA_DB, 'icao')

        cur.execute("select * from routesdata where icao=%(icao)s", {'icao': icao})
        route = cur.fetchone()
        print(route)
        return route

    def update_aircraft(self, icao: str) -> dict:
        pass

    def check_aircraft(self, icao: str) -> dict:
        cur = self.get_cursor()
        cur.execute("select * from aircraftdata where icao=%(icao)s", {'icao': icao})
        aircraft = cur.fetchone()

        # if aircraft is None:
        #     return self.update_aircraft(icao)

        return aircraft

    def check_route(self, icao: str) -> dict:
        cur = self.get_cursor()
        cur.execute("select * from routesdata where icao=%(icao)s", {'icao': icao})
        route = cur.fetchone()

        if route is None:
            self.update_route(icao)

        return route

    def get_image_id(icao: str, i: int) -> str:
        return int(icao, 16) * 100 + i

    def get_aircraft_image_data(self, icao: str) -> dict:
        icao = icao.upper()
        cur = self.get_cursor()
        cur.execute("select * from aircraftimages where icao=%(icao)s", {'icao': icao})
        images = cur.fetchall()

        cur = self.get_cursor()
        cur.execute("select has_no_images from aircraftdata where icao=%(icao)s", {'icao': icao})
        aircraft = cur.fetchone()

        if aircraft is None:
            return []
        has_no_images = aircraft['has_no_images']

        if len(images) > 0 or has_no_images:
            return images

        cur = self.con.cursor()
        count = 50

        url = f'https://www.airport-data.com/api/ac_thumb.json?m={icao}&n={count}'
        response = requests.get(url)
        if not response.ok:
            print(response.content, url)
            return []

        json_response = response.json()
        if 'data' not in json_response:
            cur = self.get_cursor()
            cur.execute("update aircraftdata set has_no_images='t' where icao=%(icao)s", {'icao': icao})
            return []

        aggregated_data = []
        n = len(json_response['data'])

        for i, aircraft in enumerate(json_response['data']):
            thumbnail = aircraft['image']
            image = thumbnail.replace('/thumbnails', '')
            link = aircraft['link']
            photographer = aircraft['photographer']

            aggregated_data.append({
                'id': int(icao, 16) * 100 + i,
                'number': i,
                'icao': icao,
                'image_url': image,
                'thumbnail_url': thumbnail,
                'link': link,
                'photographer': photographer,
            })

        self.insert_in_table(cur, self.aircraft_image_columns, aggregated_data, AIRCRAFT_IMAGES_DB, 'id')

        print('Aircraft images are stored.')
        return aggregated_data


    def get_aircraftdata(self, hexcode: str) -> dict:
        cur = self.con.cursor()
        cur.execute(f"SELECT * FROM {AIRCRAFTDATA_DB} WHERE icao=%(hex)s", {'hex': hexcode})
        rows = cur.fetchone()

        if rows is None:
            return {}

        return {
            'registration': rows[1],
            'aircrafttype': rows[2],
        }


    def table_exists(self, table_name: str) -> bool:
        cur = self.con.cursor()
        cur.execute("select * from information_schema.tables where table_name=%s", (table_name,))
        return cur.rowcount > 0


    def create_table(self, table_name: str, columns: dict) -> None:
        print(f'Creating table {table_name}')
        columns_query = ', '.join([f'{k} {v}' for k, v in columns.items()])

        cur = self.con.cursor()
        cur.execute(f'CREATE TABLE {table_name}({columns_query});')
        self.con.commit()

        if (table_name == 'flightdata'):
            cur.execute(f'CREATE INDEX flight_idx ON flightdata USING btree (flight);')
            cur.execute(f'CREATE INDEX aircrafttype_idx ON flightdata USING btree (aircrafttype);')
            cur.execute(f'CREATE INDEX registration_idx ON flightdata USING btree (registration);')
            self.con.commit()


    def store_data(self, aggregated_data: list) -> None:
        print(f'Writing {len(aggregated_data)} entries to database.')
        columns_without_id = self.flightdata_columns
        if 'id' in columns_without_id:
            del columns_without_id['id']

        cur = self.con.cursor()
        data_values = ','.join([f'%({x})s' for x in columns_without_id.keys()])
        columns_keys = ','.join(columns_without_id.keys())
        args_str = ','.join(['(' + cur.mogrify(data_values, x).decode("utf-8") + ')' for x in aggregated_data])

        cur.execute(f"INSERT INTO {FLIGHTDATA_DB} ({columns_keys}) VALUES {args_str}")
        self.con.commit()
