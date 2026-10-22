from datetime import date, datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("Africa/Nairobi")

def slot(days=3, hour=10):
    value = datetime.now(timezone.utc) + timedelta(days=days)
    while value.weekday() > 4:
        value += timedelta(days=1)
    return value.replace(hour=hour, minute=0, second=0, microsecond=0)

def future_weekday(weekday):
    day = date.today() + timedelta(days=1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day

def body(seeded, start):
    return {"doctor_id": seeded["doctor_id"], "patient_id": seeded["patient_id"], "starts_at": start.isoformat()}

def test_book_and_reject_duplicate(client, seeded):
    payload = body(seeded, slot())
    assert client.post("/appointments", json=payload).status_code == 201
    assert client.post("/appointments", json=payload).status_code == 409

def test_naive_datetime_rejected(client, seeded):
    assert client.post("/appointments", json={"doctor_id": seeded["doctor_id"], "patient_id": seeded["patient_id"], "starts_at": "2030-01-01T10:00:00"}).status_code == 422

def test_past_slot_rejected(client, seeded):
    assert client.post("/appointments", json=body(seeded, datetime.now(timezone.utc) - timedelta(days=1))).status_code == 422


def test_booking_within_one_hour_is_rejected(client, seeded):
    starts_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    response = client.post("/appointments", json=body(seeded, starts_at))
    assert response.status_code == 422
    assert "one hour in advance" in response.json()["detail"]

def test_booking_more_than_one_hour_ahead_is_allowed(client, seeded):
    response = client.post("/appointments", json=body(seeded, slot(days=3)))
    assert response.status_code == 201

def test_reschedule_within_one_hour_is_rejected(client, seeded):
    original = slot(days=3)
    item = client.post("/appointments", json=body(seeded, original)).json()
    target = datetime.now(timezone.utc) + timedelta(minutes=30)
    response = client.patch(
        f"/appointments/{item['id']}/reschedule",
        json={"starts_at": target.isoformat()},
    )
    assert response.status_code == 422
    assert "one hour in advance" in response.json()["detail"]

def test_unknown_doctor(client, seeded):
    payload = body(seeded, slot())
    payload["doctor_id"] = 999
    assert client.post("/appointments", json=payload).status_code == 404

def test_cancel_releases_slot_and_repeat_conflicts(client, seeded):
    payload = body(seeded, slot())
    item = client.post("/appointments", json=payload).json()
    path = "/appointments/" + str(item["id"]) + "/cancel"
    assert client.patch(path, json={"reason": "Schedule changed"}).status_code == 200
    assert client.patch(path, json={"reason": "Again"}).status_code == 409
    assert client.post("/appointments", json=payload).status_code == 201

def test_reschedule_releases_old_slot(client, seeded):
    original = slot()
    target = slot(4, 11)
    item = client.post("/appointments", json=body(seeded, original)).json()
    response = client.patch("/appointments/" + str(item["id"]) + "/reschedule", json={"starts_at": target.isoformat()})
    assert response.status_code == 200
    assert client.post("/appointments", json=body(seeded, original)).status_code == 201

def test_lunch_break_is_not_bookable(client, seeded):
    local_day = future_weekday(0)
    lunch = datetime.combine(local_day, time(12, 0), tzinfo=CLINIC_TZ)
    response = client.post("/appointments", json=body(seeded, lunch))
    assert response.status_code == 422

def test_appointment_must_align_to_half_hour(client, seeded):
    starts_at = slot().replace(minute=15)
    response = client.post("/appointments", json=body(seeded, starts_at))
    assert response.status_code == 422

def test_availability_observes_weekday_lunch_and_saturday_hours(client, seeded):
    monday = future_weekday(0)
    response = client.get(f"/doctors/{seeded['doctor_id']}/availability", params={"date": monday.isoformat()})
    assert response.status_code == 200
    times = [datetime.fromisoformat(item["starts_at"]).astimezone(CLINIC_TZ).time() for item in response.json()]
    assert time(8, 0) in times
    assert time(11, 30) in times
    assert time(12, 0) not in times
    assert time(12, 30) not in times
    assert time(13, 0) in times
    saturday = future_weekday(5)
    response = client.get(f"/doctors/{seeded['doctor_id']}/availability", params={"date": saturday.isoformat()})
    assert response.status_code == 200
    saturday_times = [datetime.fromisoformat(item["starts_at"]).astimezone(CLINIC_TZ).time() for item in response.json()]
    assert saturday_times
    assert min(saturday_times) >= time(9, 0)
    assert all(t < time(13, 0) for t in saturday_times)

def test_sunday_has_no_availability(client, seeded):
    sunday = future_weekday(6)
    response = client.get(f"/doctors/{seeded['doctor_id']}/availability", params={"date": sunday.isoformat()})
    assert response.status_code == 200
    assert response.json() == []
