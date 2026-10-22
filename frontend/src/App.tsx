import { useEffect, useState } from "react";
import { CalendarDays, Check, Clock3, HeartPulse, LoaderCircle, ShieldCheck, Stethoscope, X } from "lucide-react";

type Doctor = { id: number; name: string; specialty: string };
type Slot = { starts_at: string; ends_at: string };
type Appointment = { id: number; doctor_id: number; patient_id: number; starts_at: string; ends_at: string; status: string };

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const PATIENT = 1;
const CLINIC_TIME_ZONE = "Africa/Nairobi";

// SQLite can return UTC timestamps without an offset. Treat those as UTC rather
// than letting the browser interpret them as local time.
const parseApiDate = (value: string) =>
  /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? new Date(value) : new Date(`${value}Z`);

const clinicDateParts = (value: string) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parseApiDate(value));

const timeLabel = (value: string) =>
  new Intl.DateTimeFormat("en-KE", {
    timeZone: CLINIC_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  }).format(parseApiDate(value));

const appointmentDateLabel = (value: string) =>
  new Intl.DateTimeFormat("en-KE", {
    timeZone: CLINIC_TIME_ZONE,
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(parseApiDate(value));

const appointmentDayNumber = (value: string) =>
  new Intl.DateTimeFormat("en-KE", { timeZone: CLINIC_TIME_ZONE, day: "numeric" }).format(parseApiDate(value));

const appointmentMonth = (value: string) =>
  new Intl.DateTimeFormat("en-KE", { timeZone: CLINIC_TIME_ZONE, month: "short" }).format(parseApiDate(value));

const dateKey = (date: Date) =>
  date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");

const clinicDateAsLocalDate = (value: string) => {
  const parts = Object.fromEntries(clinicDateParts(value).map(({ type, value: part }) => [type, part]));
  return new Date(Number(parts.year), Number(parts.month) - 1, Number(parts.day), 12);
};

export default function App() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [doctorId, setDoctorId] = useState(1);
  const [day, setDay] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d;
  });
  const [slots, setSlots] = useState<Slot[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [selected, setSelected] = useState<Slot | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [cancelId, setCancelId] = useState<number | null>(null);
  const [reason, setReason] = useState("Schedule changed");

  const [rescheduleAppointment, setRescheduleAppointment] = useState<Appointment | null>(null);
  const [rescheduleDay, setRescheduleDay] = useState<Date>(() => new Date());
  const [rescheduleSlots, setRescheduleSlots] = useState<Slot[]>([]);
  const [rescheduleSelected, setRescheduleSelected] = useState<Slot | null>(null);
  const [rescheduleLoading, setRescheduleLoading] = useState(false);
  const [rescheduleError, setRescheduleError] = useState("");

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(API + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Request failed (" + response.status + ")");
    return body as T;
  }

  async function refreshAppointments() {
    try {
      setAppointments(await api<Appointment[]>("/patients/" + PATIENT + "/appointments"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load appointments.");
    }
  }

  async function refreshSlots(id = doctorId, date = day) {
    try {
      setSlots(await api<Slot[]>("/doctors/" + id + "/availability?date=" + dateKey(date)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load availability.");
    }
  }

  useEffect(() => {
    api<Doctor[]>("/doctors")
      .then((items) => {
        setDoctors(items);
        if (items.length) setDoctorId(items[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "API unavailable. Start the backend and retry."))
      .finally(() => setLoading(false));
    void refreshAppointments();
  }, []);

  useEffect(() => {
    if (doctorId) {
      setSelected(null);
      void refreshSlots(doctorId, day);
    }
  }, [doctorId, day]);

  useEffect(() => {
    if (!rescheduleAppointment) return;
    let active = true;
    setRescheduleLoading(true);
    setRescheduleSelected(null);
    setRescheduleError("");
    api<Slot[]>(
      "/doctors/" + rescheduleAppointment.doctor_id + "/availability?date=" + dateKey(rescheduleDay),
    )
      .then((items) => {
        if (active) setRescheduleSlots(items);
      })
      .catch((e) => {
        if (active) setRescheduleError(e instanceof Error ? e.message : "Could not load current availability.");
      })
      .finally(() => {
        if (active) setRescheduleLoading(false);
      });
    return () => {
      active = false;
    };
  }, [rescheduleAppointment?.id, rescheduleDay]);

  async function book() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/appointments", {
        method: "POST",
        body: JSON.stringify({ doctor_id: doctorId, patient_id: PATIENT, starts_at: selected.starts_at }),
      });
      setNotice("Appointment confirmed.");
      setSelected(null);
      await Promise.all([refreshAppointments(), refreshSlots()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Booking failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (cancelId === null) return;
    setBusy(true);
    setError("");
    try {
      await api("/appointments/" + cancelId + "/cancel", {
        method: "PATCH",
        body: JSON.stringify({ reason }),
      });
      setCancelId(null);
      setNotice("Appointment cancelled. Its slot is available again.");
      await Promise.all([refreshAppointments(), refreshSlots()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reschedule() {
    if (!rescheduleAppointment || !rescheduleSelected) return;
    setBusy(true);
    setRescheduleError("");
    setError("");
    try {
      await api("/appointments/" + rescheduleAppointment.id + "/reschedule", {
        method: "PATCH",
        body: JSON.stringify({ starts_at: rescheduleSelected.starts_at }),
      });
      setNotice("Appointment rescheduled to " + appointmentDateLabel(rescheduleSelected.starts_at) + " at " + timeLabel(rescheduleSelected.starts_at) + ".");
      setRescheduleAppointment(null);
      setRescheduleSelected(null);
      await Promise.all([refreshAppointments(), refreshSlots()]);
    } catch (e) {
      setRescheduleError(e instanceof Error ? e.message : "Rescheduling failed.");
    } finally {
      setBusy(false);
    }
  }

  function openReschedule(appointment: Appointment) {
    setRescheduleAppointment(appointment);
    setRescheduleDay(clinicDateAsLocalDate(appointment.starts_at));
    setRescheduleSelected(null);
    setRescheduleSlots([]);
    setRescheduleError("");
  }

  function shiftRescheduleDay(amount: number) {
    setRescheduleDay((current) => {
      const next = new Date(current);
      next.setDate(next.getDate() + amount);
      return next;
    });
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-icon"><HeartPulse /></span>
          <span>Care<span>slot</span><small>CLINIC APPOINTMENTS</small></span>
        </a>
        <div className="secure"><ShieldCheck size={15} /> Secure scheduling <b>AS</b></div>
      </header>

      <main className="page">
        <section className="intro">
          <div>
            <label>PATIENT PORTAL</label>
            <h1>Make time for<br /><em>your health.</em></h1>
            <p>Choose a clinician, find a time that works for you, and keep your appointments in one clear place.</p>
          </div>
          <div className="intro-mark"><HeartPulse size={58} /></div>
        </section>

        {error && <div className="alert error" role="alert"><X size={16} /><span>{error}</span><button onClick={() => { setError(""); void refreshSlots(); void refreshAppointments(); }}>Retry</button></div>}
        {notice && <div className="alert success" role="status"><Check size={16} /><span>{notice}</span><button onClick={() => setNotice("")}>Dismiss</button></div>}

        <div className="layout">
          <section className="card booking">
            <div className="card-head"><div><small>01 / BOOK A VISIT</small><h2>Find your appointment</h2></div><CalendarDays /></div>
            <label htmlFor="doctor">Choose a clinician</label>
            <select id="doctor" value={doctorId} disabled={loading || !doctors.length} onChange={(e) => setDoctorId(Number(e.target.value))}>
              {doctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.name} · {doctor.specialty}</option>)}
            </select>

            <div className="doctor-line">
              <span><Stethoscope size={19} /></span>
              <div><strong>{doctors.find((doctor) => doctor.id === doctorId)?.name ?? "Loading clinicians"}</strong><small>{doctors.find((doctor) => doctor.id === doctorId)?.specialty ?? "Please wait"}</small></div>
              <b>By schedule</b>
            </div>

            <div className="date-row">
              <div><label>Select a date</label><strong>{day.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</strong></div>
              <div>
                <button aria-label="Previous day" onClick={() => { const next = new Date(day); next.setDate(next.getDate() - 1); setDay(next); }}>‹</button>
                <button aria-label="Next day" onClick={() => { const next = new Date(day); next.setDate(next.getDate() + 1); setDay(next); }}>›</button>
              </div>
            </div>

            <div className="slot-title"><label>Available times</label><span><Clock3 size={13} /> 30-minute visits</span></div>
            {slots.length ? (
              <div className="slots">
                {slots.map((slot) => <button key={slot.starts_at} className={selected?.starts_at === slot.starts_at ? "slot active" : "slot"} aria-pressed={selected?.starts_at === slot.starts_at} onClick={() => setSelected(slot)}>{timeLabel(slot.starts_at)}</button>)}
              </div>
            ) : <div className="empty"><CalendarDays size={24} /><strong>No times available</strong><span>Try another date or clinician.</span></div>}

            <div className="book-footer">
              <span><ShieldCheck size={15} /> Confirmed after booking</span>
              <button className="primary" disabled={!selected || busy} onClick={() => void book()}>{busy ? <LoaderCircle className="spin" /> : <Check size={15} />} Confirm booking</button>
            </div>
          </section>

          <aside className="side">
            <section className="card visits">
              <div className="card-head"><div><small>YOUR VISITS</small><h2>Upcoming appointments</h2></div><CalendarDays /></div>
              {appointments.length ? appointments.map((appointment) => (
                <article className="visit" key={appointment.id}>
                  <div className="date-badge"><strong>{appointmentDayNumber(appointment.starts_at)}</strong><span>{appointmentMonth(appointment.starts_at)}</span></div>
                  <div className="visit-info">
                    <strong>{doctors.find((doctor) => doctor.id === appointment.doctor_id)?.name ?? "Doctor #" + appointment.doctor_id}</strong>
                    <small>{appointmentDateLabel(appointment.starts_at)} · {timeLabel(appointment.starts_at)}</small>
                    <div className="actions">
                      <button onClick={() => openReschedule(appointment)}>Find new time</button>
                      <button className="cancel-link" onClick={() => setCancelId(appointment.id)}>Cancel</button>
                    </div>
                  </div>
                </article>
              )) : <div className="empty visit-empty"><CalendarDays size={23} /><strong>No upcoming visits</strong><span>Your confirmed appointments appear here.</span></div>}
              <button className="refresh" onClick={() => { void refreshAppointments(); void refreshSlots(); }}>Refresh appointments →</button>
            </section>

            <section className="note"><ShieldCheck /><div><strong>Designed around your time</strong><p>Appointments last 30 minutes. A slot is yours once booking is confirmed.</p></div></section>
            <section className="card hours">
              <strong><Clock3 size={15} /> Clinic hours</strong>
              <p><span>Monday – Friday</span><b>8:00 AM – 5:00 PM</b></p>
              <p><span>Saturday</span><b>9:00 AM – 1:00 PM</b></p>
              <p><span>Sunday</span><b>Closed</b></p>
              <p><span>Appointment length</span><b>30 minutes</b></p>
              <small className="hours-note">Individual doctors may have shorter specialty sessions and a midday break. Available slots reflect each doctor's schedule.</small>
            </section>
          </aside>
        </div>

        <footer><strong>CARESLOT / CLINIC BOOKING DEMO</strong><span>Thoughtful care starts with a clear schedule.</span></footer>
      </main>

      {cancelId !== null && (
        <div className="overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setCancelId(null); }}>
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="cancel-heading">
            <div className="modal-x"><X /></div>
            <h2 id="cancel-heading">Cancel this appointment?</h2>
            <p>This releases the time for another patient. Please provide a short reason.</p>
            <label htmlFor="reason">Cancellation reason</label>
            <textarea id="reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={500} />
            <div className="modal-actions">
              <button onClick={() => setCancelId(null)}>Keep appointment</button>
              <button className="danger" disabled={busy || reason.trim().length < 3} onClick={() => void cancel()}>{busy ? "Cancelling…" : "Confirm cancellation"}</button>
            </div>
          </section>
        </div>
      )}

      {rescheduleAppointment && (
        <div className="overlay" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setRescheduleAppointment(null); }}>
          <section className="modal reschedule-modal" role="dialog" aria-modal="true" aria-labelledby="reschedule-heading">
            <button className="modal-close" aria-label="Close rescheduling dialog" disabled={busy} onClick={() => setRescheduleAppointment(null)}><X size={18} /></button>
            <small className="modal-eyebrow">UPDATE YOUR VISIT</small>
            <h2 id="reschedule-heading">Find a new time</h2>
            <p>Choose an available slot with {doctors.find((doctor) => doctor.id === rescheduleAppointment.doctor_id)?.name ?? "your clinician"}. Times are shown in Nairobi time.</p>
            <div className="reschedule-date-row">
              <strong>{rescheduleDay.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}</strong>
              <div>
                <button aria-label="Previous day" onClick={() => shiftRescheduleDay(-1)} disabled={rescheduleLoading || busy}>‹</button>
                <button aria-label="Next day" onClick={() => shiftRescheduleDay(1)} disabled={rescheduleLoading || busy}>›</button>
              </div>
            </div>
            {rescheduleLoading ? (
              <div className="modal-state"><LoaderCircle className="spin" /><span>Checking current availability…</span></div>
            ) : rescheduleError ? (
              <div className="modal-error" role="alert"><span>{rescheduleError}</span><button onClick={() => shiftRescheduleDay(0)}>Retry</button></div>
            ) : rescheduleSlots.length ? (
              <div className="reschedule-slots">
                {rescheduleSlots.map((slot) => (
                  <button key={slot.starts_at} className={rescheduleSelected?.starts_at === slot.starts_at ? "slot active" : "slot"} aria-pressed={rescheduleSelected?.starts_at === slot.starts_at} disabled={busy} onClick={() => setRescheduleSelected(slot)}>{timeLabel(slot.starts_at)}</button>
                ))}
              </div>
            ) : (
              <div className="modal-state"><CalendarDays size={23} /><strong>No available times on this date</strong><span>Try another day to see the clinician’s current availability.</span></div>
            )}
            <div className="modal-actions">
              <button onClick={() => setRescheduleAppointment(null)} disabled={busy}>Keep current time</button>
              <button className="primary" disabled={!rescheduleSelected || busy || rescheduleLoading} onClick={() => void reschedule()}>{busy ? <LoaderCircle className="spin" /> : <Check size={15} />} Confirm new time</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
