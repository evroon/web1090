import csv
import os
import random
import sqlite3
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from responses import AviationStackAirlineResponse, AviationStackFlightResponse
from sqlalchemy.orm.session import Session

import crud
import models
from conversion import (aviationstack_airline_to_airline,
                        aviationstack_flight_to_aircraft,
                        aviationstack_flight_to_route)

load_dotenv()


PSQL_DB = os.getenv('PSQL_DB')
PSQL_PORT = os.getenv('PSQL_PORT')
PSQL_USER = os.getenv('PSQL_USER')
PSQL_PASSWORD = os.getenv('PSQL_PASSWORD')
DUMP1090_ADDRESS = os.getenv('DUMP1090_ADDRESS')
VIRTUALRADAR_SQLITE_DB_PATH = 'data/StandingData.sqb'
AVIATIONSTACK_KEY = str(os.getenv('AVIATIONSTACK_KEY')).split(',')

ROUTESDATA_DB = 'routesdata'
FLIGHTDATA_DB = 'flightdata'
AIRCRAFTDATA_DB = 'aircraftdata'
AIRCRAFT_IMAGES_DB = 'aircraftimages'
AIRPORTDATA_DB = 'airportdata'


class DataSource(str, Enum):
    opensky = "opensky"
    flightaware = "flightaware"
    aviationstack = "aviationstack"
    aviationstack_airlines = "aviationstack.airlines"
    aviationstack_missing_routes = "aviationstack.missing_routes"
    virtualradar = "virtualradar"


