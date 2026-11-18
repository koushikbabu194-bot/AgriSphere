import express from "express";
import Database from "better-sqlite3";
import crypto from "crypto";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
const db = new Database("agrisphere.db");
const __dirname = path.dirname(fileURLToPath(import.meta.url));

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

db.exec(`
CREATE TABLE IF NOT EXISTS crops (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT,
 field TEXT,
 stage TEXT,
 health INTEGER,
 area REAL
);

CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT,
 done INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventory (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT,
 quantity REAL,
 unit TEXT
);

CREATE TABLE IF NOT EXISTS irrigation (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 zone TEXT,
 enabled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT,
 email TEXT UNIQUE,
 password_hash TEXT
);
`);

if (db.prepare("SELECT COUNT(*) n FROM crops").get().n === 0) {
  const add = db.prepare(
    "INSERT INTO crops(name,field,stage,health,area) VALUES(?,?,?,?,?)"
  );

  add.run("Rice", "Field A", "Flowering", 92, 3.2);
  add.run("Maize", "Field B", "Vegetative", 86, 2.1);
  add.run("Tomato", "Field C", "Fruiting", 74, 1.4);
  add.run("Ragi", "Field D", "Maturity", 89, 2.8);

  db.prepare("INSERT INTO tasks(title) VALUES(?)").run("Inspect irrigation lines");
  db.prepare("INSERT INTO tasks(title) VALUES(?)").run("Apply fertilizer");
  db.prepare("INSERT INTO tasks(title) VALUES(?)").run("Check pest traps");

  db.prepare("INSERT INTO inventory(name,quantity,unit) VALUES(?,?,?)")
    .run("Organic fertilizer", 72, "%");

  db.prepare("INSERT INTO inventory(name,quantity,unit) VALUES(?,?,?)")
    .run("Seeds", 31, "%");

  db.prepare("INSERT INTO irrigation(zone) VALUES(?)").run("Zone A");
  db.prepare("INSERT INTO irrigation(zone) VALUES(?)").run("Zone B");
}

const getAll = table => db.prepare(`SELECT * FROM ${table}`).all();

app.get("/api/dashboard", (req, res) => {
  res.json({
    crops: getAll("crops"),
    tasks: getAll("tasks"),
    inventory: getAll("inventory"),
    irrigation: getAll("irrigation")
  });
});

app.post("/api/crops", (req, res) => {
  const { name, field, stage, health, area } = req.body;

  if (!name) return res.status(400).json({ error: "Crop name required" });

  const result = db.prepare(`
    INSERT INTO crops(name,field,stage,health,area)
    VALUES(?,?,?,?,?)
  `).run(name, field || "New field", stage || "Seedling",
    Number(health) || 100, Number(area) || 0);

  res.json({ success: true, id: result.lastInsertRowid });
});

app.post("/api/tasks", (req, res) => {
  const result = db.prepare(
    "INSERT INTO tasks(title) VALUES(?)"
  ).run(req.body.title);

  res.json({ success: true, id: result.lastInsertRowid });
});

app.patch("/api/tasks/:id", (req, res) => {
  db.prepare("UPDATE tasks SET done=? WHERE id=?")
    .run(req.body.done ? 1 : 0, req.params.id);

  res.json({ success: true });
});

app.post("/api/inventory", (req, res) => {
  const { name, quantity, unit } = req.body;

  db.prepare(
    "INSERT INTO inventory(name,quantity,unit) VALUES(?,?,?)"
  ).run(name, Number(quantity), unit || "kg");

  res.json({ success: true });
});

app.patch("/api/irrigation/:id", (req, res) => {
  db.prepare("UPDATE irrigation SET enabled=? WHERE id=?")
    .run(req.body.enabled ? 1 : 0, req.params.id);

  res.json({ success: true });
});

// Demo farmer registration with password hashing.
// Add secure sessions and production-grade authentication before deployment.
app.post("/api/register", (req, res) => {
  const { name, email, password } = req.body;

  if (!name || !email || !password || password.length < 8) {
    return res.status(400).json({
      error: "Enter name, email and password of at least 8 characters"
    });
  }

  const hash = crypto.scryptSync(
    password, email.toLowerCase(), 64
  ).toString("hex");

  try {
    db.prepare(
      "INSERT INTO users(name,email,password_hash) VALUES(?,?,?)"
    ).run(name, email.toLowerCase(), hash);

    res.json({ success: true });
  } catch {
    res.status(409).json({ error: "Email already registered" });
  }
});

app.post("/api/login", (req, res) => {
  const { email, password } = req.body;

  const user = db.prepare(
    "SELECT * FROM users WHERE email=?"
  ).get((email || "").toLowerCase());

  if (!user) return res.status(401).json({ error: "Invalid credentials" });

  const hash = crypto.scryptSync(
    password || "", user.email, 64
  ).toString("hex");

  if (hash !== user.password_hash) {
    return res.status(401).json({ error: "Invalid credentials" });
  }

  res.json({ success: true, name: user.name });
});

app.listen(3000, () => {
  console.log("AgriSphere running at http://localhost:3000");
});