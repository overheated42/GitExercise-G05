// ============================
// Initialize Map
// ============================
var map = L.map('map').setView([2.92795, 101.64216], 17);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Restrict map bounds and zoom
var bounds = [
  [2.933524650336691, 101.63872492066997],
  [2.92263838437214, 101.64649259787942]
];
map.setMaxBounds(bounds);
map.setMinZoom(16);
map.setMaxZoom(19);


// ============================
// Load Campus Paths
// ============================
let campusPolylines = [];

fetch("static/campus_paths.geojson")
.then(res => res.json())
.then(data => {
  var campusLayer = L.geoJSON(data, { 
    style: { color: "red", weight: 2, dashArray: '2,4' } 
  }).addTo(map);

  campusLayer.eachLayer(l => { 
    if(l instanceof L.Polyline) campusPolylines.push(l); 
  });
});


// ============================
// Load Campus Places
// ============================
let campusPlaces = {};
fetch("static/campus_places.geojson")
.then(res => res.json())
.then(data => {
  data.features.forEach(feature => {
    let name = feature.properties.name;
    let coords = feature.geometry.coordinates.slice().reverse();
    campusPlaces[name] = coords;
    
  });
  initCampusSearch();
});

// ============================
// Snap to nearest polyline point
// ============================
function snapToPolyline(latlng, polylines) {
  let closestPoint = null;
  let minDist = Infinity;

  polylines.forEach(pl => {
    pl.getLatLngs().forEach(p => {
      let dist = latlng.distanceTo(p);
      if(dist < minDist) {
        minDist = dist;
        closestPoint = p;
      }
    });
  });

  return closestPoint;
}

// ============================
// Custom Campus Search + Routing
// ============================
let routingControl = null;
let userMarker, routeLine;
let currentDestMarker = null;
let searchHistory = []; // store recent searches

function initCampusSearch() {
  // ============================
  // Using HTML elements for search sidebar
  // ============================
  const searchInput = document.getElementById('searchInput');
  const suggestionBox = document.getElementById('suggestionBox');
   

  // ============================
  // Handle typing (suggestions)
  // ============================
  searchInput.addEventListener('input', function () {
    const val = this.value.toLowerCase();
    suggestionBox.innerHTML = '';
    if (!val) return;

    Object.keys(campusPlaces).forEach(name => {
      if (name.toLowerCase().includes(val)) {
        let div = document.createElement('div');
        Object.assign(div.style, {
          padding: '5px',
          cursor: 'pointer'
        });
        div.innerText = name;

        div.addEventListener('click', () => selectPlace(name));
        suggestionBox.appendChild(div);
      }
    });
  });

  // ============================
  // Show search history on focus
  // ============================
  searchInput.addEventListener('focus', function () {
    suggestionBox.innerHTML = '';

    if (searchHistory.length > 0) {
      let header = document.createElement('div');
      header.innerText = "Recent Searches";
      Object.assign(header.style, {
        fontWeight: "bold",
        borderTop: "1px solid #ccc",
        marginTop: "5px",
        padding: "5px"
      });
      suggestionBox.appendChild(header);

      searchHistory.slice(-5).reverse().forEach(item => {
        let div = document.createElement('div');
        Object.assign(div.style, {
          padding: '5px',
          cursor: 'pointer',
          color: 'gray'
        });
        div.innerText = item;
        div.addEventListener('click', () => selectPlace(item));
        suggestionBox.appendChild(div);
      });
    }
  });

  // ============================
  // Select place function
  // ============================
  function selectPlace(name) {
    let coords = campusPlaces[name];
    map.setView(coords, 18);

    // Replace destination marker
    if (currentDestMarker) map.removeLayer(currentDestMarker);
    currentDestMarker = L.marker(coords).addTo(map).bindPopup(name).openPopup();

    suggestionBox.innerHTML = '';
    searchInput.value = '';

    // Save to history (avoid duplicates)
    if (!searchHistory.includes(name)) {
      searchHistory.push(name);
    }

    if (!userMarker) return alert("Waiting for GPS location...");

    // Request route
    customRouter.route(
      [
        { latLng: userMarker.getLatLng() },
        { latLng: L.latLng(coords) }
      ],
      function (err, routes) {
        if (!err) {
          const route = routes[0];
          if (routeLine) map.removeLayer(routeLine);

          routeLine = L.polyline(route.coordinates, { color: '#00BFFF', weight: 5 }).addTo(map);
          map.fitBounds(routeLine.getBounds());

          // Show distance/time
          routeInfo.style.display = 'block';
          routeInfo.innerHTML = `
            <b>Walking Route</b><br>
            Distance: ${(route.summary.totalDistance / 1000).toFixed(2)} km<br>
            Time: ${Math.round(route.summary.totalTime / 60)} min
          `;
        }
      }
    );
  }
}

