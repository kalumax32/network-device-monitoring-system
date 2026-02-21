from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import sqlite3
from scanner import scan_network, get_bandwidth_in_out_for_ip

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "very-long-and-secure-secret-key-for-jwt-token-signing-that-is-at-least-32-bytes-long"
jwt = JWTManager(app)
CORS(app)

DATABASE = "database.db"

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            hostname TEXT,
            status TEXT,
            response_time TEXT,
            bandwidth_in TEXT,
            bandwidth_out TEXT
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1,'admin','admin123')")
    conn.commit()
    conn.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?",
                   (data["username"], data["password"]))
    user = cursor.fetchone()
    conn.close()

    if user:
        token = create_access_token(identity=data["username"])
        return jsonify(access_token=token)
    else:
        return jsonify({"msg": "Invalid credentials"}), 401

@app.route("/scan", methods=["GET"])
@jwt_required()
def scan():
    devices = scan_network("192.168.1.")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices")

    for d in devices:
        cursor.execute("""
        INSERT INTO devices (ip, hostname, status, response_time, bandwidth_in, bandwidth_out)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            d["ip"], d["hostname"], d["status"],
            d["response_time"], d["bandwidth_in"], d["bandwidth_out"]
        ))

    conn.commit()
    conn.close()
    return jsonify(devices)

@app.route("/devices", methods=["GET"])
@jwt_required()
def get_devices():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT ip, hostname, status, response_time, bandwidth_in, bandwidth_out FROM devices")
    rows = cursor.fetchall()

    devices = []
    for r in rows:
        ip, hostname, status, response_time, bw_in, bw_out = r
        if status == "Online":
            new_in, new_out = get_bandwidth_in_out_for_ip(ip)
            bw_in, bw_out = new_in, new_out
            cursor.execute(
                "UPDATE devices SET bandwidth_in=?, bandwidth_out=? WHERE ip=?",
                (bw_in, bw_out, ip),
            )

        devices.append({
            "ip": ip,
            "hostname": hostname,
            "status": status,
            "response_time": response_time,
            "bandwidth_in": bw_in,
            "bandwidth_out": bw_out,
        })

    conn.commit()
    conn.close()

    return jsonify(devices)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
