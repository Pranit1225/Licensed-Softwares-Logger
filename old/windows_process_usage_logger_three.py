"""
Windows Process Usage Logger - Version 1
Tracks process lifetime using Windows Security events:
4688 = process creation, 4689 = process termination.

Current test target: notepad.exe
Supports:
  --evtx  : historical saved EVTX parsing
  --live  : continuous Windows Security log monitoring
  both    : historical import, then live monitoring

Run as Administrator for live Security-log access.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

APP_NAME = "Notepad"
TARGET_EXE = "notepad.exe"
DEFAULT_CSV = Path("usage_log.csv")
DEFAULT_STATE = Path("usage_logger_state.json")

CSV_FIELDS = [
    "Start_EventRecordID", "End_EventRecordID", "User", "Computer",
    "Application", "Executable_Path", "Process_ID", "Start_Time_UTC",
    "End_Time_UTC", "Duration_Seconds", "Duration", "Logon_ID",
    "Parent_Process", "Exit_Status"
]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_event_xml(xml_text: str) -> Optional[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    system = {}
    data = {}

    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag == "EventID":
            system["event_id"] = int(elem.text or "0")
        elif tag == "EventRecordID":
            system["record_id"] = int(elem.text or "0")
        elif tag == "Computer":
            system["computer"] = elem.text or ""
        elif tag == "TimeCreated":
            system["system_time"] = elem.attrib.get("SystemTime", "")
        elif tag == "Data":
            name = elem.attrib.get("Name")
            if name:
                data[name] = elem.text or ""

    if system.get("event_id") not in (4688, 4689):
        return None

    return {
        "event_id": system["event_id"],
        "record_id": system.get("record_id", 0),
        "computer": system.get("computer", ""),
        "system_time": system.get("system_time", ""),
        "data": data,
    }


def is_target_start(event: dict) -> bool:
    return (
        event["event_id"] == 4688
        and event["data"].get("NewProcessName", "").lower().endswith(TARGET_EXE)
    )


def is_target_end(event: dict) -> bool:
    return (
        event["event_id"] == 4689
        and event["data"].get("ProcessName", "").lower().endswith(TARGET_EXE)
    )


def parse_utc(value: str):
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_duration(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"pending": {}, "completed_end_record_ids": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"pending": {}, "completed_end_record_ids": []}


def save_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_csv(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def append_session(path: Path, row: dict) -> None:
    ensure_csv(path)
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)
        f.flush()
        os.fsync(f.fileno())


def pending_key(user: str, logon_id: str, pid: str) -> str:
    return f"{user}|{logon_id}|{pid}"


def process_event(event: dict, state: dict, csv_path: Path) -> None:
    d = event["data"]
    user = d.get("SubjectUserName", "")
    logon_id = d.get("SubjectLogonId", "")
    pid = d.get("NewProcessId" if event["event_id"] == 4688 else "ProcessId", "")
    exe = d.get("NewProcessName" if event["event_id"] == 4688 else "ProcessName", "")
    key = pending_key(user, logon_id, pid)

    if event["event_id"] == 4688 and is_target_start(event):
        state["pending"][key] = {
            "start_record_id": event["record_id"],
            "user": user,
            "computer": event["computer"],
            "application": APP_NAME,
            "executable_path": exe,
            "process_id": pid,
            "start_time": event["system_time"],
            "logon_id": logon_id,
            "parent_process": d.get("ParentProcessName", ""),
        }
        print(f"[START] {APP_NAME} | PID {pid} | {user} | {event['system_time']}")

    elif event["event_id"] == 4689 and is_target_end(event):
        if event["record_id"] in set(state.get("completed_end_record_ids", [])):
            return

        start = state["pending"].get(key)
        if not start:
            print(f"[END WITHOUT MATCH] {APP_NAME} | PID {pid}")
            return

        start_dt = parse_utc(start["start_time"])
        end_dt = parse_utc(event["system_time"])
        duration = (end_dt - start_dt).total_seconds()

        row = {
            "Start_EventRecordID": start["start_record_id"],
            "End_EventRecordID": event["record_id"],
            "User": start["user"],
            "Computer": start["computer"] or event["computer"],
            "Application": start["application"],
            "Executable_Path": start["executable_path"],
            "Process_ID": start["process_id"],
            "Start_Time_UTC": start["start_time"],
            "End_Time_UTC": event["system_time"],
            "Duration_Seconds": f"{duration:.3f}",
            "Duration": format_duration(duration),
            "Logon_ID": start["logon_id"],
            "Parent_Process": start["parent_process"],
            "Exit_Status": d.get("Status", ""),
        }

        append_session(csv_path, row)
        state["completed_end_record_ids"].append(event["record_id"])
        state["completed_end_record_ids"] = state["completed_end_record_ids"][-5000:]
        del state["pending"][key]

        print(
            f"[SESSION] {row['Application']} | {row['User']} | "
            f"{row['Start_Time_UTC']} -> {row['End_Time_UTC']} | {row['Duration']}"
        )


def iter_evtx(path: Path):
    try:
        from Evtx.Evtx import Evtx
    except ImportError:
        raise RuntimeError(
            "Install EVTX support with: py -m pip install python-evtx"
        )

    with Evtx(str(path)) as log:
        for record in log.records():
            event = parse_event_xml(record.xml())
            if event:
                yield event


def run_evtx(path: Path, state_path: Path, csv_path: Path) -> None:
    state = load_state(state_path)
    ensure_csv(csv_path)
    count = 0

    for event in iter_evtx(path):
        if event["event_id"] in (4688, 4689):
            process_event(event, state, csv_path)
            count += 1

    save_state(state_path, state)
    print(f"\nHistorical scan complete. Relevant events processed: {count}")
    print(f"CSV:   {csv_path.resolve()}")
    print(f"State: {state_path.resolve()}")


def run_live(state_path: Path, csv_path: Path, poll_seconds: float = 1.0) -> None:
    try:
        import win32evtlog
    except ImportError:
        raise RuntimeError(
            "Install Windows Event Log support with: py -m pip install pywin32"
        )

    state = load_state(state_path)
    ensure_csv(csv_path)

    # Start after the current latest Security record.
    query = "*[System[(EventID=4688 or EventID=4689)]]"
    try:
        handle = win32evtlog.EvtQuery(
            "Security",
            win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryReverseDirection,
            query,
        )
        handles = win32evtlog.EvtNext(handle, 1)
        if handles:
            xml_text = win32evtlog.EvtRender(
                handles[0], win32evtlog.EvtRenderEventXml
            )
            latest = parse_event_xml(xml_text)
            last_record = latest["record_id"] if latest else 0
        else:
            last_record = 0
    except Exception as exc:
        raise RuntimeError(
            "Cannot read the Windows Security log. Run the terminal as Administrator."
        ) from exc

    print("LIVE MODE")
    print(f"Watching after EventRecordID {last_record}")
    print(f"Target: {TARGET_EXE}")
    print(f"CSV: {csv_path.resolve()}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            query = (
                "*[System[(EventRecordID > "
                f"{last_record}) and (EventID=4688 or EventID=4689)]]"
            )
            handle = win32evtlog.EvtQuery(
                "Security", win32evtlog.EvtQueryChannelPath, query
            )

            while True:
                handles = win32evtlog.EvtNext(handle, 64)
                if not handles:
                    break

                for event_handle in handles:
                    xml_text = win32evtlog.EvtRender(
                        event_handle, win32evtlog.EvtRenderEventXml
                    )
                    event = parse_event_xml(xml_text)
                    if event:
                        last_record = max(last_record, event["record_id"])
                        process_event(event, state, csv_path)

            save_state(state_path, state)
            time.sleep(poll_seconds)

        except KeyboardInterrupt:
            save_state(state_path, state)
            print("\nStopped. State saved.")
            return
        except Exception as exc:
            print(f"[WARN] {exc}")
            time.sleep(max(poll_seconds, 2))


def main():
    parser = argparse.ArgumentParser(
        description="Windows process usage logger; current target is notepad.exe."
    )
    parser.add_argument("--evtx", type=Path, help="Saved EVTX file for historical testing.")
    parser.add_argument("--live", action="store_true", help="Monitor new Security events.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()

    if not args.evtx and not args.live:
        parser.error("Use --evtx, --live, or both.")

    if args.evtx:
        if not args.evtx.exists():
            parser.error(f"EVTX not found: {args.evtx}")
        run_evtx(args.evtx, args.state, args.csv)

    if args.live:
        run_live(args.state, args.csv)


if __name__ == "__main__":
    main()
