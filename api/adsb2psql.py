from data import ADSBData
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


con = psycopg2.connect(database=PSQL_DB, user=PSQL_USER, password=PSQL_PASSWORD, host="127.0.0.1", port=PSQL_PORT)
print("Database opened successfully")

with open('data/db.json', 'r') as f:
    db = json.load(f)

ROUTESDATA_DB='routesdata'
FLIGHTDATA_DB='flightdata'
AIRCRAFTDATA_DB='aircraftdata'
AIRCRAFT_IMAGES_DB='aircraftimages'
AIRPORTDATA_DB='airportdata'

flightdata_columns = db['flightdata_columns']
aircraft_image_columns = db['aircraft_image_columns']
aircraftdata_columns = db['aircraftdata_columns']
airportdata_columns = db['airportdata_columns']
routesdata_columns = db['routesdata_columns']



def insert_in_table(cur, columns, aggregated_data, table_name, id=None) -> None:
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
    con.commit()


def store_routedata_virtualradar() -> None:
    print('Storing routes...')
    conn = sqlite3.connect('VIRTUALRADAR_SQLITE_DB_PATH')
    cur_in = conn.execute('select * from RouteView')
    cur = con.cursor()
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
            'dep_country_id': get_country_id(route[16]),

            'arr_icao': route[18],
            'arr_iata': route[19],
            'arr_airport': route[20],
            'arr_lat': route[21],
            'arr_lon': route[22],
            'arr_alt': route[23],
            'arr_loc': route[24],
            'arr_country': route[26],
            'arr_country_id': get_country_id(route[26]),
        })

    for i in range(0, len(aggregated_route_data), batch_size):
        insert_in_table(cur, routesdata_columns, aggregated_route_data[i:i+batch_size], ROUTESDATA_DB, 'icao')

    print('Finished loading routes.')
    conn.close()


def store_routedata_aviationstack() -> None:
    # TODO: Outdated.
    print('Storing routes...')
    total = 1e8
    pagination = 100
    cur = con.cursor()
    i = 0

    while i < total:
        params = {
            'access_key': '${AVIATIONSTACK_KEY}',
            'offset': i,
        }
        api_result = requests.get('http://api.aviationstack.com/v1/flights', params)

        if not api_result.ok:
            print(api_result.content)
            return

        api_response = api_result.json()
        total = api_response['pagination']['total']

        aggregated_route_data = []
        aggregated_aircraft_data = []
        flight_icaos = []
        aircraft_icaos = []

        for flight in api_response['data']:
            if flight['flight']['icao'] is None or flight['flight']['icao'] in flight_icaos:
                continue

            aggregated_route_data.append({
                'number': flight['flight']['number'],
                'icao': flight['flight']['icao'],
                'iata': flight['flight']['iata'],

                'airline_name': flight['airline']['name'],
                'airline_iata': flight['airline']['iata'],
                'airline_icao': flight['airline']['icao'],

                'dep_airport': flight['departure']['airport'],
                'dep_timezone': flight['departure']['timezone'],
                'dep_terminal': flight['departure']['terminal'],
                'dep_gate': flight['departure']['gate'],
                'dep_icao': flight['departure']['icao'],
                'dep_iata': flight['departure']['iata'],
                'dep_time': flight['departure']['scheduled'],

                'arr_airport': flight['arrival']['airport'],
                'arr_timezone': flight['arrival']['timezone'],
                'arr_terminal': flight['arrival']['terminal'],
                'arr_gate': flight['arrival']['gate'],
                'arr_icao': flight['arrival']['icao'],
                'arr_iata': flight['arrival']['iata'],
                'arr_time': flight['arrival']['scheduled'],
            })
            flight_icaos.append(flight['flight']['icao'])

            if flight['aircraft'] is not None and flight['aircraft']['icao24'] is not None and flight['aircraft']['icao24'] not in aircraft_icaos:
                aggregated_aircraft_data.append({
                    'icao': flight['aircraft']['icao24'],
                    'registration': flight['aircraft']['registration'],
                    'aircrafttype': flight['aircraft']['iata'],
                })
                aircraft_icaos.append(flight['aircraft']['icao24'])

        insert_in_table(cur, routesdata_columns, aggregated_route_data, ROUTESDATA_DB, 'icao')
        insert_in_table(cur, aircraftdata_columns, aggregated_aircraft_data, AIRCRAFTDATA_DB, 'icao')

        i += pagination

    print('Route data is stored.')


