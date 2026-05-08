"""
Integration tests for the SnackStad FastAPI backend.
Tests hit the real Railway deployment at:
https://web-production-8f7f6f.up.railway.app

Run locally:  pytest tests/test_api.py -v
CI/CD:        runs automatically on every push
"""

import os
import pytest
import requests

BASE_URL = os.getenv("API_BASE_URL", "https://web-production-8f7f6f.up.railway.app")


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════
def post(endpoint, payload):
    r = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()

def get(endpoint):
    r = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
    r.raise_for_status()
    return r.json()


# ══════════════════════════════════════════════════════════
# Root
# ══════════════════════════════════════════════════════════
class TestRoot:
    def test_backend_is_live(self):
        data = get("/")
        assert data["status"] == "SnackStad backend is running"

    def test_returns_version(self):
        data = get("/")
        assert "version" in data


# ══════════════════════════════════════════════════════════
# /match/state
# ══════════════════════════════════════════════════════════
class TestMatchState:

    def test_halftime_approaching(self):
        data = post("/match/state", {"scenario": "halftime_approaching"})
        assert data["break_coming"] is True
        assert data["break_in_seconds"] <= 180
        assert data["break_duration"] == 900
        assert data["var_active"] is False

    def test_mid_play(self):
        data = post("/match/state", {"scenario": "mid_play"})
        assert data["break_coming"] is False

    def test_var_extension(self):
        data = post("/match/state", {"scenario": "var_extension"})
        assert data["break_coming"] is True
        assert data["var_active"] is True
        assert data["break_duration"] > 900

    def test_required_fields_present(self):
        data = post("/match/state", {"scenario": "halftime_approaching"})
        required = ["period", "clock_min", "break_coming",
                    "break_duration", "var_active"]
        for field in required:
            assert field in data, f"Missing field: {field}"


# ══════════════════════════════════════════════════════════
# /fan/location
# ══════════════════════════════════════════════════════════
class TestFanLocation:

    def test_demo_fan_section_104(self):
        data = post("/fan/location", {
            "section": "104", "row": "G", "seat_number": "12"
        })
        assert data["seat_coords"]["x"] == 45.2
        assert data["seat_coords"]["y"] == 112.8

    def test_returns_walk_times(self):
        data = post("/fan/location", {
            "section": "104", "row": "G", "seat_number": "12"
        })
        walk_times = data["walk_times_seconds"]
        assert len(walk_times) == 8
        assert all(v >= 0 for v in walk_times.values())

    def test_returns_preferences(self):
        data = post("/fan/location", {
            "section": "104", "row": "G", "seat_number": "12"
        })
        assert isinstance(data["preferences"], list)
        assert len(data["preferences"]) > 0

    def test_nearest_stand_returned(self):
        data = post("/fan/location", {
            "section": "104", "row": "G", "seat_number": "12"
        })
        assert data["nearest_stand_id"] == "Stand_3"

    def test_unknown_seat_fallback(self):
        data = post("/fan/location", {
            "section": "999", "row": "Z", "seat_number": "99"
        })
        assert data["seat_coords"] is not None


# ══════════════════════════════════════════════════════════
# /queues/score
# ══════════════════════════════════════════════════════════
class TestQueuesScore:

    def test_returns_ranked_stands(self):
        data = post("/queues/score", {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "break_duration_sec": 900
        })
        assert len(data["ranked_stands"]) == 8

    def test_sorted_by_total_time(self):
        data = post("/queues/score", {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "break_duration_sec": 900
        })
        times = [s["total_sec"] for s in data["ranked_stands"]]
        assert times == sorted(times)

    def test_any_feasible_true_normal_break(self):
        data = post("/queues/score", {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "break_duration_sec": 900
        })
        assert data["any_feasible"] is True

    def test_any_feasible_false_short_break(self):
        data = post("/queues/score", {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "break_duration_sec": 5
        })
        assert data["any_feasible"] is False

    def test_best_stand_returned(self):
        data = post("/queues/score", {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "break_duration_sec": 900
        })
        assert data["best_stand"] is not None
        assert "stand_id" in data["best_stand"]


