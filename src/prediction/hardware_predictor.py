#!/usr/bin/env python3
"""
Predictive Hardware Failure Detection Module
AI-powered analysis of system telemetry to predict component failures weeks ahead
"""

import time
import json
import psutil
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.ensemble import IsolationForest, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error
    import cpuinfo
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    import pynvml
    GPU_MONITORING = True
except ImportError:
    GPU_MONITORING = False

class FailureSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"

class ComponentType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    GPU = "gpu"
    THERMAL = "thermal"
    POWER = "power"
    NETWORK = "network"

@dataclass
class HardwareMetric:
    component: ComponentType
    timestamp: float
    cpu_temp: float = 0.0
    cpu_usage: float = 0.0
    cpu_freq: float = 0.0
    memory_usage: float = 0.0
    memory_available: float = 0.0
    disk_usage: float = 0.0
    disk_io_read: float = 0.0
    disk_io_write: float = 0.0
    gpu_temp: float = 0.0
    gpu_usage: float = 0.0
    network_bytes_sent: float = 0.0
    network_bytes_recv: float = 0.0
    process_count: int = 0
    load_avg_1m: float = 0.0
    swap_usage: float = 0.0

@dataclass 
class FailurePrediction:
    component: ComponentType
    severity: FailureSeverity
    predicted_failure_date: datetime
    confidence: float
    current_health_score: float
    degradation_rate: float
    warning_signs: List[str]
    recommendations: List[str]
    time_to_failure_days: int
    anomaly_indicators: Dict[str, float]

