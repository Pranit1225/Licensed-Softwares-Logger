<div align="center">

# 🛡️ License Usage Logger

### Windows process-based utilization monitoring for proprietary software licenses

<p>
<img src="https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
<img src="https://img.shields.io/badge/Language-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Events-4688%20%2F%204689-6F42C1?style=for-the-badge" alt="Windows Events">
<img src="https://img.shields.io/badge/Status-Deployment%20Validation-198754?style=for-the-badge" alt="Status">
</p>

**A lightweight Windows logger that records selected application process sessions, calculates runtime, stores per-application CSV history, and generates calendar-month summaries.**

</div>

---

## 📌 1. Project Overview

Organizations often purchase expensive proprietary engineering applications and assign licenses to individual users. A license can become under-utilized when the assigned user rarely or never launches the application.

This project provides a practical Windows-based mechanism for collecting **application process-utilization data** for selected software such as:

- AutoCAD
- Creo
- CADSTAR
- Dassault products (exact product/process to be confirmed)

The logger uses Windows Security auditing rather than application-specific monitoring. It detects when a tracked executable is created and when it terminates, then calculates the process runtime.

### Example

```text
User:        Employee01
Computer:    DESIGN-PC-01
Application: AutoCAD
Start:       2026-09-08 10:15:21.125 IST
End:         2026-09-08 11:42:10.541 IST
Duration:    01:26:49.416
```

The resulting information helps administrators identify applications/users with low or high process utilization and can support later license-allocation decisions.

> **Scope:** This project measures **process lifetime**. It does not measure whether the employee was actively working inside the application.

---

# ⚙️ 2. How the Logger Works

```text
                 WINDOWS
                    │
                    ▼
          Windows Security Log
                    │
             ┌──────┴──────┐
             │             │
            4688          4689
          PROCESS START  PROCESS END
             │             │
             └──────┬──────┘
                    ▼
             License Logger
                    │
                    ▼
          tracked_apps.json
                    │
              Is it tracked?
                /        \
              NO          YES
              │            │
            Ignore         ▼
                    Match START + END
                           │
                           ▼
                    Calculate Duration
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       Session CSV               Monthly Summary
```

The two Windows event IDs used by the logger are:

| Event ID | Meaning               |
| -------- | --------------------- |
| **4688** | A process was created |
| **4689** | A process terminated  |

The logger does not continuously scan every running application. It waits for new relevant Security events, filters for configured executables, and processes only those events.

---

# 🎯 3. What Problem Does It Solve?

Example business scenario:

> A company owns 50 AutoCAD licenses, but some assigned users barely use AutoCAD.

Without utilization data, IT may not know which licenses are genuinely being used.

With this logger, an administrator can review:

- which users launched the application
- which computers ran it
- number of recorded sessions
- total runtime per calendar month
- first and last recorded usage in a month
- users with little or no recorded process usage

The project therefore turns Windows process events into administrator-readable usage data.

---

# 🧠 4. What Exactly Is Being Measured?

This project measures **process lifetime**.

If:

```text
acad.exe
START → 10:00
END   → 12:00
```

the recorded process runtime is:

```text
2 hours
```

This does **not** mathematically prove that the employee actively worked for two hours.

The logger does not intentionally track:

- keyboard activity
- mouse activity
- screen activity
- screenshots
- foreground-window focus
- files edited
- commands performed inside the application

The current scope is deliberately limited to **process tracking**.

---

# ✨ 5. Main Features

### ✅ Windows process monitoring

Uses Security Event IDs 4688 and 4689.

### ✅ Configurable application tracking

Applications are defined externally through `tracked_apps.json`.

### ✅ Executable-name based identification

The logger extracts the executable filename from the Windows event.

Example:

```text
C:\Program Files\Autodesk\AutoCAD 2026\acad.exe
                              ↓
                          acad.exe
```

The executable name is then matched against `tracked_apps.json`.

### ✅ Per-application separation

Each tracked application gets its own output folder.

