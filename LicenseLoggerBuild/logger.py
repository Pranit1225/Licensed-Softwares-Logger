import csv, json, logging, logging.handlers, os, shutil, sys, time, xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import win32evtlog

BASE = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent)
CONFIG = BASE / "tracked_apps.json"
LOGGER_CONFIG = BASE / "logger_config.json"
STATE = BASE / "usage_logger_state.json"
STATE_BACKUP = BASE / "usage_logger_state.backup.json"
OUT = BASE / "License_Usage"
LOG_DIR = BASE / "Logger_Logs"
LOG_FILE = LOG_DIR / "logger.log"
POLL = 1.0
SAVE_EVERY_BATCH = True
logger = logging.getLogger("LicenseLogger")

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

def setup_logging():
    global LOG_DIR, LOG_FILE
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)

def log_exception(message):
    logger.exception(message)

def load_logger_config():
    global OUT, POLL
    if not LOGGER_CONFIG.exists():
        LOGGER_CONFIG.write_text(
            json.dumps({
                "output_folder": str(BASE / "License_Usage"),
                "poll_interval": 1.0
            }, indent=4),
            encoding="utf-8"
        )
        return

    try:
        data = json.loads(LOGGER_CONFIG.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("logger_config.json must contain a JSON object.")

        output_folder = data.get("output_folder")
        if output_folder:
            OUT = Path(os.path.expandvars(os.path.expanduser(str(output_folder))))
            if not OUT.is_absolute():
                OUT = BASE / OUT

        poll_interval = data.get("poll_interval")
        if poll_interval is not None:
            POLL = max(0.1, float(poll_interval))
    except Exception as ex:
        raise RuntimeError(f"Invalid {LOGGER_CONFIG}: {ex}") from ex

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

def empty_state():
    return {"pending":{},"completed":[],"last_event_record_id":0}

def valid_state(st):
    return (
        isinstance(st, dict)
        and isinstance(st.get("pending", {}), dict)
        and isinstance(st.get("completed", []), list)
        and isinstance(st.get("last_event_record_id", 0), int)
    )

def normalize_state(st):
    if not isinstance(st, dict):
        return empty_state()
    st.setdefault("pending", {})
    st.setdefault("completed", [])
    st.setdefault("last_event_record_id", 0)
    return st if valid_state(st) else empty_state()

def load_state():
    candidates = [STATE, STATE_BACKUP]
    for path in candidates:
        if not path.exists():
            continue
        try:
            st = json.loads(path.read_text(encoding="utf-8"))
            if valid_state(normalize_state(st)):
                return normalize_state(st)
        except Exception:
            pass
    return empty_state()

def save_state(st):
    st = normalize_state(st)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    if STATE.exists():
        try:
            shutil.copy2(STATE, STATE_BACKUP)
        except OSError:
            pass
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

def session_exists(app, end_rid):
    p = session_file(app)
    if not p.exists():
        return False
    try:
        with p.open("r", newline="", encoding="utf-8-sig") as f:
            return any(r.get("End_EventRecordID") == str(end_rid) for r in csv.DictReader(f))
    except (OSError, csv.Error):
        return False

def append_session(app,row):
    ensure_session(app)
    if session_exists(app, row["End_EventRecordID"]):
        return False
    with session_file(app).open("a",newline="",encoding="utf-8-sig") as f:
        csv.DictWriter(f,fieldnames=SESSION_FIELDS).writerow(row)
        f.flush(); os.fsync(f.fileno())
    return True

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
    else:
        if e["rid"] in st["completed"]: return
        start=st["pending"].get(key)
        if not start:
            logger.warning("END WITHOUT MATCH | %s | %s | PID %s", app, user, pid); return
        seconds=(utc(e["time"])-utc(start["time"])).total_seconds()
        row={"Start_EventRecordID":start["rid"],"End_EventRecordID":e["rid"],
            "User":start["user"],"Computer":start["computer"] or e["computer"],
            "Application":start["app"],"Executable_Path":start["exe"],
            "Process_ID":start["pid"],"Start_Time_IST":ist(start["time"]),
            "End_Time_IST":ist(e["time"]),"Duration_Seconds":f"{seconds:.3f}",
            "Duration":dur(seconds),"Logon_ID":start["logon"],
            "Parent_Process":start["parent"]}
        written = append_session(app,row)
        if written:
            rebuild_summary(app)
        st["completed"].append(e["rid"])
        st["completed"] = st["completed"][-5000:]
        del st["pending"][key]
def latest():
    h=win32evtlog.EvtQuery("Security",win32evtlog.EvtQueryChannelPath|win32evtlog.EvtQueryReverseDirection,
        "*[System[(EventID=4688 or EventID=4689)]]")
    hs=win32evtlog.EvtNext(h,1)
    if not hs:return 0
    e=parse(win32evtlog.EvtRender(hs[0],win32evtlog.EvtRenderEventXml))
    return e["rid"] if e else 0

def main():
    setup_logging()
    try:
        load_logger_config()
        apps = load_apps()
        st = load_state()
        OUT.mkdir(parents=True, exist_ok=True)
        for app in dict.fromkeys(apps.values()):
            ensure_session(app)

        try:
            latest_rid = latest()
        except Exception as ex:
            raise RuntimeError(
                "Unable to access the Windows Security event log. Run with appropriate permissions."
            ) from ex

        last = st.get("last_event_record_id", 0)
        if last <= 0:
            last = latest_rid
            st["last_event_record_id"] = last
            save_state(st)

        logger.info("Logger started | Tracking: %s", ", ".join(dict.fromkeys(apps.values())))
        logger.info("Resuming after EventRecordID: %s", last)
        logger.info("Output: %s | Summary period: calendar month", OUT)

        while True:
            try:
                q = f"*[System[(EventRecordID > {last}) and (EventID=4688 or EventID=4689)]]"
                h = win32evtlog.EvtQuery("Security", win32evtlog.EvtQueryChannelPath, q)
                batch_processed = False
                while True:
                    hs = win32evtlog.EvtNext(h, 64)
                    if not hs:
                        break
                    for x in hs:
                        e = parse(win32evtlog.EvtRender(x, win32evtlog.EvtRenderEventXml))
                        if e:
                            handle(e, st, apps)
                            last = max(last, e["rid"])
                            st["last_event_record_id"] = last
                            batch_processed = True
                    if SAVE_EVERY_BATCH and batch_processed:
                        save_state(st)
                        batch_processed = False

                save_state(st)
                time.sleep(POLL)

            except KeyboardInterrupt:
                save_state(st)
                logger.info("Logger stopped by user")
                return
            except Exception as ex:
                save_state(st)
                logger.error("Runtime error: %s", ex, exc_info=True)
                time.sleep(2)

    except Exception as ex:
        logger.error("Startup failure: %s", ex, exc_info=True)
        return


if __name__ == "__main__":
    main()
