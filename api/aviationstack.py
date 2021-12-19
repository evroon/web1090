import os
import random
from typing import Any, Dict, Optional

import crud
import requests
from conversion import (
    aviationstack_airline_to_airline,
    aviationstack_flight_to_aircraft,
    aviationstack_flight_to_route,
)
from logger import get_logger
from responses import AviationStackAirlineResponse, AviationStackFlightResponse

AVIATIONSTACK_KEY = str(os.getenv('AVIATIONSTACK_KEY')).split(',')


class AviationStack:
    logger = get_logger('aviationstack')

    def __init__(self, data: Any) -> None:
        self.adsbdata = data
        self.db = data.db

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
            self.logger.info(f'Collecting Aviationstack flights for {flight_icao}: {i} / {total}')
            params: Dict[str, Any] = {'offset': i}

            if airline_icao is not None:
                params['airline_icao'] = airline_icao
            if flight_icao is not None:
                params['flight_icao'] = flight_icao

            api_response = self._send_request('flights', params)

            if api_response == {}:
                return

            flights: AviationStackFlightResponse = AviationStackFlightResponse.parse_obj(
                api_response
            )
            total = flights.pagination.total

            for _, flight in enumerate(flights):
                crud.update_route(self.db, aviationstack_flight_to_route(flight))
                crud.update_aircraft(self.db, aviationstack_flight_to_aircraft(flight))

            i += pagination

    def store_missing_flight_data(self) -> None:
        self.logger.info('Storing missing flight data from aviationstack...')
        max_items = 10
        rows_to_delete = []

        with open('data/to_update.csv', 'r') as f:
            lines = f.readlines()
            max_items = min(max_items, len(lines))
            for i in range(max_items):
                flight_number = random.choice(lines).strip()
                rows_to_delete.append(flight_number)
                self.logger.info(f'{flight_number} {i} / {max_items}')

                self.get_flights_by_icao(flight_icao=flight_number)

            # Delete flights that could not be found.
            with open('data/to_update.csv', 'w') as fw:
                lines = [x for x in lines if x not in rows_to_delete and x.strip() != '']
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
            params = {
                'offset': i,
            }
            api_response = self._send_request('airplanes', params)
            total = api_response['pagination']['total']
            self.logger.info(f'Aviationstack aircraft: {i} / {total}')

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

        self.logger.info('Aircraft data from aviationstack is stored.')
