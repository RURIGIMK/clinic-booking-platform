import { useEffect, useState } from "react";
import { CalendarDays, Check, Clock3, HeartPulse, LoaderCircle, ShieldCheck, Stethoscope, X } from "lucide-react";
type Doctor={id:number;name:string;specialty:string};
type Slot={starts_at:string;ends_at:string};
type Appointment={id:number;doctor_id:number;patient_id:number;starts_at:string;ends_at:string;status:string};
const API=import.meta.env.VITE_API_BASE_URL??"http://localhost:8000";
const PATIENT=1;
const timeLabel=(v:string)=>new Date(v).toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});
const dateKey=(d:Date)=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
export default function App(){
 const [doctors,setDoctors]=useState<Doctor[]>([]),[doctorId,setDoctorId]=useState(1);
 const [day,setDay]=useState(()=>{const d=new Date();d.setDate(d.getDate()+1);return d});
 const [slots,setSlots]=useState<Slot[]>([]),[appointments,setAppointments]=useState<Appointment[]>([]);
 const [selected,setSelected]=useState<Slot|null>(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
 const [error,setError]=useState(""),[notice,setNotice]=useState(""),[cancelId,setCancelId]=useState<number|null>(null),[reason,setReason]=useState("Schedule changed");
 async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const r=await fetch(API+path,{...init,headers:{"Content-Type":"application/json",...(init?.headers??{})}});
  const body=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(body.detail||"Request failed ("+r.status+")");
  return body as T;
 }
 async function refreshAppointments(){try{setAppointments(await api<Appointment[]>("/patients/"+PATIENT+"/appointments"))}catch(e){setError(e instanceof Error?e.message:"Could not load appointments.")}}
 async function refreshSlots(id=doctorId,date=day){try{setSlots(await api<Slot[]>("/doctors/"+id+"/availability?date="+dateKey(date)))}catch(e){setError(e instanceof Error?e.message:"Could not load availability.")}}
 useEffect(()=>{api<Doctor[]>("/doctors").then(ds=>{setDoctors(ds);if(ds.length)setDoctorId(ds[0].id)}).catch(e=>setError(e instanceof Error?e.message:"API unavailable. Start the backend and retry.")).finally(()=>setLoading(false));void refreshAppointments()},[]);
 useEffect(()=>{if(doctorId){setSelected(null);void refreshSlots(doctorId,day)}},[doctorId,day]);
 async function book(){if(!selected)return;setBusy(true);setError("");setNotice("");try{await api("/appointments",{method:"POST",body:JSON.stringify({doctor_id:doctorId,patient_id:PATIENT,starts_at:selected.starts_at})});setNotice("Appointment confirmed.");setSelected(null);await Promise.all([refreshAppointments(),refreshSlots()])}catch(e){setError(e instanceof Error?e.message:"Booking failed.")}finally{setBusy(false)}}
 async function cancel(){if(cancelId===null)return;setBusy(true);setError("");try{await api("/appointments/"+cancelId+"/cancel",{method:"PATCH",body:JSON.stringify({reason})});setCancelId(null);setNotice("Appointment cancelled. Its slot is available again.");await Promise.all([refreshAppointments(),refreshSlots()])}catch(e){setError(e instanceof Error?e.message:"Cancellation failed.")}finally{setBusy(false)}}
 async function reschedule(a:Appointment){if(!selected)return;setBusy(true);setError("");try{await api("/appointments/"+a.id+"/reschedule",{method:"PATCH",body:JSON.stringify({starts_at:selected.starts_at})});setNotice("Appointment rescheduled.");setSelected(null);await Promise.all([refreshAppointments(),refreshSlots()])}catch(e){setError(e instanceof Error?e.message:"Rescheduling failed.")}finally{setBusy(false)}}
 return <div className="shell"><header className="topbar"><a className="brand" href="#"><span className="brand-icon"><HeartPulse/></span><span>Care<span>slot</span><small>CLINIC APPOINTMENTS</small></span></a><div className="secure"><ShieldCheck size={15}/> Secure scheduling <b>AS</b></div></header>
 <main className="page"><section className="intro"><div><label>PATIENT PORTAL</label><h1>Make time for<br/><em>your health.</em></h1><p>Choose a clinician, find a time that works for you, and keep your appointments in one clear place.</p></div><div className="intro-mark"><HeartPulse size={58}/></div></section>
 {error&&<div className="alert error" role="alert"><X size={16}/><span>{error}</span><button onClick={()=>{setError("");void refreshSlots();void refreshAppointments()}}>Retry</button></div>}{notice&&<div className="alert success" role="status"><Check size={16}/><span>{notice}</span><button onClick={()=>setNotice("")}>Dismiss</button></div>}
 <div className="layout"><section className="card booking"><div className="card-head"><div><small>01 / BOOK A VISIT</small><h2>Find your appointment</h2></div><CalendarDays/></div>
 <label htmlFor="doctor">Choose a clinician</label><select id="doctor" value={doctorId} disabled={loading||!doctors.length} onChange={e=>setDoctorId(Number(e.target.value))}>{doctors.map(d=><option key={d.id} value={d.id}>{d.name} · {d.specialty}</option>)}</select>
 <div className="doctor-line"><span><Stethoscope size={19}/></span><div><strong>{doctors.find(d=>d.id===doctorId)?.name??"Loading clinicians"}</strong><small>{doctors.find(d=>d.id===doctorId)?.specialty??"Please wait"}</small></div><b>Weekdays</b></div>
 <div className="date-row"><div><label>Select a date</label><strong>{day.toLocaleDateString([],{weekday:"short",month:"short",day:"numeric"})}</strong></div><div><button aria-label="Previous day" onClick={()=>{const d=new Date(day);d.setDate(d.getDate()-1);setDay(d)}}>‹</button><button aria-label="Next day" onClick={()=>{const d=new Date(day);d.setDate(d.getDate()+1);setDay(d)}}>›</button></div></div>
 <div className="slot-title"><label>Available times</label><span><Clock3 size={13}/> 30-minute visits</span></div>
 {slots.length?<div className="slots">{slots.map(s=><button key={s.starts_at} className={selected?.starts_at===s.starts_at?"slot active":"slot"} onClick={()=>setSelected(s)}>{timeLabel(s.starts_at)}</button>)}</div>:<div className="empty"><CalendarDays size={24}/><strong>No times available</strong><span>Try another date or clinician.</span></div>}
 <div className="book-footer"><span><ShieldCheck size={15}/> Confirmed after booking</span><button className="primary" disabled={!selected||busy} onClick={()=>void book()}>{busy?<LoaderCircle className="spin"/>:<Check size={15}/>} Confirm booking</button></div></section>
 <aside className="side"><section className="card visits"><div className="card-head"><div><small>YOUR VISITS</small><h2>Upcoming appointments</h2></div><CalendarDays/></div>
 {appointments.length?appointments.map(a=><article className="visit" key={a.id}><div className="date-badge"><strong>{new Date(a.starts_at).getDate()}</strong><span>{new Date(a.starts_at).toLocaleDateString([],{month:"short"})}</span></div><div className="visit-info"><strong>{doctors.find(d=>d.id===a.doctor_id)?.name??"Doctor #"+a.doctor_id}</strong><small>{new Date(a.starts_at).toLocaleDateString([],{weekday:"short",month:"short",day:"numeric"})} · {timeLabel(a.starts_at)}</small><div className="actions"><button onClick={()=>{setDoctorId(a.doctor_id);setDay(new Date(a.starts_at));setNotice("Select a new slot, then choose Reschedule below.")}}>Find new time</button><button className="cancel-link" onClick={()=>setCancelId(a.id)}>Cancel</button></div>{selected&&doctorId===a.doctor_id&&<button className="reschedule" disabled={busy} onClick={()=>void reschedule(a)}>Reschedule to {timeLabel(selected.starts_at)}</button>}</div></article>):<div className="empty visit-empty"><CalendarDays size={23}/><strong>No upcoming visits</strong><span>Your confirmed appointments appear here.</span></div>}
 <button className="refresh" onClick={()=>{void refreshAppointments();void refreshSlots()}}>Refresh appointments →</button></section>
 <section className="note"><ShieldCheck/><div><strong>Designed around your time</strong><p>Appointments last 30 minutes. A slot is yours once booking is confirmed.</p></div></section>
 <section className="card hours"><strong><Clock3 size={15}/> Clinic hours</strong><p><span>Monday – Friday</span><b>9:00 AM – 5:00 PM</b></p><p><span>Appointment length</span><b>30 minutes</b></p></section></aside></div>
 <footer><strong>CARESLOT / CLINIC BOOKING DEMO</strong><span>Thoughtful care starts with a clear schedule.</span></footer></main>
 {cancelId!==null&&<div className="overlay"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="cancel-heading"><div className="modal-x"><X/></div><h2 id="cancel-heading">Cancel this appointment?</h2><p>This releases the time for another patient. Please provide a short reason.</p><label htmlFor="reason">Cancellation reason</label><textarea id="reason" value={reason} onChange={e=>setReason(e.target.value)} minLength={3} maxLength={500}/><div><button onClick={()=>setCancelId(null)}>Keep appointment</button><button className="danger" disabled={busy||reason.trim().length<3} onClick={()=>void cancel()}>{busy?"Cancelling…":"Confirm cancellation"}</button></div></section></div>}</div>
}
