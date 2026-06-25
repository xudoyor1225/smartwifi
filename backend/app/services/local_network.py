"""Local network monitoring service.

Production-grade network discovery using:
- psutil for real-time bandwidth statistics
- ARP scanning for device discovery
- Multi-interface support with smart filtering
- Deduplication by MAC address
- Gateway detection
- Async background ping/hostname resolution

Works WITHOUT a MikroTik router for local-only mode.
"""

import asyncio
import ipaddress
import logging
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class NetworkStats:
    """Real-time network statistics from local machine."""

    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    ping_ms: float = 0.0
    jitter_ms: float = 0.0


@dataclass
class LocalDevice:
    """A device discovered on the local network."""

    ip_address: str
    mac_address: str
    hostname: Optional[str] = None
    manufacturer: Optional[str] = None
    is_self: bool = False
    is_gateway: bool = False
    is_responsive: bool = False
    last_seen: float = field(default_factory=time.time)
    bytes_total: int = 0


# Track per-device traffic (placeholder - real values come from MikroTik)
_device_traffic: dict[str, dict[str, int]] = {}

# Locally-administered MAC prefixes used by virtual adapters
# (we DON'T filter these out — they are real Mobile Hotspot / ICS clients)
# But we DO use them to identify if MAC is randomized (privacy)
LOCALLY_ADMINISTERED_BIT = 0x02


def is_locally_administered_mac(mac: str) -> bool:
    """Check if MAC address is locally-administered (often randomized for privacy)."""
    try:
        first_byte = int(mac.split(":")[0], 16)
        return bool(first_byte & LOCALLY_ADMINISTERED_BIT)
    except (ValueError, IndexError):
        return False


