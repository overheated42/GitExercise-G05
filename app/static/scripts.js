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
    style: { color: "red", weight: 2, dashArray: '2,4', opacity: 0.25 } 
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

// -----------------------------
// Helpers: flatten, key, projection
// -----------------------------
function flattenLatLngs(latlngs) {
  // recursion in case getLatLngs() returns nested arrays (multilines)
  let out = [];
  latlngs.forEach(l => {
    if (Array.isArray(l)) out.push(...flattenLatLngs(l));
    else out.push(l);
  });
  return out;
}

function key(latlng) {
  return latlng.lat.toFixed(6) + "," + latlng.lng.toFixed(6);
}

// treat lat/lng as planar for small campus area: project p onto segment a-b
function projectPointOnSegment(p, a, b) {
  const px = p.lng, py = p.lat;
  const ax = a.lng, ay = a.lat;
  const bx = b.lng, by = b.lat;
  const dx = bx - ax, dy = by - ay;
  if (dx === 0 && dy === 0) return L.latLng(ay, ax);
  let t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy);
  t = Math.max(0, Math.min(1, t));
  const projX = ax + t * dx;
  const projY = ay + t * dy;
  return L.latLng(projY, projX);
}

// -----------------------------
// Improved snap: nearest point ON a segment + its segment endpoints
// returns null or { point, a, b, pl }
// -----------------------------
function snapToPolyline(latlng, polylines) {
  let best = { dist: Infinity, point: null, a: null, b: null, pl: null };

  polylines.forEach(pl => {
    let latlngs = flattenLatLngs(pl.getLatLngs());
    for (let i = 0; i < latlngs.length - 1; i++) {
      const a = latlngs[i], b = latlngs[i + 1];
      const proj = projectPointOnSegment(latlng, a, b);
      const dist = latlng.distanceTo(proj); // uses Leaflet haversine - fine for campus
      if (dist < best.dist) {
        best = { dist, point: proj, a: a, b: b, pl: pl };
      }
    }
  });

  return best.point ? best : null;
}


map.on('locationfound', function(e) {
  let rawPos = e.latlng;
  let snap = snapToPolyline(rawPos, campusPolylines);
  let userPos = snap ? snap.point : rawPos;

  // Pass userPos into the router as the starting waypoint
  L.Routing.control({
    waypoints: [
      userPos,
      destination
    ],
    router: customRouter,
    createMarker: () => null
  }).addTo(map);

  // Update the arrow marker
  if (!userMarker) {
    userMarker = L.marker(userPos, { icon: arrowIcon }).addTo(map);
  } else {
    userMarker.setLatLng(userPos);
  }
});

// -----------------------------
// Build graph (slightly hardened: flatten coordinates, avoid duplicate edges)
// -----------------------------
function buildGraphFromPolylines(polylines) {
  let graph = {};

  function addEdge(aLatLng, bLatLng, dist) {
    const a = key(aLatLng), b = key(bLatLng);
    if (!graph[a]) graph[a] = {};
    if (!graph[b]) graph[b] = {};
    // keep smallest if multiple edges between same nodes
    graph[a][b] = Math.min(graph[a][b] || Infinity, dist);
    graph[b][a] = Math.min(graph[b][a] || Infinity, dist);
  }

  polylines.forEach(pl => {
    let coords = flattenLatLngs(pl.getLatLngs());
    for (let i = 0; i < coords.length - 1; i++) {
      let a = coords[i], b = coords[i + 1];
      let dist = a.distanceTo(b);
      addEdge(a, b, dist);
    }
  });

  return graph;
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
          // Show "Start Walking" button
          document.getElementById("start-btn-container").style.display = "block";
        }
      }
    );
  }
}

document.getElementById("startBtn").addEventListener("click", () => {
  startNavigation(); // enable auto-follow
  document.getElementById("start-btn-container").style.display = "none"; // hide button once started
});

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

// ============================
// Dijkstra’s Algorithm
// ============================
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
function polylineDistance(latlngs) {
  let dist = 0;
  for (let i = 1; i < latlngs.length; i++) {
    dist += latlngs[i - 1].distanceTo(latlngs[i]);
  }
  return dist;
}