```text
License_Usage/
├── AutoCAD/
├── Creo/
├── CADSTAR/
└── Dassault/
```

### ✅ Session history

Every completed tracked process session becomes one row in the relevant session CSV.

### ✅ Calendar-month summaries

Summary data is grouped by:

```text
Month + User + Computer + Application
```

Example:

```text
2026-01
2026-02
2026-03
...
2026-12
```

### ✅ State/restart handling

Runtime state helps preserve pending process information across logger restarts.

### ✅ Duplicate protection

Previously processed termination records are tracked to reduce duplicate session rows.

### ✅ Configurable output directory

The output location can be configured without editing the logger's main source code.

### ✅ Background deployment

The EXE can be configured to start automatically at Windows startup using Task Scheduler.

### ✅ Silent operation

The deployment EXE is designed to run without a visible terminal window.

### ✅ Diagnostic logging

Troubleshooting information can be stored separately from the usage CSVs.

### ✅ Lightweight design

The logger waits for new relevant Windows events instead of continuously performing heavy process scans.

---

# 📁 6. Repository Structure

The repository separates **development/build** files from the **ready-to-deploy** package.

Recommended structure:

```text
Process_Logger/
│
├── README.md
├── .gitignore
│
├── PACKAGE/
│   │
│   ├── 01_Source_and_Build/
│   │   ├── logger.py
│   │   ├── tracked_apps.json
│   │   ├── logger_config.json
│   │   ├── requirements.txt
│   │   └── build_release.bat
│   │
│   └── 02_Ready_to_Deploy/
│       ├── LicenseLogger.exe
│       ├── tracked_apps.json
│       ├── logger_config.json
│       ├── install_license_logger_task.bat
│       └── uninstall_license_logger_task.bat
│
└── docs/
    ├── deployment/
    ├── testing/
    └── reports/
```

> Runtime-generated files such as CSVs, diagnostic logs, state files, test EVTX files, cache folders, and build output should not be distributed in the ready-to-deploy package.

---

# 👨‍💻 7. `01_Source_and_Build`

Use this folder when you want to modify the project or create a new release.

| File                 | Purpose                          |
| -------------------- | -------------------------------- |
| `logger.py`          | Main logger source code          |
| `tracked_apps.json`  | Executable → application mapping |
| `logger_config.json` | Output/polling configuration     |
| `requirements.txt`   | Development/build dependencies   |
| `build_release.bat`  | Windows EXE build script         |

## Development setup

Install Python on the development machine, then:

```powershell
python -m pip install -r requirements.txt
```

Run the Python source during development:

```powershell
python logger.py
```

Build the Windows executable with:

```powershell
build_release.bat
```

The resulting EXE is intended for the ready-to-deploy package.

---

# 📦 8. `02_Ready_to_Deploy`

This folder is for users who simply want to deploy the logger without working on the source code.

The package should contain:

```text
LicenseLogger.exe
tracked_apps.json
logger_config.json
install_license_logger_task.bat
uninstall_license_logger_task.bat
```

No separate Python installation is required for normal use of the packaged EXE.

## Basic deployment

1. Copy the entire ready-to-deploy folder to the Windows PC.
2. Keep the included files together.
3. Configure `tracked_apps.json` if required.
4. Configure `logger_config.json` if required.
5. Confirm Windows process auditing is enabled.
6. Run `install_license_logger_task.bat` as Administrator.
7. Verify that `LicenseLogger.exe` is running.
8. Test a tracked application.

---

# 🛠️ 9. Windows Audit Policy Requirement

The logger depends on Windows Security process-auditing events.

The machine must generate:

```text
4688 → Process Creation
4689 → Process Termination
```

A typical manual configuration path is:

```text
Win + R
    ↓
gpedit.msc
    ↓
Computer Configuration
    ↓
Windows Settings
    ↓
Security Settings
    ↓
Advanced Audit Policy Configuration
    ↓
System Audit Policies
    ↓
Detailed Tracking
```

Enable:

