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

    // Log visit to backend
    fetch("/admin/log_visit", {
      method: "POST",
      headers: {
      "Content-Type": "application/json"
      },
      body: JSON.stringify({ location: name })
    });


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

  if (userMarker) {
    map.setView(userMarker.getLatLng(), 19); // zoom level ~19 is good for walking
  }

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

function updateUserPosition(lat, lng, heading, snap = true) {
  let raw = L.latLng(lat, lng);


  // Snap to route if exists
  let snappedObj = (routeLine) ? snapToPolyline(raw, [routeLine]) : null;
  let snapped = (snappedObj && raw.distanceTo(snappedObj.point) < 15) 
                  ? snappedObj.point 
                  : raw; // only snap if within 15m, else use raw GPS

  if (!userMarker) {
    // Create arrow marker with id for rotation
    const circleIcon = L.divIcon({ 
      html: `<div id="arrow" style="
        width: 20px;
        height: 20px;
        background: #780606;
        border-radius: 50%;
        border: 2px solid white;
      "></div>`,
      className: "user-circle",
      iconSize: [20, 20],
      iconAnchor: [10, 10] // center the circle
    });

    userMarker = L.marker([snapped.lat, snapped.lng], { icon: circleIcon }).addTo(map);

    // Tooltip only first time
    let tooltip = userMarker.bindTooltip("You are here", {
      permanent: true,
      direction: "top",
      offset: [0, -15]
    }).openTooltip();

    setTimeout(() => { userMarker.unbindTooltip(); }, 5000);

  } else {
    userMarker.setLatLng([snapped.lat, snapped.lng]);
    
    // Rotate arrow if heading available
    const arrowEl = document.getElementById("arrow");
    if (arrowEl) {
      if (heading != null) {
        arrowEl.style.transform = `rotate(${heading}deg)`;
      } else if (lastLatLng && !snapped.equals(lastLatLng)) {
        let dx = snapped.lng - lastLatLng.lng;
        let dy = snapped.lat - lastLatLng.lat;
        let calcHeading = Math.atan2(dy, dx) * 180 / Math.PI;

        let newHeading = calcHeading; // Define newHeading here
        
        // Normalize rotation: avoid spinning across -180 / 180 boundary
        if (typeof currentHeading === "undefined") {
          currentHeading = newHeading; // first time, just set it
          }
          let diff = newHeading - currentHeading;
          if (diff > 180) diff -= 360;
          if (diff < -180) diff += 360;
          currentHeading += diff; // apply the smallest turn

        arrowEl.style.transform = `translate(-50%, -50%) rotate(${calcHeading}deg)`;
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
      (err, routes) => {
        if (!err) {
          if (routeLine) map.removeLayer(routeLine);
          routeLine = L.polyline(routes[0].coordinates, { color: '#00BFFF', weight: 5 }).addTo(map);
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
let firstLocationUpdate = true; // track first GPS update

if ("geolocation" in navigator) {
    navigator.geolocation.watchPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          const heading = pos.coords.heading ?? null;
          updateUserPosition(lat, lng, heading);
          
            // Zoom only the first time we get location
            if (firstLocationUpdate) {
              map.setView([lat, lng], 18, { animate: true });
              firstLocationUpdate = false;
            }
        },
        (err) => {
            console.warn("GPS failed, using fixed campus center:", err.message);
            updateUserPosition(CAMPUS_CENTER.lat, CAMPUS_CENTER.lng ,null);
            if (firstLocationUpdate) {
              map.setView([CAMPUS_CENTER.lat, CAMPUS_CENTER.lng], 17);
              firstLocationUpdate = false;
          }
          if (!simulateMode) {
            console.log("Starting simulation because GPS is unavailable.");
            startSimulation();
          }
        },
        { enableHighAccuracy: true, maximumAge: 0, timeout: Infinity }
    );
} else {
    console.warn("No geolocation support, using fixed campus center");
    updateUserPosition(CAMPUS_CENTER.lat, CAMPUS_CENTER.lng ,null);
    map.setView([CAMPUS_CENTER.lat, CAMPUS_CENTER.lng], 17);

  if (!simulateMode) {
    startSimulation();
  }
}


// ============================
// For testing on laptop without GPS
// ============================
let simulateMode = false;
let simulateIndex = 0;
let simulateInterval = null;

function startSimulation() {
  if (!routeLine) {
    alert("No route found! Please generate a walking route first.");
    return;
  }
  simulateMode = true;
  const coords = routeLine.getLatLngs();

  simulateIndex = 0;
  clearInterval(simulateInterval);

  // Move every 50ms for smooth animation
  simulateInterval = setInterval(() => {
    if (simulateIndex >= coords.length - 1) {
      stopSimulation();
      return;
    }

    let current = coords[simulateIndex];
    let next = coords[simulateIndex + 1];

    // Break the movement into small steps (like 20 steps between points)
    let steps = 20;
    let stepCount = 0;

    let latStep = (next.lat - current.lat) / steps;
    let lngStep = (next.lng - current.lng) / steps;

    function moveStep() {
      if (stepCount >= steps) {
        simulateIndex++;
        return;
      }

      let lat = current.lat + latStep * stepCount;
      let lng = current.lng + lngStep * stepCount;

      // calculate heading (bearing)
      let dx = next.lng - current.lng;
      let dy = next.lat - current.lat;
      let heading = Math.atan2(dx, dy) * 180 / Math.PI;

      updateUserPosition(lat, lng, heading);

      stepCount++;
      requestAnimationFrame(moveStep);
    }

    moveStep();
  }, 1000); // process next segment every second
}

function stopSimulation() {
  simulateMode = false;
  clearInterval(simulateInterval);
  simulateIndex = 0;
}

const simulateBtn = document.getElementById("simulateBtn");
if (simulateBtn) {
  simulateBtn.addEventListener("click", () => {
    if (!simulateMode) {
      startSimulation();
      simulateBtn.innerText = "⏹ Stop Simulation";
    } else {
      stopSimulation();
      simulateBtn.innerText = "🚶 Simulate Walk";
    }
  });
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




// Faculty data object
const facultyData = {
    'Faculty of Computing and Informatics': {
        title: 'Faculty of Computing and Informatics',
        subtitle: 'Shaping the Future of Technology',
        about: 'The Faculty of Computing and Informatics (FCI) at Multimedia University is a leading institution in technology education...',
        programs: [
            { icon: '🖥️', name: 'Computer Science', desc: 'Comprehensive program covering algorithms, data structures, AI, and machine learning.' },
            { icon: '💻', name: 'Software Engineering', desc: 'Focuses on designing and developing software systems with innovative methodologies and sophisticated tools. Students are exposed to various techniques of analysing user requirements and specifications, as well as the design, implementation and verification of software systems.' },
            { icon: '🔒', name: 'Cybersecurity', desc: 'Built on the technical foundation of computer science, the specialization focuses on the array of sophisticated techniques and innovative approaches used to protect data and information systems. Students are exposed to both offensive and defensive security methodologies such as ethical hacking, digital forensics and network security, as well as policies and ethical issues of cybersecurity.' },
            { icon: '📊', name: 'Data Science', desc: 'Drawing upon the technical foundation of computer science, this specialization focuses on designing and developing solutions to extract valuable insights from data. Students are exposed with fundamental theories in data science as well as hands-on experience in building practical solutions.' },
            { icon: '📱', name: 'Game Development', desc: 'Integrates fundamental concepts of software engineering with both technical and creative aspects of game design and development. Students are exposed to various types of game production – from 2D to 3D, and from virtual to augmented reality game projects.' },
            { icon: '🌐', name: 'Information Systems', desc: 'Business applications, database management, and enterprise solutions.' }
        ],
        facilities: [
            'State-of-the-art computer labs with latest hardware and software',
            'Research centers for AI, cybersecurity, and data analytics',
            'Industry partnerships providing internship and career opportunities',
            'Innovation labs for student projects and startup incubation',
            'Experienced faculty with industry and academic expertise'
        ],
        contact: {
            location: 'FCI Building, MMU Cyberjaya Campus',
            hours: 'Monday - Friday, 8:00 AM - 5:00 PM',
            email: 'fci@mmu.edu.my',
            phone: '+603-8312-5000'
        },
        mapDestination: 'Faculty of Computing and Informatics'
    },
    
    'Faculty of Creative Multimedia': {
        title: 'Faculty of Creative Multimedia',
        subtitle: 'Where Creativity Meets Technology',
        about: 'The Faculty of Creative Multimedia (FCM) at Multimedia University combines artistic creativity with cutting-edge technology...',
        programs: [
            { icon: '🎬', name: 'Digital Film & Television', desc: 'Comprehensive training in filmmaking, cinematography, and television production.' },
            { icon: '🎮', name: 'Game Development', desc: 'Interactive media design, game programming, and virtual reality development.' },
            { icon: '🎨', name: 'Media Arts', desc: 'Digital art, graphic design, and multimedia content creation.' },
            { icon: '📱', name: 'Interactive Media Design', desc: 'User experience design, web development, and mobile app interfaces.' },
            { icon: '🎭', name: 'Animation', desc: '2D/3D animation, character design, and motion graphics.' },
            { icon: '🎵', name: 'Audio Production', desc: 'Sound engineering, music production, and audio post-production.' }
        ],
        facilities: [
            'Professional film studios with latest recording equipment',
            'Animation labs with industry-standard software and hardware',
            'Game development labs with VR/AR capabilities',
            'Sound recording studios for music and audio production',
            'Industry collaborations with leading creative companies'
        ],
        contact: {
            location: 'FCM Building, MMU Cyberjaya Campus',
            hours: 'Monday - Friday, 8:00 AM - 5:00 PM',
            email: 'fcm@mmu.edu.my',
            phone: '+603-8312-5100'
        },
        mapDestination: 'Faculty of Creative Multimedia'
    },
    
    'Faculty of Engineering': {
        title: 'Faculty of Engineering',
        subtitle: 'Building Tomorrow\'s Infrastructure',
        about: 'The Faculty of Engineering (FOE) at Multimedia University develops skilled engineers for complex technological challenges...',
        programs: [
            { icon: '⚡', name: 'Electrical Engineering', desc: 'Power systems, electronics, and electrical infrastructure design.' },
            { icon: '🔧', name: 'Mechanical Engineering', desc: 'Manufacturing, robotics, and mechanical system design.' },
            { icon: '📡', name: 'Telecommunications Engineering', desc: 'Network systems, wireless communication, and satellite technology.' },
            { icon: '🏗️', name: 'Civil Engineering', desc: 'Structural design, construction management, and infrastructure planning.' },
            { icon: '🔬', name: 'Chemical Engineering', desc: 'Process engineering, materials science, and industrial chemistry.' },
            { icon: '🌱', name: 'Environmental Engineering', desc: 'Sustainable engineering, water treatment, and environmental protection.' }
        ],
        facilities: [
            'Advanced engineering labs with industry-grade equipment',
            'Research centers for renewable energy and automation',
            'Professional internship programs with leading engineering firms',
            'Project-based learning with real-world applications',
            'Industry partnerships for career placement and research'
        ],
        contact: {
            location: 'FOE Building, MMU Cyberjaya Campus',
            hours: 'Monday - Friday, 8:00 AM - 5:00 PM',
            email: 'foe@mmu.edu.my',
            phone: '+603-8312-5200'
        },
        mapDestination: 'Faculty of Engineering'
    },
    
    'Faculty of Management': {
        title: 'Faculty of Management',
        subtitle: 'Leading Business Innovation',
        about: 'The Faculty of Management (FOM) at Multimedia University prepares future business leaders and entrepreneurs...',
        programs: [
            { icon: '💼', name: 'Business Administration', desc: 'Comprehensive business management and strategic planning.' },
            { icon: '📊', name: 'Accounting & Finance', desc: 'Financial management, auditing, and investment analysis.' },
            { icon: '📈', name: 'Marketing', desc: 'Digital marketing, brand management, and consumer behavior analysis.' },
            { icon: '🏢', name: 'Human Resource Management', desc: 'Talent management, organizational behavior, and HR strategy.' },
            { icon: '🌐', name: 'International Business', desc: 'Global trade, cross-cultural management, and international economics.' },
            { icon: '💡', name: 'Entrepreneurship', desc: 'Startup development, innovation management, and business incubation.' }
        ],
        facilities: [
            'Business simulation labs for hands-on learning experience',
            'Entrepreneurship center supporting startup development',
            'Industry mentorship programs with business leaders',
            'Internship placements in multinational corporations',
            'Case study learning with real business scenarios'
        ],
        contact: {
            location: 'FOM Building, MMU Cyberjaya Campus',
            hours: 'Monday - Friday, 8:00 AM - 5:00 PM',
            email: 'fom@mmu.edu.my',
            phone: '+603-8312-5300'
        },
        mapDestination: 'Faculty of Management'
    }
};

let currentFaculty = null;

function openFacultyModal(facultyName) {
    const faculty = facultyData[facultyName];
    if (!faculty) return;
    
    currentFaculty = facultyName;
    
    // Update modal content
    document.getElementById('facultyTitle').textContent = faculty.title;
    document.getElementById('facultySubtitle').textContent = faculty.subtitle;
    
    // Generate content HTML
    const contentHTML = `
        <div class="info-section">
            <h3>About ${faculty.title.split(' ').slice(-1)[0]}</h3>
            <p>${faculty.about}</p>
        </div>

        <div class="info-section">
            <h3>Programs Offered</h3>
            <div class="programs-grid">
                ${faculty.programs.map(program => `
                    <div class="program-card">
                        <h4>${program.icon} ${program.name}</h4>
                        <p>${program.desc}</p>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="info-section">
            <h3>Facilities & Highlights</h3>
            ${faculty.facilities.map(facility => `<p>• <strong>${facility.split(' ')[0]} ${facility.split(' ')[1] || ''}</strong> ${facility.split(' ').slice(2).join(' ')}</p>`).join('')}
        </div>

        <div class="contact-info">
            <h4>📍 Contact Information</h4>
            <p><strong>Location:</strong> ${faculty.contact.location}</p>
            <p><strong>Office Hours:</strong> ${faculty.contact.hours}</p>
            <p><strong>Email:</strong> ${faculty.contact.email}</p>
            <p><strong>Phone:</strong> ${faculty.contact.phone}</p>
        </div>

        <div class="action-buttons">
            <button class="btn btn-secondary" onclick="viewFacultyPrograms()">
                📚 View All Programs
            </button>
        </div>
    `;
    
    document.getElementById('facultyContent').innerHTML = contentHTML;
    
    // Show modal
    const modal = document.getElementById('facultyModal');
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeFacultyModal() {
    const modal = document.getElementById('facultyModal');
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
    currentFaculty = null;
}

function viewFacultyPrograms() {
    if (currentFaculty) {
        const faculty = facultyData[currentFaculty];

        if (faculty.title.includes("Computing")) {
            // Direct link to FCI undergraduate programmes
            window.open("https://www.mmu.edu.my/programmes-by-campus/programmes-cyberjaya/programmes-cyberjaya-undergraduate/programmes-cyberjaya-undergraduate-information-technology", "_blank");
        } else if (faculty.title.includes("Creative Multimedia")) {
            window.open("https://www.mmu.edu.my/programmes-by-campus/programmes-cyberjaya/programmes-cyberjaya-undergraduate/programmes-cyberjaya-undergraduate-creative-multimedia", "_blank");
        } else if (faculty.title.includes("Engineering")) {
            window.open("https://www.mmu.edu.my/programmes-by-campus/programmes-cyberjaya/programmes-cyberjaya-undergraduate/programmes-cyberjaya-undergraduate-engineering", "_blank");
        } else if (faculty.title.includes("Management")) {
            window.open("https://www.mmu.edu.my/programmes-by-campus/programmes-cyberjaya/programmes-cyberjaya-undergraduate/programmes-cyberjaya-undergraduate-business-accounting", "_blank");
        }
    }
}


// Dropdown click handlers
document.addEventListener('DOMContentLoaded', function() {
    const facultyLinks = [
        { selector: '[data-destination="Faculty of Computing and Informatics"]', name: 'Faculty of Computing and Informatics' },
        { selector: '[data-destination="Faculty of Creative Multimedia"]', name: 'Faculty of Creative Multimedia' },
        { selector: '[data-destination="Faculty of Engineering"]', name: 'Faculty of Engineering' },
        { selector: '[data-destination="Faculty of Management"]', name: 'Faculty of Management' }
    ];

    facultyLinks.forEach(faculty => {
        const link = document.querySelector(faculty.selector);
        if (link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                openFacultyModal(faculty.name);
                document.getElementById('hamburger-toggle').checked = false;
            });
        }
    });

    // Close modal when clicking outside
    const modal = document.getElementById('facultyModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeFacultyModal();
            }
        });
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('facultyModal');
        if (modal && modal.classList.contains('active')) {
            closeFacultyModal();
        }
    }
});

// Food & Beverage data object
const foodData = {
    'MMU Starbees': {
        title: 'MMU Starbees',
        subtitle: 'Your Campus Coffee Hub',
        about: 'MMU Starbees is the go-to coffee destination on campus, offering a wide variety of beverages, light meals, and snacks. It\'s the perfect spot for students to grab their morning coffee, study with friends, or take a break between classes.',
        offerings: [
            { icon: '☕', name: 'Premium Coffee', desc: 'Freshly brewed espresso, cappuccino, latte, and specialty coffee drinks.' },
            { icon: '🧊', name: 'Cold Beverages', desc: 'Iced coffee, smoothies, fresh juices, and refreshing cold drinks.' },
            { icon: '🥪', name: 'Light Meals', desc: 'Sandwiches, wraps, salads, and healthy meal options.' },
            { icon: '🍰', name: 'Pastries & Snacks', desc: 'Fresh pastries, muffins, cookies, and quick snacks.' },
            { icon: '🥗', name: 'Healthy Options', desc: 'Salads, fruit bowls, and nutritious meal choices.' },
            { icon: '📚', name: 'Study Environment', desc: 'Free WiFi, comfortable seating, and study-friendly atmosphere.' }
        ],
        features: [
            'Free high-speed WiFi for students',
            'Comfortable seating with charging ports',
            'Student-friendly pricing',
            'Extended operating hours during exam periods',
            'Takeaway and dine-in options available'
        ],
        details: {
            location: 'Ground Floor, Student Center Building',
            hours: 'Monday - Friday: 7:00 AM - 10:00 PM, Saturday - Sunday: 8:00 AM - 9:00 PM',
            payment: 'Cash, Card, Student Card accepted',
            contact: '+603-8312-5400'
        },
        mapDestination: 'MMU Starbees'
    },
    
    'Restoran Haji Tapah Bistro': {
        title: 'Restoran Haji Tapah Bistro',
        subtitle: 'Authentic Malaysian Mamak Experience',
        about: 'Restoran Haji Tapah Bistro brings authentic Malaysian mamak cuisine to the MMU campus. Known for its delicious local dishes, affordable prices, and 24-hour service, it\'s a favorite among students for both quick meals and late-night dining.',
        offerings: [
            { icon: '🍛', name: 'Nasi Lemak', desc: 'Traditional Malaysian rice dish with sambal, anchovies, and side dishes.' },
            { icon: '🍜', name: 'Mee Goreng', desc: 'Stir-fried noodles with vegetables, tofu, and choice of protein.' },
            { icon: '🥘', name: 'Curry Dishes', desc: 'Authentic Malaysian curries with chicken, beef, or vegetables.' },
            { icon: '🫖', name: 'Teh Tarik', desc: 'Famous Malaysian pulled tea and other traditional beverages.' },
            { icon: '🥯', name: 'Roti Varieties', desc: 'Roti canai, roti telur, and other flatbread specialties.' },
            { icon: '🌙', name: '24-Hour Service', desc: 'Open round the clock for your convenience.' }
        ],
        features: [
            'Authentic Malaysian mamak cuisine',
            '24-hour operation for late-night dining',
            'Very affordable student pricing',
            'Halal certified food',
            'Large seating capacity for groups'
        ],
        details: {
            location: 'Near Student Residential Area',
            hours: '24 Hours Daily',
            payment: 'Cash preferred, Card accepted',
            contact: '+603-8312-5450'
        },
        mapDestination: 'Restoran Haji Tapah Bistro'
    },
    
    "Deen's Cafe": {
        title: "Deen's Cafe",
        subtitle: 'Cozy Dining & Social Hub',
        about: 'Deen\'s Cafe offers a comfortable dining experience with a diverse menu ranging from local Malaysian dishes to international cuisine. It\'s designed as a social hub where students can enjoy good food in a relaxed atmosphere.',
        offerings: [
            { icon: '🍽️', name: 'Local Cuisine', desc: 'Malaysian favorites like nasi goreng, char kway teow, and laksa.' },
            { icon: '🍕', name: 'Western Food', desc: 'Pizza, pasta, burgers, and other international dishes.' },
            { icon: '🍹', name: 'Beverages', desc: 'Fresh juices, smoothies, coffee, and specialty drinks.' },
            { icon: '🍰', name: 'Desserts', desc: 'Cakes, ice cream, and sweet treats for every craving.' },
            { icon: '🥙', name: 'Quick Bites', desc: 'Sandwiches, wraps, and fast food options.' },
            { icon: '👥', name: 'Group Dining', desc: 'Spacious seating perfect for group meals and celebrations.' }
        ],
        features: [
            'Diverse menu with local and international options',
            'Comfortable air-conditioned environment',
            'Group-friendly seating arrangements',
            'Regular student promotions and discounts',
            'Clean and modern dining space'
        ],
        details: {
            location: 'Main Campus Food Court Area',
            hours: 'Monday - Sunday: 10:00 AM - 11:00 PM',
            payment: 'Cash, Card, Digital payments accepted',
            contact: '+603-8312-5480'
        },
        mapDestination: "Deen's Cafe"
    }
};

// Facilities data object
const facilityData = {
    'Library': {
        title: 'Siti Hasmah Digital Library',
        subtitle: 'Your Gateway to Knowledge',
        about: 'The Siti Hasmah Digital Library is MMU\'s state-of-the-art learning facility, providing students with access to extensive digital and physical resources, quiet study spaces, and modern research facilities.',
        services: [
            { icon: '📚', name: 'Digital Resources', desc: 'Access to millions of e-books, journals, and research databases.' },
            { icon: '🖥️', name: 'Computer Labs', desc: 'High-performance computers with specialized software for research and projects.' },
            { icon: '📖', name: 'Study Spaces', desc: 'Quiet individual study areas and group discussion rooms.' },
            { icon: '🎧', name: 'Multimedia Center', desc: 'Audio-visual equipment for presentations and multimedia projects.' },
            { icon: '📝', name: 'Research Support', desc: 'Librarian assistance and research guidance services.' },
            { icon: '☕', name: 'He & She Cafe', desc: 'In-library cafe for refreshments during study sessions.' }
        ],
        features: [
            '24/7 access during exam periods',
            'Silent and discussion zones available',
            'Book reservation and renewal systems',
            'Printing and scanning facilities',
            'Free WiFi throughout the building'
        ],
        details: {
            location: 'Central Campus, Library Building',
            hours: 'Monday - Friday: 8:00 AM - 10:00 PM, Weekends: 9:00 AM - 6:00 PM',
            services: 'Book loans, research assistance, computer access',
            contact: '+603-8312-5500'
        },
        mapDestination: 'Library'
    },
    
    'Dewan Tun Canselor': {
        title: 'Dewan Tun Canselor (DTC)',
        subtitle: 'Premier Event & Conference Venue',
        about: 'Dewan Tun Canselor is MMU\'s main auditorium and event venue, hosting graduation ceremonies, conferences, cultural performances, and major university events. It features modern audio-visual systems and spacious seating.',
        services: [
            { icon: '🎓', name: 'Graduation Ceremonies', desc: 'Hosting convocation and graduation events for all faculties.' },
            { icon: '🎤', name: 'Conferences', desc: 'Academic conferences, seminars, and professional workshops.' },
            { icon: '🎭', name: 'Cultural Events', desc: 'Performances, concerts, and cultural celebrations.' },
            { icon: '📽️', name: 'Audio-Visual', desc: 'State-of-the-art sound and projection systems.' },
            { icon: '🏢', name: 'Corporate Events', desc: 'Professional meetings and corporate functions.' },
            { icon: '🎪', name: 'Student Activities', desc: 'Club events, competitions, and student gatherings.' }
        ],
        features: [
            'Seating capacity for 1,200 people',
            'Professional lighting and sound systems',
            'Live streaming capabilities',
            'Air-conditioned comfort',
            'Accessible facilities for disabled guests'
        ],
        details: {
            location: 'Main Campus, Central Building',
            hours: 'Event-based schedule, booking required',
            services: 'Event hosting, equipment rental, technical support',
            contact: '+603-8312-5600'
        },
        mapDestination: 'Dewan Tun Canselor'
    },
    
    'Central Lecture Complex': {
        title: 'Central Lecture Complex (CLC)',
        subtitle: 'Modern Learning Environment',
        about: 'The Central Lecture Complex houses MMU\'s largest lecture halls and classrooms, equipped with modern teaching technology and designed to provide optimal learning environments for large classes and lectures.',
        services: [
            { icon: '🏫', name: 'Lecture Halls', desc: 'Large capacity halls for major courses and guest lectures.' },
            { icon: '💻', name: 'Smart Classrooms', desc: 'Technology-enabled rooms with interactive whiteboards and projectors.' },
            { icon: '🔬', name: 'Lab Facilities', desc: 'Specialized laboratories for practical sessions.' },
            { icon: '📊', name: 'Presentation Tech', desc: 'Advanced audio-visual equipment for presentations.' },
            { icon: '🌡️', name: 'Climate Control', desc: 'Comfortable air-conditioned learning environments.' },
            { icon: '♿', name: 'Accessibility', desc: 'Facilities designed for students with disabilities.' }
        ],
        features: [
            'Multiple lecture halls with varying capacities',
            'Modern teaching technology in all rooms',
            'Comfortable seating with writing surfaces',
            'Good acoustics and visibility from all seats',
            'Easy access and navigation between floors'
        ],
        details: {
            location: 'Central Campus Area',
            hours: 'Monday - Friday: 8:00 AM - 10:00 PM, Saturday: 8:00 AM - 6:00 PM',
            services: 'Lectures, tutorials, examinations, events',
            contact: '+603-8312-5700'
        },
        mapDestination: 'Central Lecture Complex'
    },
    
    'STAD Building MMU': {
        title: 'Student Affairs Division (STAD)',
        subtitle: 'Your Student Support Center',
        about: 'The Student Affairs Division (STAD) is your one-stop center for all student-related services, from enrollment and academic matters to counseling and extracurricular activities support.',
        services: [
            { icon: '📋', name: 'Student Registration', desc: 'Course registration, enrollment, and academic record services.' },
            { icon: '💰', name: 'Financial Aid', desc: 'Scholarships, loans, and financial assistance programs.' },
            { icon: '🧠', name: 'Counseling Services', desc: 'Academic and personal counseling support.' },
            { icon: '🏆', name: 'Student Activities', desc: 'Club registration, event approval, and activity coordination.' },
            { icon: '🏠', name: 'Accommodation', desc: 'Hostel applications and housing assistance.' },
            { icon: '📄', name: 'Documentation', desc: 'Student certificates, transcripts, and official letters.' }
        ],
        features: [
            'Comprehensive student support services',
            'Professional counseling staff',
            'Online and offline service options',
            'Multilingual support staff',
            'Efficient processing of student requests'
        ],
        details: {
            location: 'Student Services Building',
            hours: 'Monday - Friday: 8:30 AM - 5:00 PM',
            services: 'All student affairs and administrative support',
            contact: '+603-8312-5800'
        },
        mapDestination: 'STAD Building MMU'
    },
    
    'Surau Al Hidayah MMU': {
        title: 'Surau Al Hidayah MMU',
        subtitle: 'Campus Prayer & Reflection Space',
        about: 'Surau Al Hidayah provides a peaceful space for Muslim students and staff to perform their daily prayers and engage in religious activities. It serves as a spiritual center promoting Islamic values and community bonding.',
        services: [
            { icon: '🕌', name: 'Daily Prayers', desc: 'Facilities for all five daily prayers with proper prayer times.' },
            { icon: '📿', name: 'Religious Classes', desc: 'Islamic studies classes and Quran recitation sessions.' },
            { icon: '🤲', name: 'Friday Prayers', desc: 'Weekly Jummah prayers with sermons and community gathering.' },
            { icon: '📚', name: 'Islamic Library', desc: 'Religious books, references, and Islamic literature.' },
            { icon: '🧘', name: 'Meditation Space', desc: 'Quiet areas for reflection and spiritual contemplation.' },
            { icon: '👥', name: 'Community Events', desc: 'Religious celebrations and Islamic community activities.' }
        ],
        features: [
            'Separate prayer areas for men and women',
            'Ablution (wudu) facilities available',
            'Air-conditioned and carpeted prayer halls',
            'Qibla direction clearly marked',
            'Religious books and materials available'
        ],
        details: {
            location: 'Near Student Residential Area',
            hours: 'Daily: 5:00 AM - 10:00 PM',
            services: 'Prayer facilities, religious education, community events',
            contact: '+603-8312-5900'
        },
        mapDestination: 'Surau Al Hidayah MMU'
    }
};

let currentFood = null;
let currentFacility = null;

// Food Modal Functions
function openFoodModal(foodName) {
    const food = foodData[foodName];
    if (!food) return;
    
    currentFood = foodName;
    
    // Update modal content
    document.getElementById('foodTitle').textContent = food.title;
    document.getElementById('foodSubtitle').textContent = food.subtitle;
    
    // Generate content HTML
    const contentHTML = `
        <div class="info-section">
            <h3>About ${food.title}</h3>
            <p>${food.about}</p>
        </div>

        <div class="info-section">
            <h3>What We Offer</h3>
            <div class="programs-grid">
                ${food.offerings.map(item => `
                    <div class="program-card">
                        <h4>${item.icon} ${item.name}</h4>
                        <p>${item.desc}</p>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="info-section">
            <h3>Features & Highlights</h3>
            ${food.features.map(feature => `<p>• <strong>${feature.split(' ')[0]} ${feature.split(' ')[1] || ''}</strong> ${feature.split(' ').slice(2).join(' ')}</p>`).join('')}
        </div>

        <div class="contact-info">
            <h4>📍 Location & Details</h4>
            <p><strong>Location:</strong> ${food.details.location}</p>
            <p><strong>Operating Hours:</strong> ${food.details.hours}</p>
            <p><strong>Payment:</strong> ${food.details.payment}</p>
            <p><strong>Contact:</strong> ${food.details.contact}</p>
        </div>

        <div class="action-buttons">
            <button class="btn btn-primary" onclick="navigateToFood()">
                🗺️ Get Directions
            </button>
            <button class="btn btn-secondary" onclick="viewFoodMenu()">
                📋 View Menu
            </button>
        </div>
    `;
    
    document.getElementById('foodContent').innerHTML = contentHTML;
    
    // Show modal
    const modal = document.getElementById('foodModal');
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeFoodModal() {
    const modal = document.getElementById('foodModal');
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
    currentFood = null;
}

// Facility Modal Functions
function openFacilityModal(facilityName) {
    const facility = facilityData[facilityName];
    if (!facility) return;
    
    currentFacility = facilityName;
    
    // Update modal content
    document.getElementById('facilityTitle').textContent = facility.title;
    document.getElementById('facilitySubtitle').textContent = facility.subtitle;
    
    // Generate content HTML
    const contentHTML = `
        <div class="info-section">
            <h3>About ${facility.title}</h3>
            <p>${facility.about}</p>
        </div>

        <div class="info-section">
            <h3>Services & Amenities</h3>
            <div class="programs-grid">
                ${facility.services.map(service => `
                    <div class="program-card">
                        <h4>${service.icon} ${service.name}</h4>
                        <p>${service.desc}</p>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="info-section">
            <h3>Features & Highlights</h3>
            ${facility.features.map(feature => `<p>• <strong>${feature.split(' ')[0]} ${feature.split(' ')[1] || ''}</strong> ${feature.split(' ').slice(2).join(' ')}</p>`).join('')}
        </div>

        <div class="contact-info">
            <h4>📍 Location & Details</h4>
            <p><strong>Location:</strong> ${facility.details.location}</p>
            <p><strong>Operating Hours:</strong> ${facility.details.hours}</p>
            <p><strong>Services:</strong> ${facility.details.services}</p>
            <p><strong>Contact:</strong> ${facility.details.contact}</p>
        </div>

        <div class="action-buttons">
            <button class="btn btn-primary" onclick="navigateToFacility()">
                🗺️ Get Directions
            </button>
            <button class="btn btn-secondary" onclick="viewFacilityInfo()">
                ℹ️ More Info
            </button>
        </div>
    `;
    
    document.getElementById('facilityContent').innerHTML = contentHTML;
    
    // Show modal
    const modal = document.getElementById('facilityModal');
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeFacilityModal() {
    const modal = document.getElementById('facilityModal');
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
    currentFacility = null;
}

// Action Functions
function navigateToFood() {
    if (currentFood) {
        const food = foodData[currentFood];
        alert(`Navigating to ${food.title} on the map...`);
        closeFoodModal();
    }
}

function viewFoodMenu() {
    if (currentFood) {
        alert(`Opening ${currentFood} menu...`);
    }
}

function navigateToFacility() {
    if (currentFacility) {
        const facility = facilityData[currentFacility];
        alert(`Navigating to ${facility.title} on the map...`);
        closeFacilityModal();
    }
}

function viewFacilityInfo() {
    if (currentFacility) {
        alert(`Opening detailed information for ${currentFacility}...`);
    }
}

// Dropdown click handlers
document.addEventListener('DOMContentLoaded', function() {
    // Food & Beverage Links
    const foodLinks = [
        { selector: '[data-destination="MMU Starbees"]', name: 'MMU Starbees' },
        { selector: '[data-destination="Restoran Haji Tapah Bistro"]', name: 'Restoran Haji Tapah Bistro' },
        { selector: '[data-destination="Deen\'s Cafe"]', name: "Deen's Cafe" }
    ];

    foodLinks.forEach(food => {
        const link = document.querySelector(food.selector);
        if (link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                openFoodModal(food.name);
                document.getElementById('hamburger-toggle').checked = false;
            });
        }
    });

    // Facility Links
    const facilityLinks = [
        { selector: '[data-destination="Library"]', name: 'Library' },
        { selector: '[data-destination="Dewan Tun Canselor"]', name: 'Dewan Tun Canselor' },
        { selector: '[data-destination="Central Lecture Complex"]', name: 'Central Lecture Complex' },
        { selector: '[data-destination="STAD Building MMU"]', name: 'STAD Building MMU' },
        { selector: '[data-destination="Surau Al Hidayah MMU"]', name: 'Surau Al Hidayah MMU' }
    ];

    facilityLinks.forEach(facility => {
        const link = document.querySelector(facility.selector);
        if (link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                openFacilityModal(facility.name);
                document.getElementById('hamburger-toggle').checked = false;
            });
        }
    });

    // Close modals when clicking outside
    const foodModal = document.getElementById('foodModal');
    const facilityModal = document.getElementById('facilityModal');
    
    if (foodModal) {
        foodModal.addEventListener('click', function(e) {
            if (e.target === foodModal) {
                closeFoodModal();
            }
        });
    }
    
    if (facilityModal) {
        facilityModal.addEventListener('click', function(e) {
            if (e.target === facilityModal) {
                closeFacilityModal();
            }
        });
    }
});

// Enhanced Escape key handler for all modals
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const activeModals = document.querySelectorAll('.modal-overlay.active');
        activeModals.forEach(modal => {
            modal.classList.remove('active');
            document.body.style.overflow = 'auto';
        });
        
        // Reset current selections
        currentFood = null;
        currentFacility = null;
        currentFaculty = null;
    }
});
