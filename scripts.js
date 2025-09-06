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

// Dashed path
var path = L.polyline([
  [2.928260982179367, 101.64158677651704],
  [2.928171748808012, 101.64181511549168],
  [2.927864389363691, 101.6419210118276]
], {
  color: '#ff9999',
  weight: 1,
  dashArray: "5,5"
}).addTo(map);