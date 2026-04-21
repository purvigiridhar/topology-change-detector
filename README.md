# 🌐 Topology Change Detector with Visualization — POX SDN Project

> A real-time Software Defined Networking (SDN) project that detects, visualizes, and logs network topology changes using the POX controller and Mininet emulator.

---

## 📌 Objective

Dynamically detect and monitor changes in network topology using SDN. The POX controller:
- Tracks switch connections and disconnections
- Detects switch-to-switch links using the OpenFlow Discovery module
- Learns host locations by inspecting incoming packets
- Displays a live, structured network topology map
- Logs every event with a timestamp to `topology_log.txt`

---

## 🛠️ Tools & Technologies

| Tool | Version | Purpose |
|------|---------|---------|
| [Mininet](http://mininet.org/) | 2.3.x | Virtual network emulator |
| [POX Controller](https://github.com/noxrepo/pox) | 0.7.0 (gar) | Python-based SDN controller |
| Python | 3.10 | Controller module scripting |
| OpenFlow | 1.0 | Switch-controller communication protocol |
| Ubuntu (VM) | 24.x | Host operating system |

---

## ⚙️ Features

- ✅ **Switch Detection** — Detects switch connections (`ConnectionUp`) and disconnections (`ConnectionDown`) in real time
- ✅ **Link Detection** — Uses POX's `openflow.discovery` module to detect switch-to-switch links being added or removed
- ✅ **Host Discovery** — Learns host locations by inspecting `PacketIn` events and mapping MAC addresses to switches
- ✅ **Live Topology Visualization** — Prints a clean, structured topology map (switches + hosts + connections) after every change
- ✅ **Topology Change Counter** — Tracks and displays an incremental change number for every event
- ✅ **Persistent Logging** — Appends every event with a timestamp to `topology_log.txt`
- ✅ **Duplicate Event Prevention** — Normalizes links (s1↔s2 = s2↔s1) and skips duplicate link events
- ✅ **Human-Readable Host Names** — Converts raw MAC addresses to readable names (h1, h2, h3, h4)

---

## 🧠 How It Works

### Event Flow

```
Mininet Network
      │
      │  OpenFlow (port 6633)
      ▼
POX Controller
      │
      ├── ConnectionUp    → Switch joined       → Update switches set  → print_topology()
      ├── ConnectionDown  → Switch left         → Update switches set  → print_topology()
      ├── LinkEvent       → Link added/removed  → Update links set     → print_network()
      └── PacketIn        → Packet arrived      → Learn host location  → Update hosts dict
```

### Data Structures

| Variable | Type | Stores |
|----------|------|--------|
| `switches` | `set` | DPIDs of all currently active switches |
| `hosts` | `dict` | MAC address → switch DPID mapping |
| `links` | `set` | Tuples of `(dpid1, dpid2)` for active switch-switch links |
| `change_count` | `int` | Running count of topology change events |

### Why `set` for switches and links?
- DPIDs and links are **unique** — sets automatically prevent duplicates
- `set.add()` and `set.discard()` are **O(1)** — very fast
- `discard()` is used instead of `remove()` to avoid crashes on unexpected events

### Host Name Resolution
The `get_host_name(mac)` function reads the last byte of the MAC address and maps it to a host name. Only MAC addresses whose last byte falls between 1 and 4 (valid Mininet hosts) are stored, filtering out switch and controller traffic.

```python
# Example: MAC = 00:00:00:00:00:01  →  last byte = 1  →  "h1"
# Example: MAC = 00:00:00:00:00:02  →  last byte = 2  →  "h2"
```

### Link Normalization
To prevent duplicate link entries (since s1→s2 and s2→s1 are the same physical link), every link is stored as a **sorted tuple**:

```python
key = tuple(sorted((s1, s2)))
# (1, 2) and (2, 1) both become (1, 2)
```

---

## 🗂️ Project Structure

```
your-repo/
├── README.md                    # This file
├── topology_detector.py         # Main POX controller module
├── topology_log.txt             # Auto-generated event log
├── docs/
│   └── project_report.docx      # Full project report
└── screenshots/
    ├── 01_controller_startup.png
    ├── 02_switches_connected.png
    ├── 03_pingall_normal.png
    ├── 04_link_down.png
    ├── 05_pingall_failure.png
    ├── 06_link_recovery.png
    ├── 07_topology_log.png
    └── 08_net_command.png
```

---

## 🚀 How to Run

### Step 1 — Clean the Environment

```bash
sudo mn -c
sudo killall pox.py
```

> Clears any leftover Mininet state and kills any previously running POX process.

---

### Step 2 — Copy the Module into POX

```bash
cp topology_detector.py ~/pox/
```

---

### Step 3 — Start the POX Controller

```bash
cd ~/pox
./pox.py log.level --ERROR forwarding.l2_learning openflow.discovery topology_detector
```

> **Important:** `openflow.discovery` must be included in the launch command. Without it, the `LinkEvent` listener will not work and link detection will be disabled.

---

### Step 4 — Start Mininet (New Terminal)

```bash
sudo mn --controller=remote,ip=127.0.0.1,port=6633 --topo tree,depth=2,fanout=2
```

> Creates a tree topology with 3 switches and 4 hosts, connecting to POX on port 6633.

---

## 🖧 Network Topology

The Mininet tree topology (depth=2, fanout=2) creates this layout:

```
               s1   (Root Switch)
              /    \
           s2        s3
          /  \      /  \
        h1   h2   h3   h4
```

### Interface Map (from `net` command in Mininet)

```
h1  h1-eth0:s2-eth1
h2  h2-eth0:s2-eth2
h3  h3-eth0:s3-eth1
h4  h4-eth0:s3-eth2
s1  s1-eth1:s2-eth3    s1-eth2:s3-eth3
s2  s2-eth1:h1-eth0    s2-eth2:h2-eth0    s2-eth3:s1-eth1
s3  s3-eth1:h3-eth0    s3-eth2:h4-eth0    s3-eth3:s1-eth2
```

---

## 📄 Sample Output

### Switch Connection Events (on controller startup)

```
===== TOPOLOGY CHANGE DETECTED =====
Change Number: 1
Event: SWITCH ADDED
Active Switches: [1]
Total Switches: 1
====================================

===== TOPOLOGY CHANGE DETECTED =====
Change Number: 2
Event: SWITCH ADDED
Active Switches: [1, 3]
Total Switches: 2
====================================

===== TOPOLOGY CHANGE DETECTED =====
Change Number: 3
Event: SWITCH ADDED
Active Switches: [1, 2, 3]
Total Switches: 3
====================================
```

### Live Topology Map (after hosts send traffic)

```
LINK ADDED: s1 <-> s2

========= NETWORK TOPOLOGY =========

Switch Connections:
s1 → s2, s3
s2 → h1, h2, s1
s3 → h3, h4, s1

Host Connections:
h1 → s2
h2 → s2
h3 → s3
h4 → s3

===================================
```

### Link Failure Output

```
LINK REMOVED: s1 <-> s2

========= NETWORK TOPOLOGY =========

Switch Connections:
s1 → s3
s2 → h1, h2
s3 → h3, h4, s1

===================================
```

---

## 🧪 Test Scenarios

### ✅ 1. Normal Operation

```bash
mininet> pingall
```

- **Expected:** `0% dropped (12/12 received)`
- **Meaning:** All 4 hosts can reach each other through s1

---

### 🔴 2. Link Failure (s1 ↔ s2 down)

```bash
mininet> link s1 s2 down
mininet> pingall
```

- **Expected:** `66% dropped (4/12 received)`
- **Meaning:** h1 and h2 (connected via s2) lose contact with h3 and h4
- **Controller shows:** `LINK REMOVED: s1 <-> s2` and an updated topology map

---

### 🟢 3. Link Recovery (s1 ↔ s2 up)

```bash
mininet> link s1 s2 up
mininet> pingall
```

- **Expected:** `0% dropped (12/12 received)`
- **Meaning:** Network fully restored
- **Controller shows:** `LINK ADDED: s1 <-> s2` and the full topology map restored

---

## 📋 topology_log.txt — Sample

```
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1]
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 3]
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]
[2026-04-15 19:48:15] LINK ADDED: s1 <-> s2
[2026-04-15 19:48:15] LINK ADDED: s1 <-> s3
[2026-04-15 20:08:26] LINK REMOVED: s1 <-> s2
[2026-04-15 20:08:26] SWITCH REMOVED -> Switches: [2, 3]
[2026-04-15 20:08:26] SWITCH REMOVED -> Switches: [2]
[2026-04-15 20:08:26] SWITCH REMOVED -> Switches: []
```

> The log file is opened in **append mode** — it is never overwritten, so the full history of all runs is preserved.

---

## 📸 Screenshots

### Controller Output — Switches Connected
![Switches Connected](screenshots/01_controller_startup.png)

### Normal Operation — 0% Packet Loss
![Normal pingall](screenshots/03_pingall_normal.png)

### Failure Scenario — 66% Packet Loss
![Link failure](screenshots/04_link_down.png)

### Recovery — Full Connectivity Restored
![Recovery](screenshots/06_link_recovery.png)

### Topology Log File
![Log file](screenshots/07_topology_log.png)

---

## ⚠️ Common Issues & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| `AttributeError: core has no attribute openflow_discovery` | `openflow.discovery` not loaded | Add `openflow.discovery` to the POX launch command |
| Links not detected | Discovery module missing | Make sure `openflow.discovery` is in the launch command |
| Hosts not appearing in topology | No traffic generated yet | Run `pingall` in Mininet to trigger PacketIn events |
| `pox.py: no process found` on cleanup | No POX was running | Safe to ignore — means the cleanup worked |
| Mininet fails to start | Previous session not cleaned | Run `sudo mn -c` before starting |

---

## 📄 Project Report

The full project report (with architecture diagrams, test results, and log analysis) is available here:

[📥 Download Project Report](docs/project_report.docx)

---

## 👩‍💻 Author

**Purvi**
SDN Lab Project — Topology Change Detector with Visualization
Date: April 2026
