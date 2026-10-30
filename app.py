"""Local-only Flask dashboard for the safe DDoS simulation."""

from flask import Flask, jsonify, render_template, request

from config import HOST, PORT
from simulator import TrafficSimulator

app = Flask(__name__)
simulator = TrafficSimulator()


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
        "img-src 'self' data:; font-src 'self'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/api/state")
def state():
    return jsonify(simulator.snapshot())


@app.post("/api/start")
def start():
    payload = request.get_json(silent=True) or {}
    try:
        simulator.start(payload.get("scenario", "normal"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(simulator.snapshot())


@app.post("/api/pause")
def pause():
    simulator.pause()
    return jsonify(simulator.snapshot())


@app.post("/api/reset")
def reset():
    simulator.reset()
    return jsonify(simulator.snapshot())


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
