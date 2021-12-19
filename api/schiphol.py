import datetime as dt
import os
from typing import Any, Dict, List, Optional

import crud
import pytz
import requests
from conversion import schiphol_flight_to_route
from logger import get_logger
from models import Route
from responses import DUMP1090Response, SchipholFlight, SchipholFlightListResponse
from simplejson.errors import JSONDecodeError

SCHIPHOL_API_ID = os.getenv('SCHIPHOL_API_ID')
SCHIPHOL_API_KEY = os.getenv('SCHIPHOL_API_KEY')


class Schiphol:
    logger = get_logger('schiphol')

    def __init__(self, data: Any) -> None:
        self.adsbdata = data
        self.db = data.db

    def _send_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            'Accept': 'application/json',
            'app_id': SCHIPHOL_API_ID,
            'app_key': SCHIPHOL_API_KEY,
            'ResourceVersion': 'v4',
        }

        api_response = requests.get(
            f'https://api.schiphol.nl/public-flights/{endpoint}', headers=headers, params=params
        )
        content = api_response.content

        if content == b'':
            return {}

        if not api_response.ok:
            self.logger.error(
                f'Schiphol API returns invalid data: {api_response.content!r} {api_response.status_code!r}'
            )
            return {}

        try:
            return dict(api_response.json())
        except JSONDecodeError:
            self.logger.error(
                f'Schiphol API returns invalid json: {api_response.content!r} {api_response.status_code!r}'
            )
            return {}

    def sanitize_registration(self, registration: Optional[str]) -> str:
        if not registration:
            return ''
        return registration.replace('-', '').upper().strip()

    def collect_flights(self, params: Dict[str, Any]) -> List[SchipholFlight]:
        result: List[SchipholFlight] = []
        page = 0
        max_page = 10

        while page < max_page:
            params['page'] = page
            api_response = self._send_request('flights', params)

            if api_response == {}:
                break

            flights = SchipholFlightListResponse.parse_obj(api_response).flights
            flights = [x for x in flights if x.prefixICAO]

            if len(flights) == 0:
                break

            result += flights
            page += 1

        return result

    def get_flights_by_airline(self, *, airline_icao: str) -> List[SchipholFlight]:
        params = {'sort': '+scheduleTime', 'airline': airline_icao}
        return self.collect_flights(params)

    def get_nearby_flights(self) -> Optional[SchipholFlight]:
        result = []
        now = dt.datetime.now().astimezone(pytz.timezone('Europe/Amsterdam'))
        params = {
            'sort': '+estimatedLandingTime',
            'searchDateTimeField': 'estimatedLandingTime',
            'fromDateTime': f'{now - dt.timedelta(minutes=10):%Y-%m-%dT%H:%M:%S}',
            'toDateTime': f'{now + dt.timedelta(hours=1):%Y-%m-%dT%H:%M:%S}',
        }

        result += self.collect_flights(params)

        params = {
            'sort': '+actualOffBlockTime',
            'searchDateTimeField': 'actualOffBlockTime',
            'fromDateTime': f'{now - dt.timedelta(hours=1, minutes=30):%Y-%m-%dT%H:%M:%S}',
            'toDateTime': f'{now:%Y-%m-%dT%H:%M:%S}',
        }

        result += self.collect_flights(params)
        return result

    def store_missing_flight_data(self) -> None:
        self.logger.info('Storing missing flight data from the Schiphol API...')
        flights: DUMP1090Response = self.adsbdata.get_live_flights()
        nearby_flights = self.get_nearby_flights()
        updated_flights = []

        assert nearby_flights

        for flight in flights:
            if not flight.registration:
                continue

            for nearby_flight in nearby_flights:
                if self.sanitize_registration(flight.registration) == self.sanitize_registration(
                    nearby_flight.aircraftRegistration
                ):
                    route = schiphol_flight_to_route(nearby_flight)

                    if flight.flight:
                        route.icao = flight.flight

                    crud.update_route(self.db, route)
                    crud.update_route_airport_data(self.db, route)
                    updated_flights.append(route)

                    # aircraft = schiphol_flight_to_aircraft(nearby_flight, flight.hex)
                    # crud.update_aircraft(self.db, aircraft)
                    break

        self.logger.info('Updated flights: ' + ','.join([x.icao for x in updated_flights]))

    def get_actual_route(self, flight_icao: str, aircraft_registration: str) -> Optional[Route]:
        self.logger.info(f'getting route for {flight_icao} - {aircraft_registration}')
        return None
        route = self.get_flight_by_registration(aircraft_registration=aircraft_registration)
        if route is None:
            return None

        route = schiphol_flight_to_route(route)
        self.logger.info(route)
        route.icao = flight_icao
        crud.update_route(self.db, route)
        return route
