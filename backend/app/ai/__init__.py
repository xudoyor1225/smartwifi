"""AI Core Package for Network Analysis.

Modules:
- traffic_classifier: Port-based traffic classification (Video, Social Media, etc.)
- anomaly_detector: Statistical anomaly detection using Isolation Forest
- health_scorer: Network health score calculator (0-100)
- malware_scanner: Suspicious network pattern detector
- engine: AI orchestration engine (integrates with BackgroundStatCollector)
"""

from app.ai.traffic_classifier import TrafficClassifier
from app.ai.anomaly_detector import AnomalyDetector
from app.ai.health_scorer import HealthScorer
from app.ai.malware_scanner import MalwareScanner
from app.ai.engine import AIEngine

__all__ = [
    "TrafficClassifier",
    "AnomalyDetector",
    "HealthScorer",
    "MalwareScanner",
    "AIEngine",
]
