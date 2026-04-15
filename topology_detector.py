from pox.core import core
import pox.openflow.libopenflow_01 as of
import datetime

log = core.getLogger()

switches = set()
change_count = 0

def _handle_ConnectionUp(event):
    switches.add(event.dpid)
    log.info("Switch %s connected", event.dpid)
    print_topology("SWITCH ADDED")

def _handle_ConnectionDown(event):
    switches.discard(event.dpid)
    log.info("Switch %s disconnected", event.dpid)
    print_topology("SWITCH REMOVED")

def print_topology(change_type):
    global change_count
    change_count += 1

    print("\n===== TOPOLOGY CHANGE DETECTED =====")
    print("Change Number:", change_count)
    print("Event:", change_type)
    print("Active Switches:", list(switches))
    print("Total Switches:", len(switches))
    print("====================================\n")

    log_to_file(f"{change_type} -> Switches: {list(switches)}")

def log_to_file(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("topology_log.txt", "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def launch():
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
