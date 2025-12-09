"""Mock UniFi API responses for testing.

Provides realistic sample responses from UniFi controller API.
"""

# Login response
LOGIN_SUCCESS = {
    "meta": {"rc": "ok"},
    "data": []
}

# Device list response (stat/device)
DEVICES_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "device001",
            "name": "UDM Pro",
            "mac": "aa:bb:cc:dd:ee:01",
            "ip": "192.168.1.1",
            "model": "UDM-Pro",
            "type": "udm",
            "version": "3.2.7",
            "adopted": True,
            "uptime": 864000,
        },
        {
            "_id": "device002",
            "name": "Main Switch",
            "mac": "aa:bb:cc:dd:ee:02",
            "ip": "192.168.1.2",
            "model": "USW-24-POE",
            "type": "usw",
            "version": "6.5.59",
            "adopted": True,
            "uptime": 432000,
        },
        {
            "_id": "device003",
            "name": "Living Room AP",
            "mac": "aa:bb:cc:dd:ee:03",
            "ip": "192.168.1.3",
            "model": "U6-Pro",
            "type": "uap",
            "version": "6.5.62",
            "adopted": True,
            "uptime": 345600,
        },
    ]
}

# WLAN configuration response (rest/wlanconf)
WLANS_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "wlan001",
            "name": "HomeNetwork",
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "wpa3_support": False,
            "wpa3_transition": False,
            "hide_ssid": False,
            "is_guest": False,
            "vlan_enabled": False,
            "vlan": "",
            "l2_isolation": False,
            "mac_filter_enabled": False,
            "pmf_mode": "disabled",
        },
        {
            "_id": "wlan002",
            "name": "GuestNetwork",
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "wpa3_support": False,
            "wpa3_transition": False,
            "hide_ssid": False,
            "is_guest": True,
            "vlan_enabled": False,
            "vlan": "",
            "l2_isolation": False,
            "mac_filter_enabled": False,
            "pmf_mode": "disabled",
        },
        {
            "_id": "wlan003",
            "name": "OpenCafe",
            "enabled": True,
            "security": "open",
            "wpa_mode": "",
            "wpa3_support": False,
            "wpa3_transition": False,
            "hide_ssid": False,
            "is_guest": True,
            "vlan_enabled": False,
            "vlan": "",
            "l2_isolation": False,
            "mac_filter_enabled": False,
            "pmf_mode": "disabled",
        },
    ]
}

# Network configuration response (rest/networkconf)
NETWORKS_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "net001",
            "name": "Default",
            "purpose": "corporate",
            "vlan_enabled": False,
            "vlan": None,
            "ip_subnet": "192.168.1.0/24",
            "dhcpd_enabled": True,
            "dhcpd_start": "192.168.1.100",
            "dhcpd_stop": "192.168.1.200",
            "dhcpd_leasetime": 86400,
            "domain_name": "local",
            "igmp_snooping": False,
            "networkgroup": "LAN",
        },
        {
            "_id": "net002",
            "name": "WAN",
            "purpose": "wan",
            "vlan_enabled": False,
            "vlan": None,
            "ip_subnet": "",
            "dhcpd_enabled": False,
            "networkgroup": "WAN",
        },
    ]
}

# Firewall rules response (rest/firewallrule)
FIREWALL_RULES_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "fw001",
            "name": "Allow established",
            "ruleset": "WAN_IN",
            "enabled": True,
            "action": "accept",
            "protocol": "all",
            "src_address": "",
            "dst_address": "",
            "dst_port": "",
            "state_established": True,
            "state_related": True,
            "rule_index": 2000,
        },
        {
            "_id": "fw002",
            "name": "Drop invalid",
            "ruleset": "WAN_IN",
            "enabled": True,
            "action": "drop",
            "protocol": "all",
            "src_address": "",
            "dst_address": "",
            "dst_port": "",
            "state_invalid": True,
            "rule_index": 2001,
        },
        {
            "_id": "fw003",
            "name": "Allow All LAN",
            "ruleset": "LAN_IN",
            "enabled": True,
            "action": "accept",
            "protocol": "all",
            "src_address": "",
            "src_networkconf_type": "NETv4",
            "dst_address": "",
            "dst_port": "",
            "rule_index": 3000,
        },
    ]
}

# Firewall groups response (rest/firewallgroup)
FIREWALL_GROUPS_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "fwg001",
            "name": "RFC1918",
            "group_type": "address-group",
            "group_members": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
        },
        {
            "_id": "fwg002",
            "name": "Common Ports",
            "group_type": "port-group",
            "group_members": ["80", "443", "8080"],
        },
    ]
}

# Settings response (rest/setting)
SETTINGS_RESPONSE = {
    "meta": {"rc": "ok"},
    "data": [
        {
            "_id": "setting_mgmt",
            "key": "mgmt",
            "x_ssh_enabled": True,
            "x_ssh_auth_password_enabled": True,
            "led_enabled": True,
            "alert_enabled": True,
            "unifi_idp_enabled": False,
        },
        {
            "_id": "setting_usg",
            "key": "usg",
            "upnp_enabled": True,
            "upnp_nat_pmp_enabled": True,
            "upnp_secure_mode": False,
        },
        {
            "_id": "setting_ips",
            "key": "ips",
            "ips_enabled": False,
            "ips_mode": "disabled",
            "dns_filtering": False,
            "honeypot_enabled": False,
        },
        {
            "_id": "setting_dpi",
            "key": "dpi",
            "enabled": False,
            "restrictions_enabled": False,
        },
    ]
}

# Sample nmap XML output
NMAP_XML_OUTPUT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -oX - --top-ports 100 192.168.1.0/24" start="1701619200" version="7.94">
<host starttime="1701619201" endtime="1701619205">
<status state="up" reason="arp-response"/>
<address addr="192.168.1.1" addrtype="ipv4"/>
<address addr="AA:BB:CC:DD:EE:01" addrtype="mac" vendor="Ubiquiti"/>
<hostnames>
<hostname name="udm-pro" type="PTR"/>
</hostnames>
<ports>
<port protocol="tcp" portid="22">
<state state="open" reason="syn-ack"/>
<service name="ssh" product="OpenSSH" version="8.9"/>
</port>
<port protocol="tcp" portid="443">
<state state="open" reason="syn-ack"/>
<service name="https"/>
</port>
</ports>
</host>
<host starttime="1701619201" endtime="1701619205">
<status state="up" reason="arp-response"/>
<address addr="192.168.1.100" addrtype="ipv4"/>
<address addr="11:22:33:44:55:66" addrtype="mac" vendor="Unknown"/>
<hostnames/>
<ports>
<port protocol="tcp" portid="80">
<state state="open" reason="syn-ack"/>
<service name="http"/>
</port>
</ports>
</host>
<runstats>
<finished time="1701619210" elapsed="10.00"/>
<hosts up="2" down="253" total="255"/>
</runstats>
</nmaprun>
"""

# Empty nmap result
NMAP_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -oX - --top-ports 100 10.0.0.0/24" start="1701619200" version="7.94">
<runstats>
<finished time="1701619210" elapsed="10.00"/>
<hosts up="0" down="255" total="255"/>
</runstats>
</nmaprun>
"""