def store_airportdata() -> None:
    print('Storing airports...')
    total = 1e8
    pagination = 100
    cur = con.cursor()
    i = 0

    while i < total:
        params = {
            'access_key': '${AVIATIONSTACK_KEY}',
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

        insert_in_table(cur, airportdata_columns, aggregated_data, AIRPORTDATA_DB, 'icao')

        i += pagination
        break

    print('Airport data is stored.')


def store_aircraftdata() -> None:
    print('Storing aircraft data in postgres...')
    cur = con.cursor()
    batch_size = 10000
    data = ADSBData()

    with open('data/flightaware.csv', 'r') as f:
        reader = csv.reader(f, delimiter=',')
        aggregated_data = []

        # Skip header
        next(reader, None)

        for i, aircraft in enumerate(reader):
            if i % 1000 == 0:
                print(f'Progress: {i}')

            icao = aircraft[0].upper()
            reg = aircraft[1]
            ac_type = aircraft[2]

            country = data.get_country(icao)
            category = data.get_category(ac_type)
            family = data.get_family(ac_type)

            aggregated_data.append({
                'icao': icao,
                'registration': reg,
                'aircrafttype': ac_type,
                'country': country,
                'category': category,
                'family': family,
            })

        for i in range(0, len(aggregated_data), batch_size):
            insert_in_table(cur, aircraftdata_columns, aggregated_data[i:i+batch_size], AIRCRAFTDATA_DB, 'icao')

        print('Aircraft data is stored.')


def get_aircraft_images(icao: str) -> None:
    print(f'Retrieving aircraft images for {icao}')
    cur = con.cursor()
    count = 50

    response = requests.get(f'https://www.airport-data.com/api/ac_thumb.json?m={icao}&n={count}')
    if not response.ok:
        return []

    json_response = response.json()
    aggregated_data = []

    for i, aircraft in enumerate(json_response['data']):
        thumbnail = aircraft[i]['image']
        image = thumbnail.replace('/thumbnails', '')
        link = aircraft[i]['link']
        photographer = aircraft[i]['photographer']

        aggregated_data.append({
            'image': image,
            'link': link,
            'photographer': photographer,
        })

    insert_in_table(cur, aircraftdata_columns, aggregated_data, AIRCRAFT_IMAGES_DB, 'id')

    print('Aircraft images are stored.')


def get_aircraftdata(hexcode: str) -> dict:
    cur = con.cursor()
    cur.execute(f"SELECT * FROM {AIRCRAFTDATA_DB} WHERE icao=%(hex)s", {'hex': hexcode})
    rows = cur.fetchone()

    if rows is None:
        return {}

    return {
        'registration': rows[1],
        'aircrafttype': rows[2],
    }


def table_exists(table_name: str) -> bool:
    cur = con.cursor()
    cur.execute("select * from information_schema.tables where table_name=%s", (table_name,))
    return cur.rowcount > 0


def create_table(table_name: str, columns: dict) -> None:
    print(f'Creating table {table_name}')
    columns_query = ', '.join([f'{k} {v}' for k, v in columns.items()])

    cur = con.cursor()
    cur.execute(f'CREATE TABLE {table_name}({columns_query});')
    con.commit()


def store_data(aggregated_data: list) -> None:
    print(f'Writing {len(aggregated_data)} entries to database.')
    columns_without_id = flightdata_columns
    if 'id' in columns_without_id:
        del columns_without_id['id']

    cur = con.cursor()
    data_values = ','.join([f'%({x})s' for x in columns_without_id.keys()])
    columns_keys = ','.join(columns_without_id.keys())
    args_str = ','.join(['(' + cur.mogrify(data_values, x).decode("utf-8") + ')' for x in aggregated_data])

    cur.execute(f"INSERT INTO {FLIGHTDATA_DB} ({columns_keys}) VALUES {args_str}")
    con.commit()


def insert_data(batch_size: int, wait_period: float) -> None:
    aggregated_data = []

    print('Start collecting data...')
    while True:
        response = requests.get(DUMP1090_ADDRESS)
        if response.ok:
            content = json.loads(response.content)

            for aircraft in content['aircraft']:
                # Store only entries with an altitude or location.
                if 'alt_baro' not in aircraft and 'lat' not in aircraft:
                    continue

                if 'flight' in aircraft:
                    aircraft['flight'] = aircraft['flight'].strip()

                if 'nav_modes' in aircraft:
                    aircraft['nav_modes'] = ','.join(aircraft['nav_modes'])

                aircraft['date_time'] = datetime.datetime.utcfromtimestamp(content['now'])
                aircraft['hex'] = aircraft['hex'].upper()

                acdata = get_aircraftdata(aircraft['hex'])

                if 'aircrafttype' in acdata:
                    aircraft['aircrafttype'] = acdata['aircrafttype']
                    aircraft['registration'] = acdata['registration']

                for key in flightdata_columns.keys():
                    if key not in aircraft:
                        aircraft[key] = None

                aggregated_data.append(aircraft)

                if len(aggregated_data) >= batch_size:
                    store_data(aggregated_data)
                    aggregated_data = []

        time.sleep(wait_period)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Stores ADS-B data in postgres database.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Number of entries to store in database per insertion.',
        default=1e3
    )
    parser.add_argument(
        '--wait-period',
        type=float,
        help='Update interval between dump1090 requests (s).',
        default=1
    )
    parser.add_argument(
        '--get-aircraft-type',
        type=str,
        help='Get the aircraft type given a hexcode.'
    )
    args = parser.parse_args()

    if not table_exists(AIRCRAFTDATA_DB):
        create_table(AIRCRAFTDATA_DB, aircraftdata_columns)
        store_aircraftdata()

    if not table_exists(ROUTESDATA_DB):
        create_table(ROUTESDATA_DB, routesdata_columns)
        store_routedata_virtualradar()

    # if not table_exists(AIRPORTDATA_DB):
    #     create_table(AIRPORTDATA_DB, airportdata_columns)
    #     store_airportdata()

    if not table_exists(FLIGHTDATA_DB):
        create_table(FLIGHTDATA_DB, flightdata_columns)

    if args.get_aircraft_type is not None:
        print(get_aircraftdata(args.get_aircraft_type))
    else:
        insert_data(args.batch_size, args.wait_period)
        con.close()
