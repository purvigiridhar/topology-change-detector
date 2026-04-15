# 🌐 Topology Change Detector using POX (SDN Project)

## 📌 Objective

Dynamically detect and monitor changes in network topology using Software Defined Networking (SDN). The controller observes switch events, updates the topology map, displays changes in real time, and logs all updates with timestamps.

---

## 🛠️ Tools & Technologies

| Tool | Purpose |
|------|---------|
| [Mininet](http://mininet.org/) | Network Emulator |
| [POX Controller](https://github.com/noxrepo/pox) | SDN Controller |
| Python | Controller logic scripting |

---

## ⚙️ Features

- ✅ Detects switch connections (`ConnectionUp`) and disconnections (`ConnectionDown`)
- ✅ Displays topology changes dynamically in the terminal
- ✅ Maintains a live topology map (active switches)
- ✅ Logs topology updates with timestamps to `topology_log.txt`
- ✅ Counts the total number of topology changes
- ✅ Displays total number of active switches after each event
- ✅ Demonstrates network behavior during link failures and recovery

---

## 🧠 How It Works

1. The POX controller listens for `ConnectionUp` and `ConnectionDown` events from switches.
2. When a switch connects or disconnects, the internal topology map is updated.
3. After each event, the system prints:
   - Event type (`SWITCH ADDED` / `SWITCH REMOVED`)
   - Change number (incremental counter)
   - List of currently active switches
   - Total number of active switches
4. All updates are logged into `topology_log.txt` with timestamps.
5. Network behavior is tested and validated using Mininet.

---

## 🚀 How to Run

### Step 1: Clean the Environment

```bash
sudo mn -c
sudo killall pox.py
```

### Step 2: Start the POX Controller

```bash
cd ~/pox
./pox.py log.level --ERROR forwarding.l2_learning topology_detector
```

### Step 3: Start Mininet (in a New Terminal)

```bash
sudo mn --controller=remote,ip=127.0.0.1,port=6633 --topo tree,depth=2,fanout=2
```

---

## 🧪 Test Scenarios

### ✅ 1. Normal Operation

```bash
pingall
```

- **Expected Output:** `0% dropped`
- **Indicates:** Full connectivity across all switches

---

### 🔴 2. Failure Scenario (Link Down)

```bash
link s1 s2 down
pingall
```

- **Expected Output:** Packet loss (e.g., `66% dropped`)
- **Indicates:** Topology disruption due to link failure

---

### 🟢 3. Recovery Scenario (Link Up)

```bash
link s1 s2 up
pingall
```

- **Expected Output:** `0% dropped`
- **Indicates:** Successful network recovery

---

## 📄 Sample Output

### Controller Terminal Output

```
===== TOPOLOGY CHANGE DETECTED =====
Change Number: 3
Event: SWITCH ADDED
Active Switches: [1, 2, 3]
Total Switches: 3
====================================
```

### topology_log.txt (excerpt)

```
SWITCH ADDED -> Switches: [1]
SWITCH ADDED -> Switches: [1, 3]
SWITCH ADDED -> Switches: [1, 2, 3]
SWITCH REMOVED -> Switches: [2, 3]
SWITCH REMOVED -> Switches: [2]
SWITCH REMOVED -> Switches: []
...
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1]
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 3]
[2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]
```

> 📝 Note: Early log entries do not include timestamps. Timestamped logging was added in a later version of the controller.

---

## 📁 Project Structure

```
~/pox/
├── pox.py                  # POX launcher
├── topology_detector.py    # Custom topology change detector module
└── topology_log.txt        # Auto-generated log file of topology events
```

---

## 👩‍💻 Author

**Purvi**
SDN Lab Project — Topology Change Detector
Date: April 2026