```text
Audit Process Creation → Success
Audit Process Termination → Success
```

Then refresh the policy:

```powershell
gpupdate /force
```

In a managed company environment, the organization can apply the equivalent policy centrally through domain/group policy.

---

# 🔐 10. Security Event Log Permissions

The logger reads the Windows **Security** Event Log.

For development/testing, an elevated Administrator context can be used.

For production deployment, IT should configure the scheduled task/account using the organization's approved security model and permissions.

Only the permissions required by the logger should be granted.

---

# ⚙️ 11. `tracked_apps.json`

This file defines which executable names are tracked.

Example:

```json
{
  "notepad.exe": "Notepad",
  "acad.exe": "AutoCAD",
  "creo.exe": "Creo",
  "cadstar.exe": "CADSTAR"
}
```

### Executable matching

If Windows reports:

```text
C:\Program Files\Autodesk\AutoCAD 2026\acad.exe
```

the logger extracts:

```text
acad.exe
```

and checks for that executable in the configuration file.

The installation directory is therefore not required for the basic executable-name match.

The complete executable path is still retained in session data.

### Important

The executable names above are examples. Verify the actual process names on the organization's installed versions before deployment.

---

# 📍 12. `logger_config.json`

This file keeps deployment-specific settings outside the Python source.

Example:

```json
{
  "output_folder": "License_Usage",
  "poll_interval": 1.0
}
```

## Output folder

Using:

```json
"output_folder": "License_Usage"
```

keeps the current testing behavior: the output folder is created relative to the logger deployment directory.

An absolute Windows path can also be used when required:

```json
{
  "output_folder": "D:\\Company\\LicenseLogs",
  "poll_interval": 1.0
}
```

## Poll interval

```json
"poll_interval": 1.0
```

controls approximately how often the logger checks for newly available relevant events.

`1.0` means approximately one second between checks.

The project currently uses `1.0` during testing.

---

# 📊 13. Runtime Output

Once the logger runs, the required runtime folders/files are created automatically.

Example:

```text
License_Usage/
│
├── AutoCAD/
│   ├── AutoCAD_Sessions.csv
│   └── AutoCAD_Monthly_Summary.csv
│
├── Creo/
│   ├── Creo_Sessions.csv
│   └── Creo_Monthly_Summary.csv
│
├── CADSTAR/
│   ├── CADSTAR_Sessions.csv
│   └── CADSTAR_Monthly_Summary.csv
│
└── Dassault/
    ├── Dassault_Sessions.csv
    └── Dassault_Monthly_Summary.csv
```

Only applications configured in `tracked_apps.json` are intended to produce usage records.

---

# 🧾 14. Session CSV

Every completed tracked process session creates one row.

Current session fields include:

```text
Start_EventRecordID
End_EventRecordID
User
Computer
Application
Executable_Path
Process_ID
Start_Time_IST
End_Time_IST
Duration_Seconds
Duration
Logon_ID
Parent_Process
```

Example:

| User       | Computer     | Application | Start | End   | Duration |
| ---------- | ------------ | ----------- | ----- | ----- | -------: |
| Employee01 | DESIGN-PC-01 | AutoCAD     | 10:15 | 11:42 | 01:26:49 |

New session records are appended to the existing application session file.

---

# 📅 15. Calendar-Month Summary

The summary aggregates sessions by:

```text
Month + User + Computer + Application
```

Example:

| Month   | User       | Application | Sessions | Total Usage |
| ------- | ---------- | ----------- | -------: | ----------: |
| 2026-01 | Employee01 | AutoCAD     |       37 |    18:42:15 |
| 2026-02 | Employee01 | AutoCAD     |       42 |    21:13:07 |
| 2026-03 | Employee01 | AutoCAD     |       31 |    14:52:41 |

The reporting period is a **calendar month**, not a rolling 30-day period.

```text
January   → 1–31
February  → 1–28/29
March     → 1–31
...
December  → 1–31
```

Raw session history is retained; the summary is an aggregation of that history.

