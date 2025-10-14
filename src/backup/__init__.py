"""
System Optimizer Pro - Backup Components

Backup and restore functionality including GitHub integration,
compression, and automated scheduling.
"""

from .github_backup import github_backup, BackupResult

__all__ = [
    'github_backup',
    'BackupResult'
]