from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math, random, uuid
from datetime import datetime

app = FastAPI(title="SnackStad Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static Data ────────────────────────────────────────────────────────────────

SEAT_MAP = {
    ("101","A","1"): {"x":10.0,"y":90.0,"zone":"West","stand_nearby":"Stand_1"},
    ("101","A","2"): {"x":10.0,"y":91.0,"zone":"West","stand_nearby":"Stand_1"},
    ("102","A","1"): {"x":20.0,"y":90.0,"zone":"West","stand_nearby":"Stand_1"},
    ("102","C","1"): {"x":22.0,"y":91.0,"zone":"West","stand_nearby":"Stand_2"},
    ("103","F","8"): {"x":38.1,"y":108.3,"zone":"North","stand_nearby":"Stand_3"},
    ("104","G","10"):{"x":45.2,"y":112.8,"zone":"North","stand_nearby":"Stand_3"},
    ("104","G","11"):{"x":45.2,"y":112.8,"zone":"North","stand_nearby":"Stand_3"},
    ("104","G","12"):{"x":45.2,"y":112.8,"zone":"North","stand_nearby":"Stand_3"},
    ("104","G","13"):{"x":45.2,"y":113.6,"zone":"North","stand_nearby":"Stand_3"},
    ("104","H","1"): {"x":46.0,"y":113.0,"zone":"North","stand_nearby":"Stand_4"},
    ("105","H","4"): {"x":52.7,"y":115.1,"zone":"North","stand_nearby":"Stand_4"},
    ("106","A","1"): {"x":60.0,"y":120.0,"zone":"East","stand_nearby":"Stand_5"},
    ("107","D","3"): {"x":66.5,"y":126.5,"zone":"East","stand_nearby":"Stand_6"},
    ("108","D","7"): {"x":70.3,"y":130.2,"zone":"East","stand_nearby":"Stand_6"},
    ("109","A","1"): {"x":75.0,"y":135.0,"zone":"South","stand_nearby":"Stand_7"},
    ("110","C","3"): {"x":81.0,"y":141.5,"zone":"South","stand_nearby":"Stand_7"},
    ("111","B","2"): {"x":85.5,"y":146.0,"zone":"South","stand_nearby":"Stand_8"},
    ("112","C","1"): {"x":91.0,"y":150.0,"zone":"West","stand_nearby":"Stand_8"},
}

STANDS = {
    "Stand_1": {"x":8.0,  "y":88.0,  "name":"Stand 1 - West Gate"},
    "Stand_2": {"x":25.0, "y":88.0,  "name":"Stand 2 - West Concourse"},
    "Stand_3": {"x":44.0, "y":125.0, "name":"Stand 3 - North Lower"},
    "Stand_4": {"x":55.0, "y":125.0, "name":"Stand 4 - North Upper"},
    "Stand_5": {"x":62.0, "y":135.0, "name":"Stand 5 - East Gate"},
    "Stand_6": {"x":72.0, "y":135.0, "name":"Stand 6 - East Concourse"},
    "Stand_7": {"x":78.0, "y":148.0, "name":"Stand 7 - South Lower"},
    "Stand_8": {"x":92.0, "y":148.0, "name":"Stand 8 - South Gate"},
}

INVENTORY = {
    "Stand_1": ["hot_dog", "water", "chips"],
    "Stand_2": ["pizza", "soda", "coffee"],
    "Stand_3": ["nachos", "soda", "beer", "hot_dog"],
    "Stand_4": ["burger", "beer", "water"],
    "Stand_5": ["nachos", "water", "chips"],
    "Stand_6": ["hot_dog", "beer", "soda"],
    "Stand_7": ["pizza", "soda", "coffee"],
    "Stand_8": ["burger", "water", "chips"],
}

FAN_PROFILES = {
    "default": {
        "fan_id": "FAN-001",
        "fan_name": "John",
        "preferences": ["nachos", "soda"],
        "loyalty_tier": "gold"
    }
}

ROUTE_INSTRUCTIONS = {
    "North": [
        "Exit your row toward the main aisle",
        "Head up the stairs to the North concourse",
        "Turn left at the blue concession sign",
        "Walk 30 metres — Stand 3 is on your left",
        "Collect your order and head back the same way"
    ],
    "South": [
        "Exit your row toward the main aisle",
        "Head down the stairs to the South concourse",
        "Follow the yellow concession signs",
        "Stand 7 is straight ahead past the restrooms"
    ],
    "East": [
        "Exit your row toward the East aisle",
        "Take the East corridor toward the main concourse",
        "Turn right at the food court sign",
        "Stand 5 is on your right"
    ],
    "West": [
        "Exit your row toward the West aisle",
        "Head to the West concourse via the main tunnel",
        "Stand 1 is immediately on your left at the tunnel exit"
    ]
}

# ─── Models ─────────────────────────────────────────────────────────────────────

class SeatInput(BaseModel):
    section: str
    row: str
    seat_number: str

class QueueInput(BaseModel):
    fan_coords: dict
    break_duration_sec: int

class InventoryInput(BaseModel):
    ranked_stands: list
    preferences: List[str]

class OrderInput(BaseModel):
    fan_id: str
    fan_name: Optional[str] = "Fan"
    confirmed_stand: dict
    available_items: List[str]
    fan_confirmed: bool

class RouteInput(BaseModel):
    fan_coords: dict
    fan_seat: dict
    confirmed_stand: dict
    break_duration_sec: int

class EdgeInput(BaseModel):
    no_feasible_stand: bool
    no_stock: bool
    var_active: bool
    order_confirmed: bool
    var_extra_seconds: Optional[int] = 0
    stand_closed_mid_journey: Optional[bool] = False
    gps_lost: Optional[bool] = False

# ─── Helpers ────────────────────────────────────────────────────────────────────

def get_seat(section, row, seat):
    key = (str(section), str(row), str(seat))
    # exact match
    if key in SEAT_MAP:
        return SEAT_MAP[key]
    # fallback: find closest seat in same section
    matches = [(k, v) for k, v in SEAT_MAP.items() if k[0] == str(section)]
    if matches:
        return matches[0][1]
    # ultimate fallback
    return {"x": 45.2, "y": 112.8, "zone": "North", "stand_nearby": "Stand_3"}

def calc_distance(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

# ─── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "SnackStad backend is running", "version": "1.0.0"}


class MatchStateInput(BaseModel):
    scenario: str  # halftime_approaching | mid_play | var_extension


@app.post("/match/state")
def get_match_state(body: MatchStateInput):
    if body.scenario == "halftime_approaching":
        return {
            "period": 1,
            "clock_min": 42,
            "clock_sec": 0,
            "break_coming": True,
            "break_in_seconds": 180,
            "break_duration": 900,
            "var_active": False,
            "extra_time_sec": 0
        }
    elif body.scenario == "var_extension":
        return {
            "period": 1,
            "clock_min": 44,
            "clock_sec": 30,
            "break_coming": True,
            "break_in_seconds": 90,
            "break_duration": 1080,
            "var_active": True,
            "extra_time_sec": 180
        }
    else:  # mid_play
        return {
            "period": 1,
            "clock_min": 25,
            "clock_sec": 0,
            "break_coming": False,
            "break_in_seconds": 1200,
            "break_duration": 900,
            "var_active": False,
            "extra_time_sec": 0
        }


@app.post("/fan/location")
def get_fan_location(body: SeatInput):
    seat = get_seat(body.section, body.row, body.seat_number)
    fan_x, fan_y = seat["x"], seat["y"]

    walk_times = {}
    for stand_id, stand in STANDS.items():
        dist = calc_distance(fan_x, fan_y, stand["x"], stand["y"])
        walk_times[stand_id] = round(dist / 1.2)

    profile = FAN_PROFILES["default"]

    return {
        "fan_id": profile["fan_id"],
        "fan_name": profile["fan_name"],
        "seat_coords": {"x": fan_x, "y": fan_y},
        "zone": seat["zone"],
        "nearest_stand_id": seat["stand_nearby"],
        "walk_times_seconds": walk_times,
        "preferences": profile["preferences"],
        "loyalty_tier": profile["loyalty_tier"]
    }


@app.post("/queues/score")
def score_queues(body: QueueInput):
    fan_x = body.fan_coords.get("x", 45.2)
    fan_y = body.fan_coords.get("y", 112.8)
    break_sec = body.break_duration_sec

    # Simulate realistic queue lengths
    queue_lengths = {
        "Stand_1": random.randint(10, 18),
        "Stand_2": random.randint(6, 12),
        "Stand_3": random.randint(2, 6),
        "Stand_4": random.randint(8, 14),
        "Stand_5": random.randint(4, 9),
        "Stand_6": random.randint(7, 13),
        "Stand_7": random.randint(10, 16),
        "Stand_8": random.randint(5, 10),
    }

    ranked = []
    for stand_id, stand in STANDS.items():
        dist = calc_distance(fan_x, fan_y, stand["x"], stand["y"])
        walk_sec = round(dist / 1.2)
        queue_len = queue_lengths[stand_id]
        wait_sec = queue_len * 45
        total_sec = walk_sec + wait_sec
        feasible = total_sec < (break_sec - 120)  # 2 min buffer to get back

        ranked.append({
            "stand_id": stand_id,
            "name": stand["name"],
            "walk_sec": walk_sec,
            "queue_len": queue_len,
            "wait_sec": wait_sec,
            "total_sec": total_sec,
            "feasible": feasible
        })

    ranked.sort(key=lambda x: x["total_sec"])
    feasible_stands = [s for s in ranked if s["feasible"]]
    best = feasible_stands[0] if feasible_stands else None

    return {
        "ranked_stands": ranked,
        "best_stand": {
            "stand_id": best["stand_id"],
            "name": best["name"],
            "total_sec": best["total_sec"]
        } if best else None,
        "any_feasible": len(feasible_stands) > 0
    }


@app.post("/inventory/check")
def check_inventory(body: InventoryInput):
    prefs = [p.lower() for p in body.preferences]

    for stand in body.ranked_stands:
        if not stand.get("feasible", True):
            continue
        stand_id = stand["stand_id"]
        stock = INVENTORY.get(stand_id, [])
        matches = [item for item in prefs if item in stock]

        if matches:
            return {
                "confirmed_stand": {
                    "stand_id": stand_id,
                    "name": STANDS[stand_id]["name"],
                    "total_sec": stand.get("total_sec", 300),
                    "walk_sec": stand.get("walk_sec", 120)
                },
                "available_items": matches,
                "stock_ok": True,
                "is_fallback": False
            }

    # fallback — return best stand with whatever it has
    if body.ranked_stands:
        best = body.ranked_stands[0]
        stand_id = best["stand_id"]
        stock = INVENTORY.get(stand_id, ["water"])
        return {
            "confirmed_stand": {
                "stand_id": stand_id,
                "name": STANDS[stand_id]["name"],
                "total_sec": best.get("total_sec", 300),
                "walk_sec": best.get("walk_sec", 120)
            },
            "available_items": stock[:2],
            "stock_ok": True,
            "is_fallback": True
        }

    return {
        "confirmed_stand": None,
        "available_items": [],
        "stock_ok": False,
        "is_fallback": False
    }


@app.post("/order/suggest")
def suggest_order(body: OrderInput):
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    stand = body.confirmed_stand

    if body.fan_confirmed:
        return {
            "order_id": order_id,
            "status": "CONFIRMED",
            "items": body.available_items,
            "stand_id": stand.get("stand_id"),
            "stand_name": stand.get("name", stand.get("stand_id")),
            "timestamp": datetime.now().isoformat(),
            "kitchen_notified": True,
            "message": f"Order confirmed! Head to {stand.get('name', stand.get('stand_id'))} — your {', '.join(body.available_items)} will be ready in ~3 min."
        }
    else:
        return {
            "order_id": order_id,
            "status": "PENDING",
            "items": body.available_items,
            "stand_id": stand.get("stand_id"),
            "stand_name": stand.get("name", stand.get("stand_id")),
            "timestamp": datetime.now().isoformat(),
            "kitchen_notified": False,
            "message": f"Tap confirm to order {', '.join(body.available_items)} from {stand.get('name', stand.get('stand_id'))}. Walk time: ~{stand.get('walk_sec', 120) // 60} min."
        }


@app.post("/route/calculate")
def calculate_route(body: RouteInput):
    stand = body.confirmed_stand
    walk_sec = stand.get("walk_sec", 120)
    break_sec = body.break_duration_sec
    return_deadline = break_sec - walk_sec - 60

    # pick route based on stand zone
    stand_id = stand.get("stand_id", "Stand_3")
    zone = "North"
    for sid, sdata in STANDS.items():
        if sid == stand_id:
            # infer zone from position
            if sdata["x"] < 30:
                zone = "West"
            elif sdata["x"] > 70:
                zone = "East"
            elif sdata["y"] > 140:
                zone = "South"
            else:
                zone = "North"

    instructions = ROUTE_INSTRUCTIONS.get(zone, ROUTE_INSTRUCTIONS["North"])

    return {
        "route_instructions": instructions,
        "countdown_alerts": [
            {
                "at_seconds_remaining": break_sec - 60,
                "message": f"Half-time started! Head to {stand.get('name', stand_id)} now."
            },
            {
                "at_seconds_remaining": return_deadline,
                "message": "Time to head back to your seat — second half starting soon!"
            },
            {
                "at_seconds_remaining": 60,
                "message": "60 seconds until second half — get back to your seat!"
            }
        ],
        "return_deadline_sec": return_deadline
    }


@app.post("/edge/handle")
def handle_edge_cases(body: EdgeInput):
    issues = []
    fallback_mode = "none"
    replan = False
    fan_msg = ""
    ops_alert = ""

    if body.gps_lost:
        issues.append("gps_lost")
        fallback_mode = "gps_fallback"
        fan_msg = "We lost your location signal. Using your section centre instead."

    if body.no_feasible_stand:
        issues.append("no_feasible_stand")
        fallback_mode = "in_seat_delivery"
        fan_msg = "Lines are too long to make it back in time. We'll deliver to your seat instead!"
        ops_alert = "In-seat delivery triggered for fan in Section 104."

    if body.no_stock:
        issues.append("no_stock")
        fallback_mode = "ops_alert"
        fan_msg = "Your preferred items are sold out. Our team is checking alternatives."
        ops_alert = "Stock alert: preferred items unavailable across feasible stands."

    if body.stand_closed_mid_journey:
        issues.append("stand_closed_mid_journey")
        fallback_mode = "reroute"
        replan = True
        fan_msg = "Stand closed — rerouting you to the next best option now."

    if body.var_active:
        issues.append("var_active")
        replan = True
        fan_msg = f"VAR added {body.var_extra_seconds}s to the break — recalculating your route."

    if not issues:
        fan_msg = "All systems normal. Enjoy your snack!"

    return {
        "issues_detected": issues,
        "fallback_mode": fallback_mode,
        "replan_required": replan,
        "fan_message": fan_msg,
        "ops_alert": ops_alert
    }