# ══════════════════════════════════════════════════════════
# /inventory/check
# ══════════════════════════════════════════════════════════
class TestInventoryCheck:

    def _ranked_stands(self):
        return [
            {"stand_id": "Stand_3", "name": "Stand 3 - North Lower",
             "walk_sec": 15, "total_sec": 200, "feasible": True},
            {"stand_id": "Stand_4", "name": "Stand 4 - North Upper",
             "walk_sec": 25, "total_sec": 350, "feasible": True},
        ]

    def test_finds_nachos_at_stand_3(self):
        data = post("/inventory/check", {
            "ranked_stands": self._ranked_stands(),
            "preferences": ["nachos", "soda"]
        })
        assert data["stock_ok"] is True
        assert data["confirmed_stand"]["stand_id"] == "Stand_3"

    def test_returns_available_items(self):
        data = post("/inventory/check", {
            "ranked_stands": self._ranked_stands(),
            "preferences": ["nachos"]
        })
        assert "nachos" in data["available_items"]

    def test_fallback_when_preference_unavailable(self):
        data = post("/inventory/check", {
            "ranked_stands": self._ranked_stands(),
            "preferences": ["sushi"]  # not in any stand
        })
        assert data["stock_ok"] is True
        assert data["is_fallback"] is True


# ══════════════════════════════════════════════════════════
# /order/suggest
# ══════════════════════════════════════════════════════════
class TestOrderSuggest:

    def _payload(self, confirmed=True):
        return {
            "fan_id": "FAN-001",
            "fan_name": "John",
            "confirmed_stand": {
                "stand_id": "Stand_3",
                "name": "Stand 3 - North Lower",
                "total_sec": 200,
                "walk_sec": 15
            },
            "available_items": ["nachos", "soda"],
            "fan_confirmed": confirmed
        }

    def test_confirmed_order_returns_confirmed_status(self):
        data = post("/order/suggest", self._payload(confirmed=True))
        assert data["status"] == "CONFIRMED"
        assert data["kitchen_notified"] is True

    def test_pending_order_not_confirmed(self):
        data = post("/order/suggest", self._payload(confirmed=False))
        assert data["status"] == "PENDING"
        assert data["kitchen_notified"] is False

    def test_order_id_generated(self):
        data = post("/order/suggest", self._payload())
        assert data["order_id"].startswith("ORD-")

    def test_order_has_timestamp(self):
        data = post("/order/suggest", self._payload())
        assert "timestamp" in data


# ══════════════════════════════════════════════════════════
# /route/calculate
# ══════════════════════════════════════════════════════════
class TestRouteCalculate:

    def _payload(self):
        return {
            "fan_coords": {"x": 45.2, "y": 112.8},
            "fan_seat": {"section": "104", "row": "G", "number": "12"},
            "confirmed_stand": {
                "stand_id": "Stand_3",
                "name": "Stand 3 - North Lower",
                "walk_sec": 15,
                "total_sec": 200
            },
            "break_duration_sec": 900
        }

    def test_returns_instructions(self):
        data = post("/route/calculate", self._payload())
        assert len(data["route_instructions"]) >= 3

    def test_returns_three_alerts(self):
        data = post("/route/calculate", self._payload())
        assert len(data["countdown_alerts"]) == 3

    def test_alerts_have_messages(self):
        data = post("/route/calculate", self._payload())
        for alert in data["countdown_alerts"]:
            assert len(alert["message"]) > 0

    def test_return_deadline_calculated(self):
        data = post("/route/calculate", self._payload())
        assert data["return_deadline_sec"] > 0


