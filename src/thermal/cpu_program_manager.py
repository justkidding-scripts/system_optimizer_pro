#!/usr/bin/env python3
"""
CPU-Based Program Manager for Thermal Gaming
Allows selection of specific programs and applies CPU-based thermal management
"""

import psutil
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import subprocess
import threading
from collections import defaultdict

@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    threads: int
    create_time: float
    cmdline: List[str]
    cpu_affinity: List[int]
    nice_value: int

@dataclass
class ThermalProfile:
    program_name: str
    max_temp_threshold: float
    target_cpu_usage: float
    priority_level: int  # -20 to 20
    cpu_affinity_strategy: str  # "dynamic", "limited", "performance"
    cooling_aggressiveness: int  # 1-10

class CPUProgramManager:
    def __init__(self):
        self.data_dir = Path.home() / ".system_optimizer_pro" / "cpu_management"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Thermal profiles for different programs
        self.thermal_profiles = self.load_thermal_profiles()
        
        # CPU monitoring
        self.cpu_cores = psutil.cpu_count(logical=False)
        self.logical_cores = psutil.cpu_count(logical=True)
        self.monitoring = False
        self.target_processes: Dict[int, ProcessInfo] = {}
        
        # Performance tracking
        self.temperature_history = []
        self.process_history = defaultdict(list)

    def discover_programs(self) -> List[ProcessInfo]:
        """Discover running programs suitable for thermal management"""
        processes = []
        
        # Get all running processes
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 
                                       'num_threads', 'create_time', 'cmdline']):
            try:
                info = proc.info
                
                # Skip system processes and low-impact processes
                if (info['cpu_percent'] > 1.0 or info['memory_percent'] > 1.0):
                    # Get additional process info
                    try:
                        affinity = proc.cpu_affinity()
                        nice = proc.nice()
                    except:
                        affinity = list(range(self.logical_cores))
                        nice = 0
                    
                    process_info = ProcessInfo(
                        pid=info['pid'],
                        name=info['name'],
                        cpu_percent=info['cpu_percent'] or 0.0,
                        memory_percent=info['memory_percent'] or 0.0,
                        threads=info['num_threads'] or 1,
                        create_time=info['create_time'] or time.time(),
                        cmdline=info['cmdline'] or [],
                        cpu_affinity=affinity,
                        nice_value=nice
                    )
                    processes.append(process_info)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by CPU usage
        processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        return processes[:20]  # Top 20 processes

    def create_thermal_profile(self, program_name: str, 
                             max_temp: float = 75.0,
                             target_usage: float = 80.0,
                             priority: int = 0,
                             affinity_strategy: str = "dynamic",
                             cooling_level: int = 5) -> ThermalProfile:
        """Create a thermal management profile for a program"""
        
        profile = ThermalProfile(
            program_name=program_name,
            max_temp_threshold=max_temp,
            target_cpu_usage=target_usage,
            priority_level=priority,
            cpu_affinity_strategy=affinity_strategy,
            cooling_aggressiveness=cooling_level
        )
        
        self.thermal_profiles[program_name] = profile
        self.save_thermal_profiles()
        return profile

    def start_thermal_management(self, program_name: str, 
                                thermal_profile: Optional[ThermalProfile] = None):
        """Start thermal management for a specific program"""
        
        if thermal_profile is None:
            thermal_profile = self.thermal_profiles.get(program_name)
            
        if thermal_profile is None:
            # Create default profile
            thermal_profile = self.create_thermal_profile(program_name)
        
        # Find target processes
        target_pids = self.find_processes_by_name(program_name)
        if not target_pids:
            print(f"❌ No processes found for program: {program_name}")
            return False
        
        print(f"🎯 Starting thermal management for {program_name}")
        print(f"   Found {len(target_pids)} processes")
        print(f"   Max temp threshold: {thermal_profile.max_temp_threshold}°C")
        print(f"   Target CPU usage: {thermal_profile.target_cpu_usage}%")
        
        # Start monitoring thread
        self.monitoring = True
        monitor_thread = threading.Thread(
            target=self._thermal_monitor_loop, 
            args=(program_name, thermal_profile)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return True

    def find_processes_by_name(self, program_name: str) -> List[int]:
        """Find all process PIDs matching the program name"""
        pids = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                info = proc.info
                if (program_name.lower() in info['name'].lower() or 
                    any(program_name.lower() in arg.lower() 
                        for arg in (info['cmdline'] or []))):
                    pids.append(info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return pids

    def _thermal_monitor_loop(self, program_name: str, profile: ThermalProfile):
        """Main thermal monitoring and management loop"""
        print(f"🌡️  Starting thermal monitoring for {program_name}")
        
        while self.monitoring:
            try:
                # Get current system temperature
                cpu_temp = self._get_cpu_temperature()
                
                # Find current processes
                target_pids = self.find_processes_by_name(program_name)
                
                if not target_pids:
                    print(f"⚠️  No processes found for {program_name}, stopping monitor")
                    break
                
                # Apply thermal management to each process
                for pid in target_pids:
                    try:
                        self._apply_thermal_management(pid, cpu_temp, profile)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Log metrics
                self.temperature_history.append({
                    'timestamp': time.time(),
                    'cpu_temp': cpu_temp,
                    'program': program_name,
                    'process_count': len(target_pids)
                })
                
                # Keep only recent history
                if len(self.temperature_history) > 1000:
                    self.temperature_history = self.temperature_history[-500:]
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                print(f"❌ Error in thermal monitor: {e}")
                time.sleep(5)
        
        print(f"🔚 Thermal monitoring stopped for {program_name}")

    def _apply_thermal_management(self, pid: int, cpu_temp: float, profile: ThermalProfile):
        """Apply thermal management to a specific process"""
        try:
            proc = psutil.Process(pid)
            
            # Determine thermal management actions based on temperature
            if cpu_temp > profile.max_temp_threshold:
                self._apply_cooling_measures(proc, cpu_temp, profile)
            elif cpu_temp < profile.max_temp_threshold - 10:  # 10°C buffer
                self._apply_performance_measures(proc, cpu_temp, profile)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def _apply_cooling_measures(self, proc: psutil.Process, cpu_temp: float, profile: ThermalProfile):
        """Apply measures to cool down the system"""
        severity = min(10, int((cpu_temp - profile.max_temp_threshold) / 2))
        
        # Adjust CPU affinity based on strategy and temperature
        if profile.cpu_affinity_strategy == "dynamic":
            # Reduce available cores as temperature increases
            available_cores = list(range(self.logical_cores))
            if severity > 5:  # Very hot
                allowed_cores = available_cores[:max(1, len(available_cores) // 4)]
            elif severity > 2:  # Hot
                allowed_cores = available_cores[:max(2, len(available_cores) // 2)]
            else:  # Warm
                allowed_cores = available_cores[:max(4, (len(available_cores) * 3) // 4)]
            
            try:
                proc.cpu_affinity(allowed_cores)
            except (psutil.AccessDenied, OSError):
                pass
        
        elif profile.cpu_affinity_strategy == "limited":
            # Always limit to fewer cores
            limited_cores = list(range(min(4, self.logical_cores)))
            try:
                proc.cpu_affinity(limited_cores)
            except (psutil.AccessDenied, OSError):
                pass
        
        # Adjust process priority (higher nice value = lower priority)
        target_nice = min(19, profile.priority_level + severity)
        try:
            current_nice = proc.nice()
            if current_nice < target_nice:
                proc.nice(target_nice)
        except (psutil.AccessDenied, OSError):
            pass
        
        # Apply CPU throttling for very high temperatures
        if severity > 7:
            self._apply_cpu_throttling(proc, profile)

    def _apply_performance_measures(self, proc: psutil.Process, cpu_temp: float, profile: ThermalProfile):
        """Apply measures to improve performance when temperatures are safe"""
        
        # Allow full CPU access
        if profile.cpu_affinity_strategy == "performance":
            all_cores = list(range(self.logical_cores))
            try:
                proc.cpu_affinity(all_cores)
            except (psutil.AccessDenied, OSError):
                pass
        
        # Improve process priority if temperature is very safe
        if cpu_temp < profile.max_temp_threshold - 15:
            target_nice = max(-5, profile.priority_level - 2)
            try:
                current_nice = proc.nice()
                if current_nice > target_nice:
                    proc.nice(target_nice)
            except (psutil.AccessDenied, OSError):
                pass

    def _apply_cpu_throttling(self, proc: psutil.Process, profile: ThermalProfile):
        """Apply CPU throttling for extreme temperature situations"""
        try:
            # Send SIGSTOP/SIGCONT signals to throttle the process
            # This is a more aggressive measure
            proc.suspend()
            time.sleep(0.1 * profile.cooling_aggressiveness)  # Pause duration
            proc.resume()
        except (psutil.AccessDenied, OSError, psutil.NoSuchProcess):
            pass

    def _get_cpu_temperature(self) -> float:
        """Get current CPU temperature"""
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
            
            # Fallback: use sensors command
            try:
                result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Core' in line and '°C' in line:
                            import re
                            temp_match = re.search(r'(\d+\.\d+)°C', line)
                            if temp_match:
                                return float(temp_match.group(1))
            except:
                pass
            
            # Final fallback: estimate based on load
            cpu_percent = psutil.cpu_percent()
            return 35.0 + (cpu_percent / 100.0 * 45.0)
            
        except Exception:
            return 50.0  # Safe fallback

    def get_process_thermal_stats(self, program_name: str) -> Dict:
        """Get thermal statistics for a program"""
        recent_history = [h for h in self.temperature_history 
                         if h['program'] == program_name and 
                         time.time() - h['timestamp'] < 3600]  # Last hour
        
        if not recent_history:
            return {}
        
        temps = [h['cpu_temp'] for h in recent_history]
        process_counts = [h['process_count'] for h in recent_history]
        
        return {
            'program_name': program_name,
            'avg_temperature': sum(temps) / len(temps),
            'max_temperature': max(temps),
            'min_temperature': min(temps),
            'avg_process_count': sum(process_counts) / len(process_counts),
            'monitoring_duration': len(recent_history) * 2,  # 2 second intervals
            'thermal_events': len([t for t in temps if t > 75])
        }

    def stop_thermal_management(self):
        """Stop thermal management monitoring"""
        self.monitoring = False
        print("🛑 Thermal management stopped")

    def create_interactive_program_selector(self):
        """Interactive program selection interface"""
        print("\n🎯 CPU-Based Program Thermal Management")
        print("=" * 50)
        
        while True:
            print("\n📋 Available Programs:")
            programs = self.discover_programs()
            
            if not programs:
                print("❌ No suitable programs found")
                return None
            
            # Display programs
            for i, prog in enumerate(programs[:10], 1):
                runtime = time.time() - prog.create_time
                runtime_str = f"{runtime/3600:.1f}h" if runtime > 3600 else f"{runtime/60:.1f}m"
                
                print(f"{i:2d}. {prog.name:20s} | CPU: {prog.cpu_percent:5.1f}% | "
                      f"RAM: {prog.memory_percent:5.1f}% | Threads: {prog.threads:3d} | "
                      f"Runtime: {runtime_str}")
            
            print(f"{len(programs[:10])+1}. 🔄 Refresh list")
            print(f"{len(programs[:10])+2}. ❌ Exit")
            
            try:
                choice = input(f"\nSelect program (1-{len(programs[:10])+2}): ").strip()
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(programs[:10]):
                    selected_program = programs[choice_num - 1]
                    return self.configure_program_thermal_management(selected_program)
                    
                elif choice_num == len(programs[:10]) + 1:
                    continue  # Refresh
                    
                elif choice_num == len(programs[:10]) + 2:
                    return None
                    
            except (ValueError, KeyboardInterrupt):
                return None

    def configure_program_thermal_management(self, program_info: ProcessInfo):
        """Configure thermal management for selected program"""
        print(f"\n⚙️  Configuring thermal management for: {program_info.name}")
        print(f"Current CPU usage: {program_info.cpu_percent:.1f}%")
        print(f"Current CPU affinity: {program_info.cpu_affinity}")
        print(f"Current nice value: {program_info.nice_value}")
        
        # Configuration options
        print("\n🌡️  Thermal Management Configuration:")
        
        try:
            max_temp = input(f"Maximum temperature threshold (default 75°C): ").strip()
            max_temp = float(max_temp) if max_temp else 75.0
            
            target_usage = input(f"Target CPU usage limit (default 80%): ").strip()
            target_usage = float(target_usage) if target_usage else 80.0
            
            print("\nCPU Affinity Strategies:")
            print("1. Dynamic - Adjust cores based on temperature")
            print("2. Limited - Always limit to fewer cores")
            print("3. Performance - Allow all cores when cool")
            
            strategy_choice = input("Select strategy (1-3, default 1): ").strip()
            strategies = {"1": "dynamic", "2": "limited", "3": "performance"}
            strategy = strategies.get(strategy_choice, "dynamic")
            
            cooling_level = input("Cooling aggressiveness (1-10, default 5): ").strip()
            cooling_level = int(cooling_level) if cooling_level else 5
            cooling_level = max(1, min(10, cooling_level))
            
            priority = input("Process priority adjustment (-5 to 5, default 0): ").strip()
            priority = int(priority) if priority else 0
            priority = max(-5, min(5, priority))
            
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Configuration cancelled")
            return None
        
        # Create thermal profile
        profile = self.create_thermal_profile(
            program_name=program_info.name,
            max_temp=max_temp,
            target_usage=target_usage,
            priority=priority,
            affinity_strategy=strategy,
            cooling_level=cooling_level
        )
        
        print(f"\n✅ Thermal profile created for {program_info.name}")
        print(f"   Max temperature: {max_temp}°C")
        print(f"   CPU strategy: {strategy}")
        print(f"   Cooling level: {cooling_level}/10")
        
        # Ask if user wants to start monitoring immediately
        start_now = input("\nStart thermal management now? (y/n): ").strip().lower()
        if start_now in ['y', 'yes']:
            self.start_thermal_management(program_info.name, profile)
            return profile
        
        return profile

    def load_thermal_profiles(self) -> Dict[str, ThermalProfile]:
        """Load thermal profiles from storage"""
        profiles_file = self.data_dir / "thermal_profiles.json"
        
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                
                profiles = {}
                for name, profile_data in data.items():
                    profiles[name] = ThermalProfile(**profile_data)
                
                return profiles
            except Exception as e:
                print(f"❌ Error loading thermal profiles: {e}")
        
        return {}

    def save_thermal_profiles(self):
        """Save thermal profiles to storage"""
        profiles_file = self.data_dir / "thermal_profiles.json"
        
        try:
            profiles_data = {}
            for name, profile in self.thermal_profiles.items():
                profiles_data[name] = {
                    'program_name': profile.program_name,
                    'max_temp_threshold': profile.max_temp_threshold,
                    'target_cpu_usage': profile.target_cpu_usage,
                    'priority_level': profile.priority_level,
                    'cpu_affinity_strategy': profile.cpu_affinity_strategy,
                    'cooling_aggressiveness': profile.cooling_aggressiveness
                }
            
            with open(profiles_file, 'w') as f:
                json.dump(profiles_data, f, indent=2)
                
        except Exception as e:
            print(f"❌ Error saving thermal profiles: {e}")

    def show_thermal_status(self):
        """Show current thermal management status"""
        print("\n📊 Thermal Management Status")
        print("=" * 50)
        
        if not self.thermal_profiles:
            print("❌ No thermal profiles configured")
            return
        
        print(f"🎯 Configured Programs: {len(self.thermal_profiles)}")
        print(f"🌡️  Current CPU Temperature: {self._get_cpu_temperature():.1f}°C")
        print(f"💻 Available CPU Cores: {self.logical_cores} ({self.cpu_cores} physical)")
        print(f"📡 Monitoring Active: {'✅' if self.monitoring else '❌'}")
        
        print("\n📋 Thermal Profiles:")
        for name, profile in self.thermal_profiles.items():
            stats = self.get_process_thermal_stats(name)
            
            print(f"\n  📦 {name}")
            print(f"     Max Temperature: {profile.max_temp_threshold}°C")
            print(f"     CPU Strategy: {profile.cpu_affinity_strategy}")
            print(f"     Cooling Level: {profile.cooling_aggressiveness}/10")
            
            if stats:
                print(f"     📈 Avg Temp: {stats['avg_temperature']:.1f}°C")
                print(f"     🔥 Max Temp: {stats['max_temperature']:.1f}°C")
                print(f"     ⚡ Thermal Events: {stats['thermal_events']}")

def main():
    """Main entry point for CPU program manager"""
    print("🖥️  CPU-Based Program Thermal Management")
    print("=" * 50)
    
    manager = CPUProgramManager()
    
    try:
        while True:
            print("\n📋 Available Options:")
            print("1. 🎯 Select program for thermal management")
            print("2. 📊 Show thermal status")
            print("3. 🛑 Stop thermal management")
            print("4. ❌ Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                profile = manager.create_interactive_program_selector()
                if profile:
                    print(f"✅ Thermal management configured for {profile.program_name}")
                    
            elif choice == "2":
                manager.show_thermal_status()
                
            elif choice == "3":
                manager.stop_thermal_management()
                
            elif choice == "4":
                manager.stop_thermal_management()
                break
                
            else:
                print("❌ Invalid choice")
                
    except KeyboardInterrupt:
        manager.stop_thermal_management()
        print("\n👋 CPU thermal management stopped")

if __name__ == "__main__":
    main()