---

# ♻️ 16. State / Restart Handling

The logger maintains runtime state for sessions where a tracked process has started but the corresponding termination event has not yet been processed.

Typical runtime files are:

```text
usage_logger_state.json
usage_logger_state.backup.json
```

These are generated runtime files and are not required in the initial ready-to-deploy package.

State handling is intended to support:

- pending START information
- logger restart recovery
- duplicate prevention
- safer continuation after interruption

---

# 🩺 17. Diagnostic / Troubleshooting Log

The diagnostic log is separate from application-usage data.

Typical location:

```text
Logger_Logs/
└── logger.log
```

It is intended for troubleshooting rather than usage analysis.

Useful information includes:

- startup/shutdown information
- configuration errors
- Security Event Log access errors
- state/recovery errors
- file-write errors
- unmatched termination events
- unexpected exceptions

The final background deployment should run without requiring a visible terminal.

---

# 🖥️ 18. Background / Boot-Up Operation

The intended deployment model is:

```text
PC powers on
      ↓
Windows starts
      ↓
Task Scheduler
      ↓
LicenseLogger.exe
      ↓
Silent background operation
      ↓
4688 / 4689 events
      ↓
Usage records
```

The provided installer:

```text
install_license_logger_task.bat
```

is intended to configure automatic startup.

The corresponding:

```text
uninstall_license_logger_task.bat
```

is intended to remove the automatic-start configuration.

---

# 🛑 19. Stopping / Disabling the Logger

For testing, the running EXE can be stopped from Task Manager by ending `LicenseLogger.exe`.

If automatic startup has been installed, disable/remove the Task Scheduler task using the provided uninstall script or the Windows Task Scheduler interface.

Stopping/removing the scheduled task should not be confused with deleting the collected CSV/history files.

---

# 🏢 20. Administrative Retrieval

The initial design does not require a central database.

Each workstation keeps its own usage data:

```text
Employee PC
    ↓
LicenseLogger.exe
    ↓
License_Usage/
    ↓
Administrator retrieves CSVs
```

If the organization already provides an approved remote-access method such as Remote Desktop, an administrator can access the workstation and retrieve the standardized CSV folder directly.

A central database/API may be introduced later if the number of workstations makes manual collection impractical.

---

# 🧪 21. Testing Performed

The prototype has been tested with Notepad for:

- 4688 START detection
- 4689 END detection
- START → END matching
- duration calculation
- multiple sessions
- unrelated processes between tracked events
- live monitoring
- persistent CSV appending
- calendar-month summaries
- logger restart recovery
- pending-session recovery
- duplicate prevention

Resource-impact testing was also performed on a Windows machine while the logger continuously monitored repeated Notepad activity.

Observed prototype measurements were approximately:

```text
Average CPU : 0.26%
Peak CPU    : 1.6%
Average RAM : 16.53 MB
Peak RAM    : 16.95 MB
```

These are prototype measurements from one Windows machine and are not a guarantee for every production environment.

---

# ✅ 22. Company Deployment Validation Checklist

### Windows configuration

- [ ] 4688 auditing enabled
- [ ] 4689 auditing enabled
- [ ] Security Event Log accessible

### Application configuration

- [ ] AutoCAD executable verified
- [ ] Creo executable verified
- [ ] CADSTAR executable verified
- [ ] Dassault product/process confirmed

### Logger

- [ ] Session detection verified
- [ ] Duration verified
- [ ] Session CSV verified
- [ ] Monthly summary verified
- [ ] Restart recovery verified
- [ ] Duplicate protection verified
- [ ] Diagnostic logging verified

### Deployment

- [ ] EXE tested
- [ ] Silent execution verified
- [ ] Task Scheduler startup verified
- [ ] Automatic recovery verified
- [ ] Output directory verified
- [ ] Administrator retrieval procedure verified

### Performance

- [ ] CPU usage acceptable
- [ ] RAM usage acceptable
- [ ] Long-running operation tested
- [ ] Disk/log growth reviewed

