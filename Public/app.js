import * as THREE from "three";

const API = "/api";

// ---------------- 3D FARM ----------------

const scene = new THREE.Scene();
scene.background = null;

const camera = new THREE.PerspectiveCamera(
  45, 1, 0.1, 1000
);

const renderer = new THREE.WebGLRenderer({
  alpha: true,
  antialias: true
});

renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
document.getElementById("farm3d").appendChild(renderer.domElement);

camera.position.set(6, 6, 9);
camera.lookAt(0, 0, 0);

scene.add(new THREE.HemisphereLight(0xffffff, 0x315b35, 2));

const sunlight = new THREE.DirectionalLight(0xffffff, 2);
sunlight.position.set(5, 10, 5);
scene.add(sunlight);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(10, 8),
  new THREE.MeshStandardMaterial({ color: 0x376c3b })
);
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

const plants = [];

for (let x = -3; x <= 3; x += 1) {
  for (let z = -2.5; z <= 2.5; z += 0.8) {
    const plant = new THREE.Group();

    const stem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.04, 0.5, 8),
      new THREE.MeshStandardMaterial({ color: 0x83bd5c })
    );
    stem.position.y = 0.25;
    plant.add(stem);

    for (const side of [-1, 1]) {
      const leaf = new THREE.Mesh(
        new THREE.SphereGeometry(0.13, 8, 8),
        new THREE.MeshStandardMaterial({ color: 0x91ce62 })
      );
      leaf.scale.set(1.5, 0.4, 0.7);
      leaf.position.set(side * 0.1, 0.35, 0);
      plant.add(leaf);
    }

    plant.position.set(x, 0, z);
    plant.userData.phase = Math.random() * 6;
    scene.add(plant);
    plants.push(plant);
  }
}

const farmhouse = new THREE.Mesh(
  new THREE.BoxGeometry(1, 0.8, 1),
  new THREE.MeshStandardMaterial({ color: 0xe5d4a7 })
);
farmhouse.position.set(3.8, 0.4, -2.5);
scene.add(farmhouse);

function resize() {
  const host = document.getElementById("farm3d");
  const w = host.clientWidth;
  const h = host.clientHeight;
  if (!w || !h) return;

  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

window.addEventListener("resize", resize);
resize();

function animate() {
  requestAnimationFrame(animate);

  const time = performance.now() * 0.001;

  plants.forEach(p => {
    p.rotation.z = Math.sin(time * 1.5 + p.userData.phase) * 0.06;
  });

  scene.rotation.y = Math.sin(time * 0.2) * 0.04;

  renderer.render(scene, camera);
}

animate();

// ---------------- DASHBOARD ----------------

async function request(url, options = {}) {
  const response = await fetch(API + url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  const data = await response.json();

  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function refreshDashboard() {
  const data = await request("/dashboard");

  document.getElementById("cropCount").textContent =
    data.crops.length;

  document.getElementById("cropTable").innerHTML =
    data.crops.map(c => `
      <tr>
        <td>${escapeHTML(c.name)}</td>
        <td>${escapeHTML(c.field || "")}</td>
        <td>${escapeHTML(c.stage || "")}</td>
        <td>${c.health}%</td>
        <td>${c.area} acres</td>
      </tr>
    `).join("");

  document.getElementById("taskList").innerHTML =
    data.tasks.map(t => `
      <p>
        <input type="checkbox"
          ${t.done ? "checked" : ""}
          onchange="completeTask(${t.id},this.checked)">
        ${escapeHTML(t.title)}
      </p>
    `).join("");

  document.getElementById("inventoryList").innerHTML =
    data.inventory.map(i => `
      <p>${escapeHTML(i.name)} — ${i.quantity} ${escapeHTML(i.unit)}</p>
    `).join("");

  document.getElementById("irrigationZones").innerHTML =
    data.irrigation.map(z => `
      <p>
        ${escapeHTML(z.zone)}
        <button onclick="toggleIrrigation(${z.id},${!z.enabled})">
          ${z.enabled ? "Turn OFF" : "Turn ON"}
        </button>
        ${z.enabled ? "ON (simulated)" : "OFF"}
      </p>
    `).join("");
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;",
    '"':"&quot;", "'":"&#39;"
  })[c]);
}