class Collector:
    def __init__(self, adsbdata: Any) -> None:
        self.adsbdata = adsbdata

    def get_db(self) -> Session:
        return self.adsbdata.db

    def store_routedata_virtualradar(self) -> None:
        print('Storing routes...')
        conn = sqlite3.connect(VIRTUALRADAR_SQLITE_DB_PATH)
        cur_in = conn.execute('select * from RouteView')
        aggregated_route_data = []
        routes = cur_in.fetchall()
        batch_size = 10000

        for i, route in enumerate(routes):
            if i % int(len(routes) / 10) == 0:
                print(f'Progress: {i} / {len(routes)} ({i/len(routes)*100:.0f}%)')

            aggregated_route_data.append(
                {
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
                }
            )

        print('Finished loading routes.')
        conn.close()

    # def store_airportdata(self) -> None:
    #     print('Storing airports...')
    #     total = 1e8
    #     pagination = 100
    #     cur = self.con.cursor()
    #     i = 0

    #     while i < total:
    #         params = {
    #             'access_key': AVIATIONSTACK_KEY,
    #             'offset': i,
    #         }
    #         api_result = requests.get('http://api.aviationstack.com/v1/airports', params)

    #         if not api_result.ok:
    #             print(api_result.content)
    #             return

    #         api_response = api_result.json()
    #         total = api_response['pagination']['total']

    #         aggregated_data = []

    #         for airport in api_response['data']:
    #             aggregated_data.append({
    #                 'name': airport['airport_name'],
    #                 'iata': airport['iata_code'],
    #                 'icao': airport['icao_code'],
    #                 'lat': airport['latitude'],
    #                 'lon': airport['longitude'],
    #                 'geoname_id': airport['geoname_id'],
    #                 'timezone': airport['timezone'],
    #                 'gmt': airport['gmt'],
    #                 'country_name': airport['country_name'],
    #                 'country_iso2': airport['country_iso2'],
    #                 'city_iata_code': airport['city_iata_code'],
    #             })

    #         self.insert_in_table(cur, self.airportdata_columns, aggregated_data, AIRPORTDATA_DB, 'icao')

    #         i += pagination
    #         break

    #     print('Airport data is stored.')

    def load_data(self, source: DataSource) -> str:
        if source == DataSource.opensky:
            return self.store_aircraftdata_opensky()
        elif source == DataSource.aviationstack_airlines:
            return self.store_airlinedata_aviationstack()
        elif source == DataSource.aviationstack_missing_routes:
            return self.store_missing_flight_data_aviationstack()

        return f'invalid source: {source}'

    def send_aviationstack_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if len(AVIATIONSTACK_KEY) < 1:
            return {}

        access_key = random.choice(AVIATIONSTACK_KEY)
        all_params = {
            **params,
            'access_key': access_key,
        }

        api_response = requests.get(f'http://api.aviationstack.com/v1/{endpoint}', all_params)
        json_response = dict(api_response.json())

        if not api_response.ok:

            if (
                'error' in json_response
                and 'code' in json_response['error']
                and json_response['error']['code'] == 'usage_limit_reached'
            ):
                del AVIATIONSTACK_KEY[AVIATIONSTACK_KEY.index(access_key)]
            else:
                print('Error:', api_response.content)

            return {}

        return json_response

    def get_aviationstack_flights_by_airline_icao(
        self, *, airline_icao: Optional[str] = None, flight_icao: Optional[str] = None
    ) -> None:
        """
        Collects all current flights from Aviationstack for a certain airline and stores them in the db.
        """
        pagination = 100
        total = pagination
        i = 0

        while i < total:
            print(f'Collecting Aviationstack flights for {flight_icao}: {i} / {total}')
            params: Dict[str, Any] = {'offset': i}

            if airline_icao is not None:
                params['airline_icao'] = airline_icao
            if flight_icao is not None:
                params['flight_icao'] = flight_icao

            api_response = self.send_aviationstack_request('flights', params)

            if api_response == {}:
                return

            flights: AviationStackFlightResponse = AviationStackFlightResponse.parse_obj(
                api_response
            )
            total = flights.pagination.total

            for _, flight in enumerate(flights):
                crud.update_route(self.get_db(), aviationstack_flight_to_route(flight))
                crud.update_aircraft(self.get_db(), aviationstack_flight_to_aircraft(flight))

            i += pagination

    def store_missing_flight_data_aviationstack(self) -> str:
        print('Storing missing flight data from aviationstack...')
        self.update_csv()
        max_items = 10
        rows_to_delete = []

        with open('data/to_update.csv', 'r') as f:
            lines = f.readlines()
            max_items = min(max_items, len(lines))
            for i in range(max_items):
                flight_number = random.choice(lines).strip()
                rows_to_delete.append(flight_number)
                print(flight_number, i, '/', max_items)

                self.get_aviationstack_flights_by_airline_icao(flight_icao=flight_number)

            # Delete flights that could not be found.
            with open('data/to_update.csv', 'w') as fw:
                lines = [x for x in lines if x not in rows_to_delete and x.strip() != '']
                fw.write('\n'.join(lines) + '\n')

        self.update_csv()
        return 'Missing flight data from aviationstack is stored.'

    def update_csv(self) -> None:
        with open('data/to_update.csv', 'r') as f:
            text = f.read()
            lines = text.split('\n')
            with open('data/to_update.csv', 'w') as fw:
                lines = [
                    x for x in lines if crud.get_route(self.get_db(), x) is None and x.strip() != ''
                ]
                fw.write('\n'.join(lines) + '\n')

    def store_airlinedata_aviationstack(self) -> str:
        print('Storing airline data from aviationstack...')
        total = 1e8
        pagination = 100
        i = 0

        while i < total:
            params = {
                'offset': i,
            }
            api_response = self.send_aviationstack_request('airlines', params)

            for a in api_response['data']:
                if not a['airline_name']:
                    print(a)

            airlines: AviationStackAirlineResponse = AviationStackAirlineResponse.parse_obj(
                api_response
            )
            total = airlines.pagination.total
            print(f'Aviationstack airlines: {i} / {total}')

            for airline in airlines:
                print(airline)
                if airline.airline_name:
                    crud.update_airline(self.get_db(), aviationstack_airline_to_airline(airline))

            i += pagination

        return 'Aircraft data from aviationstack is stored.'

    def store_aircraftdata_opensky(self) -> str:
        print('Storing aircraft data from opensky...')
        csv_path = 'data/opensky.csv'
        download_url = 'https://opensky-network.org/datasets/metadata/aircraftDatabase-2021-10.csv'

        if not os.path.exists(csv_path):
            response = requests.get(download_url, stream=True)
            with open(csv_path, 'wb') as f:
                for chunk in response:
                    f.write(chunk)

        def verify_date(date: str) -> Optional[str]:
            if len(date) < 6:
                return None
            return date

        with open(csv_path, 'r', newline='') as csv_file:
            reader = csv.DictReader(csv_file, delimiter=',')

            for row in reader:
                icao = row['icao24'].upper()
                if len(icao) != 6:
                    continue
                ac_type = row['typecode']

                country = self.adsbdata.get_country(icao)
                category = self.adsbdata.get_category(ac_type)
                family = self.adsbdata.get_family(ac_type)

                aircraft = models.Aircraft(
                    icao=icao,
                    registration=row['registration'],
                    aircrafttype=ac_type,
                    category=category,
                    country=country,
                    family=family,
                    airline_iata=row['operatoriata'],
                    plane_owner=row['owner'],
                    model_name=row['model'],
                    model_code=ac_type,
                    production_line=verify_date(row['linenumber']),
                    delivery_date=verify_date(row['built']),
                    registration_date=verify_date(row['registered']),
                    rollout_date=verify_date(row['firstflightdate']),
                )

                print(f'Adding {row["registration"]}...')
                crud.update_aircraft(self.get_db(), aircraft)

        return 'finished'

    def store_aircraftdata_flightaware(self) -> None:
        print('Storing aircraft data in postgres...')

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

                aggregated_data.append(
                    {
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
                    }
                )

            print('Aircraft data is stored.')

    def store_aircraftdata_aviationstack(self) -> None:
        print('Storing aircraft from aviationstack...')
        total = 1e8
        pagination = 100
        i = 0

        while i < total:
            params = {
                'offset': i,
            }
            api_response = self.send_aviationstack_request('airplanes', params)
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

                delivery_date = (
                    aircraft['delivery_date'] if aircraft['delivery_date'] != '0000-00-00' else None
                )
                first_flight_date = (
                    aircraft['first_flight_date']
                    if aircraft['first_flight_date'] != '0000-00-00'
                    else None
                )
                registration_date = (
                    aircraft['registration_date']
                    if aircraft['registration_date'] != '0000-00-00'
                    else None
                )
                rollout_date = (
                    aircraft['rollout_date'] if aircraft['rollout_date'] != '0000-00-00' else None
                )

                aggregated_data.append(
                    {
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
                    }
                )

            i += pagination

        print('Aircraft data from aviationstack is stored.')

    def get_image_id(self, icao: str, i: int) -> int:
        return int(icao, 16) * 100 + i

    def get_aircraft_image_data(
        self, aircraft: models.Aircraft, icao: str
    ) -> List[models.AircraftImage]:
        icao = icao.upper()

        db = self.get_db()
        images = crud.get_images(db, icao)

        if aircraft is None:
            print(f'get_aircraft_image_data: {icao}')
            return []

        if len(images) > 0 or aircraft.has_no_images:
            return images

        count = 50

        url = f'https://www.airport-data.com/api/ac_thumb.json?m={icao}&n={count}'
        print('sending api request')
        response = requests.get(url)

        if not response.ok:
            crud.set_aircraft_has_no_images(db, aircraft)
            print(response.content, url)
            return []

        json_response = response.json()
        if 'data' not in json_response:
            self.adsbdata.config.set_airport_data_window(int(response.headers['X-RateLimit-Reset']))
            print(
                response.content,
                url,
                response.headers['X-RateLimit-Remaining'],
                response.headers['X-RateLimit-Reset'],
            )
            crud.set_aircraft_has_no_images(db, aircraft)
            return []

        result: List[models.AircraftImage] = []

        for i, aircraft in enumerate(json_response['data']):
            thumbnail = aircraft['image']
            image = thumbnail.replace('/thumbnails', '')
            photographer = aircraft['photographer']

            image = crud.create_aircraft_image(
                self.get_db(),
                models.AircraftImage(
                    id=int(icao, 16) * 100 + i,
                    number=i,
                    icao=icao,
                    image_url=image,
                    thumbnail_url=thumbnail,
                    photographer=photographer,
                ),
            )
            result.append(image)

        print('Aircraft images are stored.')
        return result
