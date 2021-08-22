function UpdateStatistics(data) {
    $('#flight-count').text(`${data.flight_count}`);
    $('#registrations-count').text(`${data.registrations_count}`);
    $('#aircrafttypes-count').text(`${data.aircrafttypes_count}`);
    $('#adsb-signals-count').text(`${data.signals_count}`);
}

$(function () {
    'use strict'

    var api_domain = '<domain name>'

    if ($('#world-map').length > 0) {
        var map = L.map('world-map').setView([52.15, 4.8], 8);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            transparent: true,
        }).addTo(map);
    }

    if ($('#table-live-flights').length > 0) {
        var flights_table = $('#table-live-flights').DataTable({
            "paging": false,
            "lengthChange": false,
            "searching": false,
            "ordering": true,
            "info": false,
            "autoWidth": false,
            "responsive": true,
        });
    }

    if ($('#table-aircraft').length > 0) {
        var aircraft_table = $('#table-aircraft').DataTable({
            "paging": true,
            "lengthChange": false,
            "searching": false,
            "ordering": true,
            "info": false,
            "autoWidth": false,
            "responsive": true,
        });
    }

    var markers = {}
    var marker_urls = {}

    function UpdateAircraftTypes(aircrafttypes) {
        var colors = [];

        var dynamicColors = function () {
            var r = Math.floor(Math.random() * 255);
            var g = Math.floor(Math.random() * 255);
            var b = Math.floor(Math.random() * 255);
            return "rgb(" + r + "," + g + "," + b + ")";
        };
        for (var i in aircrafttypes) {
            colors.push(dynamicColors());
        }

        var pieChartCanvas = $('#ac-type-chart-canvas').get(0).getContext('2d')
        var pieData = {
            labels: Object.keys(aircrafttypes),
            datasets: [
                {
                    data: Object.values(aircrafttypes),
                    backgroundColor: colors
                }
            ]
        }

        var pieOptions = {
            legend: {
                display: false
            },
            maintainAspectRatio: false,
            responsive: true
        }

        new Chart(pieChartCanvas, { // lgtm[js/unused-local-variable]
            type: 'doughnut',
            data: pieData,
            options: pieOptions
        })

        for (var i in aircrafttypes) {
            aircraft_table.row.add([
                i,
                aircrafttypes[i]
            ]).draw();
        }
    }

    function UpdateLiveFlights(flights) {
        flights_table.clear().draw();

        flights.forEach(flight => {
            flight.visible = flight.flight != null || flight.registration != null || flight.alt_baro != null;
        });

        Object.keys(markers).forEach(icao => {
            var remove_marker = true;
            flights.forEach(flight => {
                if (flight.hex == icao && flight.visible)
                    remove_marker = false;
            });

            if (remove_marker) {
                map.removeControl(markers[icao]);
                delete markers[icao];
            }
        });

        flights.forEach(flight => {
            var undefined = '<i>Unknown</i>'
            var tooltip = ''
            var route_str = undefined
            var route_description = undefined

            if (flight.airline_icon != null)
                tooltip += `<img style="width: 32px; height: auto; margin-right: 8px;" src="${flight.airline_icon}"></img>`

            if (flight.flight != null)
                tooltip += `<b title="${flight.airline_name}">${flight.flight}</b></br>`

            if (flight.registration != null)
                tooltip += `${flight.registration}</br>`

            if (flight.route != null) {
                route_description = `${flight.route.dep_airport} - ${flight.route.arr_airport}`
                route_str = `<span title="${route_description}">${flight.route.dep_icao} - ${flight.route.arr_icao}</span></br>`
                tooltip += route_str
            }

            if (flight.aircrafttype != null)
                tooltip += `${flight.aircrafttype}</br>`;

            var icon_url = api_domain + `/ac_icon.svg?category=${flight.icon_category}&adsb_category=${flight.category}`;

            if (flight.lat != null) {
                var ac_marker = null;

                var ac_icon = L.icon({
                    iconUrl: icon_url,
                    iconSize: [36, 36],
                    iconAnchor: [18, 18],
                    popupAnchor: [0, -18],
                    tooltipAnchor: [18, 0],
                });

                if (flight.hex in markers) {
                    ac_marker = markers[flight.hex];
                    ac_marker.setLatLng([flight.lat, flight.lon]);
                    ac_marker.setRotationAngle(flight.track);

                    if (marker_urls[flight.hex] != icon_url) {
                        ac_marker.setIcon(ac_icon);
                        marker_urls[flight.hex] = icon_url;
                    }

                } else {
                    var ac_marker = L.marker([flight.lat, flight.lon], {
                        icon: ac_icon,
                        rotationAngle: flight.track,
                    }).addTo(map);
                    markers[flight.hex] = ac_marker;
                    marker_urls[flight.hex] = icon_url;
                }

                if (tooltip != '')
                    ac_marker.bindTooltip(tooltip);
            }

            if (!flight.visible)
                return;

            if (flight.flight != null && flight.route != null)
                flight.flight = `<span title="${flight.route.airline_name}">${flight.flight}</span>`;

            if (flight.airline_icon != null)
                flight.flight = `<img style="width: 24px; height: auto; margin-right: 8px;" src="${flight.airline_icon}"></img>` + flight.flight;

            if (flight.registration != null)
                flight.registration = `<span style="width: 24px; height: auto; margin-right: 4px;" class="flag-icon flag-icon-${flight.country.toLowerCase()}"></span> ${flight.registration}`;

            const callsign = flight.flight == null ? undefined : flight.flight;
            const registration = flight.registration == null ? undefined : flight.registration;
            const aircrafttype = flight.aircrafttype == null ? undefined : flight.aircrafttype;
            const alt = flight.alt_baro == null ? undefined : flight.alt_baro + 'ft'

            flights_table.row.add([
                callsign,
                route_str,
                registration,
                aircrafttype,
                alt
            ]).draw();
        });
    }

    function RefreshFlights() {
        if ($('#world-map').length < 1)
            return;

        fetch(api_domain + '/liveflights')
            .then(response => response.json())
            .then(data => UpdateLiveFlights(data.aircraft));
    }

    function UpdateAll() {
        if ($('#ac-type-chart').length > 0) {
            fetch(api_domain + '/aircrafttypes')
                .then(response => response.json())
                .then(data => UpdateAircraftTypes(data.data));
        }

        setInterval(RefreshFlights, 1000);

        fetch(api_domain + '/statistics')
            .then(response => response.json())
            .then(data => UpdateStatistics(data));
    }

    UpdateAll();

    // Make the dashboard widgets sortable Using jquery UI
    $('.connectedSortable').sortable({
        placeholder: 'sort-highlight',
        connectWith: '.connectedSortable',
        handle: '.card-header, .nav-tabs',
        forcePlaceholderSize: true,
        zIndex: 999999
    })
    $('.connectedSortable .card-header').css('cursor', 'move')

    // bootstrap WYSIHTML5 - text editor
    $('.textarea').summernote()

    if ($('.daterange').length > 0) {
        $('.daterange').daterangepicker({
            ranges: {
                Today: [moment(), moment()],
                Yesterday: [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
                'Last 7 Days': [moment().subtract(6, 'days'), moment()],
                'Last 30 Days': [moment().subtract(29, 'days'), moment()],
                'This Month': [moment().startOf('month'), moment().endOf('month')],
                'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
            },
            startDate: moment().subtract(29, 'days'),
            endDate: moment()
        }, function (start, end) {
            // eslint-disable-next-line no-alert
            alert('You chose: ' + start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'))
        })
    }


    if ($('#revenue-chart-canvas').length > 0) {
        /* Chart.js Charts */
        // Sales chart
        var salesChartCanvas = document.getElementById('revenue-chart-canvas').getContext('2d')
        // $('#revenue-chart').get(0).getContext('2d');

        var salesChartData = {
            labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
            datasets: [
                {
                    label: 'Digital Goods',
                    backgroundColor: 'rgba(60,141,188,0.9)',
                    borderColor: 'rgba(60,141,188,0.8)',
                    pointRadius: false,
                    pointColor: '#3b8bba',
                    pointStrokeColor: 'rgba(60,141,188,1)',
                    pointHighlightFill: '#fff',
                    pointHighlightStroke: 'rgba(60,141,188,1)',
                    data: [28, 48, 40, 19, 86, 27, 90]
                },
                {
                    label: 'Electronics',
                    backgroundColor: 'rgba(210, 214, 222, 1)',
                    borderColor: 'rgba(210, 214, 222, 1)',
                    pointRadius: false,
                    pointColor: 'rgba(210, 214, 222, 1)',
                    pointStrokeColor: '#c1c7d1',
                    pointHighlightFill: '#fff',
                    pointHighlightStroke: 'rgba(220,220,220,1)',
                    data: [65, 59, 80, 81, 56, 55, 40]
                }
            ]
        }
    }
})
