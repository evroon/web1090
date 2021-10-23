function UpdateStatistics(data) {
    $('#flight-count').text(`${data.live_flight_count}`);
    $('#registrations-count').text(`${data.registrations_count}`);
    $('#aircrafttypes-count').text(`${data.aircrafttypes_count}`);
    $('#adsb-signals-count').text(`${data.signals_count}`);
}

$(function () {
    'use strict'
    var api_domain = "";

    fetch('/config.json')
        .then(response => response.json())
        .then(data => api_domain = data.api_root_url)
        .then(data => UpdateAll(data));

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
    var active_icao = null;
    var flight_data = {};

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

        // var pieChartCanvas = $('#ac-type-chart-canvas').get(0).getContext('2d')
        // var pieData = {
        //     labels: Object.keys(aircrafttypes),
        //     datasets: [
        //         {
        //             data: Object.values(aircrafttypes),
        //             backgroundColor: colors
        //         }
        //     ]
        // }

        // var pieOptions = {
        //     legend: {
        //         display: false
        //     },
        //     maintainAspectRatio: false,
        //     responsive: true
        // }

        // new Chart(pieChartCanvas, { // lgtm[js/unused-local-variable]
        //     type: 'doughnut',
        //     data: pieData,
        //     options: pieOptions
        // })

        for (var i in aircrafttypes) {
            aircraft_table.row.add([
                i,
                aircrafttypes[i]
            ]).draw();
        }
    }

    function markerOnClick(e)
    {
        active_icao = e.sourceTarget.hex;
        UpdateInfo();
        UpdateLiveFlights();
    }

    function setValue(element, flight, field, value)
    {
        if (field == 'dep_airport')
            element.text(value + ` (${flight.route.dep_icao})`);
        else if (field == 'arr_airport')
            element.text(value + ` (${flight.route.arr_icao})`);
        else
            element.text(value);
    }

    function updateField(flight, field)
    {
        var element = $('#' + field);
        var route_elements = ['airline_name', 'dep_airport', 'arr_airport'];
        var value = null;
        if (flight != null && (!route_elements.includes(field) || flight.route != null))
            value = route_elements.includes(field) ? flight.route[field] : flight[field];

        if (flight == null || value == null) {
            element.html('<i>Unknown</i>');
        } else {
            setValue(element, flight, field, value);
        }
    }

    function UpdateInfo(flight) {
        if (flight != null && flight.flight_html != null)
            $('#callsign').html(flight.flight_html.replace('24', '64'));

        var fields = [
            'country',
            'registration',
            'aircrafttype',
            'alt_baro',
            'gs',
            'ias',
            'squawk',
            'airline_name',
            'dep_airport',
            'arr_airport'
        ];

        fields.forEach(field => {
            updateField(flight, field);
        })

        if (flight != null) {
            if (flight.images.length == 0)
                $('#img-container').hide();
            else
                $('#img-container').show();

            for (var i = 0; i < 5; i++) {
                var thumbnail_src = '';
                var image_src = '';

                if (flight.images[i] != null) {
                    thumbnail_src = api_domain + flight.images[i].thumbnail_endpoint;
                    image_src = api_domain + flight.images[i].image_endpoint;
                }

                var element = $('#image-' + i.toString());
                element.attr("src", thumbnail_src);
                element.parent().attr("href", image_src);
            }
        }
    }

    function UpdateLiveFlights() {
        flights_table.clear().draw();

        flight_data.forEach(flight => {
            flight.visible = flight.flight != null || flight.registration != null || flight.alt_baro != null;
        });

        Object.keys(markers).forEach(icao => {
            var remove_marker = true;
            flight_data.forEach(flight => {
                if (flight.hex == icao && flight.visible)
                    remove_marker = false;
            });

            if (remove_marker) {
                map.removeControl(markers[icao]);
                delete markers[icao];
            }
        });

        flight_data.forEach(flight => {
            var undefined = '<i>Unknown</i>'
            var tooltip = ''
            var route_str = undefined
            var route_description = undefined

            if (flight.airline_icon != null)
                tooltip += `<img style="width: 32px; height: auto; margin-right: 8px;" src="${api_domain + flight.airline_icon}"></img>`

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

            var is_selected = flight.hex == active_icao;
            var icon_url = api_domain + `ac_icon.svg?category=${flight.icon_category}&adsb_category=${flight.category}&is_selected=${is_selected}`;

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
                    ac_marker.on('click', markerOnClick);
                    ac_marker.hex = flight.hex;

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

            flight.flight_html = flight.flight;

            if (flight.flight != null && flight.route != null)
                flight.flight_html = `<span title="${flight.route.airline_name}">${flight.flight}</span>`;

            if (flight.airline_icon != null)
                flight.flight_html = `<img style="width: 24px; height: auto; margin-right: 8px;" src="${api_domain + flight.airline_icon}"></img>` + flight.flight_html;

            if (flight.registration != null)
                flight.registration_html = `<span style="width: 24px; height: auto; margin-right: 4px;" class="flag-icon flag-icon-${flight.country.toLowerCase()}"></span> ${flight.registration}`;

            const callsign = flight.flight_html == null ? undefined : flight.flight_html;
            const registration = flight.registration_html == null ? undefined : flight.registration_html;
            const aircrafttype = flight.aircrafttype == null ? undefined : flight.aircrafttype;
            const alt = flight.alt_baro == null ? undefined : flight.alt_baro + 'ft'

            flights_table.row.add([
                callsign,
                route_str,
                registration,
                aircrafttype,
                alt
            ]);

            if (active_icao == flight.hex)
                UpdateInfo(flight);
        });
        flights_table.draw();
    }

    function RefreshFlights() {
        if ($('#world-map').length < 1)
            return;

        fetch(api_domain + 'liveflights')
            .then(response => response.json())
            .then(data => {flight_data = data.aircraft; UpdateLiveFlights()});
    }

    function RefreshStatistics() {
        fetch(api_domain + 'statistics')
            .then(response => response.json())
            .then(data => UpdateStatistics(data));
    }

    function UpdateAll(api_domain) {
        $('#api-link').html(`<a href="${api_domain}">WEB1090 API</a>`);

        setInterval(RefreshFlights, 1000);
        setInterval(RefreshStatistics, 30000);
        RefreshStatistics();

        if ($('#ac-type-chart').length > 0) {
            fetch(api_domain + 'aircrafttypes')
                .then(response => response.json())
                .then(data => UpdateAircraftTypes(data.data));
        }
    }

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
