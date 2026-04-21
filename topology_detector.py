# =============================================================================
# topology_detector.py — POX SDN Topology Change Detector + Visualization
# =============================================================================
# This is a custom component for the POX SDN controller.
#
# It does four things:
#   1. SWITCH TRACKING  — detects when switches connect or disconnect
#   2. LINK TRACKING    — detects when switch-to-switch links appear or vanish
#   3. HOST DISCOVERY   — learns which switch each host is connected to
#   4. VISUALIZATION    — prints a live, structured topology map after each change
#
# All events are also written to topology_log.txt with timestamps.
#
# How to run:
#   ./pox.py log.level --ERROR forwarding.l2_learning openflow.discovery topology_detector
#
# IMPORTANT: openflow.discovery MUST be in the launch command.
#            Without it, LinkEvent will never fire and link detection won't work.
# =============================================================================


# ── IMPORTS ───────────────────────────────────────────────────────────────────

from pox.core import core
# 'core' is the central hub of POX — it connects all running components.
# It gives us access to the OpenFlow subsystem (core.openflow) and the
# discovery module (core.openflow_discovery) through a shared service locator.

import pox.openflow.libopenflow_01 as of
# The OpenFlow 1.0 message library. Defines all the message types used
# to communicate between the POX controller and OpenFlow-enabled switches.
# Not directly used in this file, but it's a standard import for POX
# components that may later send flow rules or port commands.

import pox.openflow.discovery
# This imports POX's built-in link discovery module.
# It works by sending LLDP (Link Layer Discovery Protocol) probe packets
# between switches and listening for replies to detect active links.
# Simply importing it here makes it available; it is started via the
# launch command with 'openflow.discovery'.

import datetime
# Python's standard date/time library.
# Used to attach human-readable timestamps to every log file entry.


# ── LOGGER SETUP ──────────────────────────────────────────────────────────────

log = core.getLogger()
# Creates a POX logger named after this module ("topology_detector").
# Sends output to POX's unified log stream.
# log.info()    → informational messages (visible at INFO level)
# log.warning() → warnings
# log.error()   → errors
# In our launch command, --ERROR suppresses INFO/WARNING messages so only
# our custom print() output is visible in the terminal.


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

switches = set()
# Tracks the DPID (Datapath ID) of every currently connected switch.
#
# What is a DPID?
#   A unique 64-bit integer that identifies each OpenFlow switch,
#   similar to a MAC address but for switches.
#
# Why a set (not a list)?
#   - DPIDs are unique — sets prevent accidental duplicates
#   - set.add() and set.discard() are O(1) — extremely fast
#   - No ordering needed — we just need to know if a switch is active or not

hosts = {}
# Maps each host's MAC address (string) → the DPID of the switch it's on.
#
# Example entry:
#   { "00:00:00:00:00:01": 2 }  →  h1 is connected to switch s2
#
# This is built dynamically from PacketIn events — the controller learns
# host locations by observing where packets come FROM, not from config.
# This is called "reactive host learning" in SDN.
#
# Why a dict (not a set)?
#   Because we need to store two pieces of information per host:
#   the MAC address (key) and which switch it's on (value).

links = set()
# Tracks active switch-to-switch links as sorted tuples: (dpid1, dpid2).
#
# Example entry:
#   (1, 2)  →  there is an active link between s1 and s2
#
# Why sorted tuples?
#   A link between s1 and s2 is the same physical cable as s2 and s1.
#   By sorting the DPIDs before storing, we ensure both directions
#   map to the same key and avoid duplicates.
#   e.g. tuple(sorted((2, 1))) == tuple(sorted((1, 2))) == (1, 2)
#
# Why a set of tuples?
#   - Links are unique — a set prevents duplicate entries
#   - Tuples are hashable — required for storing in a set

change_count = 0
# A simple integer counter that increments with every topology change event.
# Persists across all event handler calls because it's declared at
# module level (outside any function).
# Helps track: how many changes happened since the controller started?


# ── HELPER FUNCTION ───────────────────────────────────────────────────────────

