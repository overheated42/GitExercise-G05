// center of the map
var map = L.map('map').setView([2.927953649184701, 101.64216861623053], 17);


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
  });

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

function onLocationError(e) {
    alert("Unable to retrieve your location. Please allow location access.");
}

map.on('locationfound', onLocationFound);
map.on('locationerror', onLocationError);

// Start tracking user's location
map.locate({ setView: true, watch: true, maxZoom: 18 });