# =============================================================================
# topology_detector.py — POX SDN Topology Change Detector
# =============================================================================
# This module is a custom component for the POX SDN controller.
# It monitors the network for switch connection and disconnection events,
# maintains a live set of active switches, prints topology changes to the
# terminal, and logs every event with a timestamp to topology_log.txt.
#
# How to load this module with POX:
#   ./pox.py log.level --ERROR forwarding.l2_learning topology_detector
# =============================================================================
 
 
# --- Imports ------------------------------------------------------------------
 
from pox.core import core
# 'core' is the central object in POX. It acts as a service locator —
# it holds references to all running POX components (like openflow, etc.)
# and allows components to communicate with each other.
 
import pox.openflow.libopenflow_01 as of
# This imports the OpenFlow 1.0 library, which defines the message structures
# used to communicate between the POX controller and OpenFlow-enabled switches.
# Although not directly used in this file, it is a standard import for
# POX components that may later send flow rules or other OpenFlow messages.
 
import datetime
# Standard Python library for getting the current date and time.
# Used here to attach a human-readable timestamp to every log entry.
 
 
# --- Logger Setup -------------------------------------------------------------
 
log = core.getLogger()
# POX provides a built-in logging system through core.getLogger().
# This creates a logger named after the module (topology_detector),
# which sends messages to POX's unified log output.
# Usage: log.info("message"), log.warning("message"), log.error("message")
 
 
# --- Global State -------------------------------------------------------------
 
switches = set()
# A Python set that tracks the DPID (Datapath ID) of every currently
# connected switch. A set is used because:
#   - DPIDs are unique, so no duplicates are needed
#   - set.add() and set.discard() are O(1) — very fast
#   - It automatically prevents duplicate entries
 
change_count = 0
# A counter that increments every time the topology changes (switch added
# or removed). Helps track how many topology events have occurred since
# the controller started. Declared globally so it persists across multiple
# event handler calls.
 
 
# --- Event Handlers -----------------------------------------------------------
 
def _handle_ConnectionUp(event):
    """
    Called automatically by POX when a switch connects to the controller.
 
    The 'event' object contains information about the switch that just
    connected, including its DPID (Datapath ID) — a unique 64-bit identifier
    for each OpenFlow switch (similar to a MAC address for switches).
 
    Flow:
      1. Add the new switch's DPID to the active switches set
      2. Log the connection via POX's logger
      3. Call print_topology() to display and record the change
    """
    switches.add(event.dpid)
    # event.dpid is the unique ID of the switch that just connected.
    # Adding it to the set registers it as an active switch.
 
    log.info("Switch %s connected", event.dpid)
    # Logs an informational message to POX's log output.
    # This is separate from our custom file log — it goes to the terminal
    # via POX's own logging system (visible when log level allows INFO).
 
    print_topology("SWITCH ADDED")
    # Trigger the topology display and file logging with the event label.
 
 
def _handle_ConnectionDown(event):
    """
    Called automatically by POX when a switch disconnects from the controller.
 
    This can happen due to:
      - A physical or virtual link going down (e.g., 'link s1 s2 down' in Mininet)
      - A switch crashing or being shut down
      - Network failure between the switch and controller
 
    Flow:
      1. Remove the switch's DPID from the active switches set
      2. Log the disconnection via POX's logger
      3. Call print_topology() to display and record the change
    """
    switches.discard(event.dpid)
    # discard() is used instead of remove() because:
    #   - remove() raises a KeyError if the DPID is not found
    #   - discard() safely does nothing if the DPID is missing
    # This makes the code more robust against unexpected duplicate events.
 
    log.info("Switch %s disconnected", event.dpid)
    # Log the disconnection event through POX's logging system.
 
    print_topology("SWITCH REMOVED")
    # Trigger the topology display and file logging with the event label.
 
 
# --- Topology Display ---------------------------------------------------------
 
def print_topology(change_type):
    """
    Prints a formatted summary of the current topology to the terminal,
    and writes the event to the log file.
 
    Parameters:
      change_type (str): A label describing what happened.
                         Either "SWITCH ADDED" or "SWITCH REMOVED".
 
    This function uses the 'global' keyword to modify change_count,
    which lives outside the function's local scope.
    """
    global change_count
    # 'global' tells Python we want to modify the module-level variable,
    # not create a new local variable with the same name.
 
    change_count += 1
    # Increment the event counter each time a topology change occurs.
 
    # Print a clearly formatted block to the terminal so changes are easy
    # to spot in the controller's output stream.
    print("\n===== TOPOLOGY CHANGE DETECTED =====")
    print("Change Number:", change_count)       # Which topology change this is (e.g., 1st, 2nd...)
    print("Event:", change_type)                # What happened: SWITCH ADDED or SWITCH REMOVED
    print("Active Switches:", list(switches))   # Convert set → list for readable display (sets have no order)
    print("Total Switches:", len(switches))     # How many switches are currently connected
    print("====================================\n")
 
    # Also write this event to the persistent log file.
    log_to_file(f"{change_type} -> Switches: {list(switches)}")
    # The f-string builds the message dynamically, e.g.:
    #   "SWITCH ADDED -> Switches: [1, 2, 3]"
 
 
# --- File Logging -------------------------------------------------------------
 
def log_to_file(message):
    """
    Appends a timestamped log entry to 'topology_log.txt'.
 
    Each call adds one line in the format:
      [YYYY-MM-DD HH:MM:SS] <message>
 
    Example:
      [2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]
 
    Parameters:
      message (str): The topology event description to log.
 
    Note: The file is opened in append mode ("a"), so previous logs are
    never overwritten — all history is preserved across topology changes.
    The file is automatically closed after each write (context manager).
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # datetime.now() returns the current local date and time as a datetime object.
    # strftime() formats it as a human-readable string:
    #   %Y = 4-digit year  (e.g., 2026)
    #   %m = 2-digit month (e.g., 04)
    #   %d = 2-digit day   (e.g., 15)
    #   %H = Hour, 24h     (e.g., 19)
    #   %M = Minutes       (e.g., 48)
    #   %S = Seconds       (e.g., 13)
 
    with open("topology_log.txt", "a") as f:
        # "a" = append mode: opens the file and writes at the end.
        # If topology_log.txt doesn't exist yet, Python creates it automatically.
        # The 'with' statement ensures the file is properly closed even if an
        # error occurs during the write.
 
        f.write(f"[{timestamp}] {message}\n")
        # Writes the full log line, e.g.:
        #   [2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]
        # The \n at the end moves to a new line for the next log entry.
 
 
# --- Launch Function ----------------------------------------------------------
 
def launch():
    """
    The entry point for this POX component.
 
    POX calls launch() automatically when this module is loaded via the
    command line (e.g., ./pox.py topology_detector).
 
    This function registers our event handler functions with POX's OpenFlow
    event system so they are called whenever a switch connects or disconnects.
 
    addListenerByName(event_name, handler_function) tells POX:
      "Whenever the OpenFlow subsystem fires an event named <event_name>,
       call <handler_function> and pass it the event object."
    """
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    # Register _handle_ConnectionUp to be called on every "ConnectionUp" event.
    # ConnectionUp fires when a new switch establishes an OpenFlow connection
    # with the controller.
 
    core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
    # Register _handle_ConnectionDown to be called on every "ConnectionDown" event.
    # ConnectionDown fires when an existing switch loses its connection
    # to the controller (gracefully or due to failure).
 
    log.info("Topology Change Detector is running and listening for switch events...")
    # Confirm the module has loaded successfully and is ready to detect changes.