def get_host_name(mac):
    """
    Converts a raw MAC address string into a human-readable host name.

    How it works:
      - Splits the MAC address by ":" to get each byte as a hex string
      - Reads the LAST byte (e.g., "01", "02", "03", "04")
      - Converts it from hexadecimal to an integer
      - If the value is between 1 and 4 (valid Mininet hosts), returns "h{n}"
      - Otherwise returns None to filter out non-host traffic

    Parameters:
      mac (str): A MAC address string, e.g. "00:00:00:00:00:01"

    Returns:
      str | None: "h1", "h2", "h3", "h4", or None if not a valid host MAC

    Examples:
      get_host_name("00:00:00:00:00:01") → "h1"
      get_host_name("00:00:00:00:00:03") → "h3"
      get_host_name("00:00:00:00:00:ff") → None  (last byte 255, out of range)

    Why do this?
      Mininet assigns MACs like 00:00:00:00:00:0N where N is the host number.
      By filtering on the last byte, we ignore traffic from switches and
      the controller itself, and only track real hosts.
    """
    try:
        last = int(mac.split(":")[-1], 16)
        # mac.split(":")      → ["00", "00", "00", "00", "00", "01"]
        # [-1]                → "01"  (last element of the list)
        # int(..., 16)        → 1     (convert hex string to integer)

        if 1 <= last <= 4:
            return f"h{last}"
            # Returns "h1", "h2", "h3", or "h4" for valid hosts
        else:
            return None
            # Filters out any other MAC address (switches, controllers, etc.)
    except:
        return None
        # Catches any error (e.g., malformed MAC) and safely returns None
        # instead of crashing the controller


# ── SWITCH EVENT HANDLERS ─────────────────────────────────────────────────────

def _handle_ConnectionUp(event):
    """
    Called automatically by POX when a switch establishes a connection
    with the controller via OpenFlow.

    This happens when:
      - Mininet starts and all switches connect to POX
      - A switch recovers after a failure
      - A new switch is added to the network

    The 'event' object contains:
      event.dpid       → the unique ID of the switch that just connected
      event.connection → the OpenFlow connection object
      event.ofp        → the raw OpenFlow FEATURES_REPLY message

    Flow:
      1. Register the switch's DPID in the active switches set
      2. Log the event via POX's logger
      3. Call print_topology() to display and log the change
    """
    switches.add(event.dpid)
    # Registers this switch as active. set.add() is safe to call even if
    # the DPID is already there (it simply won't add a duplicate).

    log.info("Switch %s connected", event.dpid)
    # Sends an INFO-level log message to POX's log output.
    # Suppressed in our terminal because of --ERROR in the launch command,
    # but would appear if you ran without the log level flag.

    print_topology("SWITCH ADDED")
    # Trigger the topology summary display and write to log file.


def _handle_ConnectionDown(event):
    """
    Called automatically by POX when a switch loses its connection
    to the controller.

    This happens when:
      - 'link s1 s2 down' is run in Mininet (causes switch to disconnect)
      - Mininet exits ('exit' command stops all switches)
      - A real switch crashes or is powered off

    Flow:
      1. Remove the switch's DPID from the active switches set
      2. Log the event via POX's logger
      3. Call print_topology() to display and log the change
    """
    switches.discard(event.dpid)
    # Removes this switch from the active set.
    # discard() is used instead of remove() because:
    #   - remove() raises KeyError if the DPID is not found
    #   - discard() silently does nothing if the DPID is missing
    # This makes the code robust if a duplicate disconnect event arrives.

    log.info("Switch %s disconnected", event.dpid)
    # Log the disconnection through POX's logging system.

    print_topology("SWITCH REMOVED")
    # Trigger the topology summary display and write to log file.


# ── LINK EVENT HANDLER ────────────────────────────────────────────────────────