// ============================
// Build Graph from Campus Paths
// ============================
function buildGraphFromPolylines(polylines) {
  let graph = {};

  function key(latlng) {
    return latlng.lat.toFixed(6) + "," + latlng.lng.toFixed(6);
  }

  polylines.forEach(pl => {
    let coords = pl.getLatLngs();
    for (let i = 0; i < coords.length - 1; i++) {
      let a = key(coords[i]);
      let b = key(coords[i + 1]);
      let dist = coords[i].distanceTo(coords[i + 1]);

      if (!graph[a]) graph[a] = {};
      if (!graph[b]) graph[b] = {};

      graph[a][b] = dist;
      graph[b][a] = dist;
    }
  });

  return graph;
}

// Dijkstra’s Algorithm
function dijkstra(graph, startKey, endKey) {
  let distances = {};
  let prev = {};
  let pq = new Set(Object.keys(graph));

  Object.keys(graph).forEach(node => {
    distances[node] = Infinity;
  });
  distances[startKey] = 0;

  while (pq.size > 0) {
    let u = null;
    pq.forEach(node => {
      if (u === null || distances[node] < distances[u]) {
        u = node;
      }
    });

    if (u === endKey) break;
    pq.delete(u);

    Object.keys(graph[u]).forEach(v => {
      let alt = distances[u] + graph[u][v];
      if (alt < distances[v]) {
        distances[v] = alt;
        prev[v] = u;
      }
    });
  }

  let path = [];
  let u = endKey;
  while (u) {
    path.unshift(u);
    u = prev[u];
  }

  return path;
}

// ============================
// Polyline Distance Helper
// ============================
function polylineDistance(coords) {
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    total += coords[i - 1].distanceTo(coords[i]);
  }
  return total; // meters
}

// ============================
// Custom Router with Dijkstra
// ============================
var customRouter = {
  route: function(waypoints, callback) {
    let start = waypoints[0].latLng;
    let end = waypoints[1].latLng;

    let startSnap = snapToPolyline(start, campusPolylines);
    let endSnap = snapToPolyline(end, campusPolylines);

    if (!startSnap || !endSnap) {
      return callback("No nearby campus paths found", null);
    }

    let graph = buildGraphFromPolylines(campusPolylines);
    let startKey = startSnap.lat.toFixed(6) + "," + startSnap.lng.toFixed(6);
    let endKey = endSnap.lat.toFixed(6) + "," + endSnap.lng.toFixed(6);

    let pathKeys = dijkstra(graph, startKey, endKey);
    if (pathKeys.length === 0) {
      return callback("No path found", null);
    }

    // Convert keys back to LatLngs
    let coords = pathKeys.map(k => {
      let [lat, lng] = k.split(",").map(Number);
      return L.latLng(lat, lng);
    });

    // Add exact start/end
    if (!coords[0].equals(start)) coords.unshift(start);
    if (!coords[coords.length - 1].equals(end)) coords.push(end);

    let totalDist = polylineDistance(coords);

    callback(null, [{
      name: "Campus Route",
      coordinates: coords,
      instructions: [],
      summary: { 
        totalDistance: totalDist, 
        totalTime: totalDist / 1.4
      },
      inputWaypoints: waypoints,
      waypoints: coords,
      bounds: L.polyline(coords).getBounds()
    }]);
  }
};


