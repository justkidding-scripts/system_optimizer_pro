#!/usr/bin/env python3
"""
Cross-platform compatibility layer for System Optimizer Pro
Provides unified interface for Windows and Linux operations
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

# Windows-specific imports (conditional)
if platform.system() == 'Windows':
    try:
        import winreg
        import win32api
        import win32con
        import win32service
        import win32serviceutil
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
        winreg = None
        win32api = None
else:
    HAS_WIN32 = False
    winreg = None

@dataclass
class SystemInfo:
    """Cross-platform system information"""
    platform: str
    platform_version: str
    architecture: str
    hostname: str
    username: str
    home_dir: Path
    temp_dir: Path
    config_dir: Path
    log_dir: Path
    
class PlatformInterface(ABC):
    """Abstract interface for platform-specific operations"""
    
    @abstractmethod
    def get_system_info(self) -> SystemInfo:
        """Get system information"""
        pass
    
    @abstractmethod
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """Get list of running processes"""
        pass
    
    @abstractmethod
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process by PID"""
        pass
    
    @abstractmethod
    def get_system_services(self) -> List[Dict[str, Any]]:
        """Get system services"""
        pass
    
    @abstractmethod
    def start_service(self, service_name: str) -> bool:
        """Start a system service"""
        pass
    
    @abstractmethod
    def stop_service(self, service_name: str) -> bool:
        """Stop a system service"""
        pass
    
    @abstractmethod
    def get_startup_programs(self) -> List[Dict[str, Any]]:
        """Get startup programs"""
        pass
    
    @abstractmethod
    def disable_startup_program(self, program_id: str) -> bool:
        """Disable a startup program"""
        pass
    
    @abstractmethod
    def cleanup_temp_files(self) -> Dict[str, int]:
        """Clean up temporary files"""
        pass
    
    @abstractmethod
    def optimize_system(self) -> Dict[str, Any]:
        """Perform platform-specific optimizations"""
        pass
    
    @abstractmethod
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get platform-specific system metrics"""
        pass

class WindowsPlatform(PlatformInterface):
    """Windows-specific implementation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.Windows')
        if not HAS_WIN32:
            self.logger.warning("Windows-specific libraries not available, limited functionality")
    
    def get_system_info(self) -> SystemInfo:
        """Get Windows system information"""
        import getpass
        
        return SystemInfo(
            platform="Windows",
            platform_version=platform.platform(),
            architecture=platform.machine(),
            hostname=platform.node(),
            username=getpass.getuser(),
            home_dir=Path.home(),
            temp_dir=Path(os.getenv('TEMP', Path.home() / 'AppData/Local/Temp')),
            config_dir=Path.home() / 'AppData/Roaming/SystemOptimizerPro',
            log_dir=Path.home() / 'AppData/Local/SystemOptimizerPro/Logs'
        )
    
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """Get Windows running processes"""
        processes = []
        
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'status']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_mb': proc.info['memory_info'].rss // 1024 // 1024,
                        'cpu_percent': proc.info['cpu_percent'] or 0,
                        'status': proc.info['status']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            # Fallback using tasklist command
            try:
                result = subprocess.run(['tasklist', '/fo', 'csv'], 
                                      capture_output=True, text=True, check=True)
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.replace('"', '').split(',')
                    if len(parts) >= 5:
                        processes.append({
                            'pid': int(parts[1]),
                            'name': parts[0],
                            'memory_mb': int(parts[4].replace(',', '').replace(' K', '')) // 1024,
                            'cpu_percent': 0,
                            'status': 'running'
                        })
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to get processes: {e}")
        
        return processes
    
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill Windows process"""
        try:
            cmd = ['taskkill', '/PID', str(pid)]
            if force:
                cmd.append('/F')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to kill process {pid}: {e}")
            return False
    
    def get_system_services(self) -> List[Dict[str, Any]]:
        """Get Windows services"""
        services = []
        
        if HAS_WIN32:
            try:
                # Use win32service for detailed service info
                scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
                service_list = win32service.EnumServicesStatus(scm)
                
                for service in service_list:
                    services.append({
                        'name': service[0],
                        'display_name': service[1],
                        'status': self._get_service_status_text(service[2][1]),
                        'startup_type': 'automatic',  # Would need additional call to get this
                        'pid': service[2][7] if service[2][7] != 0 else None
                    })
                
                win32service.CloseServiceHandle(scm)
                
            except Exception as e:
                self.logger.error(f"Failed to get services with win32service: {e}")
        
        # Fallback using sc command
        if not services:
            try:
                result = subprocess.run(['sc', 'query', 'state=', 'all'], 
                                      capture_output=True, text=True, check=True)
                
                service_blocks = result.stdout.split('\n\n')
                for block in service_blocks:
                    lines = [line.strip() for line in block.split('\n') if line.strip()]
                    if len(lines) >= 3:
                        service_name = lines[0].split(':')[1].strip() if ':' in lines[0] else ''
                        display_name = lines[1].split(':')[1].strip() if ':' in lines[1] else ''
                        status = lines[2].split(':')[1].strip() if ':' in lines[2] else ''
                        
                        if service_name:
                            services.append({
                                'name': service_name,
                                'display_name': display_name,
                                'status': status.lower(),
                                'startup_type': 'unknown',
                                'pid': None
                            })
                            
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to get services with sc: {e}")
        
        return services
    
    def _get_service_status_text(self, status_code: int) -> str:
        """Convert Windows service status code to text"""
        status_map = {
            1: 'stopped',
            2: 'start_pending',
            3: 'stop_pending',
            4: 'running',
            5: 'continue_pending',
            6: 'pause_pending',
            7: 'paused'
        }
        return status_map.get(status_code, 'unknown')
    
    def start_service(self, service_name: str) -> bool:
        """Start Windows service"""
        try:
            result = subprocess.run(['sc', 'start', service_name], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to start service {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop Windows service"""
        try:
            result = subprocess.run(['sc', 'stop', service_name], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    def get_startup_programs(self) -> List[Dict[str, Any]]:
        """Get Windows startup programs"""
        startup_programs = []
        
        if winreg:
            # Check registry locations for startup programs
            registry_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ]
            
            for hive, path in registry_paths:
                try:
                    key = winreg.OpenKey(hive, path)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            startup_programs.append({
                                'id': f"{hive}\\{path}\\{name}",
                                'name': name,
                                'command': value,
                                'location': 'registry',
                                'enabled': True
                            })
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                except Exception as e:
                    self.logger.debug(f"Could not access registry path {path}: {e}")
        
        # Check Startup folder
        startup_folders = [
            Path.home() / 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup',
            Path('C:/ProgramData/Microsoft/Windows/Start Menu/Programs/StartUp')
        ]
        
        for folder in startup_folders:
            if folder.exists():
                for item in folder.iterdir():
                    if item.is_file():
                        startup_programs.append({
                            'id': str(item),
                            'name': item.name,
                            'command': str(item),
                            'location': 'startup_folder',
                            'enabled': True
                        })
        
        return startup_programs
    
    def disable_startup_program(self, program_id: str) -> bool:
        """Disable Windows startup program"""
        try:
            if program_id.startswith('HKEY'):
                # Registry entry
                if not winreg:
                    return False
                
                parts = program_id.split('\\')
                hive_name = parts[0]
                key_path = '\\'.join(parts[1:-1])
                value_name = parts[-1]
                
                hive = getattr(winreg, hive_name)
                key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, value_name)
                winreg.CloseKey(key)
                
                return True
                
            else:
                # File in startup folder
                file_path = Path(program_id)
                if file_path.exists():
                    file_path.unlink()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to disable startup program {program_id}: {e}")
        
        return False
    
    def cleanup_temp_files(self) -> Dict[str, int]:
        """Clean up Windows temporary files"""
        cleanup_stats = {
            'files_deleted': 0,
            'space_freed': 0,
            'errors': 0
        }
        
        temp_locations = [
            Path(os.getenv('TEMP', '')),
            Path(os.getenv('TMP', '')),
            Path('C:/Windows/Temp'),
            Path.home() / 'AppData/Local/Temp',
            Path('C:/Users/Default/AppData/Local/Temp')
        ]
        
        for temp_dir in temp_locations:
            if temp_dir.exists():
                try:
                    for item in temp_dir.iterdir():
                        try:
                            if item.is_file():
                                size = item.stat().st_size
                                item.unlink()
                                cleanup_stats['files_deleted'] += 1
                                cleanup_stats['space_freed'] += size
                            elif item.is_dir() and item.name.startswith('tmp'):
                                shutil.rmtree(item)
                                cleanup_stats['files_deleted'] += 1
                                
                        except (PermissionError, FileNotFoundError):
                            cleanup_stats['errors'] += 1
                            continue
                            
                except PermissionError:
                    cleanup_stats['errors'] += 1
                    continue
        
        return cleanup_stats
    
    def optimize_system(self) -> Dict[str, Any]:
        """Perform Windows-specific optimizations"""
        optimizations = {
            'registry_cleaned': False,
            'services_optimized': False,
            'startup_optimized': False,
            'temp_cleaned': False,
            'performance_tweaks': False
        }
        
        try:
            # Clean temporary files
            cleanup_result = self.cleanup_temp_files()
            optimizations['temp_cleaned'] = cleanup_result['files_deleted'] > 0
            
            # Basic registry cleanup (safe operations only)
            if winreg:
                try:
                    # Clear run dialog history
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                       r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
                                       0, winreg.KEY_SET_VALUE)
                    i = 0
                    while True:
                        try:
                            value_name, _, _ = winreg.EnumValue(key, i)
                            if value_name != 'MRUList':
                                winreg.DeleteValue(key, value_name)
                            else:
                                winreg.SetValueEx(key, 'MRUList', 0, winreg.REG_SZ, '')
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                    optimizations['registry_cleaned'] = True
                except Exception:
                    pass
            
            # Performance tweaks via registry
            if winreg:
                try:
                    # Disable Windows Search indexing for better performance
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                       r"SYSTEM\CurrentControlSet\Services\WSearch",
                                       0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, 'Start', 0, winreg.REG_DWORD, 4)  # Disabled
                    winreg.CloseKey(key)
                    optimizations['performance_tweaks'] = True
                except Exception:
                    pass
        
        except Exception as e:
            self.logger.error(f"Error during Windows optimization: {e}")
        
        return optimizations
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get Windows-specific system metrics"""
        metrics = {}
        
        try:
            # Windows Performance Counters
            import subprocess
            
            # Get memory info
            result = subprocess.run(['wmic', 'computersystem', 'get', 'TotalPhysicalMemory', '/value'], 
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'TotalPhysicalMemory=' in line:
                    metrics['total_memory'] = int(line.split('=')[1]) if line.split('=')[1] else 0
            
            # Get CPU info
            result = subprocess.run(['wmic', 'cpu', 'get', 'NumberOfCores,NumberOfLogicalProcessors', '/value'], 
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'NumberOfCores=' in line:
                    metrics['cpu_cores'] = int(line.split('=')[1]) if line.split('=')[1] else 0
                elif 'NumberOfLogicalProcessors=' in line:
                    metrics['cpu_threads'] = int(line.split('=')[1]) if line.split('=')[1] else 0
            
            # Windows-specific metrics
            metrics['platform_specific'] = {
                'windows_version': platform.win32_ver(),
                'registry_size': self._estimate_registry_size(),
                'services_count': len(self.get_system_services()),
                'startup_programs': len(self.get_startup_programs())
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Windows metrics: {e}")
        
        return metrics
    
    def _estimate_registry_size(self) -> int:
        """Estimate Windows registry size"""
        try:
            registry_files = [
                Path('C:/Windows/System32/config/SYSTEM'),
                Path('C:/Windows/System32/config/SOFTWARE'),
                Path('C:/Windows/System32/config/SECURITY'),
                Path('C:/Windows/System32/config/SAM'),
                Path.home() / 'NTUSER.DAT'
            ]
            
            total_size = 0
            for reg_file in registry_files:
                if reg_file.exists():
                    total_size += reg_file.stat().st_size
            
            return total_size
            
        except Exception:
            return 0

class LinuxPlatform(PlatformInterface):
    """Linux-specific implementation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.Linux')
    
    def get_system_info(self) -> SystemInfo:
        """Get Linux system information"""
        import getpass
        
        return SystemInfo(
            platform="Linux",
            platform_version=platform.platform(),
            architecture=platform.machine(),
            hostname=platform.node(),
            username=getpass.getuser(),
            home_dir=Path.home(),
            temp_dir=Path('/tmp'),
            config_dir=Path.home() / '.system_optimizer_pro',
            log_dir=Path.home() / '.system_optimizer_pro/logs'
        )
    
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """Get Linux running processes"""
        processes = []
        
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'status']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_mb': proc.info['memory_info'].rss // 1024 // 1024,
                        'cpu_percent': proc.info['cpu_percent'] or 0,
                        'status': proc.info['status']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            # Fallback using ps command
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, check=True)
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append({
                            'pid': int(parts[1]),
                            'name': parts[10].split()[0],
                            'memory_mb': int(float(parts[5])) // 1024,  # VSZ in KB
                            'cpu_percent': float(parts[2]),
                            'status': 'running'
                        })
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to get processes: {e}")
        
        return processes
    
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill Linux process"""
        try:
            signal_type = '-9' if force else '-15'
            result = subprocess.run(['kill', signal_type, str(pid)], 
                                  capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to kill process {pid}: {e}")
            return False
    
    def get_system_services(self) -> List[Dict[str, Any]]:
        """Get Linux system services"""
        services = []
        
        # Try systemd first
        try:
            result = subprocess.run(['systemctl', 'list-units', '--type=service', '--all', '--no-pager'], 
                                  capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if not line.strip() or line.startswith('●'):
                    continue
                
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    services.append({
                        'name': parts[0].replace('.service', ''),
                        'display_name': parts[4] if len(parts) > 4 else parts[0],
                        'status': parts[2].lower(),
                        'startup_type': 'enabled' if parts[1] == 'loaded' else 'disabled',
                        'pid': None
                    })
                    
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to init.d services
            try:
                init_dir = Path('/etc/init.d')
                if init_dir.exists():
                    for service_file in init_dir.iterdir():
                        if service_file.is_file() and service_file.stat().st_mode & 0o111:
                            services.append({
                                'name': service_file.name,
                                'display_name': service_file.name,
                                'status': 'unknown',
                                'startup_type': 'unknown',
                                'pid': None
                            })
            except Exception as e:
                self.logger.error(f"Failed to get init.d services: {e}")
        
        return services
    
    def start_service(self, service_name: str) -> bool:
        """Start Linux service"""
        try:
            # Try systemctl first
            result = subprocess.run(['sudo', 'systemctl', 'start', service_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return True
                
            # Fallback to service command
            result = subprocess.run(['sudo', 'service', service_name, 'start'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to start service {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop Linux service"""
        try:
            # Try systemctl first
            result = subprocess.run(['sudo', 'systemctl', 'stop', service_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return True
                
            # Fallback to service command
            result = subprocess.run(['sudo', 'service', service_name, 'stop'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    def get_startup_programs(self) -> List[Dict[str, Any]]:
        """Get Linux startup programs"""
        startup_programs = []
        
        # Check desktop autostart files
        autostart_dirs = [
            Path.home() / '.config/autostart',
            Path('/etc/xdg/autostart')
        ]
        
        for autostart_dir in autostart_dirs:
            if autostart_dir.exists():
                for desktop_file in autostart_dir.glob('*.desktop'):
                    try:
                        content = desktop_file.read_text()
                        name = ''
                        command = ''
                        enabled = True
                        
                        for line in content.split('\n'):
                            if line.startswith('Name='):
                                name = line.split('=', 1)[1]
                            elif line.startswith('Exec='):
                                command = line.split('=', 1)[1]
                            elif line.startswith('Hidden=true') or line.startswith('X-GNOME-Autostart-enabled=false'):
                                enabled = False
                        
                        if name and command:
                            startup_programs.append({
                                'id': str(desktop_file),
                                'name': name,
                                'command': command,
                                'location': 'desktop_file',
                                'enabled': enabled
                            })
                            
                    except Exception as e:
                        self.logger.debug(f"Could not parse desktop file {desktop_file}: {e}")
        
        # Check user's shell profile files
        profile_files = [
            Path.home() / '.profile',
            Path.home() / '.bashrc',
            Path.home() / '.bash_profile',
            Path.home() / '.zshrc'
        ]
        
        for profile_file in profile_files:
            if profile_file.exists():
                try:
                    content = profile_file.read_text()
                    for line_num, line in enumerate(content.split('\n'), 1):
                        line = line.strip()
                        if line and not line.startswith('#') and ('&' in line or 'nohup' in line):
                            startup_programs.append({
                                'id': f"{profile_file}:{line_num}",
                                'name': f"Shell startup ({profile_file.name})",
                                'command': line,
                                'location': 'shell_profile',
                                'enabled': True
                            })
                except Exception as e:
                    self.logger.debug(f"Could not parse profile file {profile_file}: {e}")
        
        return startup_programs
    
    def disable_startup_program(self, program_id: str) -> bool:
        """Disable Linux startup program"""
        try:
            if program_id.endswith('.desktop'):
                # Desktop file
                desktop_file = Path(program_id)
                if desktop_file.exists():
                    content = desktop_file.read_text()
                    if 'Hidden=true' not in content:
                        content += '\nHidden=true\n'
                        desktop_file.write_text(content)
                    return True
                    
            elif ':' in program_id:
                # Shell profile entry
                file_path, line_num = program_id.split(':', 1)
                profile_file = Path(file_path)
                if profile_file.exists():
                    lines = profile_file.read_text().split('\n')
                    line_idx = int(line_num) - 1
                    if 0 <= line_idx < len(lines):
                        lines[line_idx] = '# ' + lines[line_idx]  # Comment out
                        profile_file.write_text('\n'.join(lines))
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to disable startup program {program_id}: {e}")
        
        return False
    
    def cleanup_temp_files(self) -> Dict[str, int]:
        """Clean up Linux temporary files"""
        cleanup_stats = {
            'files_deleted': 0,
            'space_freed': 0,
            'errors': 0
        }
        
        temp_locations = [
            Path('/tmp'),
            Path('/var/tmp'),
            Path.home() / '.cache',
            Path.home() / '.local/share/Trash'
        ]
        
        for temp_dir in temp_locations:
            if temp_dir.exists():
                try:
                    for item in temp_dir.iterdir():
                        try:
                            if item.is_file() and item.name.startswith('tmp'):
                                size = item.stat().st_size
                                item.unlink()
                                cleanup_stats['files_deleted'] += 1
                                cleanup_stats['space_freed'] += size
                            elif item.is_dir() and item.name.startswith('tmp'):
                                shutil.rmtree(item)
                                cleanup_stats['files_deleted'] += 1
                                
                        except (PermissionError, FileNotFoundError):
                            cleanup_stats['errors'] += 1
                            continue
                            
                except PermissionError:
                    cleanup_stats['errors'] += 1
                    continue
        
        # Clean package manager caches
        try:
            # APT cache
            if shutil.which('apt-get'):
                result = subprocess.run(['sudo', 'apt-get', 'clean'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    cleanup_stats['files_deleted'] += 1
            
            # YUM/DNF cache
            if shutil.which('dnf'):
                result = subprocess.run(['sudo', 'dnf', 'clean', 'all'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    cleanup_stats['files_deleted'] += 1
            elif shutil.which('yum'):
                result = subprocess.run(['sudo', 'yum', 'clean', 'all'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    cleanup_stats['files_deleted'] += 1
                    
        except Exception as e:
            self.logger.debug(f"Package cache cleanup error: {e}")
        
        return cleanup_stats
    
    def optimize_system(self) -> Dict[str, Any]:
        """Perform Linux-specific optimizations"""
        optimizations = {
            'temp_cleaned': False,
            'packages_updated': False,
            'services_optimized': False,
            'kernel_parameters': False,
            'swap_optimized': False
        }
        
        try:
            # Clean temporary files
            cleanup_result = self.cleanup_temp_files()
            optimizations['temp_cleaned'] = cleanup_result['files_deleted'] > 0
            
            # Optimize swap usage
            try:
                result = subprocess.run(['sudo', 'sysctl', 'vm.swappiness=10'], 
                                      capture_output=True, text=True)
                optimizations['swap_optimized'] = result.returncode == 0
            except Exception:
                pass
            
            # Update package database (but don't upgrade)
            try:
                if shutil.which('apt-get'):
                    result = subprocess.run(['sudo', 'apt-get', 'update'], 
                                          capture_output=True, text=True, timeout=300)
                    optimizations['packages_updated'] = result.returncode == 0
                elif shutil.which('dnf'):
                    result = subprocess.run(['sudo', 'dnf', 'check-update'], 
                                          capture_output=True, text=True, timeout=300)
                    optimizations['packages_updated'] = True  # Always returns non-zero if updates available
            except Exception:
                pass
        
        except Exception as e:
            self.logger.error(f"Error during Linux optimization: {e}")
        
        return optimizations
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get Linux-specific system metrics"""
        metrics = {}
        
        try:
            # Memory info from /proc/meminfo
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if 'MemTotal:' in line:
                        metrics['total_memory'] = int(line.split()[1]) * 1024  # Convert KB to bytes
                    elif 'MemAvailable:' in line:
                        metrics['available_memory'] = int(line.split()[1]) * 1024
            
            # CPU info from /proc/cpuinfo
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                metrics['cpu_cores'] = cpuinfo.count('processor\t:')
            
            # Load average
            with open('/proc/loadavg', 'r') as f:
                load_avg = f.read().strip().split()[:3]
                metrics['load_average'] = [float(x) for x in load_avg]
            
            # Linux-specific metrics
            metrics['platform_specific'] = {
                'kernel_version': platform.release(),
                'distribution': self._get_distribution_info(),
                'uptime': self._get_uptime(),
                'package_count': self._get_package_count()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Linux metrics: {e}")
        
        return metrics
    
    def _get_distribution_info(self) -> Dict[str, str]:
        """Get Linux distribution information"""
        try:
            # Try /etc/os-release first
            if Path('/etc/os-release').exists():
                with open('/etc/os-release', 'r') as f:
                    info = {}
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            info[key] = value.strip('"')
                    return info
            
            # Fallback to lsb_release
            result = subprocess.run(['lsb_release', '-a'], capture_output=True, text=True)
            if result.returncode == 0:
                info = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip().lower().replace(' ', '_')] = value.strip()
                return info
                
        except Exception:
            pass
        
        return {'name': 'Unknown', 'version': 'Unknown'}
    
    def _get_uptime(self) -> float:
        """Get system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.read().split()[0])
        except Exception:
            return 0.0
    
    def _get_package_count(self) -> int:
        """Get installed package count"""
        try:
            if shutil.which('dpkg'):
                result = subprocess.run(['dpkg', '-l'], capture_output=True, text=True)
                return len([line for line in result.stdout.split('\n') if line.startswith('ii')])
            elif shutil.which('rpm'):
                result = subprocess.run(['rpm', '-qa'], capture_output=True, text=True)
                return len([line for line in result.stdout.split('\n') if line.strip()])
        except Exception:
            pass
        
        return 0

# Platform factory
class PlatformManager:
    """Factory for creating platform-specific implementations"""
    
    _instance = None
    _platform = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_platform(self) -> PlatformInterface:
        """Get the appropriate platform implementation"""
        if self._platform is None:
            system = platform.system().lower()
            
            if system == 'windows':
                self._platform = WindowsPlatform()
            elif system == 'linux':
                self._platform = LinuxPlatform()
            else:
                # Default to Linux for Unix-like systems
                self._platform = LinuxPlatform()
        
        return self._platform
    
    def is_windows(self) -> bool:
        """Check if running on Windows"""
        return platform.system().lower() == 'windows'
    
    def is_linux(self) -> bool:
        """Check if running on Linux"""
        return platform.system().lower() == 'linux'
    
    def get_system_info(self) -> SystemInfo:
        """Get cross-platform system information"""
        return self.get_platform().get_system_info()

# Global platform manager instance
platform_manager = PlatformManager()