def _handle_LinkEvent(event):
    """
    Called automatically by POX's openflow.discovery module when a
    switch-to-switch link is detected as added or removed.

    How discovery works:
      POX periodically sends LLDP (Link Layer Discovery Protocol) packets
      out of every switch port. When a switch receives an LLDP packet on
      a port, it reports it back to the controller via a PacketIn event.
      The discovery module uses these reports to build a map of which
      switch ports are connected to which other switches.

    The 'event' object contains:
      event.link        → a Link object with dpid1, port1, dpid2, port2
      event.added       → True if this is a new link
      event.removed     → True if this link just disappeared

    Flow:
      1. Extract the two switch DPIDs from the link object
      2. Create a normalized (sorted) key to avoid duplicate entries
      3. Skip the event if it's already in the correct state (dedup check)
      4. Add or remove the link from the links set
      5. Print the event and the updated topology map
    """

    link = event.link
    # The Link object — contains both endpoints of the discovered link.

    s1 = link.dpid1
    s2 = link.dpid2
    # Extract the DPID of each switch at either end of the link.
    # dpid1/dpid2 are just integers (e.g., 1 and 2 for s1 and s2).

    # ── Normalize the link key ─────────────────────────────────────────────
    key = tuple(sorted((s1, s2)))
    # Why sort? A link between s1 and s2 is the same physical cable as s2 and s1.
    # By sorting the two DPIDs, we ensure both directions produce the same key.
    #
    # Example:
    #   s1=2, s2=1  →  sorted((2,1))  →  (1, 2)
    #   s1=1, s2=2  →  sorted((1,2))  →  (1, 2)
    # Both map to the same key, preventing duplicate entries in the links set.

    # ── Duplicate event prevention ─────────────────────────────────────────
    if event.added and key in links:
        return
    # If we already know this link exists, ignore the repeated "added" event.
    # POX discovery may fire LinkEvent multiple times for the same link.

    if event.removed and key not in links:
        return
    # If we don't have this link recorded and get a "removed" event,
    # there's nothing to remove — ignore it to avoid processing ghost events.

    # ── Update the links set and build the log message ─────────────────────
    if event.added:
        links.add(key)
        # Register the new link in our set.
        msg = f"LINK ADDED: s{s1} <-> s{s2}"
        # Build a human-readable message using switch names (s1, s2, etc.)

    elif event.removed:
        links.discard(key)
        # Remove the link from our set.
        msg = f"LINK REMOVED: s{s1} <-> s{s2}"
        # Build the removal message.

    print("\n" + msg)
    # Print the link event message to the terminal.
    # The leading \n adds visual separation from previous output.

    log_to_file(msg)
    # Write this link event to topology_log.txt with a timestamp.

    print_network()
    # After every link change, print the full updated topology map
    # so the current state of the network is always visible.


# ── PACKET EVENT HANDLER (HOST DISCOVERY) ─────────────────────────────────────

def _handle_PacketIn(event):
    """
    Called automatically by POX when a switch receives a packet it
    doesn't know how to forward and sends it to the controller.

    This is the standard OpenFlow "reactive" behavior — unknown packets
    are forwarded to the controller (PacketIn), which processes them
    and decides what to do.

    We use this event purely to LEARN host locations:
      - When a packet arrives from a host, we know that host's MAC address
      - We also know WHICH switch received it (event.dpid)
      - So we can record: "host with this MAC is reachable via switch X"

    The 'event' object contains:
      event.parsed  → the parsed Ethernet frame
      event.dpid    → the DPID of the switch that received the packet
      event.port    → the port number the packet arrived on

    Flow:
      1. Parse the incoming packet to get the Ethernet frame
      2. Extract the source MAC address (tells us who sent the packet)
      3. Convert the MAC to a host name using get_host_name()
      4. If it's a valid host MAC, store the MAC → switch mapping
    """

    packet = event.parsed
    # event.parsed gives us the decoded Ethernet frame.
    # This is much easier to work with than raw bytes.

    if not packet:
        return
    # Guard against empty or malformed packets that couldn't be parsed.
    # Without this check, accessing packet.src below would crash.

    src_mac = str(packet.src)
    # packet.src is the source MAC address object from the Ethernet header.
    # str() converts it to a readable string like "00:00:00:00:00:01".
    # This tells us WHO sent the packet.

    dpid = event.dpid
    # The DPID of the switch that received this packet.
    # This tells us WHICH switch the source host is connected to.

    host = get_host_name(src_mac)
    # Convert the raw MAC address to a readable name (h1, h2, etc.)
    # Returns None if the MAC doesn't belong to a valid Mininet host.

    if host:
        hosts[src_mac] = dpid
        # Only store entries for valid hosts (h1 to h4).
        # dict update: if this MAC was already known, just update the switch.
        # This handles hosts that might move between switches (rare in Mininet
        # but important in real networks).
        #
        # After this line: hosts["00:00:00:00:00:01"] = 2
        # means h1 is connected to switch s2.