class HardwarePredictor:
    def __init__(self, data_retention_days: int = 90):
        self.data_retention_days = data_retention_days
        self.data_dir = Path.home() / ".system_optimizer_pro" / "hardware_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_history: List[HardwareMetric] = []
        self.models: Dict[ComponentType, Any] = {}
        self.scalers: Dict[ComponentType, StandardScaler] = {}
        self.baseline_metrics: Dict[ComponentType, Dict[str, float]] = {}
        
        # Initialize GPU monitoring
        if GPU_MONITORING:
            try:
                pynvml.nvmlInit()
                self.gpu_available = True
                self.gpu_count = pynvml.nvmlDeviceGetCount()
            except:
                self.gpu_available = False
                self.gpu_count = 0
        else:
            self.gpu_available = False
            self.gpu_count = 0
        
        # Load existing data
        self.load_historical_data()
        
        # Initialize ML models if available
        if ML_AVAILABLE:
            self.initialize_models()

    def collect_current_metrics(self) -> HardwareMetric:
        """Collect current system hardware metrics"""
        current_time = time.time()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = cpu_freq.current if cpu_freq else 0.0
        
        # Get CPU temperature (Linux-specific)
        cpu_temp = self._get_cpu_temperature()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Network metrics
        network = psutil.net_io_counters()
        
        # Process metrics
        process_count = len(psutil.pids())
        
        # Load average (Linux/Unix)
        try:
            load_avg = psutil.getloadavg()[0]  # 1-minute load average
        except (AttributeError, OSError):
            load_avg = 0.0
        
        # GPU metrics
        gpu_temp, gpu_usage = self._get_gpu_metrics()
        
        return HardwareMetric(
            component=ComponentType.CPU,
            timestamp=current_time,
            cpu_temp=cpu_temp,
            cpu_usage=cpu_percent,
            cpu_freq=cpu_freq_current,
            memory_usage=memory.percent,
            memory_available=memory.available / (1024**3),  # GB
            disk_usage=disk.percent,
            disk_io_read=disk_io.read_bytes if disk_io else 0,
            disk_io_write=disk_io.write_bytes if disk_io else 0,
            gpu_temp=gpu_temp,
            gpu_usage=gpu_usage,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            process_count=process_count,
            load_avg_1m=load_avg,
            swap_usage=swap.percent
        )

    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature (Linux-specific)"""
        try:
            # Try multiple temperature sources
            temp_sources = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp',
                '/sys/class/hwmon/hwmon0/temp1_input',
                '/sys/class/hwmon/hwmon1/temp1_input'
            ]
            
            for source in temp_sources:
                temp_file = Path(source)
                if temp_file.exists():
                    temp_str = temp_file.read_text().strip()
                    temp_value = float(temp_str)
                    # Convert from millidegrees to degrees if necessary
                    if temp_value > 1000:
                        temp_value = temp_value / 1000
                    return temp_value
            
            return 0.0
        except:
            return 0.0

    def _get_gpu_metrics(self) -> Tuple[float, float]:
        """Get GPU temperature and usage"""
        if not self.gpu_available:
            return 0.0, 0.0
        
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return float(temp), float(util.gpu)
        except:
            return 0.0, 0.0

    def analyze_hardware_health(self) -> List[FailurePrediction]:
        """Analyze current hardware health and predict failures"""
        current_metrics = self.collect_current_metrics()
        self.metrics_history.append(current_metrics)
        
        # Save metrics
        self.save_metrics([current_metrics])
        
        # Clean old data
        self._cleanup_old_data()
        
        predictions = []
        
        if len(self.metrics_history) < 10:
            # Not enough data for prediction
            return self._generate_baseline_predictions(current_metrics)
        
        # Analyze each component
        for component in ComponentType:
            prediction = self._predict_component_failure(component, current_metrics)
            if prediction:
                predictions.append(prediction)
        
        return sorted(predictions, key=lambda x: x.severity.value, reverse=True)

    def _predict_component_failure(self, component: ComponentType, current: HardwareMetric) -> Optional[FailurePrediction]:
        """Predict failure for a specific component"""
        if not ML_AVAILABLE or len(self.metrics_history) < 50:
            return self._rule_based_prediction(component, current)
        
        try:
            # Prepare feature data
            features = self._extract_features_for_component(component)
            if len(features) < 10:
                return self._rule_based_prediction(component, current)
            
            # Detect anomalies
            anomalies = self._detect_anomalies(component, features)
            
            # Calculate health score
            health_score = self._calculate_health_score(component, current)
            
            # Predict degradation rate
            degradation_rate = self._calculate_degradation_rate(component)
            
            # Determine failure timeline
            time_to_failure = self._estimate_failure_timeline(health_score, degradation_rate)
            
            # Generate warnings and recommendations
            warnings_list, recommendations = self._generate_warnings_recommendations(
                component, current, anomalies, health_score
            )
            
            # Determine severity
            severity = self._determine_severity(health_score, time_to_failure, anomalies)
            
            if severity != FailureSeverity.LOW or len(warnings_list) > 0:
                predicted_date = datetime.now() + timedelta(days=time_to_failure)
                confidence = min(0.95, max(0.1, 1.0 - (health_score / 100)))
                
                return FailurePrediction(
                    component=component,
                    severity=severity,
                    predicted_failure_date=predicted_date,
                    confidence=confidence,
                    current_health_score=health_score,
                    degradation_rate=degradation_rate,
                    warning_signs=warnings_list,
                    recommendations=recommendations,
                    time_to_failure_days=time_to_failure,
                    anomaly_indicators=anomalies
                )
        except Exception as e:
            print(f"Error predicting {component.value}: {e}")
            return self._rule_based_prediction(component, current)
        
        return None

    def _rule_based_prediction(self, component: ComponentType, current: HardwareMetric) -> Optional[FailurePrediction]:
        """Fallback rule-based prediction when ML is unavailable"""
        warnings_list = []
        recommendations = []
        health_score = 100.0
        
        if component == ComponentType.CPU:
            if current.cpu_temp > 85:
                warnings_list.append("CPU temperature critically high")
                recommendations.append("Check CPU cooling system")
                health_score -= 30
            elif current.cpu_temp > 75:
                warnings_list.append("CPU temperature elevated")
                health_score -= 15
                
            if current.cpu_usage > 90:
                warnings_list.append("CPU usage consistently high")
                recommendations.append("Identify resource-intensive processes")
                health_score -= 10
                
        elif component == ComponentType.MEMORY:
            if current.memory_usage > 95:
                warnings_list.append("Memory usage critically high")
                recommendations.append("Close unnecessary applications or add more RAM")
                health_score -= 25
            elif current.memory_usage > 85:
                warnings_list.append("Memory usage high")
                health_score -= 10
                
            if current.swap_usage > 50:
                warnings_list.append("Heavy swap usage detected")
                recommendations.append("Consider upgrading RAM")
                health_score -= 15
                
        elif component == ComponentType.DISK:
            if current.disk_usage > 95:
                warnings_list.append("Disk space critically low")
                recommendations.append("Free up disk space immediately")
                health_score -= 30
            elif current.disk_usage > 85:
                warnings_list.append("Disk space running low")
                health_score -= 10
        
        if warnings_list:
            time_to_failure = max(1, int(health_score))
            severity = self._determine_severity(health_score, time_to_failure, {})
            predicted_date = datetime.now() + timedelta(days=time_to_failure)
            
            return FailurePrediction(
                component=component,
                severity=severity,
                predicted_failure_date=predicted_date,
                confidence=0.7,
                current_health_score=health_score,
                degradation_rate=1.0,
                warning_signs=warnings_list,
                recommendations=recommendations,
                time_to_failure_days=time_to_failure,
                anomaly_indicators={}
            )
        
        return None

    def _extract_features_for_component(self, component: ComponentType) -> np.ndarray:
        """Extract relevant features for component analysis"""
        if not self.metrics_history:
            return np.array([])
        
        features = []
        for metric in self.metrics_history[-100:]:  # Last 100 data points
            if component == ComponentType.CPU:
                features.append([
                    metric.cpu_temp, metric.cpu_usage, metric.cpu_freq,
                    metric.load_avg_1m, metric.process_count
                ])
            elif component == ComponentType.MEMORY:
                features.append([
                    metric.memory_usage, metric.memory_available, 
                    metric.swap_usage, metric.process_count
                ])
            elif component == ComponentType.DISK:
                features.append([
                    metric.disk_usage, metric.disk_io_read, 
                    metric.disk_io_write
                ])
            elif component == ComponentType.GPU and self.gpu_available:
                features.append([
                    metric.gpu_temp, metric.gpu_usage
                ])
        
        return np.array(features) if features else np.array([])

    def _detect_anomalies(self, component: ComponentType, features: np.ndarray) -> Dict[str, float]:
        """Detect anomalies in component behavior"""
        if len(features) < 10:
            return {}
        
        try:
            # Use Isolation Forest for anomaly detection
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_scores = iso_forest.fit_predict(features)
            
            # Calculate anomaly metrics
            anomaly_ratio = np.sum(anomaly_scores == -1) / len(anomaly_scores)
            
            # Recent anomalies (last 20% of data)
            recent_size = max(1, len(features) // 5)
            recent_anomalies = anomaly_scores[-recent_size:]
            recent_anomaly_ratio = np.sum(recent_anomalies == -1) / len(recent_anomalies)
            
            return {
                'overall_anomaly_ratio': anomaly_ratio,
                'recent_anomaly_ratio': recent_anomaly_ratio,
                'anomaly_trend': recent_anomaly_ratio - anomaly_ratio
            }
        except:
            return {}

    def _calculate_health_score(self, component: ComponentType, current: HardwareMetric) -> float:
        """Calculate current health score for component"""
        base_score = 100.0
        
        if component == ComponentType.CPU:
            # Temperature penalties
            if current.cpu_temp > 85:
                base_score -= 40
            elif current.cpu_temp > 75:
                base_score -= 20
            elif current.cpu_temp > 65:
                base_score -= 10
                
            # Usage penalties
            if current.cpu_usage > 95:
                base_score -= 15
            elif current.cpu_usage > 85:
                base_score -= 8
                
        elif component == ComponentType.MEMORY:
            if current.memory_usage > 95:
                base_score -= 30
            elif current.memory_usage > 85:
                base_score -= 15
                
            if current.swap_usage > 75:
                base_score -= 20
            elif current.swap_usage > 50:
                base_score -= 10
                
        elif component == ComponentType.DISK:
            if current.disk_usage > 95:
                base_score -= 35
            elif current.disk_usage > 85:
                base_score -= 20
            elif current.disk_usage > 75:
                base_score -= 10
        
        return max(0.0, min(100.0, base_score))

    def _calculate_degradation_rate(self, component: ComponentType) -> float:
        """Calculate degradation rate per day"""
        if len(self.metrics_history) < 20:
            return 0.1  # Default low degradation
        
        try:
            # Analyze health score trend over time
            recent_health = []
            for i in range(-20, 0):  # Last 20 data points
                metric = self.metrics_history[i]
                health = self._calculate_health_score(component, metric)
                recent_health.append(health)
            
            # Calculate linear trend
            x = np.arange(len(recent_health))
            slope, _ = np.polyfit(x, recent_health, 1)
            
            # Convert to daily degradation rate
            degradation_per_sample = -slope  # Negative slope means degradation
            samples_per_day = 24 * 6  # Assuming 10-minute intervals
            degradation_rate = max(0.01, degradation_per_sample * samples_per_day)
            
            return min(5.0, degradation_rate)  # Cap at 5% per day
        except:
            return 0.1

    def _estimate_failure_timeline(self, health_score: float, degradation_rate: float) -> int:
        """Estimate days until potential failure"""
        if degradation_rate <= 0:
            return 365  # Very stable
        
        # Calculate days until health score reaches critical threshold (20%)
        critical_threshold = 20.0
        days_to_critical = max(1, int((health_score - critical_threshold) / degradation_rate))
        
        # Add some randomness and bounds
        days_to_critical = max(1, min(365, days_to_critical))
        
        return days_to_critical

    def _determine_severity(self, health_score: float, days_to_failure: int, anomalies: Dict[str, float]) -> FailureSeverity:
        """Determine failure prediction severity"""
        if health_score < 30 or days_to_failure < 7:
            return FailureSeverity.CRITICAL
        elif health_score < 50 or days_to_failure < 21:
            return FailureSeverity.HIGH
        elif health_score < 70 or days_to_failure < 60:
            return FailureSeverity.MEDIUM
        else:
            return FailureSeverity.LOW

    def _generate_warnings_recommendations(self, component: ComponentType, current: HardwareMetric, 
                                         anomalies: Dict[str, float], health_score: float) -> Tuple[List[str], List[str]]:
        """Generate specific warnings and recommendations"""
        warnings_list = []
        recommendations = []
        
        if component == ComponentType.CPU:
            if current.cpu_temp > 80:
                warnings_list.append(f"CPU temperature at {current.cpu_temp:.1f}°C")
                recommendations.append("Clean CPU cooler and check thermal paste")
                recommendations.append("Verify case ventilation and fan operation")
                
            if current.cpu_usage > 90:
                warnings_list.append("CPU usage consistently above 90%")
                recommendations.append("Identify and optimize resource-intensive processes")
                
            if anomalies.get('recent_anomaly_ratio', 0) > 0.3:
                warnings_list.append("Unusual CPU behavior patterns detected")
                recommendations.append("Monitor for hardware instability signs")
                
        elif component == ComponentType.MEMORY:
            if current.memory_usage > 90:
                warnings_list.append("Memory usage critically high")
                recommendations.append("Close unnecessary applications")
                recommendations.append("Consider RAM upgrade")
                
            if current.swap_usage > 50:
                warnings_list.append("Heavy swap file usage")
                recommendations.append("Increase physical RAM capacity")
                
        elif component == ComponentType.DISK:
            if current.disk_usage > 90:
                warnings_list.append("Disk space critically low")
                recommendations.append("Clean temporary files and logs")
                recommendations.append("Move large files to external storage")
                recommendations.append("Consider storage expansion")
        
        return warnings_list, recommendations

    def _generate_baseline_predictions(self, current: HardwareMetric) -> List[FailurePrediction]:
        """Generate basic predictions with insufficient data"""
        predictions = []
        
        # Basic CPU check
        if current.cpu_temp > 75:
            predictions.append(FailurePrediction(
                component=ComponentType.CPU,
                severity=FailureSeverity.MEDIUM,
                predicted_failure_date=datetime.now() + timedelta(days=30),
                confidence=0.5,
                current_health_score=70.0,
                degradation_rate=1.0,
                warning_signs=["High CPU temperature detected"],
                recommendations=["Monitor thermal conditions", "Check cooling system"],
                time_to_failure_days=30,
                anomaly_indicators={}
            ))
        
        return predictions

    def save_metrics(self, metrics: List[HardwareMetric]):
        """Save metrics to persistent storage"""
        metrics_file = self.data_dir / "hardware_metrics.jsonl"
        
        with open(metrics_file, 'a') as f:
            for metric in metrics:
                f.write(json.dumps(asdict(metric)) + '\n')

    def load_historical_data(self):
        """Load historical metrics data"""
        metrics_file = self.data_dir / "hardware_metrics.jsonl"
        
        if not metrics_file.exists():
            return
        
        try:
            with open(metrics_file, 'r') as f:
                for line in f:
                    data = json.loads(line.strip())
                    # Convert component string back to enum
                    data['component'] = ComponentType(data['component'])
                    metric = HardwareMetric(**data)
                    self.metrics_history.append(metric)
            
            print(f"Loaded {len(self.metrics_history)} historical data points")
        except Exception as e:
            print(f"Error loading historical data: {e}")

    def _cleanup_old_data(self):
        """Remove data older than retention period"""
        cutoff_time = time.time() - (self.data_retention_days * 24 * 3600)
        self.metrics_history = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]

    def initialize_models(self):
        """Initialize ML models for each component"""
        if not ML_AVAILABLE:
            return
            
        for component in ComponentType:
            self.scalers[component] = StandardScaler()
            # Models will be trained when enough data is available

    def get_component_status_summary(self) -> Dict[str, Any]:
        """Get summary status of all components"""
        predictions = self.analyze_hardware_health()
        
        summary = {
            'overall_health': 100.0,
            'components': {},
            'critical_issues': 0,
            'warnings': 0,
            'next_maintenance': None
        }
        
        for prediction in predictions:
            component_name = prediction.component.value
            summary['components'][component_name] = {
                'health_score': prediction.current_health_score,
                'severity': prediction.severity.value,
                'time_to_failure_days': prediction.time_to_failure_days,
                'warnings': len(prediction.warning_signs)
            }
            
            # Update overall metrics
            if prediction.severity == FailureSeverity.CRITICAL:
                summary['critical_issues'] += 1
            elif prediction.severity in [FailureSeverity.HIGH, FailureSeverity.MEDIUM]:
                summary['warnings'] += 1
                
            # Update overall health (minimum of all components)
            summary['overall_health'] = min(
                summary['overall_health'], 
                prediction.current_health_score
            )
            
            # Track next maintenance needed
            if (not summary['next_maintenance'] or 
                prediction.time_to_failure_days < summary['next_maintenance']):
                summary['next_maintenance'] = prediction.time_to_failure_days
        
        return summary

def main():
    """Test the hardware predictor"""
    print("🔮 Hardware Failure Prediction System")
    print("=" * 50)
    
    predictor = HardwarePredictor()
    
    print("📊 Analyzing current hardware health...")
    predictions = predictor.analyze_hardware_health()
    
    if not predictions:
        print("✅ All hardware components appear healthy!")
        return
    
    print(f"\n🎯 Found {len(predictions)} potential issues:")
    
    for i, prediction in enumerate(predictions, 1):
        print(f"\n{i}. {prediction.component.value.upper()} - {prediction.severity.value.upper()}")
        print(f"   Health Score: {prediction.current_health_score:.1f}/100")
        print(f"   Predicted Failure: {prediction.predicted_failure_date.strftime('%Y-%m-%d')}")
        print(f"   Confidence: {prediction.confidence:.0%}")
        print(f"   Days to Failure: {prediction.time_to_failure_days}")
        
        if prediction.warning_signs:
            print(f"   ⚠️  Warning Signs:")
            for warning in prediction.warning_signs:
                print(f"      • {warning}")
        
        if prediction.recommendations:
            print(f"   🔧 Recommendations:")
            for rec in prediction.recommendations:
                print(f"      • {rec}")

if __name__ == "__main__":
    main()