// ============================
// User Tracking (Snapped to Route)
// ============================
function updateUserPosition(lat, lng) {
  let latlng = L.latLng(lat, lng);

  // If a route exists, snap to nearest point on it
  let snapped = (routeLine) ? snapToPolyline(latlng, [routeLine]) : latlng;

  if(!userMarker){
    const arrowIcon = L.divIcon({ 
      html: `<div style="color:#780606; font-size:25px;">➤</div>`,
      className: "user-arrow",
      iconSize: [30, 30]
    });
    userMarker = L.marker(snapped, {icon: arrowIcon}).addTo(map)

    let tooltip = userMarker.bindTooltip("You are here", {
      permanent: true,
      direction: "top",
      offset: [0, -10]
    }).openTooltip();
    
    // Hide after 5 seconds
    setTimeout(() => {
      userMarker.unbindTooltip();
    }, 5000);
  } else {
    userMarker.setLatLng(snapped);
  }

  // Smooth follow
  map.setView(snapped, map.getZoom(), { animate: true });

  // Auto-update route if destination exists
  if(userMarker && currentDestMarker) {
    customRouter.route(
      [
        { latLng: snapped },  // use snapped position
        { latLng: currentDestMarker.getLatLng() }
      ],
      function(err, routes) {
        if(!err) {
          if(routeLine) map.removeLayer(routeLine);
          routeLine = L.polyline(routes[0].coordinates, { color: 'blue', weight: 5 }).addTo(map);
        }
      }
    );
  }
}

// ============================
// Detect Geolocation or fallback to fixed campus center
// ============================
const CAMPUS_CENTER = { lat: 2.92795, lng: 101.64216 }; // your campus center

if ("geolocation" in navigator) {
    navigator.geolocation.watchPosition(
        (pos) => {
            updateUserPosition(pos.coords.latitude, pos.coords.longitude);
        },
        (err) => {
            console.warn("GPS failed, using fixed campus center:", err.message);
            updateUserPosition(CAMPUS_CENTER.lat, CAMPUS_CENTER.lng);
        },
        { enableHighAccuracy: true }
    );
} else {
    console.warn("No geolocation support, using fixed campus center");
    updateUserPosition(CAMPUS_CENTER.lat, CAMPUS_CENTER.lng);
}


// ============================
// Sidebar Dropdown Toggle
// ============================
const routeInfo = document.getElementById("route-info");

function updateRouteInfo(route, destinationName) {
  routeInfo.style.display = 'block';
  routeInfo.innerHTML = `
    <b>Walking Route </b><br>
    Distance: ${(route.summary.totalDistance / 1000).toFixed(2)} km<br>
    Time: ${Math.round(route.summary.totalTime / 60)} min
  `;
}
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".dropdown-toggle").forEach(toggle => {
      toggle.addEventListener("click", function (e) {
          e.preventDefault();
          this.parentElement.classList.toggle("open");
      });
  });

  // Handle clicks on dropdown menu items -> trigger map route
  document.querySelectorAll(".dropdown-menu a").forEach(link => {
      link.addEventListener("click", function (e) {
          e.preventDefault();
          const destKey = this.dataset.destination; // e.g. "faculty-computing"

          if (campusPlaces[destKey]) {
              const coords = campusPlaces[destKey];
              map.setView(coords, 18);

              // replace destination marker
              if (currentDestMarker) map.removeLayer(currentDestMarker);
              currentDestMarker = L.marker(coords).addTo(map).bindPopup(this.textContent).openPopup();


              // request route from user to this place
              if (userMarker) {
                customRouter.route(
                  [
                    { latLng: userMarker.getLatLng() },
                    { latLng: L.latLng(coords) }
                  ],
                  function(err, routes) {
                    if (!err) {
                      const route = routes[0];
                      if(routeLine) map.removeLayer(routeLine);
                      routeLine = L.polyline(route.coordinates, { color: '#00BFFF', weight: 5 }).addTo(map);
                      map.fitBounds(routeLine.getBounds());
      
              // ✅ Update distance/time info 
                updateRouteInfo(route, link.textContent);
                      
                    }
                  }
                );
              } else {
                  alert("Waiting for GPS location...");
              }
          } else {
              alert("No coordinates found for " + destKey);
          }
      });
  });
});