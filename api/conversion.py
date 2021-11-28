from responses import AviationStackAirline

from models import Airline


def aviationstack_airline_to_airline(as_airline: AviationStackAirline) -> Airline:
    return Airline(**as_airline.dict(exclude={'id'}), aviationstack_id=as_airline.id)
