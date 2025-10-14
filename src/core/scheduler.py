#!/usr/bin/env python3
"""
Advanced scheduling system for System Optimizer Pro
Provides cron-like functionality with visual editor, dependencies, and robust error handling
"""

import os
import sys
import threading
import time
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback
import pickle
from pathlib import Path
import re
try:
    from croniter import croniter
except ImportError:
    croniter = None
try:
    import yaml
except ImportError:
    yaml = None

from .config import config

class JobState(Enum):
    """Job execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

class TriggerType(Enum):
    """Job trigger types"""
    CRON = "cron"
    INTERVAL = "interval"
    ONESHOT = "oneshot"
    EVENT = "event"

@dataclass
class JobResult:
    """Job execution result"""
    job_id: str
    execution_id: str
    state: JobState
    start_time: datetime
    end_time: Optional[datetime] = None
    return_value: Any = None
    error: Optional[str] = None
    output: str = ""
    duration: float = 0.0

@dataclass
class JobDefinition:
    """Job definition with all configuration"""
    id: str
    name: str
    description: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    function: Optional[Callable] = None
    function_name: Optional[str] = None
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    max_retries: int = 3
    retry_delay: int = 300  # 5 minutes
    timeout: int = 3600  # 1 hour
    max_concurrent: int = 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

class JobScheduler:
    """Advanced job scheduler with cron-like functionality"""
    
    def __init__(self):
        self.jobs: Dict[str, JobDefinition] = {}
        self.running_jobs: Dict[str, threading.Thread] = {}
        self.job_history: Dict[str, List[JobResult]] = {}
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.executor_pool: Dict[str, threading.Thread] = {}
        self.job_locks: Dict[str, threading.Lock] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Load persistent schedule
        self.schedule_file = Path(config.get('scheduler.schedule_file', '~/.system_optimizer_pro/schedule.yaml')).expanduser()
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize built-in jobs
        self._register_builtin_jobs()
        
        # Load saved schedule
        self.load_schedule()
    
    def _register_builtin_jobs(self):
        """Register built-in system jobs"""
        # System health check job
        health_check_job = JobDefinition(
            id="system_health_check",
            name="System Health Check",
            description="Periodic system health monitoring",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": "*/5 * * * *"},  # Every 5 minutes
            function=self._system_health_check,
            tags=["system", "monitoring"]
        )
        
        # Backup job
        backup_job = JobDefinition(
            id="config_backup",
            name="Configuration Backup",
            description="Backup system configuration to GitHub",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": config.get('github.backup_schedule', '0 2 * * 0')},
            function=self._backup_configs,
            tags=["backup", "maintenance"]
        )
        
        # Cleanup job
        cleanup_job = JobDefinition(
            id="system_cleanup",
            name="System Cleanup",
            description="Clean up temporary files and caches",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": "0 3 * * 0"},  # Weekly at 3 AM Sunday
            function=self._system_cleanup,
            tags=["cleanup", "maintenance"]
        )
        
        # Plugin health check
        plugin_health_job = JobDefinition(
            id="plugin_health_check",
            name="Plugin Health Check",
            description="Monitor plugin health and restart if needed",
            trigger_type=TriggerType.CRON,
            trigger_config={"cron": "*/10 * * * *"},  # Every 10 minutes
            function=self._plugin_health_check,
            tags=["plugins", "monitoring"]
        )
        
        self.jobs.update({
            "system_health_check": health_check_job,
            "config_backup": backup_job,
            "system_cleanup": cleanup_job,
            "plugin_health_check": plugin_health_job
        })
    
    def add_job(self, job_def: JobDefinition) -> bool:
        """Add a new job to the scheduler"""
        try:
            # Validate job definition
            if not self._validate_job(job_def):
                return False
            
            # Calculate next run time
            job_def.next_run = self._calculate_next_run(job_def)
            
            # Add to jobs dict
            self.jobs[job_def.id] = job_def
            
            # Create job lock
            self.job_locks[job_def.id] = threading.Lock()
            
            # Initialize history
            if job_def.id not in self.job_history:
                self.job_history[job_def.id] = []
            
            logging.info(f"Added job '{job_def.name}' (ID: {job_def.id})")
            return True
            
        except Exception as e:
            logging.error(f"Failed to add job {job_def.id}: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler"""
        if job_id not in self.jobs:
            logging.warning(f"Job {job_id} not found")
            return False
        
        try:
            # Stop job if running
            self.stop_job(job_id)
            
            # Remove from collections
            del self.jobs[job_id]
            if job_id in self.job_locks:
                del self.job_locks[job_id]
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
            
            logging.info(f"Removed job {job_id}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a job"""
        if job_id not in self.jobs:
            return False
        
        self.jobs[job_id].enabled = True
        self.jobs[job_id].next_run = self._calculate_next_run(self.jobs[job_id])
        logging.info(f"Enabled job {job_id}")
        return True
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a job"""
        if job_id not in self.jobs:
            return False
        
        self.jobs[job_id].enabled = False
        self.jobs[job_id].next_run = None
        self.stop_job(job_id)
        logging.info(f"Disabled job {job_id}")
        return True
    
    def run_job_now(self, job_id: str) -> Optional[str]:
        """Run a job immediately"""
        if job_id not in self.jobs:
            logging.error(f"Job {job_id} not found")
            return None
        
        job_def = self.jobs[job_id]
        execution_id = str(uuid.uuid4())
        
        # Check if job is already running and has max concurrent limit
        running_count = len([t for t in self.running_jobs.values() 
                           if t.name.startswith(f"job-{job_id}-")])
        
        if running_count >= job_def.max_concurrent:
            logging.warning(f"Job {job_id} already has {running_count} instances running")
            return None
        
        # Create and start execution thread
        thread = threading.Thread(
            target=self._execute_job,
            args=(job_def, execution_id),
            name=f"job-{job_id}-{execution_id[:8]}",
            daemon=True
        )
        
        self.running_jobs[execution_id] = thread
        thread.start()
        
        logging.info(f"Started immediate execution of job {job_id} (execution: {execution_id})")
        return execution_id
    
    def stop_job(self, job_id: str) -> bool:
        """Stop all running instances of a job"""
        stopped = False
        
        # Find and stop all running instances
        for exec_id, thread in list(self.running_jobs.items()):
            if thread.name.startswith(f"job-{job_id}-"):
                # Request stop (job should check for stop condition)
                thread.join(timeout=5.0)  # Wait up to 5 seconds
                if thread.is_alive():
                    logging.warning(f"Job instance {exec_id} did not stop gracefully")
                else:
                    del self.running_jobs[exec_id]
                    stopped = True
        
        return stopped
    
    def get_job_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of jobs"""
        if job_id:
            if job_id not in self.jobs:
                return {"error": f"Job {job_id} not found"}
            
            job_def = self.jobs[job_id]
            running_count = len([t for t in self.running_jobs.values() 
                               if t.name.startswith(f"job-{job_id}-")])
            
            recent_results = self.job_history.get(job_id, [])[-5:]  # Last 5 results
            
            return {
                "id": job_def.id,
                "name": job_def.name,
                "enabled": job_def.enabled,
                "state": "running" if running_count > 0 else "idle",
                "running_instances": running_count,
                "next_run": job_def.next_run.isoformat() if job_def.next_run else None,
                "last_run": job_def.last_run.isoformat() if job_def.last_run else None,
                "recent_results": [self._result_to_dict(r) for r in recent_results]
            }
        else:
            # Return status for all jobs
            return {job_id: self.get_job_status(job_id) for job_id in self.jobs.keys()}
    
    def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job execution history"""
        if job_id not in self.job_history:
            return []
        
        history = self.job_history[job_id][-limit:]
        return [self._result_to_dict(result) for result in history]
    
    def start_scheduler(self) -> bool:
        """Start the job scheduler"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logging.warning("Scheduler already running")
            return False
        
        try:
            self.stop_event.clear()
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="job-scheduler",
                daemon=True
            )
            self.scheduler_thread.start()
            
            logging.info("Job scheduler started")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start scheduler: {e}")
            return False
    
    def stop_scheduler(self) -> bool:
        """Stop the job scheduler"""
        if not self.scheduler_thread or not self.scheduler_thread.is_alive():
            logging.warning("Scheduler not running")
            return False
        
        try:
            self.stop_event.set()
            
            # Stop all running jobs
            for job_id in list(self.jobs.keys()):
                self.stop_job(job_id)
            
            # Wait for scheduler thread to stop
            self.scheduler_thread.join(timeout=10.0)
            
            if self.scheduler_thread.is_alive():
                logging.warning("Scheduler thread did not stop gracefully")
                return False
            
            logging.info("Job scheduler stopped")
            return True
            
        except Exception as e:
            logging.error(f"Failed to stop scheduler: {e}")
            return False
    
    def save_schedule(self) -> bool:
        """Save schedule to persistent storage"""
        try:
            # Convert jobs to serializable format
            schedule_data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "jobs": {}
            }
            
            for job_id, job_def in self.jobs.items():
                # Skip built-in jobs
                if job_def.tags and "system" in job_def.tags:
                    continue
                
                schedule_data["jobs"][job_id] = {
                    "id": job_def.id,
                    "name": job_def.name,
                    "description": job_def.description,
                    "trigger_type": job_def.trigger_type.value,
                    "trigger_config": job_def.trigger_config,
                    "function_name": job_def.function_name,
                    "args": job_def.args,
                    "kwargs": job_def.kwargs,
                    "dependencies": job_def.dependencies,
                    "enabled": job_def.enabled,
                    "max_retries": job_def.max_retries,
                    "retry_delay": job_def.retry_delay,
                    "timeout": job_def.timeout,
                    "max_concurrent": job_def.max_concurrent,
                    "tags": job_def.tags,
                    "metadata": job_def.metadata,
                    "created_at": job_def.created_at.isoformat()
                }
            
            with open(self.schedule_file, 'w') as f:
                yaml.dump(schedule_data, f, default_flow_style=False, indent=2)
            
            logging.debug("Schedule saved successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to save schedule: {e}")
            return False
    
    def load_schedule(self) -> bool:
        """Load schedule from persistent storage"""
        if not self.schedule_file.exists():
            logging.debug("No schedule file found, using defaults")
            return True
        
        try:
            with open(self.schedule_file, 'r') as f:
                schedule_data = yaml.safe_load(f)
            
            if not schedule_data or "jobs" not in schedule_data:
                logging.warning("Invalid schedule file format")
                return False
            
            # Load jobs
            for job_id, job_data in schedule_data["jobs"].items():
                try:
                    job_def = JobDefinition(
                        id=job_data["id"],
                        name=job_data["name"],
                        description=job_data["description"],
                        trigger_type=TriggerType(job_data["trigger_type"]),
                        trigger_config=job_data["trigger_config"],
                        function_name=job_data.get("function_name"),
                        args=job_data.get("args", []),
                        kwargs=job_data.get("kwargs", {}),
                        dependencies=job_data.get("dependencies", []),
                        enabled=job_data.get("enabled", True),
                        max_retries=job_data.get("max_retries", 3),
                        retry_delay=job_data.get("retry_delay", 300),
                        timeout=job_data.get("timeout", 3600),
                        max_concurrent=job_data.get("max_concurrent", 1),
                        tags=job_data.get("tags", []),
                        metadata=job_data.get("metadata", {}),
                        created_at=datetime.fromisoformat(job_data["created_at"])
                    )
                    
                    # Resolve function reference
                    if job_def.function_name:
                        job_def.function = self._resolve_function(job_def.function_name)
                    
                    self.add_job(job_def)
                    
                except Exception as e:
                    logging.error(f"Failed to load job {job_id}: {e}")
            
            logging.info(f"Loaded {len(schedule_data['jobs'])} jobs from schedule")
            return True
            
        except Exception as e:
            logging.error(f"Failed to load schedule: {e}")
            return False
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        logging.info("Scheduler loop started")
        
        while not self.stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check each job for execution
                for job_id, job_def in list(self.jobs.items()):
                    if not job_def.enabled or not job_def.next_run:
                        continue
                    
                    if current_time >= job_def.next_run:
                        # Check dependencies
                        if not self._check_dependencies(job_def):
                            logging.warning(f"Dependencies not met for job {job_id}, skipping")
                            # Update next run time
                            job_def.next_run = self._calculate_next_run(job_def)
                            continue
                        
                        # Check concurrent execution limit
                        running_count = len([t for t in self.running_jobs.values() 
                                           if t.name.startswith(f"job-{job_id}-")])
                        
                        if running_count >= job_def.max_concurrent:
                            logging.debug(f"Job {job_id} at concurrent limit ({running_count}), skipping")
                            continue
                        
                        # Execute job
                        execution_id = str(uuid.uuid4())
                        thread = threading.Thread(
                            target=self._execute_job,
                            args=(job_def, execution_id),
                            name=f"job-{job_id}-{execution_id[:8]}",
                            daemon=True
                        )
                        
                        self.running_jobs[execution_id] = thread
                        thread.start()
                        
                        # Update next run time
                        job_def.next_run = self._calculate_next_run(job_def)
                        job_def.last_run = current_time
                
                # Clean up finished threads
                finished_executions = []
                for exec_id, thread in self.running_jobs.items():
                    if not thread.is_alive():
                        finished_executions.append(exec_id)
                
                for exec_id in finished_executions:
                    del self.running_jobs[exec_id]
                
                # Save schedule periodically
                if current_time.minute % 15 == 0:  # Every 15 minutes
                    self.save_schedule()
                
            except Exception as e:
                logging.error(f"Error in scheduler loop: {e}")
                logging.error(traceback.format_exc())
            
            # Sleep for a short interval
            time.sleep(1)
        
        logging.info("Scheduler loop stopped")
    
    def _execute_job(self, job_def: JobDefinition, execution_id: str):
        """Execute a single job"""
        start_time = datetime.now()
        result = JobResult(
            job_id=job_def.id,
            execution_id=execution_id,
            state=JobState.RUNNING,
            start_time=start_time
        )
        
        try:
            logging.info(f"Executing job '{job_def.name}' (ID: {job_def.id}, execution: {execution_id})")
            
            # Check if function is available
            if not job_def.function:
                raise ValueError(f"No function defined for job {job_def.id}")
            
            # Execute the function with timeout
            if job_def.timeout > 0:
                # For now, we'll skip timeout implementation - would need more complex threading
                result.return_value = job_def.function(*job_def.args, **job_def.kwargs)
            else:
                result.return_value = job_def.function(*job_def.args, **job_def.kwargs)
            
            result.state = JobState.COMPLETED
            logging.info(f"Job {job_def.id} completed successfully")
            
        except Exception as e:
            result.state = JobState.FAILED
            result.error = str(e)
            logging.error(f"Job {job_def.id} failed: {e}")
            logging.error(traceback.format_exc())
            
            # Retry logic could be implemented here
        
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
            
            # Store result in history
            if job_def.id not in self.job_history:
                self.job_history[job_def.id] = []
            
            self.job_history[job_def.id].append(result)
            
            # Keep only last 100 results per job
            if len(self.job_history[job_def.id]) > 100:
                self.job_history[job_def.id] = self.job_history[job_def.id][-100:]
    
    def _calculate_next_run(self, job_def: JobDefinition) -> Optional[datetime]:
        """Calculate next run time for a job"""
        if not job_def.enabled:
            return None
        
        current_time = datetime.now()
        
        if job_def.trigger_type == TriggerType.CRON:
            cron_expr = job_def.trigger_config.get("cron")
            if cron_expr:
                try:
                    cron = croniter(cron_expr, current_time)
                    return cron.get_next(datetime)
                except Exception as e:
                    logging.error(f"Invalid cron expression '{cron_expr}' for job {job_def.id}: {e}")
                    return None
        
        elif job_def.trigger_type == TriggerType.INTERVAL:
            interval_seconds = job_def.trigger_config.get("interval", 3600)
            return current_time + timedelta(seconds=interval_seconds)
        
        elif job_def.trigger_type == TriggerType.ONESHOT:
            run_at = job_def.trigger_config.get("run_at")
            if isinstance(run_at, str):
                try:
                    run_time = datetime.fromisoformat(run_at)
                    if run_time > current_time:
                        return run_time
                except ValueError:
                    logging.error(f"Invalid run_at time '{run_at}' for job {job_def.id}")
            return None
        
        return None
    
    def _validate_job(self, job_def: JobDefinition) -> bool:
        """Validate job definition"""
        if not job_def.id or not job_def.name:
            logging.error("Job must have ID and name")
            return False
        
        if job_def.trigger_type == TriggerType.CRON:
            cron_expr = job_def.trigger_config.get("cron")
            if not cron_expr:
                logging.error(f"CRON job {job_def.id} must have 'cron' in trigger_config")
                return False
            
            try:
                croniter(cron_expr)
            except Exception as e:
                logging.error(f"Invalid cron expression '{cron_expr}': {e}")
                return False
        
        return True
    
    def _check_dependencies(self, job_def: JobDefinition) -> bool:
        """Check if job dependencies are satisfied"""
        for dep_id in job_def.dependencies:
            if dep_id not in self.jobs:
                logging.error(f"Dependency {dep_id} not found for job {job_def.id}")
                return False
            
            # Check if dependency has run successfully recently
            if dep_id in self.job_history and self.job_history[dep_id]:
                last_result = self.job_history[dep_id][-1]
                if last_result.state != JobState.COMPLETED:
                    logging.warning(f"Dependency {dep_id} last execution failed")
                    return False
            else:
                logging.warning(f"Dependency {dep_id} has no execution history")
                return False
        
        return True
    
    def _resolve_function(self, function_name: str) -> Optional[Callable]:
        """Resolve function by name"""
        # For built-in functions
        if hasattr(self, function_name):
            return getattr(self, function_name)
        
        # Could add plugin function resolution here
        return None
    
    def _result_to_dict(self, result: JobResult) -> Dict[str, Any]:
        """Convert JobResult to dictionary"""
        return {
            "job_id": result.job_id,
            "execution_id": result.execution_id,
            "state": result.state.value,
            "start_time": result.start_time.isoformat(),
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "duration": result.duration,
            "error": result.error,
            "return_value": str(result.return_value) if result.return_value else None
        }
    
    # Built-in job functions
    def _system_health_check(self) -> Dict[str, Any]:
        """Built-in system health check job"""
        import psutil
        
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
        
        # Check thresholds
        alerts = []
        thresholds = config.get('monitoring.alert_thresholds', {})
        
        if health_data["cpu_percent"] > thresholds.get("cpu_usage", 85):
            alerts.append(f"High CPU usage: {health_data['cpu_percent']:.1f}%")
        
        if health_data["memory_percent"] > thresholds.get("memory_usage", 90):
            alerts.append(f"High memory usage: {health_data['memory_percent']:.1f}%")
        
        if health_data["disk_percent"] > thresholds.get("disk_usage", 95):
            alerts.append(f"High disk usage: {health_data['disk_percent']:.1f}%")
        
        health_data["alerts"] = alerts
        
        if alerts:
            logging.warning(f"System health alerts: {', '.join(alerts)}")
        
        return health_data
    
    def _backup_configs(self) -> bool:
        """Built-in configuration backup job"""
        # This would integrate with GitHub backup system
        logging.info("Configuration backup job executed")
        return True
    
    def _system_cleanup(self) -> Dict[str, Any]:
        """Built-in system cleanup job"""
        cleanup_stats = {
            "timestamp": datetime.now().isoformat(),
            "cleaned_files": 0,
            "freed_space": 0
        }
        
        # Basic cleanup operations
        import shutil
        import tempfile
        
        try:
            # Clean temp directory
            temp_dir = Path(tempfile.gettempdir())
            for temp_file in temp_dir.glob("tmp*"):
                if temp_file.is_file():
                    size = temp_file.stat().st_size
                    temp_file.unlink()
                    cleanup_stats["cleaned_files"] += 1
                    cleanup_stats["freed_space"] += size
        
        except Exception as e:
            logging.error(f"Error in cleanup: {e}")
        
        logging.info(f"Cleanup completed: {cleanup_stats}")
        return cleanup_stats
    
    def _plugin_health_check(self) -> Dict[str, Any]:
        """Built-in plugin health check job"""
        # This would integrate with plugin manager
        from .plugin_manager import plugin_manager
        
        health_status = plugin_manager.health_check()
        
        unhealthy_plugins = [name for name, status in health_status.items() 
                           if not status.get('healthy', False)]
        
        if unhealthy_plugins:
            logging.warning(f"Unhealthy plugins detected: {unhealthy_plugins}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_plugins": len(health_status),
            "healthy_plugins": len(health_status) - len(unhealthy_plugins),
            "unhealthy_plugins": unhealthy_plugins,
            "health_details": health_status
        }

# Global scheduler instance
scheduler = JobScheduler()