# ── NETWORK VISUALIZATION ─────────────────────────────────────────────────────

def print_network():
    """
    Prints a clean, structured snapshot of the entire network topology.

    Shows:
      1. Switch Connections — which switches and hosts each switch is linked to
      2. Host Connections   — which switch each host is directly connected to

    Called after every LinkEvent so the display is always up to date.

    How it builds the map:
      - Starts with an empty neighbor list for each active switch
      - Adds switch neighbors from the 'links' set
      - Adds host neighbors from the 'hosts' dict
      - Sorts all connections alphabetically for consistent, readable output
    """

    print("\n========= NETWORK TOPOLOGY =========\n")

    # ── Build the switch neighbor map ──────────────────────────────────────
    switch_map = {s: [] for s in switches}
    # Creates a dictionary where each active switch DPID maps to an empty list.
    # This list will hold the names of everything connected to that switch.
    #
    # Example after initialization with 3 switches:
    #   { 1: [], 2: [], 3: [] }

    # ── Add switch-to-switch connections from the links set ───────────────
    for (s1, s2) in links:
        switch_map.setdefault(s1, []).append(f"s{s2}")
        switch_map.setdefault(s2, []).append(f"s{s1}")
        # For each link (s1, s2):
        #   - Add "s2" to s1's neighbor list
        #   - Add "s1" to s2's neighbor list (links are bidirectional)
        #
        # setdefault(key, []) creates an empty list if the key doesn't exist,
        # or returns the existing list. Safer than switch_map[s1] in case
        # a link involves a switch not yet in switch_map.
        #
        # Example: link (1, 2) adds:
        #   switch_map[1] → ["s2"]
        #   switch_map[2] → ["s1"]

    # ── Add host-to-switch connections from the hosts dict ────────────────
    for mac, sw in hosts.items():
        host = get_host_name(mac)
        if host:
            switch_map.setdefault(sw, []).append(host)
            # For each known host MAC and the switch it's on:
            #   - Add the host name (e.g., "h1") to that switch's neighbor list
            #
            # Example: hosts["00:00:00:00:00:01"] = 2  adds:
            #   switch_map[2] → [..., "h1"]

    # ── Print switch connections ───────────────────────────────────────────
    print("Switch Connections:")
    for sw in sorted(switch_map):
        # sorted(switch_map) sorts switches numerically by DPID (1, 2, 3...)
        # so the output is always in a consistent order.

        connections = ", ".join(sorted(set(switch_map[sw])))
        # set(...)    → removes any duplicate neighbor names
        # sorted(...) → sorts neighbors alphabetically (h1, h2, s1, s3...)
        # ", ".join() → formats as a comma-separated string

        print(f"s{sw} → {connections}")
        # Example output:
        #   s1 → s2, s3
        #   s2 → h1, h2, s1
        #   s3 → h3, h4, s1

    # ── Print host-to-switch connections ──────────────────────────────────
    print("\nHost Connections:")
    for mac, sw in sorted(hosts.items()):
        # sorted(hosts.items()) sorts by MAC address string alphabetically,
        # which effectively sorts hosts in order (h1, h2, h3, h4) because
        # Mininet MAC addresses increment predictably.

        host = get_host_name(mac)
        if host:
            print(f"{host} → s{sw}")
            # Example output:
            #   h1 → s2
            #   h2 → s2
            #   h3 → s3
            #   h4 → s3

    print("\n===================================\n")
    # Closing border and blank line for visual clarity in the terminal.


# ── TOPOLOGY SUMMARY (SWITCH LEVEL) ───────────────────────────────────────────

def print_topology(change_type):
    """
    Prints a switch-level topology summary to the terminal and logs the event.

    Called by _handle_ConnectionUp and _handle_ConnectionDown whenever
    a switch joins or leaves the network.

    Parameters:
      change_type (str): Either "SWITCH ADDED" or "SWITCH REMOVED"

    Note: Uses the 'global' keyword because it modifies change_count,
    which is a module-level variable. Without 'global', Python would
    create a new local variable instead of updating the real counter.
    """

    global change_count
    # Declares that we want to modify the module-level change_count variable,
    # not create a new local one inside this function.

    change_count += 1
    # Increment the counter each time this function is called.

    print("\n===== TOPOLOGY CHANGE DETECTED =====")
    print("Change Number:", change_count)
    # Which topology change this is since the controller started (1, 2, 3...)

    print("Event:", change_type)
    # What happened: "SWITCH ADDED" or "SWITCH REMOVED"

    print("Active Switches:", list(switches))
    # Convert the set to a list for display — sets don't have a reliable
    # print order, and lists display in a familiar [1, 2, 3] format.

    print("Total Switches:", len(switches))
    # How many switches are currently connected to the controller.

    print("====================================\n")

    log_to_file(f"{change_type} -> Switches: {list(switches)}")
    # Write this switch-level event to the log file with a timestamp.
    # Example log entry:
    #   [2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]


