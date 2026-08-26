import csv, json, os, time, xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import win32evtlog

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "tracked_apps.json"
STATE = BASE / "usage_logger_state.json"
OUT = BASE / "License_Usage"
POLL = 1.0

SESSION_FIELDS = [
    "Start_EventRecordID","End_EventRecordID","User","Computer","Application",
    "Executable_Path","Process_ID","Start_Time_IST","End_Time_IST",
    "Duration_Seconds","Duration","Logon_ID","Parent_Process"
]
SUMMARY_FIELDS = [
    "Month",
    "User",
    "Computer",
    "Application",
    "Sessions",
    "Total_Usage",
    "First_Usage_IST",
    "Last_Usage_IST"
]

def load_apps():
    if not CONFIG.exists():
        raise RuntimeError(f"Missing {CONFIG}. Create it before running.")
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    return {str(k).lower(): str(v) for k,v in data.items()}

def lname(tag): return tag.rsplit("}",1)[-1]

def parse(xml):
    root=ET.fromstring(xml); s={}; d={}
    for e in root.iter():
        t=lname(e.tag)
        if t=="EventID": s["id"]=int(e.text or 0)
        elif t=="EventRecordID": s["rid"]=int(e.text or 0)
        elif t=="Computer": s["computer"]=e.text or ""
        elif t=="TimeCreated": s["time"]=e.attrib.get("SystemTime","")
        elif t=="Data" and e.attrib.get("Name"): d[e.attrib["Name"]]=e.text or ""
    if s.get("id") not in (4688,4689): return None
    return {"id":s["id"],"rid":s.get("rid",0),"computer":s.get("computer",""),
            "time":s.get("time",""),"d":d}

def utc(v): return datetime.fromisoformat(v.replace("Z","+00:00"))

def ist(v):
    x=utc(v).astimezone(timezone(timedelta(hours=5,minutes=30)))
    return x.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def dur(sec):
    whole=int(sec); ms=int(round((sec-whole)*1000))
    if ms==1000: whole+=1; ms=0
    h,r=divmod(whole,3600); m,s=divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def load_state():
    if not STATE.exists(): return {"pending":{},"completed":[]}
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except: return {"pending":{},"completed":[]}

def save_state(st):
    tmp=STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st,indent=2),encoding="utf-8")
    tmp.replace(STATE)

def safe(s): return "".join("_" if c in '<>:"/\\|?*' else c for c in s)

def session_file(app):
    p=OUT/safe(app); p.mkdir(parents=True,exist_ok=True)
    return p/f"{safe(app)}_Sessions.csv"

def summary_file(app):
    p=OUT/safe(app); p.mkdir(parents=True,exist_ok=True)
    return p/f"{safe(app)}_Monthly_Summary.csv"

def ensure_session(app):
    p=session_file(app)
    if not p.exists() or p.stat().st_size==0:
        with p.open("w",newline="",encoding="utf-8-sig") as f:
            csv.DictWriter(f,fieldnames=SESSION_FIELDS).writeheader()

def append_session(app,row):
    ensure_session(app)
    with session_file(app).open("a",newline="",encoding="utf-8-sig") as f:
        csv.DictWriter(f,fieldnames=SESSION_FIELDS).writerow(row)
        f.flush(); os.fsync(f.fileno())

