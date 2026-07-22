from http.server import BaseHTTPRequestHandler
import json
import os
import pathlib

import joblib
import pandas as pd

FEATURES = [
    "bedrooms", "bathrooms", "size_sqft",
    "has_parking", "has_laundry", "furnished", "pets_allowed",
    "neighbourhood", "property_type",
]

MODEL_PATH = pathlib.Path(__file__).parent.parent / "model" / "rent_model.joblib"
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = joblib.load(MODEL_PATH)
    return _pipeline


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            row = pd.DataFrame([{
                "bedrooms":     float(body.get("bedrooms", 1)),
                "bathrooms":    float(body.get("bathrooms", 1)),
                "size_sqft":    float(body.get("size_sqft", 600)),
                "has_parking":  int(bool(body.get("has_parking", False))),
                "has_laundry":  int(bool(body.get("has_laundry", False))),
                "furnished":    int(bool(body.get("furnished", False))),
                "pets_allowed": int(bool(body.get("pets_allowed", False))),
                "neighbourhood":  str(body.get("neighbourhood", "Downtown Core")),
                "property_type":  str(body.get("property_type", "Apartment")),
            }])[FEATURES]

            rent = round(float(_get_pipeline().predict(row)[0]))
            self._respond(200, {"rent": rent})
        except Exception as exc:
            self._respond(500, {"error": str(exc)})

    def _respond(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass  # suppress access logs
