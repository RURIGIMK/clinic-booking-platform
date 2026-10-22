from datetime import datetime, timedelta, timezone
def slot(days=3,hour=10):
    value=datetime.now(timezone.utc)+timedelta(days=days)
    while value.weekday()>4: value+=timedelta(days=1)
    return value.replace(hour=hour,minute=0,second=0,microsecond=0)
def body(seeded,start):
    return {"doctor_id":seeded["doctor_id"],"patient_id":seeded["patient_id"],"starts_at":start.isoformat()}
def test_book_and_reject_duplicate(client,seeded):
    payload=body(seeded,slot())
    assert client.post("/appointments",json=payload).status_code==201
    assert client.post("/appointments",json=payload).status_code==409
def test_naive_datetime_rejected(client,seeded):
    assert client.post("/appointments",json={"doctor_id":seeded["doctor_id"],"patient_id":seeded["patient_id"],"starts_at":"2030-01-01T10:00:00"}).status_code==422
def test_past_slot_rejected(client,seeded):
    assert client.post("/appointments",json=body(seeded,datetime.now(timezone.utc)-timedelta(days=1))).status_code==422
def test_unknown_doctor(client,seeded):
    payload=body(seeded,slot()); payload["doctor_id"]=999
    assert client.post("/appointments",json=payload).status_code==404
def test_cancel_releases_slot_and_repeat_conflicts(client,seeded):
    payload=body(seeded,slot()); item=client.post("/appointments",json=payload).json(); path="/appointments/"+str(item["id"])+"/cancel"
    assert client.patch(path,json={"reason":"Schedule changed"}).status_code==200
    assert client.patch(path,json={"reason":"Again"}).status_code==409
    assert client.post("/appointments",json=payload).status_code==201
def test_reschedule_releases_old_slot(client,seeded):
    original=slot(); target=slot(4,11); item=client.post("/appointments",json=body(seeded,original)).json()
    response=client.patch("/appointments/"+str(item["id"])+"/reschedule",json={"starts_at":target.isoformat()})
    assert response.status_code==200
    assert client.post("/appointments",json=body(seeded,original)).status_code==201
