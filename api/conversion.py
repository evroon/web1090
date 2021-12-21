from models import Aircraft, Airline, Route
from responses import (
    AviationStackAirline,
    AviationStackRealTimeFlight,
    GoogleFlightMetaTag,
    SchipholFlight,
    VirtualRadarRoute,
)


def aviationstack_airline_to_airline(as_airline: AviationStackAirline) -> Airline:
    return Airline(**as_airline.dict(exclude={'id'}), aviationstack_id=as_airline.id)


def aviationstack_flight_to_route(as_flight: AviationStackRealTimeFlight) -> Route:
    return Route(
        icao=as_flight.flight.icao,
        iata=as_flight.flight.iata,
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
        icao=as_flight.aircraft.icao24.lower(),
        iata=as_flight.aircraft.iata,
        model_code=as_flight.aircraft.icao,
        registration=as_flight.aircraft.registration,
    )


def schiphol_flight_to_route(sch_flight: SchipholFlight) -> Route:
    return Route(
        icao=sch_flight.flightName,
        iata=sch_flight.flightName,
        number=sch_flight.flightNumber,
        airline_icao=sch_flight.prefixICAO,
        airline_iata=sch_flight.prefixIATA,
        dep_iata=sch_flight.route.destinations[0] if sch_flight.flightDirection == 'A' else 'AMS',
        arr_iata=sch_flight.route.destinations[0] if sch_flight.flightDirection == 'D' else 'AMS',
    )


def schiphol_flight_to_aircraft(sch_flight: SchipholFlight, icao: str) -> Aircraft:
    return Aircraft(
        icao=icao,
        iata=sch_flight.aircraftType.iataMain,
        airline_iata=sch_flight.prefixIATA,
        registration=sch_flight.aircraftRegistration,
    )


def virtualradar_route_to_route(vr_flight: VirtualRadarRoute) -> Route:
    return Route(
        icao=vr_flight.Callsign,
        iata=None,
        airline_name=vr_flight.OperatorName,
        airline_iata=vr_flight.OperatorIata,
        airline_icao=vr_flight.OperatorIcao,
        dep_airport=vr_flight.FromAirportName,
        dep_icao=vr_flight.FromAirportIcao,
        dep_iata=vr_flight.FromAirportIata,
        dep_lat=vr_flight.FromAirportLatitude,
        dep_lon=vr_flight.FromAirportLongitude,
        dep_alt=vr_flight.FromAirportAltitude,
        dep_loc=vr_flight.FromAirportLocation,
        dep_country=vr_flight.FromAirportCountry,
        dep_country_id=vr_flight.FromAirportCountryId,
        arr_airport=vr_flight.ToAirportName,
        arr_icao=vr_flight.ToAirportIcao,
        arr_iata=vr_flight.ToAirportIata,
        arr_lat=vr_flight.ToAirportLatitude,
        arr_lon=vr_flight.ToAirportLongitude,
        arr_alt=vr_flight.ToAirportAltitude,
        arr_loc=vr_flight.ToAirportLocation,
        arr_country=vr_flight.ToAirportCountry,
        arr_country_id=vr_flight.ToAirportCountryId,
    )


def google_flight_to_route(g_flight: GoogleFlightMetaTag, icao: str) -> Route:
    return Route(
        icao=icao,
        iata=g_flight.title.split(' ')[0] if g_flight.title is not None else None,
        airline_icao=g_flight.airline,
        dep_icao=g_flight.origin,
        arr_icao=g_flight.destination,
    )
