import requests
import csv
import sqlite3
import os

from sqlalchemy.orm.session import Session
from api.schemas import AircraftImage
import crud
import models

from typing import Any, List, Dict

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


    def store_aircraftdata_flightaware(self) -> None:
        print('Storing aircraft data in postgres...')
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

            print('Aircraft data is stored.')


    def store_aircraftdata_aviationstack(self) -> None:
        print('Storing aircraft from aviationstack...')
        total = 1e8
        pagination = 100
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

            i += pagination

        print('Aircraft data from aviationstack is stored.')

    def get_image_id(self, icao: str, i: int) -> int:
        return int(icao, 16) * 100 + i

    def get_aircraft_image_data(self, aircraft: models.Aircraft, icao: str) -> List[models.AircraftImage]:
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
            print(response.content, url, response.headers['X-RateLimit-Remaining'], response.headers['X-RateLimit-Reset'])
            crud.set_aircraft_has_no_images(db, aircraft)
            return []

        result: List[AircraftImage] = []

        for i, aircraft in enumerate(json_response['data']):
            thumbnail = aircraft['image']
            image = thumbnail.replace('/thumbnails', '')
            photographer = aircraft['photographer']

            image = crud.create_aircraft_image(self.get_db(), models.AircraftImage(
                id=int(icao, 16) * 100 + i,
                number=i,
                icao=icao,
                image_url=image,
                thumbnail_url=thumbnail,
                photographer=photographer
            ))
            result.append(image)

        print('Aircraft images are stored.')
        return result
