#!/usr/bin/env python3
"""
Thermal Management Gaming Module
Performance optimization that treats CPU/GPU temps like a competitive game with scoring, achievements, and leaderboards
"""

import time
import psutil
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import subprocess

try:
    import pygame
    import numpy as np
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.live import Live
    from rich.layout import Layout
    GAMING_UI_AVAILABLE = True
    console = Console()
except ImportError:
    GAMING_UI_AVAILABLE = False

try:
    import pynvml
    GPU_MONITORING = True
except ImportError:
    GPU_MONITORING = False

class ThermalChallenge(Enum):
    COOL_RUNNER = "cool_runner"          # Keep temps below threshold
    EFFICIENCY_MASTER = "efficiency_master"  # Balance performance/temp
    STRESS_SURVIVOR = "stress_survivor"   # Survive high load
    SILENT_OPERATOR = "silent_operator"   # Low fan noise + temp
    OVERCLOCKED_BEAST = "overclocked_beast"  # Max performance safely

class Achievement(Enum):
    FIRST_VICTORY = "first_victory"
    TEMPERATURE_TAMER = "temperature_tamer"
    EFFICIENCY_EXPERT = "efficiency_expert"
    MARATHON_RUNNER = "marathon_runner"
    PERFECT_BALANCE = "perfect_balance"
    ICE_COLD = "ice_cold"
    POWER_SAVER = "power_saver"
    MULTITASKING_MASTER = "multitasking_master"
    THERMAL_NINJA = "thermal_ninja"
    LEGENDARY_COOLER = "legendary_cooler"

@dataclass
class GameSession:
    session_id: str
    start_time: float
    end_time: Optional[float]
    challenge: ThermalChallenge
    target_program: Optional[str]
    score: int
    max_cpu_temp: float
    max_gpu_temp: float
    avg_cpu_temp: float
    avg_gpu_temp: float
    achievements_earned: List[Achievement]
    performance_points: int
    efficiency_rating: float
    completed: bool = False

@dataclass
class ThermalMetrics:
    timestamp: float
    cpu_temp: float
    gpu_temp: float
    cpu_usage: float
    gpu_usage: float
    cpu_freq: float
    fan_speed: float
    power_draw: float
    ambient_temp: float = 25.0  # Default room temperature

@dataclass
class PlayerStats:
    total_sessions: int
    best_score: int
    total_playtime: float
    achievements: List[Achievement]
    level: int
    experience_points: int
    thermal_mastery_rating: float
    favorite_challenge: ThermalChallenge
    current_streak: int

class ThermalGameEngine:
    def __init__(self):
        self.data_dir = Path.home() / ".system_optimizer_pro" / "thermal_gaming"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Game state
        self.current_session: Optional[GameSession] = None
        self.player_stats = self.load_player_stats()
        self.metrics_history: List[ThermalMetrics] = []
        self.running = False
        self.target_process: Optional[str] = None
        
        # Scoring system
        self.base_score = 1000
        self.temp_penalty_threshold = 75.0  # °C
        self.efficiency_bonus_threshold = 0.8
        
        # Challenge parameters
        self.challenge_configs = {
            ThermalChallenge.COOL_RUNNER: {
                "max_temp": 65.0,
                "duration": 300,  # 5 minutes
                "score_multiplier": 1.0,
                "description": "Keep CPU/GPU below 65°C for 5 minutes"
            },
            ThermalChallenge.EFFICIENCY_MASTER: {
                "min_efficiency": 0.85,
                "duration": 600,  # 10 minutes
                "score_multiplier": 1.5,
                "description": "Maintain >85% efficiency for 10 minutes"
            },
            ThermalChallenge.STRESS_SURVIVOR: {
                "min_load": 80.0,
                "max_temp": 85.0,
                "duration": 180,  # 3 minutes
                "score_multiplier": 2.0,
                "description": "Survive high load while keeping temps safe"
            },
            ThermalChallenge.SILENT_OPERATOR: {
                "max_fan_speed": 50.0,
                "max_temp": 70.0,
                "duration": 900,  # 15 minutes
                "score_multiplier": 1.3,
                "description": "Low noise operation with good cooling"
            },
            ThermalChallenge.OVERCLOCKED_BEAST: {
                "min_performance": 110.0,  # % of base performance
                "max_temp": 80.0,
                "duration": 240,  # 4 minutes
                "score_multiplier": 2.5,
                "description": "Push limits safely with overclocking"
            }
        }
        
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

    def start_gaming_interface(self):
        """Start the thermal gaming interface"""
        if GAMING_UI_AVAILABLE:
            self._start_rich_interface()
        else:
            self._start_simple_interface()

    def _start_rich_interface(self):
        """Start the rich terminal interface"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=5)
        )
        
        layout["main"].split_row(
            Layout(name="game", ratio=2),
            Layout(name="stats", ratio=1)
        )
        
        with Live(layout, refresh_per_second=4, screen=True):
            while True:
                try:
                    # Update header
                    layout["header"].update(Panel(
                        "🎮 THERMAL MANAGEMENT GAMING - System Performance Challenge",
                        style="bold green"
                    ))
                    
                    # Update main game area
                    if self.current_session:
                        game_panel = self._create_game_panel()
                    else:
                        game_panel = self._create_menu_panel()
                    layout["game"].update(game_panel)
                    
                    # Update stats
                    stats_panel = self._create_stats_panel()
                    layout["stats"].update(stats_panel)
                    
                    # Update footer
                    footer_panel = self._create_footer_panel()
                    layout["footer"].update(footer_panel)
                    
                    # Check for user input (simplified)
                    if not self.current_session:
                        choice = self._get_menu_choice()
                        if choice:
                            self._handle_menu_choice(choice)
                    else:
                        self._update_current_session()
                    
                    time.sleep(0.25)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    time.sleep(1)

    def _create_menu_panel(self) -> Panel:
        """Create main menu panel"""
        menu_text = """
