from responses import AviationStackAirline, AviationStackRealTimeFlight

from models import Aircraft, Airline, Route


def aviationstack_airline_to_airline(as_airline: AviationStackAirline) -> Airline:
    return Airline(**as_airline.dict(exclude={'id'}), aviationstack_id=as_airline.id)


def aviationstack_flight_to_route(as_flight: AviationStackRealTimeFlight) -> Route:
    return Route(
        icao=as_flight.flight.icao,
        number=as_flight.flight.number,
        airline_name=as_flight.airline.name,
        airline_iata=as_flight.airline.iata,
        airline_icao=as_flight.airline.icao,
        dep_airport=as_flight.departure.airport,
        dep_icao=as_flight.departure.icao,
        dep_iata=as_flight.departure.iata,
        arr_airport=as_flight.arrival.airport,
        arr_icao=as_flight.arrival.icao,
        arr_iata=as_flight.arrival.iata,
    )

def aviationstack_flight_to_aircraft(as_flight: AviationStackRealTimeFlight) -> Aircraft:
    return Aircraft(
        icao=as_flight.aircraft.icao,
        iata=as_flight.aircraft.iata,
        registration=as_flight.aircraft.registration,
    )
