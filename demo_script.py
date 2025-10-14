#!/usr/bin/env python3
"""
System Optimizer Pro - Complete Demonstration Script
Shows off all the key features and capabilities
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def print_banner(title, char="="):
    """Print a nice banner"""
    print(f"\n{char * 60}")
    print(f"🚀 {title}")
    print(f"{char * 60}")

def demo_system_info():
    """Demo: System Information"""
    print_banner("SYSTEM INFORMATION & METRICS")
    
    try:
        from core.platform_compat import platform_manager
        import psutil
        
        pm = platform_manager.get_platform()
        info = pm.get_system_info()
        
        print(f"📊 Platform: {info.platform} {info.platform_version}")
        print(f"🏗️  Architecture: {info.architecture}")
        print(f"🏠 Hostname: {info.hostname}")
        print(f"👤 User: {info.username}")
        print(f"📂 Home Directory: {info.home_dir}")
        
        # System metrics with progress bars
        print(f"\n📈 Real-time Metrics:")
        cpu_percent = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        def progress_bar(percent, width=25):
            filled = int(width * percent / 100)
            bar = "█" * filled + "░" * (width - filled)
            return f"[{bar}] {percent:5.1f}%"
        
        print(f"  💻 CPU:    {progress_bar(cpu_percent)}")
        print(f"  🧠 Memory: {progress_bar(memory.percent)}")
        print(f"  💾 Disk:   {progress_bar(disk.percent)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_security_scan():
    """Demo: Security Scanning"""
    print_banner("SECURITY SCANNING SYSTEM")
    
    try:
        from scanning.system_scanner import SystemScanner, ScanCategory
        
        print("🔍 Running comprehensive security scan...")
        scanner = SystemScanner()
        
        def progress_callback(message, percent):
            print(f"\r🔄 {message} ({percent}%)", end="", flush=True)
        
        scan_result = scanner.scan_system(
            categories=[ScanCategory.SECURITY, ScanCategory.PERFORMANCE],
            deep_scan=False,
            progress_callback=progress_callback
        )
        
        print(f"\n\n📊 SCAN RESULTS:")
        print(f"  ⌚ Duration: {scan_result.duration:.2f} seconds")
        print(f"  🔍 Total Findings: {len(scan_result.findings)}")
        print(f"  🚨 Critical: {len(scan_result.critical_findings)}")
        print(f"  ⚠️  High: {len(scan_result.high_findings)}")
        print(f"  📊 Security Score: {scan_result.security_score}/100")
        
        if scan_result.critical_findings:
            print(f"\n🚨 CRITICAL SECURITY ISSUES:")
            for i, finding in enumerate(scan_result.critical_findings[:3], 1):
                print(f"  {i}. {finding.title}")
                print(f"     📍 Location: {finding.location}")
                print(f"     🔧 Fix: {finding.recommendation}")
        
        if scan_result.high_findings:
            print(f"\n⚠️  HIGH PRIORITY ISSUES:")
            for finding in scan_result.high_findings[:3]:
                print(f"  • {finding.title}: {finding.description}")
        
        if not scan_result.findings:
            print("\n✅ No security issues detected!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_validation_system():
    """Demo: Pre-Action Validation"""
    print_banner("PRE-ACTION VALIDATION SYSTEM")
    
    try:
        from scanning.pre_action_validator import (
            PreActionValidator, ActionPlan, ActionCategory, ValidationLevel
        )
        
        # Create test action
        test_action = ActionPlan(
            action_id="demo_action_001",
            category=ActionCategory.SYSTEM_OPTIMIZATION,
            description="Optimize system performance and clean temporary files",
            target_files=["/tmp/demo_file.txt", "/var/log/demo.log"],
            estimated_duration=45,
            requires_reboot=False,
            reversible=True,
            backup_required=True
        )
        
        print(f"🔒 Validating action: {test_action.description}")
        print(f"📋 Category: {test_action.category.value}")
        print(f"⏱️  Duration: {test_action.estimated_duration}s")
        
        # Validate
        validator = PreActionValidator(validation_level=ValidationLevel.STANDARD)
        result = validator.validate_action(test_action)
        
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"  ✅ Approved: {'YES' if result.approved_for_execution else 'NO'}")
        print(f"  💥 Risk Level: {result.risk_assessment.overall_risk.value.upper()}")
        print(f"  📊 Risk Score: {result.risk_assessment.risk_score}/100")
        print(f"  🔴 Blocking Issues: {len(result.blocking_issues)}")
        print(f"  ⚠️  Warnings: {len(result.warnings)}")
        print(f"  💾 Backup Ready: {'YES' if result.risk_assessment.backup_plan else 'NO'}")
        
        if result.risk_assessment.backup_plan:
            backup = result.risk_assessment.backup_plan
            print(f"     📦 Backup ID: {backup['backup_id']}")
            print(f"     📂 Location: {backup['backup_location']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_scheduler():
    """Demo: Job Scheduler"""
    print_banner("JOB SCHEDULING SYSTEM")
    
    try:
        from core.scheduler import scheduler
        
        jobs = scheduler.get_job_status()
        print(f"⏰ Scheduled Jobs ({len(jobs)}):")
        
        for job_id, status in jobs.items():
            if isinstance(status, dict) and 'name' in status:
                state = status.get('state', 'unknown')
                next_run = status.get('next_run', 'Not scheduled')
                enabled = '🟢' if status.get('enabled', False) else '🔴'
                print(f"  {enabled} {status['name']}")
                print(f"     State: {state}, Next: {next_run}")
        
        print(f"\n🎯 Job Management Features:")
        print(f"  • Automated system health checks")
        print(f"  • Configuration backups")
        print(f"  • System cleanup routines")
        print(f"  • Plugin health monitoring")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_configuration():
    """Demo: Configuration Management"""
    print_banner("CONFIGURATION SYSTEM")
    
    try:
        from core.config import config
        
        summary = config.get_config_summary()
        print(f"⚙️  Configuration Overview:")
        
        for key, value in summary.items():
            if isinstance(value, dict):
                print(f"  📁 {key.replace('_', ' ').title()}:")
                for k, v in value.items():
                    print(f"    • {k}: {v}")
            else:
                icon = '✅' if value else '❌'
                print(f"  {icon} {key.replace('_', ' ').title()}: {value}")
        
        print(f"\n🔧 Configuration Features:")
        print(f"  • YAML-based configuration")
        print(f"  • User-specific overrides")
        print(f"  • Plugin-specific settings")
        print(f"  • Automatic backup and restore")
        print(f"  • Runtime configuration changes")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_plugins():
    """Demo: Plugin System"""
    print_banner("PLUGIN MANAGEMENT SYSTEM")
    
    try:
        from core.plugin_manager import plugin_manager
        
        # Discover plugins
        discovered = plugin_manager.discover_plugins()
        plugins = plugin_manager.get_plugin_list()
        
        print(f"🔌 Plugin Discovery Results:")
        print(f"  • Discovered: {len(discovered)} plugins")
        print(f"  • Plugin directories: {discovered}")
        
        if plugins:
            print(f"\n📋 Available Plugins:")
            for plugin in plugins:
                state_icon = '🟢' if plugin['state'] == 'loaded' else '🔴'
                print(f"  {state_icon} {plugin['name']}")
                print(f"     Description: {plugin['metadata']['description']}")
                print(f"     State: {plugin['state']}")
        else:
            print(f"\n📝 No plugins currently loaded")
        
        print(f"\n🎯 Plugin System Features:")
        print(f"  • Auto-discovery from multiple directories")
        print(f"  • Hot-loading and unloading")
        print(f"  • Plugin health monitoring")
        print(f"  • Sandboxed execution")
        print(f"  • Memory usage tracking")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run complete demonstration"""
    print_banner("SYSTEM OPTIMIZER PRO - COMPLETE DEMONSTRATION", "🚀")
    print("This demonstration showcases all major features of the System Optimizer Pro")
    print("framework, including security scanning, validation, automation, and monitoring.")
    
    # Run all demonstrations
    demos = [
        demo_system_info,
        demo_security_scan,
        demo_validation_system,
        demo_scheduler,
        demo_configuration,
        demo_plugins
    ]
    
    for i, demo_func in enumerate(demos, 1):
        print(f"\n{'='*60}")
        print(f"🎯 DEMO {i}/{len(demos)}: {demo_func.__name__.replace('demo_', '').replace('_', ' ').title()}")
        print(f"{'='*60}")
        
        try:
            demo_func()
            print(f"\n✅ Demo completed successfully!")
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
        
        # Small pause between demos
        time.sleep(1)
    
    print_banner("DEMONSTRATION COMPLETE! 🎉")
    print("🔧 To interact with the system: python main.py --cli")
    print("📊 To see status: python main.py")
    print("🔍 To run security scan: python main.py --cli -> 'scan'")
    print("⚙️  To manage config: python main.py --cli -> 'config show'")
    print("💡 For help: python main.py --cli -> 'help'")

if __name__ == "__main__":
    main()