🎯 THERMAL CHALLENGES AVAILABLE:

1. 🏃 Cool Runner - Keep temps below 65°C (5min)
2. ⚡ Efficiency Master - Maintain >85% efficiency (10min) 
3. 💪 Stress Survivor - High load + safe temps (3min)
4. 🤫 Silent Operator - Low noise cooling (15min)
5. 🚀 Overclocked Beast - Push limits safely (4min)

6. 📊 View Player Stats
7. 🏆 View Achievements
8. ⚙️  Configure Target Program
9. ❌ Exit

Select Challenge: """
        return Panel(menu_text, title="Main Menu", border_style="cyan")

    def _create_game_panel(self) -> Panel:
        """Create active game panel"""
        session = self.current_session
        config = self.challenge_configs[session.challenge]
        
        # Get current metrics
        current_metrics = self._collect_current_metrics()
        elapsed = time.time() - session.start_time
        remaining = config["duration"] - elapsed
        
        progress = min(100, (elapsed / config["duration"]) * 100)
        
        game_text = f"""
🎮 CHALLENGE: {session.challenge.value.replace('_', ' ').title()}
📝 {config['description']}

⏱️  TIME: {remaining:.0f}s remaining ({progress:.1f}% complete)
🎯 SCORE: {session.score:,} points

🌡️  CURRENT TEMPERATURES:
   🖥️  CPU: {current_metrics.cpu_temp:.1f}°C
   🎮 GPU: {current_metrics.gpu_temp:.1f}°C

📊 PERFORMANCE:
   💻 CPU Usage: {current_metrics.cpu_usage:.1f}%
   🎮 GPU Usage: {current_metrics.gpu_usage:.1f}%
   🌀 Fan Speed: {current_metrics.fan_speed:.0f}%

🏆 CHALLENGE STATUS:
   {self._get_challenge_status_text(session, current_metrics)}
"""
        
        # Color based on performance
        border_color = "green"
        if current_metrics.cpu_temp > 80 or current_metrics.gpu_temp > 80:
            border_color = "red"
        elif current_metrics.cpu_temp > 70 or current_metrics.gpu_temp > 70:
            border_color = "yellow"
        
        return Panel(game_text, title=f"ACTIVE CHALLENGE", border_style=border_color)

    def _create_stats_panel(self) -> Panel:
        """Create player stats panel"""
        stats = self.player_stats
        
        stats_table = Table(title="Player Profile")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="yellow")
        
        stats_table.add_row("Level", f"{stats.level}")
        stats_table.add_row("Experience", f"{stats.experience_points:,} XP")
        stats_table.add_row("Best Score", f"{stats.best_score:,}")
        stats_table.add_row("Total Sessions", f"{stats.total_sessions}")
        stats_table.add_row("Playtime", f"{stats.total_playtime/3600:.1f}h")
        stats_table.add_row("Mastery Rating", f"{stats.thermal_mastery_rating:.1f}")
        stats_table.add_row("Current Streak", f"{stats.current_streak}")
        stats_table.add_row("Achievements", f"{len(stats.achievements)}/10")
        
        return Panel(stats_table)

    def _create_footer_panel(self) -> Panel:
        """Create footer with controls and tips"""
        if self.current_session:
            footer_text = """