# ══════════════════════════════════════════════════════════
# /edge/handle
# ══════════════════════════════════════════════════════════
class TestEdgeHandle:

    def test_clean_pipeline_no_issues(self):
        data = post("/edge/handle", {
            "no_feasible_stand": False,
            "no_stock": False,
            "var_active": False,
            "order_confirmed": True
        })
        assert data["issues_detected"] == []
        assert data["fallback_mode"] == "none"

    def test_no_feasible_triggers_in_seat_delivery(self):
        data = post("/edge/handle", {
            "no_feasible_stand": True,
            "no_stock": False,
            "var_active": False,
            "order_confirmed": False
        })
        assert "no_feasible_stand" in data["issues_detected"]
        assert data["fallback_mode"] == "in_seat_delivery"

    def test_var_active_detected(self):
        data = post("/edge/handle", {
            "no_feasible_stand": False,
            "no_stock": False,
            "var_active": True,
            "var_extra_seconds": 180,
            "order_confirmed": True
        })
        assert "var_active" in data["issues_detected"]

    def test_no_stock_triggers_ops_alert(self):
        data = post("/edge/handle", {
            "no_feasible_stand": False,
            "no_stock": True,
            "var_active": False,
            "order_confirmed": False
        })
        assert "no_stock" in data["issues_detected"]
        assert data["fallback_mode"] == "ops_alert"

    def test_stand_closed_triggers_reroute(self):
        data = post("/edge/handle", {
            "no_feasible_stand": False,
            "no_stock": False,
            "var_active": False,
            "stand_closed_mid_journey": True,
            "order_confirmed": False
        })
        assert "stand_closed_mid_journey" in data["issues_detected"]
        assert data["fallback_mode"] == "reroute"

    def test_fan_message_always_present(self):
        data = post("/edge/handle", {
            "no_feasible_stand": False,
            "no_stock": False,
            "var_active": False,
            "order_confirmed": True
        })
        assert len(data["fan_message"]) > 0


# ══════════════════════════════════════════════════════════
# Full Pipeline Integration Test
# ══════════════════════════════════════════════════════════
class TestFullPipeline:
    """
    Simulates the complete 7-agent pipeline calling
    each endpoint in sequence, just like Orchestrate does.
    """

    def test_full_halftime_pipeline(self):
        # Step 1 — Break Predictor
        match = post("/match/state", {"scenario": "halftime_approaching"})
        assert match["break_coming"] is True

        # Step 2 — Location Agent
        fan = post("/fan/location", {
            "section": "104", "row": "G", "seat_number": "12"
        })
        assert fan["seat_coords"]["x"] == 45.2

        # Step 3 — Queue Scout
        queues = post("/queues/score", {
            "fan_coords": fan["seat_coords"],
            "break_duration_sec": match["break_duration"]
        })
        assert queues["any_feasible"] is True

        # Step 4 — Inventory Agent
        inventory = post("/inventory/check", {
            "ranked_stands": queues["ranked_stands"],
            "preferences": fan["preferences"]
        })
        assert inventory["stock_ok"] is True

        # Step 5 — Order Agent
        order = post("/order/suggest", {
            "fan_id": fan["fan_id"],
            "fan_name": fan["fan_name"],
            "confirmed_stand": inventory["confirmed_stand"],
            "available_items": inventory["available_items"],
            "fan_confirmed": True
        })
        assert order["status"] == "CONFIRMED"

        # Step 6 — Route Agent
        route = post("/route/calculate", {
            "fan_coords": fan["seat_coords"],
            "fan_seat": {"section": "104", "row": "G", "number": "12"},
            "confirmed_stand": inventory["confirmed_stand"],
            "break_duration_sec": match["break_duration"]
        })
        assert len(route["route_instructions"]) >= 3

        # Step 7 — Edge Case Handler
        edge = post("/edge/handle", {
            "no_feasible_stand": not queues["any_feasible"],
            "no_stock": not inventory["stock_ok"],
            "var_active": match["var_active"],
            "order_confirmed": order["status"] == "CONFIRMED"
        })
        assert edge["issues_detected"] == []
        assert edge["fan_message"] != ""