// ============================
// Custom Router with Dijkstra + Snap Points
// ============================
var customRouter = {
  route: function(waypoints, callback) {
    let start = waypoints[0].latLng;
    let end = waypoints[1].latLng;

    // build graph from red campus polylines
    let graph = buildGraphFromPolylines(campusPolylines);

    // snap start & end to nearest points on campus polylines
    let startSnap = snapToPolyline(start, campusPolylines);
    let endSnap = snapToPolyline(end, campusPolylines);

    if (!startSnap || !endSnap) {
      return callback("No nearby path found", null);
    }
    // helper: add snapped point into the graph as a new node
    function insertSnapNode(snapObj) {
      const snapKey = key(snapObj.point);
      if (graph[snapKey]) return; // already inserted

      const aKey = key(snapObj.a);
      const bKey = key(snapObj.b);

      if (!graph[aKey]) graph[aKey] = {};
      if (!graph[bKey]) graph[bKey] = {};

      const da = snapObj.point.distanceTo(snapObj.a);
      const db = snapObj.point.distanceTo(snapObj.b);

      graph[snapKey] = {};
      graph[snapKey][aKey] = da;
      graph[aKey][snapKey] = da;

      graph[snapKey][bKey] = db;
      graph[bKey][snapKey] = db;
    }

    // insert the snapped start and end into graph
    insertSnapNode(startSnap);
    insertSnapNode(endSnap);

    // run Dijkstra
    let startKey = key(startSnap.point);
    let endKey = key(endSnap.point);
    let pathKeys = dijkstra(graph, startKey, endKey);

    // convert keys back into Leaflet LatLng
    let coords = pathKeys.map(k => {
      let [lat, lng] = k.split(",").map(Number);
      return L.latLng(lat, lng);
    });

    // force exact start & end positions in the polyline
    if (!coords[0].equals(start)) coords.unshift(start);
    if (!coords[coords.length - 1].equals(end)) coords.push(end);

    let totalDist = polylineDistance(coords);

    // return result
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
let navigationMode = false; // free explore by default
let lastLatLng = null;

function updateUserPosition(lat, lng, heading) {
  let latlng = L.latLng(lat, lng);

  // Snap to route if exists
  let snapped = (routeLine) ? snapToPolyline(latlng, [routeLine]) : latlng;

  if (!userMarker) {
    // Create arrow marker with id for rotation
    const arrowIcon = L.divIcon({ 
      html: `<div id="arrow" style="color:#780606; font-size:25px;">➤</div>`,
      className: "user-arrow",
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    });

    userMarker = L.marker(snapped, { icon: arrowIcon }).addTo(map);

    // Tooltip only first time
    let tooltip = userMarker.bindTooltip("You are here", {
      permanent: true,
      direction: "top",
      offset: [0, -10]
    }).openTooltip();

    setTimeout(() => { userMarker.unbindTooltip(); }, 5000);

  } else {
    userMarker.setLatLng(snapped);

    // Rotate arrow if heading available
    const arrowEl = document.getElementById("arrow");
    if (arrowEl) {
      if (heading != null) {
        arrowEl.style.transform = `rotate(${heading}deg)`;
      } else if (lastLatLng) {
        // fallback: calculate heading from movement
        let dx = snapped.lng - lastLatLng.lng;
        let dy = snapped.lat - lastLatLng.lat;
        let calcHeading = Math.atan2(dx, dy) * 180 / Math.PI;
        arrowEl.style.transform = `rotate(${calcHeading}deg)`;
      }
    }
  }

  lastLatLng = snapped; // store for next movement

   //Only recenter if auto-follow is ON
   if (navigationMode) {
    map.setView(snapped, 18, { animate: true });
  }


  // Auto-update route if destination exists
  if (userMarker && currentDestMarker) {
    customRouter.route(
      [
        { latLng: snapped },
        { latLng: currentDestMarker.getLatLng() }
      ],
      function(err, routes) {
        if (!err) {
          if (routeLine) map.removeLayer(routeLine);
          routeLine = L.polyline(routes[0].coordinates, { color: 'blue', weight: 5 }).addTo(map);
        }
      }
    );
  }
}

// Call this when user searches & clicks a place
function startNavigation() {
  navigationMode = true;
}

// Call this to stop navigation (let user explore freely)
function stopNavigation() {
  navigationMode = false;
}

// ============================
// Recenter Button
// ============================
const recenterBtn = L.control({ position: "topleft" });

recenterBtn.onAdd = function(map) {
  let btn = L.DomUtil.create("button", "recenter-button");
  btn.innerHTML = "📍";

  btn.onclick = () => {
    navigationMode = true; // turn auto-follow back on
    if (userMarker) {
      map.setView(userMarker.getLatLng(), 18, { animate: true });
    }
  };

  return btn;
};
recenterBtn.addTo(map);

// Detect when user manually drags/zooms → stop auto-follow
map.on("dragstart zoomstart", () => {
  navigationMode = false;
});


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

                     // ✅ Show Start Walking button
                    document.getElementById("start-btn-container").style.display = "block";
                      
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