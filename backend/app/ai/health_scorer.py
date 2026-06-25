"""Network health scoring system.

Aggregates multiple metrics into a single 0-100 score:
- Ping latency
- Jitter
- Bandwidth utilization
- Anomaly count
"""

import logging

logger = logging.getLogger(__name__)

class HealthScorer:
    """Calculates an overall network health score from 0-100."""

    def calculate_score(
        self,
        ping_ms: float,
        jitter_ms: float,
        active_anomalies: int,
        download_mbps: float,
        uplink_capacity_mbps: float = 100.0,
    ) -> dict:
        """Calculate network health score.
        
        Returns:
            dict containing:
            - score: 0-100 integer
            - status: "Excellent", "Good", "Fair", "Poor", "Critical"
            - issues: List of string descriptions of problems
        """
        score = 100
        issues = []
        
        # 1. Ping Penalty (Max 30 points)
        if ping_ms == 0:
            pass # No data
        elif ping_ms > 150:
            score -= 30
            issues.append(f"High latency ({ping_ms:.0f}ms)")
        elif ping_ms > 80:
            penalty = int((ping_ms - 80) / 70 * 30)
            score -= penalty
            issues.append(f"Elevated latency ({ping_ms:.0f}ms)")
            
        # 2. Jitter Penalty (Max 20 points)
        if jitter_ms > 30:
            score -= 20
            issues.append(f"High jitter ({jitter_ms:.1f}ms)")
        elif jitter_ms > 10:
            penalty = int((jitter_ms - 10) / 20 * 20)
            score -= penalty
            
        # 3. Bandwidth Congestion Penalty (Max 25 points)
        utilization = 0.0
        if uplink_capacity_mbps > 0:
            utilization = download_mbps / uplink_capacity_mbps
            
        if utilization > 0.9:
            score -= 25
            issues.append("Network highly congested (>90%)")
        elif utilization > 0.7:
            penalty = int((utilization - 0.7) / 0.2 * 25)
            score -= penalty
            
        # 4. Security/Anomaly Penalty (Max 25 points)
        if active_anomalies > 0:
            penalty = min(25, active_anomalies * 8)
            score -= penalty
            issues.append(f"{active_anomalies} active anomalies detected")
            
        # Ensure bounds
        score = max(0, min(100, score))
        
        # Determine status text
        if score >= 90:
            status = "Excellent"
        elif score >= 75:
            status = "Good"
        elif score >= 60:
            status = "Fair"
        elif score >= 40:
            status = "Poor"
        else:
            status = "Critical"
            
        return {
            "score": score,
            "status": status,
            "issues": issues
        }