window.addCrop = async () => {
  const name = prompt("Enter crop name:");
  if (!name) return;

  const field = prompt("Enter field:", "Field E");
  const area = Number(prompt("Enter area in acres:", "1"));

  await request("/crops", {
    method: "POST",
    body: JSON.stringify({
      name, field, area, stage: "Seedling", health: 100
    })
  });

  refreshDashboard();
};

window.addTask = async () => {
  const title = prompt("Enter field activity:");
  if (!title) return;

  await request("/tasks", {
    method: "POST",
    body: JSON.stringify({ title })
  });

  refreshDashboard();
};

window.addStock = async () => {
  const name = prompt("Inventory name:");
  if (!name) return;

  const quantity = Number(prompt("Enter quantity:", "50"));
  const unit = prompt("Unit:", "kg") || "kg";

  await request("/inventory", {
    method: "POST",
    body: JSON.stringify({ name, quantity, unit })
  });

  refreshDashboard();
};

window.completeTask = async (id, done) => {
  await request(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ done })
  });
};

window.toggleIrrigation = async (id, enabled) => {
  await request(`/irrigation/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled })
  });

  refreshDashboard();
};

// ---------------- WEATHER API ----------------

async function loadWeather() {
  try {
    const url =
      "https://api.open-meteo.com/v1/forecast" +
      "?latitude=12.9716&longitude=77.5946" +
      "&current=temperature_2m,relative_humidity_2m,wind_speed_10m" +
      "&timezone=Asia%2FKolkata";

    const response = await fetch(url);
    if (!response.ok) throw new Error("Weather unavailable");

    const data = await response.json();
    const w = data.current;

    document.getElementById("temperature").textContent =
      w.temperature_2m + "°C";

    document.getElementById("humidity").textContent =
      "Humidity: " + w.relative_humidity_2m + "%";

    document.getElementById("wind").textContent =
      "Wind: " + w.wind_speed_10m + " km/h";

    document.getElementById("weatherDescription").textContent =
      "Current Bengaluru weather";
  } catch {
    document.getElementById("temperature").textContent =
      "Weather unavailable";
  }
}

loadWeather();
setInterval(loadWeather, 900000);

// ---------------- LEAF SCREENING ----------------

document.getElementById("leafImage").addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;

  if (!file.type.startsWith("image/")) return;

  const image = document.getElementById("preview");
  image.src = URL.createObjectURL(file);
  image.hidden = false;
});

window.screenDisease = () => {
  const selected = [
    ...document.querySelectorAll(
      '#disease input[type="checkbox"]:checked'
    )
  ].map(x => x.value);

  const output = document.getElementById("diseaseResult");

  if (!document.getElementById("preview").src) {
    output.textContent = "Upload a leaf image first.";
    return;
  }

  if (!selected.length) {
    output.textContent = "No symptoms selected. Continue monitoring the crop.";
    return;
  }

  output.textContent =
    "Observed symptoms: " + selected.join(", ") +
    ". These symptoms can have several causes. This demo does not diagnose " +
    "plant disease. Consult a local agricultural expert for confirmation.";
};

// ---------------- SOIL MONITORING ----------------

window.updateMoisture = value => {
  document.getElementById("moisture").textContent = value + "%";

  const alert = document.getElementById("irrigationAlert");

  if (value < 35) {
    alert.textContent =
      "LOW MOISTURE ALERT: Check the field and irrigation requirements.";
  } else if (value > 80) {
    alert.textContent =
      "HIGH MOISTURE: Check for possible waterlogging.";
  } else {
    alert.textContent =
      "Soil moisture is within the demo target range.";
  }
};

// ---------------- FARMER ACCOUNT ----------------

window.registerFarmer = async () => {
  try {
    const name = document.getElementById("farmerName").value;
    const email = document.getElementById("farmerEmail").value;
    const password = document.getElementById("farmerPassword").value;

    await request("/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password })
    });

    document.getElementById("accountMessage").textContent =
      "Farmer registered successfully!";
  } catch (error) {
    document.getElementById("accountMessage").textContent = error.message;
  }
};

window.loginFarmer = async () => {
  try {
    const email = document.getElementById("farmerEmail").value;
    const password = document.getElementById("farmerPassword").value;

    const result = await request("/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    document.getElementById("accountMessage").textContent =
      "Welcome " + result.name;
  } catch (error) {
    document.getElementById("accountMessage").textContent = error.message;
  }
};

refreshDashboard().catch(console.error);