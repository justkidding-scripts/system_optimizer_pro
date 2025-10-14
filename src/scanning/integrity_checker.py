#!/usr/bin/env python3
"""
Integrity Checker - System File Integrity Validation

Validates system file integrity, detects unauthorized modifications,
and ensures system consistency and security.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
import os

class IntegrityLevel(Enum):
    """Integrity violation levels"""
    CLEAN = "clean"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"

@dataclass
class IntegrityViolation:
    """Individual integrity violation"""
    violation_id: str
    file_path: str
    violation_type: str
    level: IntegrityLevel
    description: str
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    recommendation: str = ""

@dataclass
class SystemIntegrityReport:
    """System integrity analysis report"""
    report_id: str
    timestamp: datetime
    violations: List[IntegrityViolation]
    integrity_score: int  # 0-100
    files_checked: int
    recommendations: List[str] = field(default_factory=list)

class IntegrityChecker:
    """System integrity validation checker"""
    
    def __init__(self):
        self.baseline_hashes = {}
        self.critical_files = self._get_critical_files()
    
    def _get_critical_files(self) -> List[str]:
        """Get list of critical system files to monitor"""
        import platform
        
        if platform.system().lower() == 'linux':
            return [
                '/etc/passwd',
                '/etc/shadow',
                '/etc/group',
                '/etc/sudoers',
                '/etc/hosts',
                '/etc/fstab'
            ]
        elif platform.system().lower() == 'windows':
            return [
                'C:\\Windows\\System32\\drivers\\etc\\hosts',
                'C:\\Windows\\System32\\config\\SAM'
            ]
        return []
    
    def check_integrity(self, files_to_check: Optional[List[str]] = None) -> SystemIntegrityReport:
        """Perform system integrity check"""
        if files_to_check is None:
            files_to_check = self.critical_files
        
        violations = []
        files_checked = 0
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                try:
                    violation = self._check_file_integrity(file_path)
                    if violation:
                        violations.append(violation)
                    files_checked += 1
                except Exception as e:
                    violations.append(IntegrityViolation(
                        violation_id=f"integrity_error_{files_checked}",
                        file_path=file_path,
                        violation_type="Access Error",
                        level=IntegrityLevel.MODERATE,
                        description=f"Could not check file integrity: {str(e)}",
                        recommendation="Verify file permissions and accessibility"
                    ))
        
        integrity_score = self._calculate_integrity_score(violations, files_checked)
        
        return SystemIntegrityReport(
            report_id=f"integrity_report_{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            violations=violations,
            integrity_score=integrity_score,
            files_checked=files_checked,
            recommendations=self._generate_recommendations(violations)
        )
    
    def _check_file_integrity(self, file_path: str) -> Optional[IntegrityViolation]:
        """Check integrity of individual file"""
        try:
            # Check file permissions
            stat_info = os.stat(file_path)
            
            # Check for world-writable files
            if stat_info.st_mode & 0o002:  # World writable
                return IntegrityViolation(
                    violation_id=f"perm_violation_{hash(file_path)}",
                    file_path=file_path,
                    violation_type="Permission Violation",
                    level=IntegrityLevel.SEVERE,
                    description="File is world-writable",
                    recommendation=f"Fix file permissions: chmod 644 {file_path}"
                )
            
            # Check for recent modifications of critical files
            modification_time = datetime.fromtimestamp(stat_info.st_mtime)
            time_diff = datetime.now() - modification_time
            
            if file_path in ['/etc/passwd', '/etc/shadow', '/etc/sudoers'] and time_diff.days < 1:
                return IntegrityViolation(
                    violation_id=f"mod_violation_{hash(file_path)}",
                    file_path=file_path,
                    violation_type="Recent Modification",
                    level=IntegrityLevel.MODERATE,
                    description="Critical system file recently modified",
                    recommendation="Verify if modification was authorized"
                )
        
        except Exception:
            pass
        
        return None
    
    def _calculate_integrity_score(self, violations: List[IntegrityViolation], files_checked: int) -> int:
        """Calculate system integrity score"""
        if files_checked == 0:
            return 0
        
        if not violations:
            return 100
        
        violation_weights = {
            IntegrityLevel.CRITICAL: 50,
            IntegrityLevel.SEVERE: 30,
            IntegrityLevel.MODERATE: 15,
            IntegrityLevel.MINOR: 5
        }
        
        total_impact = sum(violation_weights.get(v.level, 0) for v in violations)
        max_possible_impact = files_checked * 50  # Assume all could be critical
        
        if max_possible_impact == 0:
            return 100
        
        return max(0, 100 - int((total_impact / max_possible_impact) * 100))
    
    def _generate_recommendations(self, violations: List[IntegrityViolation]) -> List[str]:
        """Generate integrity recommendations"""
        recommendations = []
        
        if any(v.level == IntegrityLevel.CRITICAL for v in violations):
            recommendations.append("Critical integrity violations detected - immediate action required")
        
        if any(v.violation_type == "Permission Violation" for v in violations):
            recommendations.append("Fix file permission issues immediately")
        
        if any(v.violation_type == "Recent Modification" for v in violations):
            recommendations.append("Review recent modifications to critical system files")
        
        if not recommendations:
            recommendations.append("System integrity appears good - maintain monitoring")
        
        return recommendations