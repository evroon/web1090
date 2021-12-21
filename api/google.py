import os
import random
from typing import Any, Dict, List

import crud
import requests
from conversion import google_flight_to_route
from logger import get_logger
from responses import GoogleFlightMetaTag, GoogleFlightResponse

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_API_CX = os.getenv('GOOGLE_API_CX')


class Google:
    logger = get_logger('google')

    def __init__(self, data: Any) -> None:
        self.adsbdata = data
        self.db = data.db

    def _send_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params['key'] = GOOGLE_API_KEY
        params['cx'] = GOOGLE_API_CX
        headers = {
            'Accept': 'application/json',
        }

        api_response = requests.get(
            f'https://www.googleapis.com/customsearch/v1/', params=params, headers=headers
        )
        json_response = dict(api_response.json())

        if not api_response.ok:
            self.logger.error(api_response.content)
            return {}

        return json_response

    def get_best_flight(self, metatags: List[GoogleFlightMetaTag]) -> GoogleFlightMetaTag:
        highest = (0, 0)
        for i, metatag in enumerate(metatags):
            score = int(metatag.title is not None) + int(metatag.origin is not None) + int(
                metatag.airline is not None
            ) + int(metatag.destination is not None) + int(metatag.aircrafttype is not None) + (
                'live' in metatag.og_url
            ) and not (
                'history' in metatag.og_url
            )
            if score > highest[0]:
                highest = (i, score)

        return metatags[highest[0]]

    def get_flights_by_icao(self, flight_icao: str) -> None:
        api_response = self._send_request({'q': flight_icao})

        if api_response == {}:
            return

        flights: GoogleFlightResponse = GoogleFlightResponse.parse_obj(api_response)
        if flights.items is not None:
            best_flight = self.get_best_flight([x.pagemap.metatags[0] for x in flights.items])
            crud.update_route(self.db, google_flight_to_route(best_flight, flight_icao))
            self.logger.info(f'Stored flight from Google ({flight_icao})')
        else:
            self.logger.info(f'Could not find flight from Google ({flight_icao})')

    def store_missing_flight_data(self) -> None:
        self.logger.info('Storing missing flight data from Google...')
        max_items = 4
        rows_to_delete = []

        with open('data/to_update.csv', 'r') as f:
            lines = f.readlines()
            max_items = min(max_items, len(lines))
            for _ in range(max_items):
                flight_number = random.choice(lines).strip()
                rows_to_delete.append(flight_number)

                self.get_flights_by_icao(flight_icao=flight_number)

            # Delete flights that could not be found.
            with open('data/to_update.csv', 'w') as fw:
                lines = [x for x in lines if x not in rows_to_delete and x.strip() != '']
                fw.write('\n'.join(lines) + '\n')

        self.logger.info('Missing flight data from Google is stored.')
