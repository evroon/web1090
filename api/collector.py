import csv
import gzip
import os
import shutil
import sqlite3
from enum import Enum
from typing import Any, List, Optional

import crud
import models
import requests
from aviationstack import AviationStack
from conversion import virtualradar_route_to_route
from dotenv import load_dotenv
from logger import get_logger
from responses import VirtualRadarRoute
from schiphol import Schiphol
from sqlalchemy.orm.session import Session

load_dotenv()


class DataSource(str, Enum):
    opensky = "opensky"
    flightaware = "flightaware"
    aviationstack = "aviationstack"
    aviationstack_airlines = "aviationstack.airlines"
    aviationstack_missing_routes = "aviationstack.missing_routes"
    schiphol_missing_routes = "schiphol.missing_routes"
    virtualradar = "virtualradar"


class Collector:
    def __init__(self, adsbdata: Any) -> None:
        self.adsbdata = adsbdata
        self.logger = get_logger('collector')

    def get_db(self) -> Session:
        return self.adsbdata.db

    def store_routedata_virtualradar(self) -> None:
        self.logger.info('Storing routes...')
        download_url = 'https://www.virtualradarserver.co.uk/Files/StandingData.sqb.gz'
        sqb_gz_path = 'data/virtualradar.sqb.gz'
        sqb_path = sqb_gz_path[:-3]

        if not os.path.exists(sqb_path):
            self.logger.info('Downloading sqb...')
            response = requests.get(download_url, stream=True)
            with open(sqb_gz_path, 'wb') as f:
                for chunk in response:
                    f.write(chunk)

            self.logger.info(f'Extracting {sqb_gz_path}...')
            with gzip.open(sqb_gz_path, 'rb') as f_in:
                with open(sqb_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            self.logger.info(f'Finished extracting {sqb_gz_path}...')

        conn = sqlite3.connect(sqb_path)
        conn.row_factory = sqlite3.Row
        cur_in = conn.execute('select * from RouteView ORDER BY RouteId desc')
        aggregated_route_data = []
        routes = cur_in.fetchall()

        for i, vr_route in enumerate(routes):
            if i % int(len(routes) / 100) == 0:
                self.logger.info(f'Progress: {i} / {len(routes)} ({i/len(routes)*100:.0f}%)')

            route = VirtualRadarRoute.parse_obj(vr_route)
            route.FromAirportCountryId = self.adsbdata.get_country_id(route.FromAirportCountry)
            route.ToAirportCountryId = self.adsbdata.get_country_id(route.ToAirportCountry)

            crud.update_route(self.get_db(), virtualradar_route_to_route(route))
            aggregated_route_data.append(route)

        self.logger.info('Finished loading routes.')
        conn.close()

    def load_data(self, source: DataSource) -> None:
        self.update_csv()

        if source == DataSource.opensky:
            self.store_aircraftdata_opensky()
        elif source == DataSource.aviationstack_airlines:
            aviationstack = AviationStack()
            aviationstack.store_airlinedata()
        elif source == DataSource.aviationstack_missing_routes:
            aviationstack = AviationStack(self.adsbdata)
            aviationstack.store_missing_flight_data()
        elif source == DataSource.schiphol_missing_routes:
            schiphol = Schiphol(self.adsbdata)
            schiphol.store_missing_flight_data()
        elif source == DataSource.virtualradar:
            self.store_routedata_virtualradar()
        else:
            self.logger.error(f'invalid source: {source}')

    def update_csv(self) -> None:
        with open('data/to_update.csv', 'r') as f:
            text = f.read()
            lines = text.split('\n')
            with open('data/to_update.csv', 'w') as fw:
                lines = [
                    x for x in lines if crud.get_route(self.get_db(), x) is None and x.strip() != ''
                ]
                fw.write('\n'.join(lines) + '\n')

    def store_aircraftdata_opensky(self) -> None:
        self.logger.info('Storing aircraft data from opensky...')
        csv_path = 'data/opensky.csv'
        download_url = 'https://opensky-network.org/datasets/metadata/aircraftDatabase-2021-12.csv'

        if not os.path.exists(csv_path):
            self.logger.info(f'Downloading {download_url}...')
            response = requests.get(download_url, stream=True)

            with open(csv_path, 'wb') as f:
                for chunk in response:
                    f.write(chunk)

            self.logger.info(f'Finished downloading {download_url}...')

        def verify_date(date: str) -> Optional[str]:
            return None if len(date) < 6 else date

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

                self.logger.info(f'Adding {row["registration"]}...')
                crud.update_aircraft(self.get_db(), aircraft)

        self.logger.info('finished')

    def store_aircraftdata_flightaware(self) -> None:
        self.logger.info('Storing aircraft data in postgres...')

        with open('data/flightaware.csv', 'r') as f:
            reader = csv.reader(f, delimiter=',')
            aggregated_data = []

            # Skip header
            next(reader, None)

            for i, aircraft in enumerate(reader):
                if i % 10000 == 0:
                    self.logger.info(f'Progress: {i}')

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

            self.logger.info('Aircraft data is stored.')

    def get_image_id(self, icao: str, i: int) -> int:
        return int(icao, 16) * 100 + i

    def get_aircraft_image_data(
        self, aircraft: models.Aircraft, icao: str
    ) -> List[models.AircraftImage]:
        icao = icao.upper()

        db = self.get_db()
        images: List[models.AircraftImage] = crud.get_images(db, icao)

        if aircraft is None:
            self.logger.debug(f'get_aircraft_image_data: {icao}')
            return []

        if len(images) > 0 or aircraft.has_no_images:
            return images

        count = 50

        url = f'https://www.airport-data.com/api/ac_thumb.json?m={icao}&n={count}'
        self.logger.debug('Sending api request')
        response = requests.get(url)

        if not response.ok:
            crud.set_aircraft_has_no_images(db, aircraft)
            self.logger.error(f'{response.content!r} {url!r}')
            return []

        json_response = response.json()
        if 'data' not in json_response:
            self.adsbdata.config.set_airport_data_window(int(response.headers['X-RateLimit-Reset']))
            self.logger.warning(
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

        self.logger.info('Aircraft images are stored.')
        return result
