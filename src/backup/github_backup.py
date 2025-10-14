#!/usr/bin/env python3
"""
GitHub backup integration for System Optimizer Pro
Handles automated backup of configurations, logs, and system data to GitHub
"""

import os
import base64
import json
import gzip
import tarfile
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import logging
import requests
from dataclasses import dataclass

from ..core.config import config

@dataclass
class BackupResult:
    """Result of a backup operation"""
    success: bool
    timestamp: datetime
    commit_sha: Optional[str] = None
    files_backed_up: int = 0
    total_size: int = 0
    error: Optional[str] = None

class GitHubBackupManager:
    """Manages automated backups to GitHub repositories"""
    
    def __init__(self):
        self.username = config.get('github.username', '')
        self.token = config.get('github.token', '')
        self.repo_name = config.get('github.repo_name', 'system-optimizer-backups')
        self.branch = config.get('github.backup_branch', 'main')
        
        self.api_base = "https://api.github.com"
        self.session = requests.Session()
        
        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'System-Optimizer-Pro/1.0'
            })
    
    def is_configured(self) -> bool:
        """Check if GitHub backup is properly configured"""
        return bool(self.username and self.token)
    
    def test_connection(self) -> bool:
        """Test GitHub API connection"""
        if not self.is_configured():
            return False
        
        try:
            response = self.session.get(f"{self.api_base}/user")
            return response.status_code == 200
        except Exception as e:
            logging.error(f"GitHub connection test failed: {e}")
            return False
    
    def create_backup_repo(self) -> bool:
        """Create the backup repository if it doesn't exist"""
        if not self.is_configured():
            return False
        
        try:
            # Check if repo exists
            response = self.session.get(f"{self.api_base}/repos/{self.username}/{self.repo_name}")
            if response.status_code == 200:
                logging.info(f"Backup repository {self.repo_name} already exists")
                return True
            
            # Create repository
            repo_data = {
                "name": self.repo_name,
                "description": "Automated backups from System Optimizer Pro",
                "private": True,
                "auto_init": True
            }
            
            response = self.session.post(f"{self.api_base}/user/repos", json=repo_data)
            
            if response.status_code == 201:
                logging.info(f"Created backup repository: {self.repo_name}")
                return True
            else:
                logging.error(f"Failed to create repository: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error creating backup repository: {e}")
            return False
    
    def backup_configurations(self) -> BackupResult:
        """Backup system configurations to GitHub"""
        start_time = datetime.now()
        result = BackupResult(success=False, timestamp=start_time)
        
        if not self.is_configured():
            result.error = "GitHub backup not configured"
            return result
        
        try:
            # Prepare backup data
            backup_data = self._prepare_config_backup()
            
            # Create commit
            commit_sha = self._create_backup_commit(
                backup_data, 
                f"Config backup - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if commit_sha:
                result.success = True
                result.commit_sha = commit_sha
                result.files_backed_up = len(backup_data)
                result.total_size = sum(len(data.encode()) for data in backup_data.values())
                logging.info(f"Configuration backup completed: {commit_sha}")
            else:
                result.error = "Failed to create backup commit"
                
        except Exception as e:
            result.error = str(e)
            logging.error(f"Configuration backup failed: {e}")
        
        return result
    
    def backup_logs(self) -> BackupResult:
        """Backup system logs to GitHub"""
        start_time = datetime.now()
        result = BackupResult(success=False, timestamp=start_time)
        
        if not config.get('github.include_logs', False):
            result.error = "Log backup is disabled in configuration"
            return result
        
        if not self.is_configured():
            result.error = "GitHub backup not configured"
            return result
        
        try:
            # Prepare log backup data
            log_data = self._prepare_log_backup()
            
            if not log_data:
                result.error = "No log data to backup"
                return result
            
            # Create compressed backup
            compressed_data = self._compress_backup_data(log_data)
            
            # Create commit
            commit_sha = self._create_backup_commit(
                {"logs_backup.tar.gz": compressed_data},
                f"Logs backup - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if commit_sha:
                result.success = True
                result.commit_sha = commit_sha
                result.files_backed_up = len(log_data)
                result.total_size = len(compressed_data)
                logging.info(f"Logs backup completed: {commit_sha}")
            else:
                result.error = "Failed to create backup commit"
                
        except Exception as e:
            result.error = str(e)
            logging.error(f"Logs backup failed: {e}")
        
        return result
    
    def full_backup(self) -> BackupResult:
        """Perform a full system backup"""
        start_time = datetime.now()
        result = BackupResult(success=False, timestamp=start_time)
        
        if not self.is_configured():
            result.error = "GitHub backup not configured"
            return result
        
        try:
            # Prepare full backup data
            backup_data = {}
            
            # Add configurations
            config_data = self._prepare_config_backup()
            backup_data.update(config_data)
            
            # Add logs if enabled
            if config.get('github.include_logs', False):
                log_data = self._prepare_log_backup()
                if log_data:
                    # Compress logs
                    compressed_logs = self._compress_backup_data(log_data)
                    backup_data["logs_backup.tar.gz"] = compressed_logs
            
            # Add system information
            system_info = self._get_system_info()
            backup_data["system_info.json"] = json.dumps(system_info, indent=2)
            
            # Create commit
            commit_sha = self._create_backup_commit(
                backup_data,
                f"Full backup - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if commit_sha:
                result.success = True
                result.commit_sha = commit_sha
                result.files_backed_up = len(backup_data)
                result.total_size = sum(
                    len(data.encode() if isinstance(data, str) else data) 
                    for data in backup_data.values()
                )
                logging.info(f"Full backup completed: {commit_sha}")
            else:
                result.error = "Failed to create backup commit"
                
        except Exception as e:
            result.error = str(e)
            logging.error(f"Full backup failed: {e}")
        
        return result
    
    def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent backups from GitHub"""
        if not self.is_configured():
            return []
        
        try:
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/commits",
                params={"per_page": limit}
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to list backups: {response.status_code}")
                return []
            
            commits = response.json()
            backups = []
            
            for commit in commits:
                backup_info = {
                    "sha": commit["sha"],
                    "message": commit["commit"]["message"],
                    "timestamp": commit["commit"]["author"]["date"],
                    "author": commit["commit"]["author"]["name"],
                    "url": commit["html_url"]
                }
                backups.append(backup_info)
            
            return backups
            
        except Exception as e:
            logging.error(f"Error listing backups: {e}")
            return []
    
    def restore_backup(self, commit_sha: str, restore_path: Optional[str] = None) -> bool:
        """Restore a backup from GitHub"""
        if not self.is_configured():
            return False
        
        try:
            # Get commit tree
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/commits/{commit_sha}"
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to get commit: {response.status_code}")
                return False
            
            commit_data = response.json()
            tree_sha = commit_data["tree"]["sha"]
            
            # Get tree contents
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/trees/{tree_sha}",
                params={"recursive": "1"}
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to get tree: {response.status_code}")
                return False
            
            tree_data = response.json()
            restore_base = Path(restore_path or config.config_dir / "restore")
            restore_base.mkdir(parents=True, exist_ok=True)
            
            # Download and restore files
            for item in tree_data["tree"]:
                if item["type"] == "blob":
                    file_content = self._download_blob(item["sha"])
                    if file_content is not None:
                        file_path = restore_base / item["path"]
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        if isinstance(file_content, bytes):
                            file_path.write_bytes(file_content)
                        else:
                            file_path.write_text(file_content)
                        
                        logging.debug(f"Restored: {item['path']}")
            
            logging.info(f"Backup {commit_sha[:8]} restored to {restore_base}")
            return True
            
        except Exception as e:
            logging.error(f"Error restoring backup {commit_sha}: {e}")
            return False
    
    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Clean up old backups beyond retention period"""
        if not self.is_configured():
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            backups = self.list_backups(limit=100)  # Get more for cleanup
            
            deleted_count = 0
            
            for backup in backups:
                backup_date = datetime.fromisoformat(backup["timestamp"].replace('Z', '+00:00'))
                
                if backup_date < cutoff_date:
                    # Note: GitHub doesn't allow deleting commits via API
                    # This is a placeholder for cleanup logic
                    # In practice, you might create a new repository or use force push
                    logging.info(f"Would delete backup: {backup['sha'][:8]} from {backup_date}")
                    # deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logging.error(f"Error cleaning up backups: {e}")
            return 0
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup system status"""
        status = {
            "configured": self.is_configured(),
            "connection_ok": False,
            "repository_exists": False,
            "last_backup": None,
            "total_backups": 0,
            "total_size": 0
        }
        
        if not status["configured"]:
            return status
        
        try:
            # Test connection
            status["connection_ok"] = self.test_connection()
            
            if status["connection_ok"]:
                # Check repository
                response = self.session.get(f"{self.api_base}/repos/{self.username}/{self.repo_name}")
                status["repository_exists"] = response.status_code == 200
                
                if status["repository_exists"]:
                    repo_data = response.json()
                    status["total_size"] = repo_data.get("size", 0) * 1024  # Convert KB to bytes
                    
                    # Get recent backups
                    backups = self.list_backups(limit=1)
                    if backups:
                        status["last_backup"] = backups[0]["timestamp"]
                        status["total_backups"] = len(self.list_backups(limit=100))
        
        except Exception as e:
            logging.error(f"Error getting backup status: {e}")
        
        return status
    
    def _prepare_config_backup(self) -> Dict[str, str]:
        """Prepare configuration files for backup"""
        backup_data = {}
        
        try:
            # Main configuration
            if config.config_file.exists():
                backup_data["config/main.yaml"] = config.config_file.read_text()
            
            # User configuration
            if config.user_config_file.exists():
                backup_data["config/user.yaml"] = config.user_config_file.read_text()
            
            # Plugin configurations
            for plugin_config in config.plugin_config_dir.glob("*.yaml"):
                backup_data[f"config/plugins/{plugin_config.name}"] = plugin_config.read_text()
            
            # Schedule configuration
            from ..core.scheduler import scheduler
            if scheduler.schedule_file.exists():
                backup_data["config/schedule.yaml"] = scheduler.schedule_file.read_text()
            
            # System information
            system_info = self._get_system_info()
            backup_data["system_info.json"] = json.dumps(system_info, indent=2)
            
        except Exception as e:
            logging.error(f"Error preparing config backup: {e}")
        
        return backup_data
    
    def _prepare_log_backup(self) -> Dict[str, str]:
        """Prepare log files for backup"""
        log_data = {}
        
        try:
            log_dir = Path(config.get('core.log_file')).parent
            
            # Get recent log files (last 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            
            for log_file in log_dir.glob("*.log*"):
                if log_file.is_file():
                    stat = log_file.stat()
                    if datetime.fromtimestamp(stat.st_mtime) > cutoff_time:
                        try:
                            content = log_file.read_text()
                            log_data[f"logs/{log_file.name}"] = content
                        except Exception as e:
                            logging.warning(f"Could not read log file {log_file}: {e}")
        
        except Exception as e:
            logging.error(f"Error preparing log backup: {e}")
        
        return log_data
    
    def _compress_backup_data(self, data: Dict[str, str]) -> bytes:
        """Compress backup data using gzip"""
        with tempfile.NamedTemporaryFile() as temp_file:
            with tarfile.open(temp_file.name, "w:gz") as tar:
                for file_path, content in data.items():
                    # Create a tarinfo object
                    info = tarfile.TarInfo(name=file_path)
                    content_bytes = content.encode('utf-8')
                    info.size = len(content_bytes)
                    info.mtime = int(datetime.now().timestamp())
                    
                    # Add to archive
                    tar.addfile(info, fileobj=tempfile.BytesIO(content_bytes))
            
            return Path(temp_file.name).read_bytes()
    
    def _create_backup_commit(self, backup_data: Dict[str, Union[str, bytes]], message: str) -> Optional[str]:
        """Create a commit with backup data"""
        try:
            # Get current branch reference
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/ref/heads/{self.branch}"
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to get branch reference: {response.status_code}")
                return None
            
            current_sha = response.json()["object"]["sha"]
            
            # Get current tree
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/commits/{current_sha}"
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to get current commit: {response.status_code}")
                return None
            
            parent_tree_sha = response.json()["tree"]["sha"]
            
            # Create blobs for each file
            tree_items = []
            
            for file_path, content in backup_data.items():
                blob_data = {
                    "content": base64.b64encode(
                        content.encode() if isinstance(content, str) else content
                    ).decode(),
                    "encoding": "base64"
                }
                
                blob_response = self.session.post(
                    f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/blobs",
                    json=blob_data
                )
                
                if blob_response.status_code != 201:
                    logging.error(f"Failed to create blob for {file_path}")
                    continue
                
                blob_sha = blob_response.json()["sha"]
                
                tree_items.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })
            
            # Create tree
            tree_data = {
                "base_tree": parent_tree_sha,
                "tree": tree_items
            }
            
            tree_response = self.session.post(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/trees",
                json=tree_data
            )
            
            if tree_response.status_code != 201:
                logging.error(f"Failed to create tree: {tree_response.status_code}")
                return None
            
            tree_sha = tree_response.json()["sha"]
            
            # Create commit
            commit_data = {
                "message": message,
                "tree": tree_sha,
                "parents": [current_sha]
            }
            
            commit_response = self.session.post(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/commits",
                json=commit_data
            )
            
            if commit_response.status_code != 201:
                logging.error(f"Failed to create commit: {commit_response.status_code}")
                return None
            
            commit_sha = commit_response.json()["sha"]
            
            # Update branch reference
            ref_data = {"sha": commit_sha}
            
            ref_response = self.session.patch(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/refs/heads/{self.branch}",
                json=ref_data
            )
            
            if ref_response.status_code != 200:
                logging.error(f"Failed to update branch reference: {ref_response.status_code}")
                return None
            
            return commit_sha
            
        except Exception as e:
            logging.error(f"Error creating backup commit: {e}")
            return None
    
    def _download_blob(self, blob_sha: str) -> Optional[Union[str, bytes]]:
        """Download a blob from GitHub"""
        try:
            response = self.session.get(
                f"{self.api_base}/repos/{self.username}/{self.repo_name}/git/blobs/{blob_sha}"
            )
            
            if response.status_code != 200:
                return None
            
            blob_data = response.json()
            
            if blob_data["encoding"] == "base64":
                content = base64.b64decode(blob_data["content"])
                
                # Try to decode as text first
                try:
                    return content.decode('utf-8')
                except UnicodeDecodeError:
                    return content
            else:
                return blob_data["content"]
                
        except Exception as e:
            logging.error(f"Error downloading blob {blob_sha}: {e}")
            return None
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for backup"""
        import platform
        import psutil
        
        try:
            system_info = {
                "backup_timestamp": datetime.now().isoformat(),
                "system": {
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "python_version": platform.python_version()
                },
                "resources": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": psutil.virtual_memory().total,
                    "disk_total": psutil.disk_usage('/').total
                },
                "optimizer_version": "1.0.0",  # Should come from version module
                "config_summary": config.get_config_summary()
            }
            
            return system_info
        except Exception as e:
            logging.error(f"Error getting system info: {e}")
            return {"error": str(e)}

# Global GitHub backup manager instance
github_backup = GitHubBackupManager()