# ── FILE LOGGING ──────────────────────────────────────────────────────────────

def log_to_file(message):
    """
    Appends a timestamped line to topology_log.txt.

    Every call writes exactly one line in this format:
      [YYYY-MM-DD HH:MM:SS] <message>

    Examples:
      [2026-04-15 19:48:13] SWITCH ADDED -> Switches: [1, 2, 3]
      [2026-04-15 20:08:26] LINK REMOVED: s1 <-> s2

    Parameters:
      message (str): The event description to log.

    Key design decisions:
      - Append mode ("a"): Never overwrites old entries — full history preserved
      - 'with' statement: Guarantees the file closes cleanly even if an error occurs
      - Auto-created: If topology_log.txt doesn't exist, Python creates it
    """

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # datetime.now()   → current local date and time as a datetime object
    # strftime(...)    → formats it as a readable string:
    #   %Y = 4-digit year   (e.g., 2026)
    #   %m = 2-digit month  (e.g., 04)
    #   %d = 2-digit day    (e.g., 15)
    #   %H = hour, 24h      (e.g., 20)
    #   %M = minutes        (e.g., 08)
    #   %S = seconds        (e.g., 26)

    with open("topology_log.txt", "a") as f:
        # "a" = append mode: writes at the end of the file.
        # If the file doesn't exist yet, Python creates it automatically.
        # The 'with' block ensures f.close() is always called, even if
        # an exception occurs during the write.

        f.write(f"[{timestamp}] {message}\n")
        # Writes the complete log line.
        # The \n moves to a new line so each entry appears on its own row.
        #
        # Example output in file:
        #   [2026-04-15 19:48:15] LINK ADDED: s1 <-> s2


# ── LAUNCH FUNCTION ───────────────────────────────────────────────────────────

def launch():
    """
    Entry point for this POX component.

    POX calls launch() automatically when this module is loaded from the
    command line:
      ./pox.py log.level --ERROR forwarding.l2_learning openflow.discovery topology_detector

    This function registers all four event handler functions with POX's
    event system. Each registration tells POX:
      "Whenever event X fires, call function Y and pass it the event object."

    The two event sources used:
      core.openflow           → switch-level events (ConnectionUp/Down, PacketIn)
      core.openflow_discovery → link-level events (LinkEvent)
    """

    # ── Register switch connect/disconnect handlers ────────────────────────
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    # POX calls _handle_ConnectionUp every time a switch connects.
    # "ConnectionUp" is the OpenFlow event POX fires on receiving FEATURES_REPLY.

    core.openflow.addListenerByName("ConnectionDown", _handle_ConnectionDown)
    # POX calls _handle_ConnectionDown every time a switch disconnects.

    # ── Register packet handler for host discovery ─────────────────────────
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    # POX calls _handle_PacketIn every time a switch sends an unmatched
    # packet to the controller. We use this to passively learn host locations.
    # Note: l2_learning also handles PacketIn — both handlers run independently.

    # ── Register link discovery handler ───────────────────────────────────
    core.openflow_discovery.addListenerByName("LinkEvent", _handle_LinkEvent)
    # POX calls _handle_LinkEvent every time the discovery module detects
    # a link being added or removed between switches.
    #
    # IMPORTANT: This only works because openflow.discovery was included in
    # the POX launch command, which started the discovery module and made
    # core.openflow_discovery available. If it's missing from the command,
    # this line will raise:
    #   AttributeError: 'core' object has no attribute 'openflow_discovery'

    log.info("Topology Detector running — listening for switch, link, and host events...")
    # Confirm to the POX log that this module loaded and registered successfully.