def rebuild_summary(app):
    # Rebuild the summary using calendar months.
    # Raw session history is never deleted.
    # Each User + Computer + Application gets one row per calendar month
    # in which that application has recorded usage.
    src = session_file(app)
    dst = summary_file(app)
    if not src.exists():
        return

    groups = defaultdict(
        lambda: {"n": 0, "sec": 0.0, "first": None, "last": None}
    )

    with src.open("r", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                st = datetime.strptime(
                    r["Start_Time_IST"],
                    "%Y-%m-%d %H:%M:%S.%f"
                ).replace(
                    tzinfo=timezone(timedelta(hours=5, minutes=30))
                )

                en = datetime.strptime(
                    r["End_Time_IST"],
                    "%Y-%m-%d %H:%M:%S.%f"
                ).replace(
                    tzinfo=timezone(timedelta(hours=5, minutes=30))
                )

                # Calendar month is determined from the session start date.
                month = st.strftime("%Y-%m")
                key = (
                    month,
                    r["User"],
                    r["Computer"],
                    r["Application"]
                )

                g = groups[key]
                g["n"] += 1
                g["sec"] += float(r["Duration_Seconds"])

                if g["first"] is None or st < g["first"]:
                    g["first"] = st

                if g["last"] is None or en > g["last"]:
                    g["last"] = en

            except (KeyError, ValueError):
                pass

    with dst.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()

        for (month, user, computer, app_name), g in sorted(groups.items()):
            w.writerow({
                "Month": month,
                "User": user,
                "Computer": computer,
                "Application": app_name,
                "Sessions": g["n"],
                "Total_Usage": dur(g["sec"]),
                "First_Usage_IST": (
                    g["first"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                ),
                "Last_Usage_IST": (
                    g["last"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                )
            })

def handle(e,st,apps):
    d=e["d"]; user=d.get("SubjectUserName",""); logon=d.get("SubjectLogonId","")
    pid=d.get("NewProcessId" if e["id"]==4688 else "ProcessId","")
    exe=d.get("NewProcessName" if e["id"]==4688 else "ProcessName","")
    app=apps.get(Path(exe).name.lower())
    if not app: return
    key=f"{user}|{logon}|{pid}"
    if e["id"]==4688:
        st["pending"][key]={"rid":e["rid"],"user":user,"computer":e["computer"],
            "app":app,"exe":exe,"pid":pid,"time":e["time"],"logon":logon,
            "parent":d.get("ParentProcessName","")}
        print(f"[START] {app} | {user} | PID {pid} | {ist(e['time'])} IST")
    else:
        if e["rid"] in st["completed"]: return
        start=st["pending"].get(key)
        if not start:
            print(f"[END WITHOUT MATCH] {app} | {user} | PID {pid}"); return
        seconds=(utc(e["time"])-utc(start["time"])).total_seconds()
        row={"Start_EventRecordID":start["rid"],"End_EventRecordID":e["rid"],
            "User":start["user"],"Computer":start["computer"] or e["computer"],
            "Application":start["app"],"Executable_Path":start["exe"],
            "Process_ID":start["pid"],"Start_Time_IST":ist(start["time"]),
            "End_Time_IST":ist(e["time"]),"Duration_Seconds":f"{seconds:.3f}",
            "Duration":dur(seconds),"Logon_ID":start["logon"],
            "Parent_Process":start["parent"]}
        append_session(app,row); rebuild_summary(app)
        st["completed"].append(e["rid"]); st["completed"]=st["completed"][-5000:]
        del st["pending"][key]
        print(f"[SESSION] {app} | {row['User']} | {row['Start_Time_IST']} -> {row['End_Time_IST']} IST | {row['Duration']}")

def latest():
    h=win32evtlog.EvtQuery("Security",win32evtlog.EvtQueryChannelPath|win32evtlog.EvtQueryReverseDirection,
        "*[System[(EventID=4688 or EventID=4689)]]")
    hs=win32evtlog.EvtNext(h,1)
    if not hs:return 0
    e=parse(win32evtlog.EvtRender(hs[0],win32evtlog.EvtRenderEventXml))
    return e["rid"] if e else 0

def main():
    apps=load_apps(); st=load_state(); OUT.mkdir(exist_ok=True)
    for app in dict.fromkeys(apps.values()): ensure_session(app)
    try: last=latest()
    except Exception as ex: raise RuntimeError("Run this program from an Administrator terminal.") from ex
    print("LIVE LOGGER V2 | Tracking:",", ".join(dict.fromkeys(apps.values())))
    print("Starting after EventRecordID:",last)
    print("Output:",OUT); print("Summary period: calendar month"); print("Ctrl+C to stop.")
    while True:
        try:
            q=f"*[System[(EventRecordID > {last}) and (EventID=4688 or EventID=4689)]]"
            h=win32evtlog.EvtQuery("Security",win32evtlog.EvtQueryChannelPath,q)
            while True:
                hs=win32evtlog.EvtNext(h,64)
                if not hs: break
                for x in hs:
                    e=parse(win32evtlog.EvtRender(x,win32evtlog.EvtRenderEventXml))
                    if e: last=max(last,e["rid"]); handle(e,st,apps)
            save_state(st); time.sleep(POLL)
        except KeyboardInterrupt:
            save_state(st); print("Stopped."); return
        except Exception as ex:
            print("[WARNING]",ex); time.sleep(2)

if __name__=="__main__": main()