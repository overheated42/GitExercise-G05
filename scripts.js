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



L.marker([2.927953649184701, 101.64216861623053]).addTo(map)
  .bindPopup("Campus Center")
  .openPopup();