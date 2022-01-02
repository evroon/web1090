import os
import random
from collections import Counter
from typing import Any, Dict, Optional

import crud
import requests
from conversion import (
    aviationstack_aircraft_to_aircraft,
    aviationstack_airline_to_airline,
    aviationstack_flight_to_aircraft,
    aviationstack_flight_to_route,
)
from logger import get_logger
from pydantic.error_wrappers import ValidationError
from responses import (
    AviationStackAircraftResponse,
    AviationStackAirlineResponse,
    AviationStackFlightResponse,
)

AVIATIONSTACK_KEY = str(os.getenv('AVIATIONSTACK_KEY')).split(',')


class AviationStack:
    logger = get_logger('aviationstack')

    def __init__(self, data: Any) -> None:
        self.adsbdata = data
        self.db = data.db
        self.config = data.config

    def _send_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
                self.logger.error(api_response.content)

            return {}

        return json_response

    def get_flights_by_icao(
        self, *, airline_icao: Optional[str] = None, flight_icao: Optional[str] = None
    ) -> None:
        """
        Collects all current flights from Aviationstack and stores them in the db.
        Either filters on airline icao or flight icao.
        """
        pagination = 100
        total = pagination
        i = 0

        while i < total:
            self.logger.info(f'Collecting Aviationstack flights for {airline_icao}: {i} / {total}')
            params: Dict[str, Any] = {'offset': i}

            if airline_icao is not None:
                params['airline_icao'] = airline_icao
            if flight_icao is not None:
                params['flight_icao'] = flight_icao

            api_response = self._send_request('flights', params)

            if api_response == {}:
                return

            try:
                flights: AviationStackFlightResponse = AviationStackFlightResponse.parse_obj(
                    api_response
                )
                total = flights.pagination.total
            except ValidationError as e:
                self.logger.error(e)
                raise

            for _, flight in enumerate(flights):
                crud.update_route(self.db, aviationstack_flight_to_route(flight))
                if flight.aircraft:
                    crud.update_aircraft(self.db, aviationstack_flight_to_aircraft(flight))

            i += pagination

    def store_missing_flight_data(self) -> None:
        self.logger.info('Storing missing flight data from aviationstack...')
        max_items = 10
        rows_to_delete = []

        with open(self.config.routes_to_update_path, 'r') as f:
            lines = [x.strip() for x in f.readlines()]
            airlines = [x[:3] for x in lines]
            top_airlines = Counter(airlines).most_common(max_items)
            max_items = len(top_airlines)

        for i in range(max_items):
            airline_icao = top_airlines[i][0]

            for j, l in enumerate(lines):
                if l.startswith(airline_icao):
                    rows_to_delete.append(l)

            self.logger.info(f'{airline_icao} {i} / {max_items}')
            self.get_flights_by_icao(airline_icao=airline_icao)

        # Delete flights that could not be found.
        lines = [x for x in lines if x not in rows_to_delete and x != '']
        with open(self.config.routes_to_update_path, 'w') as fw:
            fw.write('\n'.join(lines) + '\n')

        self.logger.info('Missing flight data from aviationstack is stored.')

    def store_airlinedata(self) -> None:
        self.logger.info('Storing airline data from aviationstack...')
        total = 1e8
        pagination = 100
        i = 0

        while i < total:
            params = {
                'offset': i,
            }
            api_response = self._send_request('airlines', params)

            for a in api_response['data']:
                if not a['airline_name']:
                    self.logger.debug(a)

            airlines: AviationStackAirlineResponse = AviationStackAirlineResponse.parse_obj(
                api_response
            )
            total = airlines.pagination.total
            self.logger.info(f'Aviationstack airlines: {i} / {total}')

            for airline in airlines:
                self.logger.debug(airline)
                if airline.airline_name:
                    crud.update_airline(self.db, aviationstack_airline_to_airline(airline))

            i += pagination

        self.logger.info('Aircraft data from aviationstack is stored.')

    def store_aircraftdata(self) -> None:
        self.logger.info('Storing aircraft from aviationstack...')
        total = 1e8
        pagination = 100
        i = 0

        while i < total:
            params = {'offset': i}
            api_response = self._send_request('airplanes', params)
            aircraft_list: AviationStackAircraftResponse = AviationStackAircraftResponse.parse_obj(
                api_response
            )
            total = aircraft_list.pagination.total
            self.logger.info(f'Aviationstack aircraft: {i} / {total}')

            for as_aircraft in aircraft_list:
                if as_aircraft.icao_code_hex is None:
                    continue

                db_aircraft = aviationstack_aircraft_to_aircraft(self.adsbdata, as_aircraft)
                crud.update_aircraft(self.db, db_aircraft)

            i += pagination

        self.logger.info('Aircraft data from aviationstack is stored.')