---

# 🔧 23. Troubleshooting

## Logger does not record an application

Check:

```text
1. Is the executable present in tracked_apps.json?
2. Is Windows generating Event 4688?
3. Is Windows generating Event 4689?
4. Does the logger have permission to read Security?
5. Is the executable name correct?
```

## Logger starts but no CSV appears

Check `logger_config.json` and verify the configured output location.

Then inspect `Logger_Logs/` for diagnostic information.

## START is recorded but no completed session appears

Check whether the corresponding 4689 termination event exists.

Possible causes include:

- logger restart
- missing termination event
- abnormal process termination
- state/recovery issue

## Logger does not start after reboot

Open:

```text
Task Scheduler
→ Task Scheduler Library
→ License Usage Logger
```

Check that the scheduled task exists and is enabled.

---

# 🔄 24. Development → Release Workflow

```text
Modify logger.py
       ↓
Update configuration if necessary
       ↓
Test locally
       ↓
Run build_release.bat
       ↓
Build LicenseLogger.exe
       ↓
Prepare ready-to-deploy package
       ↓
Test on target environment
       ↓
Release new version
```

Use versioned releases when appropriate:

```text
V01
V02
V03
...
```

This makes deployment and rollback easier to manage.

---

# 🔒 25. Security & Privacy Considerations

The logger is intended to collect application/process utilization metadata.

It does not intentionally collect:

- document contents
- CAD drawings
- screenshots
- keyboard input
- mouse input
- passwords
- application command content

Organizations should deploy and retain the collected information according to their internal monitoring, security, privacy, and employee-data policies.

---

# 🚫 26. Current Non-Goals / Future Enhancements

The initial implementation does not require:

- a central database
- a central API
- a live web dashboard
- keyboard/mouse monitoring
- screenshot monitoring
- foreground-window tracking
- application-internal activity analysis
- cloud infrastructure

These can be considered later if organizational requirements expand.

---

# 📈 27. Why This Can Be Useful for License Management

The collected data can help IT answer questions such as:

```text
Which users launched AutoCAD this month?
Which users barely used AutoCAD?
How many sessions did each user have?
How many total hours did each user run the application?
Which computers generated the usage?
Which applications appear under-utilized?
```

This information can support license reassignment/review decisions. It should be combined with the organization's actual license records and business requirements before making licensing decisions.

---

# 🚀 28. Quick Start

## Developer

```text
1. Open PACKAGE/01_Source_and_Build/
2. Install Python
3. Run: python -m pip install -r requirements.txt
4. Modify logger.py/configuration if required
5. Test
6. Run build_release.bat
7. Use the generated EXE for deployment testing
```

## Deployment User

```text
1. Open PACKAGE/02_Ready_to_Deploy/
2. Copy the folder to the target Windows PC
3. Configure tracked_apps.json if necessary
4. Configure logger_config.json if necessary
5. Ensure Windows process auditing is enabled
6. Run install_license_logger_task.bat as Administrator
7. Verify LicenseLogger.exe in Task Manager
8. Test a tracked application
9. Review License_Usage/
10. Use Logger_Logs/ only for troubleshooting
```

---

# 📌 29. Project Status

| Area                                      | Status         |
| ----------------------------------------- | -------------- |
| Windows 4688/4689 process-event mechanism | ✅ Completed   |
| Session detection                         | ✅ Completed   |
| Duration calculation                      | ✅ Completed   |
| Per-application CSVs                      | ✅ Completed   |
| Calendar-month summaries                  | ✅ Completed   |
| Configurable application list             | ✅ Completed   |
| State/restart handling                    | ✅ Tested      |
| Resource-impact prototype test            | ✅ Completed   |
| Diagnostic logging                        | ✅ Implemented |
| Silent EXE architecture                   | ✅ Prepared    |
| Automatic startup                         | ✅ Prepared    |

---

<div align="center">

## 🛡️ License Usage Logger

**Detect → Record → Aggregate → Review**

</div>
