// center of the map
var map = L.map('map').setView([2.927953649184701, 101.642168616230531], 17);


L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// like how much users can zoom in
var bounds = [
[2.925007050745863, 101.64058962504915],
[2.930762314451626, 101.64356106174803]
];

// restrict like how much only the users can view
map.setMaxBounds(bounds);
map.setMinZoom(16);   // stop zooming too far out
map.setMaxZoom(19);   // limit zoom in

fetch("campus_paths.geojson")
  .then(response => response.json())
  .then(data => {
    L.geoJSON(data, {
      style: {
        color: "#ff6666",   // lighter red
        weight: 1.5,
        dashArray: "2,8" // dashed line
      }
    }).addTo(map);
    window.campusPaths = data;
  });

  // Load campus places from GeoJSON
let campusPlaces = {};
let campusPolylines = [];
let routingControl = null;
let userMarker = null;

 // Load campus paths
 fetch("campus_paths.geojson")
 .then(res => res.json())
 .then(data => {
   var campusLayer = L.geoJSON(data, {
     style: { color: "red", weight: 3 }
   }).addTo(map);

   var campusPolylines = [];
   campusLayer.eachLayer(l => {
     if (l instanceof L.Polyline) campusPolylines.push(l);
   });


 fetch("campus_places.geojson")
  .then(res => res.json())
  .then(data => {
    data.features.forEach(feature => {
      let name = feature.properties.name;
      let coords = feature.geometry.coordinates.slice().reverse(); // [lat, lng]
      campusPlaces[name] = coords;

      // Optional: add markers for each place
      L.marker(coords).addTo(map).bindPopup(name);
    });
  });

   // Custom router for campus paths
   var customRouter = {
    route: function(waypoints, callback) {
      var line = [];
      waypoints.forEach(wp => {
        var closest = L.GeometryUtil.closest(map, campusPolylines, wp.latLng);
        line.push(closest);
      });
      var lineRoute = L.polyline(line, { color: 'blue', weight: 5 });

      callback(null, [{
        name: "Campus Route",
        coordinates: line,
        instructions: [],
        summary: { totalDistance: 0, totalTime: 0 },
        inputWaypoints: waypoints,
        waypoints: line.map(c => L.latLng(c)),
        bounds: lineRoute.getBounds()
      }]);
    }
  };


// Marker for user's location
let userMarker;

function onLocationFound(e) {
    const radius = e.accuracy;

    if (!userMarker) {
        userMarker = L.marker(e.latlng).addTo(map)
            .bindPopup("You are here")
            .openPopup();
        L.circle(e.latlng, radius, { color: 'blue', fillOpacity: 0.1 }).addTo(map);
    } else {
        userMarker.setLatLng(e.latlng);
    }
}


map.on('locationfound', onLocationFound);
map.on('locationerror', () => alert("Location access denied"));

// Start tracking user's location
map.locate({ setView: true, watch: true, maxZoom: 18 });

    // Search bar
    var geocoder = L.Control.geocoder({
      defaultMarkGeocode: false
    })
    .on('markgeocode', function(e) {
      var destLatLng = e.geocode.center;

      // Remove old route if exists
      if (routingControl) {
        map.removeControl(routingControl);
      }

      // Draw new route
      routingControl = L.Routing.control({
        waypoints: [
          userLatLng,
          destLatLng
        ],
        router: customRouter,
        routeWhileDragging: false,
        show: false,
        createMarker: function() { return null; }
      }).addTo(map);
    })
    .addTo(map);
  });
  

