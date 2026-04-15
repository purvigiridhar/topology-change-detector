from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

switches = set()

def _handle_ConnectionUp(event):
    switches.add(event.dpid)
    log.info("Switch %s connected", event.dpid)
    print_topology("SWITCH ADDED")

def _handle_ConnectionDown(event):
    switches.discard(event.dpid)
    log.info("Switch %s disconnected", event.dpid)
    print_topology("SWITCH REMOVED")

def print_topology(change_type):
    print("\n===== TOPOLOGY CHANGE DETECTED =====")
    print("Event:", change_type)
    print("Active Switches:", list(switches))
    print("====================================\n")

    # Save logs (IMPORTANT for marks)
    with open("topology_log.txt", "a") as f:
        f.write(f"{change_type} -> Switches: {list(switches)}\n")

def launch():
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
