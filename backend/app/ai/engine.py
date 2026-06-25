"""AI Engine orchestration.

Integrates the various AI modules and exposes a clean interface for the
background stat collector to use.
"""

import logging
from typing import Optional

from app.ai.traffic_classifier import TrafficClassifier
from app.ai.anomaly_detector import AnomalyDetector
from app.ai.malware_scanner import MalwareScanner
from app.ai.health_scorer import HealthScorer

logger = logging.getLogger(__name__)


class AIEngine:
    """Orchestrates all AI network analysis features.
    
    Provides a unified interface for the stat collector to push new network
    data and receive AI insights and alerts in return.
    """

    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        
        # Initialize modules
        self.classifier = TrafficClassifier()
        self.anomaly_detector = AnomalyDetector(tenant_id)
        self.malware_scanner = MalwareScanner(tenant_id)
        self.health_scorer = HealthScorer()

    def process_network_tick(
        self, 
        bytes_recv: int, 
        bytes_sent: int,
        ping_ms: float,
        jitter_ms: float,
        active_connections: list
    ) -> dict:
        """Process a single tick of network data (called every second).
        
        Args:
            bytes_recv: Total bytes received in the last second
            bytes_sent: Total bytes sent in the last second
            ping_ms: Current latency
            jitter_ms: Current jitter
            active_connections: List of active psutil.sconn objects
            
        Returns:
            Dict containing any generated alerts and AI insights
        """
        total_volume = float(bytes_recv + bytes_sent)
        num_connections = len(active_connections)
        
        alerts = []
        
        # 1. Detect statistical anomalies
        anomaly_alert = self.anomaly_detector.detect_anomaly(
            current_volume=total_volume,
            current_connections=num_connections
        )
        if anomaly_alert:
            alerts.append(anomaly_alert)
            
        # 2. Scan for malware signatures (C2, DNS abuse)
        malware_alert = self.malware_scanner.scan_connections(active_connections)
        if malware_alert:
            alerts.append(malware_alert)
            
        # 3. Calculate health score
        # In a real deployment, we'd query the DB for active anomalies in the last 24h.
        # For real-time processing, we'll just count immediate ones.
        health = self.health_scorer.calculate_score(
            ping_ms=ping_ms,
            jitter_ms=jitter_ms,
            active_anomalies=len(alerts),
            download_mbps=(bytes_recv * 8) / 1_000_000,
            uplink_capacity_mbps=100.0  # Placeholder capacity
        )
        
        return {
            "alerts": alerts,
            "health": health
        }

    def get_traffic_distribution(self) -> dict:
        """Get the current traffic categorization distribution."""
        # This module reads psutil on its own
        return self.classifier.get_distribution_for_api()
        
    def get_baseline_status(self) -> dict:
        """Get the ML baseline learning status."""
        return self.anomaly_detector.get_baseline_status()

# Singleton instance for the background worker
_engine_instance: Optional[AIEngine] = None

def get_ai_engine() -> AIEngine:
    """Get or create the singleton AIEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AIEngine()
    return _engine_instance