class NetworkMonitor:
    """Production-grade local network monitor."""

    def __init__(self) -> None:
        self._last_stats: Optional[tuple[float, int, int]] = None
        self._ping_history: list[float] = []
        self._device_cache: dict[str, LocalDevice] = {}
        self._cache_time: float = 0.0
        self._gateway_ip: Optional[str] = None
        self._self_macs: set[str] = set()  # All MACs of local machine interfaces

    # === Network stats (psutil) ===

    def get_network_stats(self) -> NetworkStats:
        """Get current real-time network bandwidth statistics."""
        net = psutil.net_io_counters()
        now = time.time()

        stats = NetworkStats(
            bytes_sent=net.bytes_sent,
            bytes_recv=net.bytes_recv,
            packets_sent=net.packets_sent,
            packets_recv=net.packets_recv,
        )

        if self._last_stats is not None:
            last_time, last_sent, last_recv = self._last_stats
            elapsed = now - last_time
            if elapsed > 0:
                stats.upload_mbps = round(
                    ((net.bytes_sent - last_sent) * 8 / 1_000_000) / elapsed, 2
                )
                stats.download_mbps = round(
                    ((net.bytes_recv - last_recv) * 8 / 1_000_000) / elapsed, 2
                )

        self._last_stats = (now, net.bytes_sent, net.bytes_recv)

        ping = self._measure_ping()
        stats.ping_ms = ping
        self._ping_history.append(ping)
        if len(self._ping_history) > 10:
            self._ping_history.pop(0)

        if len(self._ping_history) >= 2:
            avg = sum(self._ping_history) / len(self._ping_history)
            variance = sum((p - avg) ** 2 for p in self._ping_history) / len(self._ping_history)
            stats.jitter_ms = round(variance**0.5, 1)

        return stats

    def _measure_ping(self, host: str = "8.8.8.8") -> float:
        """Measure ping latency to a host."""
        try:
            import platform

            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
            timeout_value = "1000" if platform.system().lower() == "windows" else "1"

            result = subprocess.run(
                ["ping", param, "1", timeout_param, timeout_value, host],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return 0.0

            match = re.search(r"[Tt]ime[=<](\d+\.?\d*)\s*ms", result.stdout)
            if match:
                return round(float(match.group(1)), 1)
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"Ping failed: {e}")
        return 0.0

    # === Local machine info ===

    def get_local_ip(self) -> str:
        """Get the primary local IP address (the one used for internet)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def get_local_subnet(self) -> Optional[str]:
        """Get the primary local subnet in CIDR notation."""
        local_ip = self.get_local_ip()
        if local_ip == "127.0.0.1":
            return None

        try:
            for _, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address == local_ip:
                        if addr.netmask:
                            network = ipaddress.IPv4Network(
                                f"{addr.address}/{addr.netmask}", strict=False
                            )
                            return str(network)
        except Exception as e:
            logger.debug(f"Could not determine subnet: {e}")

        ip_obj = ipaddress.IPv4Address(local_ip)
        network = ipaddress.IPv4Network(f"{ip_obj}/24", strict=False)
        return str(network)

    def _get_all_local_macs(self) -> set[str]:
        """Get MAC addresses of ALL local network interfaces (used to filter self)."""
        macs: set[str] = set()
        try:
            for _, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == psutil.AF_LINK and addr.address:
                        mac = addr.address.replace("-", ":").upper()
                        if len(mac) == 17 and mac != "00:00:00:00:00:00":
                            macs.add(mac)
        except Exception as e:
            logger.debug(f"Could not get local MACs: {e}")
        return macs

    def _get_default_gateway(self) -> Optional[str]:
        """Detect the default gateway IP."""
        try:
            import platform

            if platform.system().lower() == "windows":
                # Use 'route print' or 'ipconfig' to find default gateway
                result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                # Look for "Default Gateway" or Russian "Основной шлюз"
                for line in result.stdout.splitlines():
                    line_lower = line.lower()
                    if "gateway" in line_lower or "шлюз" in line_lower:
                        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                        if match:
                            return match.group(1)
            else:
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                match = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.debug(f"Could not get gateway: {e}")
        return None

    def _get_self_device(self) -> Optional[LocalDevice]:
        """Get the local machine as a LocalDevice (primary interface only)."""
        try:
            local_ip = self.get_local_ip()
            if local_ip == "127.0.0.1":
                return None

            mac = self._get_local_mac_for_ip(local_ip)
            if not mac:
                return None

            try:
                hostname = socket.gethostname()
            except Exception:
                hostname = None

            manufacturer = lookup_manufacturer(mac)

            return LocalDevice(
                ip_address=local_ip,
                mac_address=mac,
                hostname=hostname,
                manufacturer=manufacturer,
                is_self=True,
                is_responsive=True,
            )
        except Exception as e:
            logger.debug(f"Could not get self device: {e}")
            return None

    def _get_local_mac_for_ip(self, local_ip: str) -> Optional[str]:
        """Get MAC address of the network interface that has the given IP."""
        try:
            for _, addrs in psutil.net_if_addrs().items():
                has_matching_ip = False
                mac_address = None
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address == local_ip:
                        has_matching_ip = True
                    if addr.family == psutil.AF_LINK:
                        mac_address = addr.address
                if has_matching_ip and mac_address:
                    mac = mac_address.replace("-", ":").upper()
                    if len(mac) == 17:
                        return mac
        except Exception as e:
            logger.debug(f"Could not get local MAC: {e}")
        return None

    # === Device discovery ===

    async def scan_local_devices(self, force: bool = False) -> list[LocalDevice]:
        """Discover devices on the local network.

        Strategy:
        1. ARP scan for all known devices (fast - reads system table)
        2. Add self device (this computer)
        3. Mark gateway device
        4. Deduplicate by MAC address (same MAC = same device)
        5. Filter to primary subnet (avoid showing virtual network devices)
        6. Background: ping for responsiveness + DNS for hostnames

        Returns immediately (~50ms). Background tasks update cache.
        """
        now = time.time()
        if not force and (now - self._cache_time) < 10 and self._device_cache:
            return list(self._device_cache.values())

        # Refresh local MACs and gateway
        self._self_macs = self._get_all_local_macs()
        self._gateway_ip = self._get_default_gateway()

        # ARP scan
        raw_devices = await asyncio.to_thread(self._arp_scan)

        # Add self device
        self_device = self._get_self_device()
        if self_device:
            raw_devices.insert(0, self_device)

        # === Deduplicate and filter ===
        primary_subnet_str = self.get_local_subnet()
        primary_network: Optional[ipaddress.IPv4Network] = None
        if primary_subnet_str:
            try:
                primary_network = ipaddress.IPv4Network(primary_subnet_str, strict=False)
            except Exception:
                pass

        # Deduplicate by MAC, keeping the entry with the most info
        # Priority: in primary subnet > has hostname > most recent
        by_mac: dict[str, LocalDevice] = {}
        for d in raw_devices:
            mac = d.mac_address.upper()

            # Skip if MAC matches one of our local interface MACs (it's our own machine, not a separate device)
            # but DON'T skip the actual is_self entry (that's our own primary interface)
            if not d.is_self and mac in self._self_macs:
                continue

            existing = by_mac.get(mac)
            if existing is None:
                by_mac[mac] = d
                continue

            # Resolve which entry to keep
            new_in_primary = (
                primary_network is not None
                and self._is_in_network(d.ip_address, primary_network)
            )
            existing_in_primary = (
                primary_network is not None
                and self._is_in_network(existing.ip_address, primary_network)
            )

            # Prefer in-primary-subnet entry
            if new_in_primary and not existing_in_primary:
                by_mac[mac] = d
            elif new_in_primary == existing_in_primary:
                # Both in or both out - prefer one with hostname
                if d.hostname and not existing.hostname:
                    by_mac[mac] = d

        deduplicated = list(by_mac.values())

        # === Mark gateway ===
        if self._gateway_ip:
            for d in deduplicated:
                if d.ip_address == self._gateway_ip:
                    d.is_gateway = True
                    if not d.hostname:
                        d.hostname = "Router/Gateway"

        # === Restore previous responsiveness from cache ===
        for d in deduplicated:
            if d.is_self or d.is_gateway:
                d.is_responsive = True
            elif d.mac_address in self._device_cache:
                cached = self._device_cache[d.mac_address]
                d.is_responsive = cached.is_responsive
                if not d.hostname and cached.hostname:
                    d.hostname = cached.hostname

            if d.mac_address not in _device_traffic:
                _device_traffic[d.mac_address] = {"bytes_total": 0}
            d.bytes_total = _device_traffic[d.mac_address]["bytes_total"]

        # Sort: self first, then gateway, then by IP
        def sort_key(d: LocalDevice) -> tuple:
            if d.is_self:
                return (0, "")
            if d.is_gateway:
                return (1, "")
            try:
                ip_int = int(ipaddress.IPv4Address(d.ip_address))
                return (2, ip_int)
            except Exception:
                return (3, d.ip_address)

        deduplicated.sort(key=sort_key)

        # Update cache
        self._device_cache = {d.mac_address: d for d in deduplicated}
        self._cache_time = now

        # Schedule background enrichment (ping + hostname resolution)
        asyncio.create_task(self._enrich_devices_background(deduplicated))

        return deduplicated

    @staticmethod
    def _is_in_network(ip: str, network: ipaddress.IPv4Network) -> bool:
        """Check if an IP belongs to a network."""
        try:
            return ipaddress.IPv4Address(ip) in network
        except Exception:
            return False

    async def _enrich_devices_background(self, devices: list[LocalDevice]) -> None:
        """Background task: ping devices and resolve hostnames.

        Updates the cache so next API call returns enriched data.
        Doesn't block the API response.
        """
        # Ping responsiveness for non-self, non-gateway devices
        targets = [d for d in devices if not d.is_self and not d.is_gateway]
        if targets:
            try:
                ping_tasks = [
                    asyncio.to_thread(self._ping_device, d.ip_address) for d in targets
                ]
                ping_results = await asyncio.wait_for(
                    asyncio.gather(*ping_tasks, return_exceptions=True),
                    timeout=4.0,
                )
                for d, result in zip(targets, ping_results):
                    is_responsive = bool(result) and not isinstance(result, Exception)
                    d.is_responsive = is_responsive
                    if d.mac_address in self._device_cache:
                        self._device_cache[d.mac_address].is_responsive = is_responsive
            except Exception as e:
                logger.debug(f"Background ping failed: {e}")

        # Resolve hostnames for devices without hostname
        no_hostname = [d for d in devices if not d.hostname and not d.is_self]
        if no_hostname:
            try:
                hostname_tasks = [
                    asyncio.to_thread(self._resolve_hostname, d.ip_address)
                    for d in no_hostname
                ]
                hostname_results = await asyncio.wait_for(
                    asyncio.gather(*hostname_tasks, return_exceptions=True),
                    timeout=4.0,
                )
                for d, hostname in zip(no_hostname, hostname_results):
                    if hostname and not isinstance(hostname, Exception):
                        d.hostname = hostname
                        if d.mac_address in self._device_cache:
                            self._device_cache[d.mac_address].hostname = hostname
            except Exception as e:
                logger.debug(f"Background hostname resolution failed: {e}")

    def _ping_device(self, ip: str) -> bool:
        """Quick ping check (for responsiveness)."""
        try:
            import platform

            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
            timeout_value = "300" if platform.system().lower() == "windows" else "1"
            result = subprocess.run(
                ["ping", param, "1", timeout_param, timeout_value, ip],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _arp_scan(self) -> list[LocalDevice]:
        """Run ARP scan to find devices on local network.

        Fast: only reads system ARP table, no DNS lookups.
        Filters multicast/broadcast and zero MACs.
        """
        devices: list[LocalDevice] = []

        try:
            import platform

            if platform.system().lower() == "windows":
                result = subprocess.run(
                    ["arp", "-a"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                output = result.stdout
                for line in output.splitlines():
                    match = re.search(
                        r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})",
                        line,
                    )
                    if match:
                        ip, mac = match.groups()
                        mac_formatted = mac.replace("-", ":").upper()
                        if not self._is_real_device_mac(mac_formatted):
                            continue
                        if not self._is_real_device_ip(ip):
                            continue
                        cached = self._device_cache.get(mac_formatted)
                        hostname = cached.hostname if cached else None
                        devices.append(
                            LocalDevice(
                                ip_address=ip,
                                mac_address=mac_formatted,
                                hostname=hostname,
                                manufacturer=lookup_manufacturer(mac_formatted),
                            )
                        )
            else:
                result = subprocess.run(
                    ["arp", "-n"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                for line in result.stdout.splitlines():
                    match = re.search(
                        r"(\d+\.\d+\.\d+\.\d+)\s+\S+\s+([0-9a-fA-F:]{17})",
                        line,
                    )
                    if match:
                        ip, mac = match.groups()
                        mac_formatted = mac.upper()
                        if not self._is_real_device_mac(mac_formatted):
                            continue
                        if not self._is_real_device_ip(ip):
                            continue
                        cached = self._device_cache.get(mac_formatted)
                        hostname = cached.hostname if cached else None
                        devices.append(
                            LocalDevice(
                                ip_address=ip,
                                mac_address=mac_formatted,
                                hostname=hostname,
                                manufacturer=lookup_manufacturer(mac_formatted),
                            )
                        )
        except Exception as e:
            logger.warning(f"ARP scan failed: {e}")

        return devices

    @staticmethod
    def _is_real_device_mac(mac: str) -> bool:
        """Filter out multicast/broadcast/zero MAC addresses."""
        # Broadcast
        if mac == "FF:FF:FF:FF:FF:FF":
            return False
        # Zero MAC
        if mac == "00:00:00:00:00:00":
            return False
        # IPv4 multicast (01:00:5E:xx:xx:xx)
        if mac.startswith("01:00:5E"):
            return False
        # IPv6 multicast (33:33:xx:xx:xx:xx)
        if mac.startswith("33:33"):
            return False
        # Spanning tree, LLDP, etc. (01:80:C2)
        if mac.startswith("01:80:C2"):
            return False
        return True

    @staticmethod
    def _is_real_device_ip(ip: str) -> bool:
        """Filter out broadcast/multicast/network IPs."""
        if ip == "255.255.255.255":
            return False
        # Multicast range 224.0.0.0/4
        try:
            first_octet = int(ip.split(".")[0])
            if 224 <= first_octet <= 239:
                return False
        except (ValueError, IndexError):
            return False
        # Network address (last octet 0)
        if ip.endswith(".0"):
            return False
        # Broadcast (last octet 255)
        if ip.endswith(".255"):
            return False
        return True

    def _resolve_hostname(self, ip: str) -> Optional[str]:
        """Resolve hostname via reverse DNS (with timeout)."""
        try:
            socket.setdefaulttimeout(0.5)
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, socket.timeout, OSError):
            return None
        finally:
            socket.setdefaulttimeout(None)


# === OUI Database for manufacturer lookup ===

OUI_DATABASE: dict[str, str] = {
    # Apple
    "9C:2F:9D": "Liteon (laptop WiFi)",
    "00:03:93": "Apple", "00:05:02": "Apple", "00:0A:27": "Apple", "00:0A:95": "Apple",
    "00:0D:93": "Apple", "00:10:FA": "Apple", "00:11:24": "Apple", "00:14:51": "Apple",
    "00:16:CB": "Apple", "00:17:F2": "Apple", "00:19:E3": "Apple", "00:1B:63": "Apple",
    "00:1D:4F": "Apple", "00:1E:52": "Apple", "00:1E:C2": "Apple", "00:1F:5B": "Apple",
    "00:1F:F3": "Apple", "00:21:E9": "Apple", "00:22:41": "Apple", "00:23:12": "Apple",
    "00:23:32": "Apple", "00:23:6C": "Apple", "00:23:DF": "Apple", "00:24:36": "Apple",
    "00:25:00": "Apple", "00:25:4B": "Apple", "00:25:BC": "Apple", "00:26:08": "Apple",
    "00:26:4A": "Apple", "00:26:B0": "Apple", "00:26:BB": "Apple", "00:88:65": "Apple",
    "AC:DE:48": "Apple", "F0:18:98": "Apple", "F4:0F:24": "Apple", "F8:1E:DF": "Apple",
    "FC:FC:48": "Apple",
    # Samsung
    "00:00:F0": "Samsung", "00:07:AB": "Samsung", "00:0D:AE": "Samsung", "00:12:47": "Samsung",
    "00:12:FB": "Samsung", "00:13:77": "Samsung", "00:15:99": "Samsung", "00:15:B9": "Samsung",
    "00:16:32": "Samsung", "00:16:6B": "Samsung", "00:16:6C": "Samsung", "00:16:DB": "Samsung",
    "00:17:C9": "Samsung", "00:17:D5": "Samsung", "00:18:AF": "Samsung", "00:1A:8A": "Samsung",
    "00:1B:98": "Samsung", "00:1C:43": "Samsung", "00:1D:25": "Samsung", "00:1D:F6": "Samsung",
    "00:1E:7D": "Samsung", "00:1E:E1": "Samsung", "00:1E:E2": "Samsung", "00:1F:CC": "Samsung",
    "00:21:19": "Samsung", "00:21:4C": "Samsung", "00:21:D1": "Samsung", "00:21:D2": "Samsung",
    "00:23:39": "Samsung", "00:23:99": "Samsung", "00:23:D6": "Samsung", "00:24:54": "Samsung",
    "00:24:90": "Samsung", "00:24:91": "Samsung", "00:25:38": "Samsung", "00:25:67": "Samsung",
    "00:26:37": "Samsung",
    # TP-Link
    "00:14:78": "TP-Link", "00:19:E0": "TP-Link", "00:1D:0F": "TP-Link", "00:21:27": "TP-Link",
    "00:23:CD": "TP-Link", "00:25:86": "TP-Link", "00:27:19": "TP-Link", "14:CC:20": "TP-Link",
    "14:CF:E2": "TP-Link", "30:B5:C2": "TP-Link", "50:C7:BF": "TP-Link", "60:E3:27": "TP-Link",
    "64:66:B3": "TP-Link",
    # Cisco/Linksys
    "00:0F:66": "Cisco-Linksys", "00:13:10": "Cisco-Linksys", "00:14:BF": "Cisco-Linksys",
    "00:18:39": "Cisco-Linksys", "00:18:F8": "Cisco-Linksys", "00:1A:70": "Cisco-Linksys",
    "00:1C:10": "Cisco-Linksys", "00:1D:7E": "Cisco-Linksys", "00:1E:E5": "Cisco-Linksys",
    "00:21:29": "Cisco-Linksys", "00:22:6B": "Cisco-Linksys", "00:23:69": "Cisco-Linksys",
    "00:25:9C": "Cisco-Linksys", "00:00:0C": "Cisco", "00:01:42": "Cisco", "00:01:43": "Cisco",
    # NETGEAR
    "00:14:6C": "NETGEAR", "00:18:4D": "NETGEAR", "00:1B:2F": "NETGEAR", "00:1E:2A": "NETGEAR",
    "00:1F:33": "NETGEAR", "00:22:3F": "NETGEAR", "00:24:B2": "NETGEAR", "00:26:F2": "NETGEAR",
    "20:E5:2A": "NETGEAR",
    # MikroTik
    "C8:1F:66": "MikroTik", "4C:5E:0C": "MikroTik", "B8:69:F4": "MikroTik", "DC:2C:6E": "MikroTik",
    "E4:8D:8C": "MikroTik", "6C:3B:6B": "MikroTik", "74:4D:28": "MikroTik", "00:0C:42": "MikroTik",
    "08:55:31": "MikroTik", "18:FD:74": "MikroTik", "2C:C8:1B": "MikroTik", "48:8F:5A": "MikroTik",
    "64:D1:54": "MikroTik",
    # Xiaomi
    "EC:08:6B": "Xiaomi", "F8:A4:5F": "Xiaomi", "F0:B4:29": "Xiaomi", "F4:F5:DB": "Xiaomi",
    "9C:99:A0": "Xiaomi", "98:FA:E3": "Xiaomi", "8C:BE:BE": "Xiaomi", "78:11:DC": "Xiaomi",
    "64:09:80": "Xiaomi", "50:8F:4C": "Xiaomi", "34:CE:00": "Xiaomi", "28:E3:1F": "Xiaomi",
    "0C:1D:AF": "Xiaomi",
    # Raspberry Pi
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "E4:5F:01": "Raspberry Pi",
    # Dell, HP
    "00:14:38": "HP", "00:21:F7": "HP", "00:1C:23": "Dell", "00:1D:09": "Dell",
    "00:21:9B": "Dell", "00:22:19": "Dell", "00:24:E8": "Dell", "00:13:72": "Dell",
    # ASUS
    "00:E0:18": "ASUS", "00:11:2F": "ASUS", "00:11:D8": "ASUS", "00:13:D4": "ASUS",
    "00:15:F2": "ASUS", "00:17:31": "ASUS", "00:18:F3": "ASUS", "00:1A:92": "ASUS",
    "00:1B:FC": "ASUS", "00:1D:60": "ASUS", "00:1E:8C": "ASUS", "00:1F:C6": "ASUS",
    "00:22:15": "ASUS", "00:23:54": "ASUS", "00:24:8C": "ASUS", "00:26:18": "ASUS",
    "1C:87:2C": "ASUS", "10:7B:44": "ASUS",
    # Microsoft / Hyper-V
    "00:15:5D": "Microsoft Hyper-V",
    "00:50:F2": "Microsoft", "00:0D:3A": "Microsoft", "00:1D:D8": "Microsoft",
    "00:25:AE": "Microsoft", "28:18:78": "Microsoft",
    # Virtual machines
    "00:50:56": "VMware", "00:0C:29": "VMware", "00:1C:42": "Parallels",
    "08:00:27": "VirtualBox",
}


def lookup_manufacturer(mac: str) -> str:
    """Look up manufacturer name from MAC address OUI prefix."""
    if not mac or len(mac) < 8:
        return "Unknown"
    prefix = mac[:8].upper()
    name = OUI_DATABASE.get(prefix)
    if name:
        return name

    # Check if it's a randomized/locally-administered MAC
    if is_locally_administered_mac(mac):
        return "Mobile (random MAC)"

    return "Unknown"


# === Singleton ===

_monitor: Optional[NetworkMonitor] = None


def get_network_monitor() -> NetworkMonitor:
    """Get the singleton NetworkMonitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = NetworkMonitor()
    return _monitor