🎮 CONTROLS: Press 'q' to quit challenge, 'p' to pause
💡 TIP: Monitor temperatures closely - overheating will end the challenge!
🏆 Earn bonus points for maintaining optimal performance ranges
"""
        else:
            footer_text = """
🎮 CONTROLS: Type number + Enter to select, 'q' to quit
💡 TIP: Start with Cool Runner challenge to learn the basics!
🔧 Configure target programs to focus cooling on specific applications
"""
        
        return Panel(footer_text, title="Help & Controls", border_style="blue")

    def _get_menu_choice(self) -> Optional[str]:
        """Get menu choice from user (simplified for demo)"""
        # In a real implementation, this would handle actual input
        # For now, we'll simulate some choices
        return None

    def _handle_menu_choice(self, choice: str):
        """Handle user menu selection"""
        try:
            choice_num = int(choice)
            
            if 1 <= choice_num <= 5:
                challenge_list = list(ThermalChallenge)
                challenge = challenge_list[choice_num - 1]
                self.start_challenge(challenge)
            elif choice_num == 6:
                self._show_player_stats()
            elif choice_num == 7:
                self._show_achievements()
            elif choice_num == 8:
                self._configure_target_program()
            elif choice_num == 9:
                exit(0)
                
        except ValueError:
            pass

    def start_challenge(self, challenge: ThermalChallenge, target_program: Optional[str] = None):
        """Start a thermal challenge"""
        session_id = f"session_{int(time.time())}"
        
        self.current_session = GameSession(
            session_id=session_id,
            start_time=time.time(),
            end_time=None,
            challenge=challenge,
            target_program=target_program or self.target_process,
            score=self.base_score,
            max_cpu_temp=0.0,
            max_gpu_temp=0.0,
            avg_cpu_temp=0.0,
            avg_gpu_temp=0.0,
            achievements_earned=[],
            performance_points=0,
            efficiency_rating=0.0
        )
        
        # Start monitoring thread
        self.running = True
        monitor_thread = threading.Thread(target=self._challenge_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        console.print(f"🚀 Started challenge: {challenge.value}")

    def _challenge_monitor(self):
        """Monitor challenge progress and scoring"""
        session = self.current_session
        config = self.challenge_configs[session.challenge]
        
        start_time = session.start_time
        duration = config["duration"]
        
        temp_readings = []
        performance_readings = []
        
        while self.running and time.time() - start_time < duration:
            # Collect metrics
            metrics = self._collect_current_metrics()
            self.metrics_history.append(metrics)
            temp_readings.append((metrics.cpu_temp, metrics.gpu_temp))
            
            # Update session stats
            session.max_cpu_temp = max(session.max_cpu_temp, metrics.cpu_temp)
            session.max_gpu_temp = max(session.max_gpu_temp, metrics.gpu_temp)
            
            # Calculate current score
            session.score = self._calculate_current_score(session, metrics, config)
            
            # Check challenge-specific conditions
            if not self._check_challenge_conditions(session, metrics, config):
                # Challenge failed
                self._end_challenge(False)
                return
            
            # Apply thermal management if needed
            if session.target_program:
                self._apply_thermal_management(metrics, session.target_program)
            
            time.sleep(1)  # Update every second
        
        # Challenge completed successfully
        session.avg_cpu_temp = sum(t[0] for t in temp_readings) / len(temp_readings)
        session.avg_gpu_temp = sum(t[1] for t in temp_readings) / len(temp_readings)
        
        self._end_challenge(True)

    def _collect_current_metrics(self) -> ThermalMetrics:
        """Collect current system thermal metrics"""
        current_time = time.time()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = cpu_freq.current if cpu_freq else 0.0
        
        # Get CPU temperature
        cpu_temp = self._get_cpu_temperature()
        
        # GPU metrics
        gpu_temp, gpu_usage = self._get_gpu_metrics()
        
        # Fan speed (simplified)
        fan_speed = self._get_fan_speed()
        
        # Power draw estimation
        power_draw = self._estimate_power_draw(cpu_percent, gpu_usage)
        
        return ThermalMetrics(
            timestamp=current_time,
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
            cpu_usage=cpu_percent,
            gpu_usage=gpu_usage,
            cpu_freq=cpu_freq_current,
            fan_speed=fan_speed,
            power_draw=power_draw
        )

    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature"""
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
                    if temp_value > 1000:
                        temp_value = temp_value / 1000
                    return temp_value
            
            # Fallback: simulate temperature
            base_temp = 35.0
            load_factor = psutil.cpu_percent() / 100.0
            return base_temp + (load_factor * 45.0) + random.uniform(-2, 2)
            
        except:
            return 45.0  # Safe fallback

    def _get_gpu_metrics(self) -> Tuple[float, float]:
        """Get GPU temperature and usage"""
        if not self.gpu_available:
            # Simulate GPU metrics
            cpu_load = psutil.cpu_percent()
            gpu_usage = max(0, cpu_load - 20 + random.uniform(-10, 15))
            gpu_temp = 40 + (gpu_usage / 100 * 50) + random.uniform(-3, 3)
            return gpu_temp, gpu_usage
        
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return float(temp), float(util.gpu)
        except:
            return 50.0, 0.0

    def _get_fan_speed(self) -> float:
        """Get fan speed percentage"""
        try:
            # Try to get fan speed from sensors
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                # Parse fan speed from sensors output
                for line in result.stdout.split('\n'):
                    if 'fan' in line.lower() and 'rpm' in line.lower():
                        # Extract RPM and convert to percentage (rough estimate)
                        import re
                        rpm_match = re.search(r'(\d+)\s*RPM', line)
                        if rpm_match:
                            rpm = int(rpm_match.group(1))
                            return min(100, (rpm / 2000) * 100)  # Assume max 2000 RPM
            
            # Fallback: estimate based on temperature
            cpu_temp = self._get_cpu_temperature()
            if cpu_temp > 70:
                return 80 + random.uniform(-5, 10)
            elif cpu_temp > 60:
                return 60 + random.uniform(-5, 10)
            else:
                return 30 + random.uniform(-5, 10)
                
        except:
            return 50.0

    def _estimate_power_draw(self, cpu_usage: float, gpu_usage: float) -> float:
        """Estimate system power draw"""
        # Base power consumption
        base_power = 50.0
        
        # CPU power (rough estimate)
        cpu_power = (cpu_usage / 100) * 100.0  # Up to 100W for CPU
        
        # GPU power (rough estimate)  
        gpu_power = (gpu_usage / 100) * 150.0  # Up to 150W for GPU
        
        return base_power + cpu_power + gpu_power

    def _calculate_current_score(self, session: GameSession, metrics: ThermalMetrics, config: Dict) -> int:
        """Calculate current challenge score"""
        base = self.base_score
        multiplier = config["score_multiplier"]
        
        # Temperature penalties
        temp_penalty = 0
        if metrics.cpu_temp > self.temp_penalty_threshold:
            temp_penalty += (metrics.cpu_temp - self.temp_penalty_threshold) * 10
        if metrics.gpu_temp > self.temp_penalty_threshold:
            temp_penalty += (metrics.gpu_temp - self.temp_penalty_threshold) * 10
        
        # Efficiency bonus
        efficiency = self._calculate_efficiency(metrics)
        efficiency_bonus = 0
        if efficiency > self.efficiency_bonus_threshold:
            efficiency_bonus = (efficiency - self.efficiency_bonus_threshold) * 200
        
        # Time bonus
        elapsed = time.time() - session.start_time
        time_bonus = min(100, elapsed / 60)  # Up to 100 points per minute
        
        score = int((base + efficiency_bonus + time_bonus - temp_penalty) * multiplier)
        return max(0, score)

    def _calculate_efficiency(self, metrics: ThermalMetrics) -> float:
        """Calculate performance efficiency rating"""
        # Simple efficiency calculation: performance per degree
        total_usage = metrics.cpu_usage + metrics.gpu_usage
        total_temp = metrics.cpu_temp + metrics.gpu_temp
        
        if total_temp > 0:
            return total_usage / total_temp
        return 0.0

    def _check_challenge_conditions(self, session: GameSession, metrics: ThermalMetrics, config: Dict) -> bool:
        """Check if challenge conditions are still met"""
        challenge = session.challenge
        
        if challenge == ThermalChallenge.COOL_RUNNER:
            return (metrics.cpu_temp <= config["max_temp"] and 
                   metrics.gpu_temp <= config["max_temp"])
        
        elif challenge == ThermalChallenge.EFFICIENCY_MASTER:
            efficiency = self._calculate_efficiency(metrics)
            return efficiency >= config["min_efficiency"]
        
        elif challenge == ThermalChallenge.STRESS_SURVIVOR:
            load_ok = (metrics.cpu_usage >= config["min_load"] or 
                      metrics.gpu_usage >= config["min_load"])
            temp_ok = (metrics.cpu_temp <= config["max_temp"] and 
                      metrics.gpu_temp <= config["max_temp"])
            return load_ok and temp_ok
        
        elif challenge == ThermalChallenge.SILENT_OPERATOR:
            return (metrics.fan_speed <= config["max_fan_speed"] and
                   metrics.cpu_temp <= config["max_temp"] and
                   metrics.gpu_temp <= config["max_temp"])
        
        elif challenge == ThermalChallenge.OVERCLOCKED_BEAST:
            # Check if performance is above baseline
            performance = (metrics.cpu_usage + metrics.gpu_usage) / 2
            temp_ok = (metrics.cpu_temp <= config["max_temp"] and
                      metrics.gpu_temp <= config["max_temp"])
            return performance >= config["min_performance"] and temp_ok
        
        return True

    def _get_challenge_status_text(self, session: GameSession, metrics: ThermalMetrics) -> str:
        """Get challenge-specific status text"""
        challenge = session.challenge
        config = self.challenge_configs[challenge]
        
        if challenge == ThermalChallenge.COOL_RUNNER:
            cpu_ok = "✅" if metrics.cpu_temp <= config["max_temp"] else "❌"
            gpu_ok = "✅" if metrics.gpu_temp <= config["max_temp"] else "❌"
            return f"   {cpu_ok} CPU ≤ {config['max_temp']}°C\n   {gpu_ok} GPU ≤ {config['max_temp']}°C"
        
        elif challenge == ThermalChallenge.EFFICIENCY_MASTER:
            efficiency = self._calculate_efficiency(metrics)
            eff_ok = "✅" if efficiency >= config["min_efficiency"] else "❌"
            return f"   {eff_ok} Efficiency: {efficiency:.2f} (need ≥{config['min_efficiency']})"
        
        elif challenge == ThermalChallenge.STRESS_SURVIVOR:
            load_ok = "✅" if max(metrics.cpu_usage, metrics.gpu_usage) >= config["min_load"] else "❌"
            temp_ok = "✅" if max(metrics.cpu_temp, metrics.gpu_temp) <= config["max_temp"] else "❌"
            return f"   {load_ok} High Load (≥{config['min_load']}%)\n   {temp_ok} Safe Temps (≤{config['max_temp']}°C)"
        
        elif challenge == ThermalChallenge.SILENT_OPERATOR:
            fan_ok = "✅" if metrics.fan_speed <= config["max_fan_speed"] else "❌"
            temp_ok = "✅" if max(metrics.cpu_temp, metrics.gpu_temp) <= config["max_temp"] else "❌"
            return f"   {fan_ok} Fan Speed ≤ {config['max_fan_speed']}%\n   {temp_ok} Temps ≤ {config['max_temp']}°C"
        
        elif challenge == ThermalChallenge.OVERCLOCKED_BEAST:
            perf = (metrics.cpu_usage + metrics.gpu_usage) / 2
            perf_ok = "✅" if perf >= config["min_performance"] else "❌"
            temp_ok = "✅" if max(metrics.cpu_temp, metrics.gpu_temp) <= config["max_temp"] else "❌"
            return f"   {perf_ok} Performance: {perf:.1f}% (need ≥{config['min_performance']}%)\n   {temp_ok} Temps ≤ {config['max_temp']}°C"
        
        return "   Status: Running..."

    def _apply_thermal_management(self, metrics: ThermalMetrics, target_program: str):
        """Apply thermal management to target program"""
        try:
            # Find target process
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                if target_program.lower() in proc.info['name'].lower():
                    pid = proc.info['pid']
                    
                    # Apply CPU affinity management based on temperature
                    if metrics.cpu_temp > 75:
                        # Reduce CPU affinity to cool down
                        available_cores = list(range(psutil.cpu_count(logical=False)))
                        limited_cores = available_cores[:max(1, len(available_cores)//2)]
                        psutil.Process(pid).cpu_affinity(limited_cores)
                    elif metrics.cpu_temp < 60:
                        # Allow full CPU usage
                        psutil.Process(pid).cpu_affinity(list(range(psutil.cpu_count())))
                    
                    # Adjust process priority based on thermal state
                    if metrics.cpu_temp > 80:
                        psutil.Process(pid).nice(10)  # Lower priority
                    elif metrics.cpu_temp < 65:
                        psutil.Process(pid).nice(-5)  # Higher priority (if allowed)
                    
                    break
        except:
            pass  # Ignore errors in thermal management

    def _end_challenge(self, success: bool):
        """End the current challenge"""
        self.running = False
        session = self.current_session
        
        if not session:
            return
        
        session.end_time = time.time()
        session.completed = success
        
        # Calculate final scores and achievements
        if success:
            self._award_achievements(session)
            self._update_player_stats(session)
        
        # Save session data
        self._save_session(session)
        
        console.print(f"\n🎮 Challenge {'COMPLETED' if success else 'FAILED'}!")
        console.print(f"🏆 Final Score: {session.score:,} points")
        
        if session.achievements_earned:
            console.print("🎯 New Achievements:")
            for achievement in session.achievements_earned:
                console.print(f"   ⭐ {achievement.value.replace('_', ' ').title()}")
        
        self.current_session = None

    def _award_achievements(self, session: GameSession):
        """Award achievements based on session performance"""
        achievements = []
        
        # First victory
        if self.player_stats.total_sessions == 0:
            achievements.append(Achievement.FIRST_VICTORY)
        
        # Temperature achievements
        if session.max_cpu_temp <= 60 and session.max_gpu_temp <= 60:
            achievements.append(Achievement.ICE_COLD)
        elif session.max_cpu_temp <= 70 and session.max_gpu_temp <= 70:
            achievements.append(Achievement.TEMPERATURE_TAMER)
        
        # Efficiency achievements
        if session.efficiency_rating >= 0.9:
            achievements.append(Achievement.EFFICIENCY_EXPERT)
        
        # Score achievements
        if session.score >= 2000:
            achievements.append(Achievement.PERFECT_BALANCE)
        if session.score >= 3000:
            achievements.append(Achievement.LEGENDARY_COOLER)
        
        # Challenge-specific achievements
        if session.challenge == ThermalChallenge.STRESS_SURVIVOR and session.completed:
            achievements.append(Achievement.MARATHON_RUNNER)
        
        # Filter new achievements
        new_achievements = [a for a in achievements if a not in self.player_stats.achievements]
        session.achievements_earned = new_achievements
        
        # Add to player stats
        self.player_stats.achievements.extend(new_achievements)

    def _update_player_stats(self, session: GameSession):
        """Update player statistics"""
        stats = self.player_stats
        
        stats.total_sessions += 1
        stats.best_score = max(stats.best_score, session.score)
        stats.total_playtime += (session.end_time - session.start_time)
        
        # Update experience points
        xp_gained = session.score // 10
        stats.experience_points += xp_gained
        
        # Level up system
        new_level = int(stats.experience_points // 1000) + 1
        if new_level > stats.level:
            stats.level = new_level
            console.print(f"🎉 LEVEL UP! You are now level {stats.level}!")
        
        # Update mastery rating
        if session.completed:
            stats.current_streak += 1
            session_rating = min(100, session.score / 30)  # Convert to 0-100 scale
            stats.thermal_mastery_rating = (stats.thermal_mastery_rating * 0.9) + (session_rating * 0.1)
        else:
            stats.current_streak = 0
        
        # Update favorite challenge
        # This would track which challenges are played most
        
        self._save_player_stats()

    def _save_session(self, session: GameSession):
        """Save session data"""
        session_file = self.data_dir / f"session_{session.session_id}.json"
        with open(session_file, 'w') as f:
            # Convert enums to strings for JSON serialization
            session_data = asdict(session)
            session_data['challenge'] = session.challenge.value
            session_data['achievements_earned'] = [a.value for a in session.achievements_earned]
            json.dump(session_data, f, indent=2)

    def load_player_stats(self) -> PlayerStats:
        """Load player statistics"""
        stats_file = self.data_dir / "player_stats.json"
        
        if stats_file.exists():
            try:
                with open(stats_file, 'r') as f:
                    data = json.load(f)
                
                # Convert achievement strings back to enums
                achievements = [Achievement(a) for a in data.get('achievements', [])]
                favorite = ThermalChallenge(data.get('favorite_challenge', ThermalChallenge.COOL_RUNNER.value))
                
                return PlayerStats(
                    total_sessions=data.get('total_sessions', 0),
                    best_score=data.get('best_score', 0),
                    total_playtime=data.get('total_playtime', 0.0),
                    achievements=achievements,
                    level=data.get('level', 1),
                    experience_points=data.get('experience_points', 0),
                    thermal_mastery_rating=data.get('thermal_mastery_rating', 0.0),
                    favorite_challenge=favorite,
                    current_streak=data.get('current_streak', 0)
                )
            except:
                pass
        
        # Default stats for new player
        return PlayerStats(
            total_sessions=0,
            best_score=0,
            total_playtime=0.0,
            achievements=[],
            level=1,
            experience_points=0,
            thermal_mastery_rating=0.0,
            favorite_challenge=ThermalChallenge.COOL_RUNNER,
            current_streak=0
        )

    def _save_player_stats(self):
        """Save player statistics"""
        stats_file = self.data_dir / "player_stats.json"
        
        # Convert enums to strings for JSON serialization
        stats_data = asdict(self.player_stats)
        stats_data['achievements'] = [a.value for a in self.player_stats.achievements]
        stats_data['favorite_challenge'] = self.player_stats.favorite_challenge.value
        
        with open(stats_file, 'w') as f:
            json.dump(stats_data, f, indent=2)

    def _start_simple_interface(self):
        """Simple text-based interface"""
        console.print("🎮 Thermal Management Gaming - Simple Mode")
        console.print("Rich interface not available, using basic text mode")
        
        while True:
            print("\n" + "="*50)
            print("THERMAL GAMING MENU")
            print("="*50)
            
            for i, challenge in enumerate(ThermalChallenge, 1):
                config = self.challenge_configs[challenge]
                print(f"{i}. {challenge.value.replace('_', ' ').title()}")
                print(f"   {config['description']}")
            
            print("6. Exit")
            
            try:
                choice = input("\nSelect challenge (1-6): ").strip()
                choice_num = int(choice)
                
                if 1 <= choice_num <= 5:
                    challenge_list = list(ThermalChallenge)
                    challenge = challenge_list[choice_num - 1]
                    self.start_challenge(challenge)
                    
                    # Simple monitoring loop
                    self._simple_challenge_loop()
                    
                elif choice_num == 6:
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break

    def _simple_challenge_loop(self):
        """Simple challenge monitoring loop"""
        session = self.current_session
        config = self.challenge_configs[session.challenge]
        
        start_time = session.start_time
        duration = config["duration"]
        
        print(f"\n🚀 Challenge started: {session.challenge.value}")
        print(f"Duration: {duration}s")
        print("Press Ctrl+C to quit early\n")
        
        try:
            while time.time() - start_time < duration:
                metrics = self._collect_current_metrics()
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                
                # Update score
                session.score = self._calculate_current_score(session, metrics, config)
                
                # Check conditions
                if not self._check_challenge_conditions(session, metrics, config):
                    print("❌ Challenge failed! Conditions not met.")
                    self._end_challenge(False)
                    return
                
                # Display status
                print(f"\r⏱️  {remaining:3.0f}s | 🌡️  CPU:{metrics.cpu_temp:4.1f}°C GPU:{metrics.gpu_temp:4.1f}°C | 🏆 {session.score:,}", end='')
                
                time.sleep(1)
            
            print("\n✅ Challenge completed successfully!")
            self._end_challenge(True)
            
        except KeyboardInterrupt:
            print("\n⏹️  Challenge stopped by user")
            self._end_challenge(False)

def main():
    """Main entry point for thermal gaming"""
    print("🎮 Thermal Management Gaming System")
    print("=" * 50)
    print("Turn system cooling into a competitive game!")
    print("Earn points, unlock achievements, and master thermal efficiency!")
    print()
    
    game = ThermalGameEngine()
    
    try:
        game.start_gaming_interface()
    except KeyboardInterrupt:
        print("\n👋 Thanks for playing Thermal Gaming!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
