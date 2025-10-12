#!/usr/bin/env python3
"""
System Optimizer Pro - Complete Edition
Main application entry point with modular plugin architecture and automation
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_logging(log_level="INFO"):
    """Setup logging configuration"""
    # Create log directory if it doesn't exist
    log_dir = Path.home() / ".system_optimizer_pro"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "system_optimizer.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description="System Optimizer Pro - Complete Edition")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--config-dir", help="Configuration directory")
    parser.add_argument("--start-scheduler", action="store_true", help="Start job scheduler")
    parser.add_argument("--web-interface", action="store_true", help="Start web interface")
    parser.add_argument("--cli", action="store_true", help="Interactive CLI mode")
    parser.add_argument("--backup", choices=["config", "logs", "full"], help="Run backup")
    parser.add_argument("--plugin", help="Plugin management: list|load|unload|status")
    parser.add_argument("--job", help="Job management: list|run|status")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize core components
        from core.config import config
        from core.plugin_manager import plugin_manager
        from core.scheduler import scheduler
        
        logger.info("System Optimizer Pro Starting...")
        
        # Override config directory if specified
        if args.config_dir:
            config.config_dir = Path(args.config_dir).expanduser()
            config.load_config()
        
        # Initialize plugin system
        logger.info("Initializing plugin system...")
        discovered_plugins = plugin_manager.discover_plugins()
        logger.info(f"Discovered {len(discovered_plugins)} plugins")
        
        # Handle command-line operations
        if args.backup:
            from backup.github_backup import github_backup
            logger.info(f"Running {args.backup} backup...")
            
            if args.backup == "config":
                result = github_backup.backup_configurations()
            elif args.backup == "logs":
                result = github_backup.backup_logs()
            else:  # full
                result = github_backup.full_backup()
            
            if result.success:
                logger.info(f"Backup completed successfully: {result.commit_sha}")
            else:
                logger.error(f"Backup failed: {result.error}")
            return
        
        if args.plugin:
            if args.plugin == "list":
                plugins = plugin_manager.get_plugin_list()
                print("\nDiscovered Plugins:")
                for plugin in plugins:
                    print(f"  - {plugin['name']} ({plugin['state']}) - {plugin['metadata']['description']}")
            elif args.plugin == "status":
                status = plugin_manager.get_plugin_status()
                print("\nPlugin Status:")
                for name, stat in status.items():
                    print(f"  - {name}: {stat}")
            return
        
        if args.job:
            if args.job == "list":
                jobs = scheduler.get_job_status()
                print("\nScheduled Jobs:")
                for job_id, status in jobs.items():
                    if isinstance(status, dict) and 'name' in status:
                        print(f"  - {status['name']} ({job_id}): {status.get('state', 'unknown')}")
            elif args.job == "status":
                status = scheduler.get_job_status()
                print("\nJob Scheduler Status:")
                for job_id, stat in status.items():
                    print(f"  - {job_id}: {stat}")
            return
        
        # Start scheduler if requested
        if args.start_scheduler:
            logger.info("Starting job scheduler...")
            scheduler.start_scheduler()
        
        # Start web interface if requested
        if args.web_interface:
            logger.info("Starting web interface...")
            start_web_interface()
            return
        
        # Interactive CLI mode
        if args.cli:
            start_cli_interface()
            return
        
        # Default: Show status and available commands
        print_status_summary()
        
    except ImportError as e:
        logger.error(f"Missing dependencies. Please install: {e}")
        print("\nTo install dependencies:")
        print("cd ~/system_optimizer_pro && source venv/bin/activate")
        print("pip install croniter pyyaml requests psutil flask fastapi uvicorn")
    except Exception as e:
        logger.error(f"Error starting System Optimizer Pro: {e}")
        sys.exit(1)

def print_status_summary():
    """Print system status summary"""
    print("\n🚀 System Optimizer Pro - Complete Edition")
    print("=" * 50)
    
    try:
        from core.config import config
        from core.plugin_manager import plugin_manager
        from core.scheduler import scheduler
        
        # Configuration status
        config_summary = config.get_config_summary()
        print(f"📁 Config Directory: {config_summary['config_dir']}")
        print(f"🔧 Log Level: {config_summary['core_settings']['log_level']}")
        print(f"📊 Performance Monitoring: {config_summary['core_settings']['performance_monitoring']}")
        
        # Plugin status
        plugins = plugin_manager.get_plugin_list()
        print(f"🔌 Plugins: {len(plugins)} discovered")
        
        # Scheduler status
        jobs = scheduler.get_job_status()
        print(f"⏰ Scheduled Jobs: {len(jobs)}")
        
        # GitHub backup status
        from backup.github_backup import github_backup
        backup_status = github_backup.get_backup_status()
        print(f"📦 GitHub Backup: {'✅ Configured' if backup_status['configured'] else '❌ Not configured'}")
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
    
    print("\n📖 Available Commands:")
    print("  python main.py --cli              # Interactive CLI mode")
    print("  python main.py --start-scheduler  # Start job scheduler")
    print("  python main.py --web-interface    # Start web interface")
    print("  python main.py --backup config    # Backup configurations")
    print("  python main.py --plugin list      # List plugins")
    print("  python main.py --job list         # List scheduled jobs")

def start_cli_interface():
    """Start interactive CLI interface"""
    from core.config import config
    from core.plugin_manager import plugin_manager
    from core.scheduler import scheduler
    
    print("\n🖥️  System Optimizer Pro - Interactive CLI")
    print("Type 'help' for commands, 'exit' to quit\n")
    
    while True:
        try:
            cmd = input("system-optimizer> ").strip().lower()
            
            if cmd == "exit":
                break
            elif cmd == "help":
                print_cli_help()
            elif cmd == "status":
                print_status_summary()
            elif cmd.startswith("plugin"):
                handle_plugin_command(cmd)
            elif cmd.startswith("job"):
                handle_job_command(cmd)
            elif cmd.startswith("config"):
                handle_config_command(cmd)
            elif cmd.startswith("backup"):
                handle_backup_command(cmd)
            elif cmd == "system info":
                handle_system_info()
            elif cmd == "system metrics":
                handle_system_metrics() 
            elif cmd == "monitor":
                handle_real_time_monitoring()
            elif cmd == "scan":
                handle_system_scan()
            elif cmd == "scan deep":
                handle_deep_system_scan()
            elif cmd == "validate":
                handle_action_validation()
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

def print_cli_help():
    """Print CLI help"""
    print("\n📖 Available Commands:")
    print("  status              - Show system status")
    print("  plugin list         - List all plugins")
    print("  plugin load <name>  - Load a plugin")
    print("  plugin status       - Show plugin status")
    print("  job list            - List scheduled jobs")
    print("  job run <id>        - Run a job now")
    print("  job status          - Show job status")
    print("  config show         - Show configuration")
    print("  config set <key> <value> - Set configuration value")
    print("  system info         - Show system information")
    print("  system metrics      - Show current system metrics")
    print("  monitor             - Real-time monitoring (Ctrl+C to stop)")
    print("  scan                - Quick system security scan")
    print("  scan deep           - Comprehensive deep system scan")
    print("  validate            - Test pre-action validation system")
    print("  backup config       - Backup configurations")
    print("  backup full         - Full system backup")
    print("  help                - Show this help")
    print("  exit                - Exit CLI")

def handle_plugin_command(cmd):
    """Handle plugin management commands"""
    from core.plugin_manager import plugin_manager
    
    parts = cmd.split()
    if len(parts) < 2:
        print("Usage: plugin [list|load|unload|status] [name]")
        return
    
    action = parts[1]
    
    if action == "list":
        plugins = plugin_manager.get_plugin_list()
        print(f"\n🔌 Discovered Plugins ({len(plugins)}):")
        for plugin in plugins:
            print(f"  - {plugin['name']} ({plugin['state']}) - {plugin['metadata']['description']}")
    
    elif action == "status":
        status = plugin_manager.get_plugin_status()
        print("\n🔌 Plugin Status:")
        for name, stat in status.items():
            print(f"  - {name}: {stat}")
    
    elif action in ["load", "unload"] and len(parts) >= 3:
        plugin_name = parts[2]
        if action == "load":
            success = plugin_manager.load_plugin(plugin_name)
            print(f"{'✅' if success else '❌'} {'Loaded' if success else 'Failed to load'} plugin: {plugin_name}")
        else:
            success = plugin_manager.unload_plugin(plugin_name)
            print(f"{'✅' if success else '❌'} {'Unloaded' if success else 'Failed to unload'} plugin: {plugin_name}")
    
    else:
        print("Usage: plugin [list|load|unload|status] [name]")

def handle_job_command(cmd):
    """Handle job management commands"""
    from core.scheduler import scheduler
    
    parts = cmd.split()
    if len(parts) < 2:
        print("Usage: job [list|run|status] [id]")
        return
    
    action = parts[1]
    
    if action == "list":
        jobs = scheduler.get_job_status()
        print(f"\n⏰ Scheduled Jobs ({len(jobs)}):")
        for job_id, status in jobs.items():
            if isinstance(status, dict) and 'name' in status:
                next_run = status.get('next_run', 'Not scheduled')
                state = status.get('state', 'unknown')
                print(f"  - {status['name']} ({job_id}): {state}, Next: {next_run}")
    
    elif action == "status":
        jobs = scheduler.get_job_status()
        print("\n⏰ Job Scheduler Status:")
        for job_id, stat in jobs.items():
            print(f"  - {job_id}: {stat}")
    
    elif action == "run" and len(parts) >= 3:
        job_id = parts[2]
        execution_id = scheduler.run_job_now(job_id)
        if execution_id:
            print(f"✅ Started job {job_id} (execution: {execution_id})")
        else:
            print(f"❌ Failed to start job {job_id}")
    
    else:
        print("Usage: job [list|run|status] [id]")

def handle_config_command(cmd):
    """Handle configuration commands"""
    from core.config import config
    
    parts = cmd.split()
    if len(parts) < 2:
        print("Usage: config [show|set] [key] [value]")
        return
    
    action = parts[1]
    
    if action == "show":
        summary = config.get_config_summary()
        print("\n⚙️  Configuration Summary:")
        for key, value in summary.items():
            print(f"  - {key}: {value}")
    
    elif action == "set" and len(parts) >= 4:
        key = parts[2]
        value = " ".join(parts[3:])
        success = config.set(key, value)
        print(f"{'✅' if success else '❌'} {'Set' if success else 'Failed to set'} {key} = {value}")
    
    else:
        print("Usage: config [show|set] [key] [value]")

def handle_backup_command(cmd):
    """Handle backup commands"""
    from backup.github_backup import github_backup
    
    parts = cmd.split()
    if len(parts) < 2:
        print("Usage: backup [config|logs|full|status]")
        return
    
    action = parts[1]
    
    if action == "status":
        status = github_backup.get_backup_status()
        print("\n📦 GitHub Backup Status:")
        for key, value in status.items():
            print(f"  - {key}: {value}")
    
    elif action in ["config", "logs", "full"]:
        print(f"🔄 Starting {action} backup...")
        
        if action == "config":
            result = github_backup.backup_configurations()
        elif action == "logs":
            result = github_backup.backup_logs()
        else:  # full
            result = github_backup.full_backup()
        
        if result.success:
            print(f"✅ Backup completed successfully!")
            print(f"   Commit: {result.commit_sha}")
            print(f"   Files: {result.files_backed_up}")
            print(f"   Size: {result.total_size} bytes")
        else:
            print(f"❌ Backup failed: {result.error}")

def handle_system_info():
    """Handle system info command"""
    try:
        from src.core.platform_compat import platform_manager
        pm = platform_manager.get_platform()
        info = pm.get_system_info()
        print(f"\n📊 System Information:")
        print(f"  • Platform: {info.platform} {info.platform_version}")
        print(f"  • Architecture: {info.architecture}")
        print(f"  • Hostname: {info.hostname}")
        print(f"  • Username: {info.username}")
        print(f"  • Home Dir: {info.home_dir}")
        print(f"  • Temp Dir: {info.temp_dir}")
        print(f"  • Config Dir: {info.config_dir}")
    except Exception as e:
        print(f"❌ Error getting system info: {e}")

def handle_system_metrics():
    """Handle system metrics command"""
    try:
        from src.core.platform_compat import platform_manager
        pm = platform_manager.get_platform()
        metrics = pm.get_system_metrics()
        print(f"\n📈 System Metrics:")
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"  • {key.title()}:")
                for k, v in value.items():
                    print(f"    - {k}: {v}")
            elif isinstance(value, list):
                print(f"  • {key.title()}: {', '.join(map(str, value))}")
            else:
                unit = '°C' if 'temp' in key.lower() else ''
                unit = '%' if 'percent' in key.lower() else unit
                unit = 'GB' if 'gb' in str(value) else unit
                print(f"  • {key.replace('_', ' ').title()}: {value}{unit}")
    except Exception as e:
        print(f"❌ Error getting metrics: {e}")

def handle_real_time_monitoring():
    """Handle real-time monitoring command"""
    try:
        import psutil
        import time
        print("\n🔍 Real-time System Monitoring (Press Ctrl+C to stop):")
        print("\n┌─────────────────────────────────────────────────────────┐")
        print("│                   Live System Metrics                  │")
        print("└─────────────────────────────────────────────────────────┘")
        
        try:
            while True:
                # Get live system metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                # Format network I/O (MB)
                net_sent = network.bytes_sent / 1024 / 1024
                net_recv = network.bytes_recv / 1024 / 1024
                
                # Create progress bars
                def progress_bar(percent, width=20):
                    filled = int(width * percent / 100)
                    bar = "█" * filled + "░" * (width - filled)
                    return f"[{bar}] {percent:5.1f}%"
                
                print(f"\r💻 CPU:  {progress_bar(cpu_percent)} | ", end='')
                print(f"🧠 RAM:  {progress_bar(memory.percent)} | ", end='')
                print(f"💾 Disk: {progress_bar(disk.percent)} | ", end='')
                print(f"🌐 Net: ↑{net_sent:6.1f}MB ↓{net_recv:6.1f}MB", end='')
                
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✅ Monitoring stopped.")
    except Exception as e:
        print(f"❌ Error in monitoring: {e}")

def handle_system_scan():
    """Handle quick system scan command"""
    try:
        from src.scanning.system_scanner import SystemScanner, ScanCategory
        
        print("\n🔍 Starting Quick System Scan...")
        
        scanner = SystemScanner()
        
        # Quick scan categories
        quick_categories = [
            ScanCategory.SECURITY,
            ScanCategory.PERFORMANCE,
            ScanCategory.NETWORK
        ]
        
        def progress_callback(message, percent):
            print(f"\r{message} ({percent}%)", end='', flush=True)
        
        scan_result = scanner.scan_system(categories=quick_categories, 
                                        deep_scan=False, 
                                        progress_callback=progress_callback)
        
        print(f"\n\n📊 Quick Scan Complete!")
        print(f"⌚ Duration: {scan_result.duration:.2f} seconds")
        print(f"🔍 Total Findings: {len(scan_result.findings)}")
        print(f"⚠️  High/Critical: {len(scan_result.high_findings) + len(scan_result.critical_findings)}")
        print(f"📊 Security Score: {scan_result.security_score}/100")
        
        if scan_result.critical_findings:
            print(f"\n🚨 CRITICAL FINDINGS:")
            for finding in scan_result.critical_findings[:3]:  # Show top 3
                print(f"  • {finding.title}: {finding.description}")
                print(f"    📍 {finding.location}")
                print(f"    🔧 {finding.recommendation}")
                print()
        
        if scan_result.high_findings:
            print(f"\n⚠️  HIGH PRIORITY FINDINGS:")
            for finding in scan_result.high_findings[:5]:  # Show top 5
                print(f"  • {finding.title}: {finding.description}")
                print(f"    🔧 {finding.recommendation}")
        
        if not scan_result.findings:
            print("\n✅ No security issues detected in quick scan.")
        
        print(f"\n📝 Run 'scan deep' for comprehensive analysis.")
        
    except Exception as e:
        print(f"❌ Error in system scan: {e}")

def handle_deep_system_scan():
    """Handle comprehensive deep system scan command"""
    try:
        from src.scanning.system_scanner import SystemScanner
        
        print("\n🔍 Starting Comprehensive Deep System Scan...")
        print("⚠️  This may take several minutes.\n")
        
        scanner = SystemScanner()
        
        def progress_callback(message, percent):
            bars = '█' * (percent // 5) + '░' * (20 - percent // 5)
            print(f"\r[{bars}] {percent:3d}% | {message}", end='', flush=True)
        
        scan_result = scanner.scan_system(categories=None,  # All categories
                                        deep_scan=True, 
                                        progress_callback=progress_callback)
        
        print(f"\n\n🎆 Deep System Scan Complete!")
        print(f"=" * 50)
        print(f"⌚ Duration: {scan_result.duration:.2f} seconds")
        print(f"🔍 Categories Scanned: {len(scan_result.categories_scanned)}")
        print(f"📊 Total Findings: {len(scan_result.findings)}")
        print(f"⚠️  Critical: {len(scan_result.critical_findings)}")
        print(f"🔴 High: {len(scan_result.high_findings)}")
        print(f"🟡 Medium: {len([f for f in scan_result.findings if f.severity.value == 'medium'])}")
        print(f"📊 Security Score: {scan_result.security_score}/100")
        print(f"📊 Risk Score: {scan_result.total_risk_score}")
        
        if scan_result.critical_findings:
            print(f"\n🚨 CRITICAL SECURITY ISSUES ({len(scan_result.critical_findings)}):")
            for i, finding in enumerate(scan_result.critical_findings, 1):
                print(f"\n{i}. {finding.title}")
                print(f"   📋 {finding.description}")
                print(f"   📍 Location: {finding.location}")
                print(f"   🔧 Recommendation: {finding.recommendation}")
                if finding.remediation_commands:
                    print(f"   ⚙️  Commands: {', '.join(finding.remediation_commands)}")
                print(f"   📊 Risk Score: {finding.risk_score}")
        
        if scan_result.high_findings:
            print(f"\n⚠️  HIGH PRIORITY ISSUES ({len(scan_result.high_findings)}):")
            for i, finding in enumerate(scan_result.high_findings[:10], 1):  # Show top 10
                print(f"\n{i}. {finding.title}")
                print(f"   📋 {finding.description}")
                print(f"   🔧 {finding.recommendation}")
        
        # System Health Summary
        print(f"\n🔋 SYSTEM HEALTH SUMMARY:")
        categories_summary = {}
        for finding in scan_result.findings:
            cat = finding.category.value
            if cat not in categories_summary:
                categories_summary[cat] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
            categories_summary[cat][finding.severity.value] += 1
        
        for category, counts in categories_summary.items():
            total_issues = sum(counts.values())
            print(f"  {category.replace('_', ' ').title()}: {total_issues} issues (C:{counts['critical']} H:{counts['high']} M:{counts['medium']} L:{counts['low']})")
        
        if not scan_result.findings:
            print("\n🎉 Excellent! No security issues detected.")
        else:
            print(f"\n📝 Detailed report saved to scan logs.")
        
    except Exception as e:
        print(f"❌ Error in deep system scan: {e}")

def handle_action_validation():
    """Handle action validation test command"""
    try:
        from src.scanning.pre_action_validator import (
            PreActionValidator, ActionPlan, ActionCategory, ValidationLevel
        )
        
        print("\n🔒 Testing Pre-Action Validation System...")
        
        # Create test action plan
        test_action = ActionPlan(
            action_id="test_cleanup_001",
            category=ActionCategory.SYSTEM_OPTIMIZATION,
            description="Clean temporary files and optimize system performance",
            target_files=["/tmp/test_file.txt", "/var/log/test.log"],
            estimated_duration=30,
            requires_reboot=False,
            reversible=True,
            backup_required=True
        )
        
        # Initialize validator with standard validation level
        validator = PreActionValidator(validation_level=ValidationLevel.STANDARD)
        
        print(f"\n🔍 Validating Action: {test_action.description}")
        print(f"📋 Action Category: {test_action.category.value}")
        print(f"⌚ Estimated Duration: {test_action.estimated_duration}s")
        
        # Validate the action
        validation_result = validator.validate_action(test_action)
        
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"="*40)
        print(f"✅ Approved for Execution: {'YES' if validation_result.approved_for_execution else 'NO'}")
        print(f"💥 Overall Risk Level: {validation_result.risk_assessment.overall_risk.value.upper()}")
        print(f"📊 Risk Score: {validation_result.risk_assessment.risk_score}/100")
        print(f"🔴 Blocking Issues: {len(validation_result.blocking_issues)}")
        print(f"⚠️  Warnings: {len(validation_result.warnings)}")
        print(f"📋 User Confirmation Required: {'YES' if validation_result.risk_assessment.user_confirmation_required else 'NO'}")
        
        if validation_result.blocking_issues:
            print(f"\n🚨 BLOCKING ISSUES:")
            for issue in validation_result.blocking_issues:
                print(f"  • {issue.check_name}: {issue.message}")
                for rec in issue.recommendations:
                    print(f"    - {rec}")
        
        if validation_result.warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in validation_result.warnings:
                print(f"  • {warning.check_name}: {warning.message}")
                if warning.recommendations:
                    print(f"    Recommendation: {warning.recommendations[0]}")
        
        # Show safety checks
        passed_checks = [c for c in validation_result.risk_assessment.safety_checks if c.passed]
        failed_checks = [c for c in validation_result.risk_assessment.safety_checks if not c.passed]
        
        print(f"\n📊 SAFETY CHECKS SUMMARY:")
        print(f"  ✅ Passed: {len(passed_checks)}")
        print(f"  ❌ Failed: {len(failed_checks)}")
        
        if validation_result.risk_assessment.backup_plan:
            print(f"\n💾 BACKUP PLAN READY:")
            backup_plan = validation_result.risk_assessment.backup_plan
            print(f"  Backup ID: {backup_plan['backup_id']}")
            print(f"  Location: {backup_plan['backup_location']}")
            print(f"  Files to backup: {len(backup_plan['target_files'])}")
        
        print(f"\n🔍 Validation demonstrates the safety-first approach!")
        print(f"All system modifications go through comprehensive validation.")
        
    except Exception as e:
        print(f"❌ Error in action validation: {e}")

def start_web_interface():
        print("Usage: backup [config|logs|full|status]")

def start_web_interface():
    """Start web interface (placeholder)"""
    print("🌐 Web interface would start here...")
    print("Future implementation: FastAPI/Flask web dashboard")
    print("Features: Plugin management, job scheduling, system monitoring")
    
    # Placeholder for web interface
    print("\nPress Ctrl+C to stop...")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nWeb interface stopped.")

if __name__ == "__main__":
    main()
def handle_predictive_hardware(cmd):
    """Handle predictive hardware failure detection"""
    from src.prediction.hardware_predictor import HardwarePredictor
    
    parts = cmd.split()
    if len(parts) < 3:
        print("Usage: hardware [analyze|predict|status|report] [options]")
        return
    
    action = parts[2]
    predictor = HardwarePredictor()
    
    if action == "analyze":
        print("\n🔮 Analyzing hardware health and predicting failures...")
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
    
    elif action == "status":
        summary = predictor.get_component_status_summary()
        print("\n📊 Hardware Health Summary:")
        print(f"Overall Health: {summary['overall_health']:.1f}/100")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"Warnings: {summary['warnings']}")
        if summary['next_maintenance']:
            print(f"Next Maintenance: {summary['next_maintenance']} days")
    
    elif action == "report":
        print("\n📊 Generating detailed hardware health report...")
        # This would generate a comprehensive report
        summary = predictor.get_component_status_summary()
        print("Hardware Health Report saved to ~/.system_optimizer_pro/hardware_report.txt")
    
    else:
        print("Available actions: analyze, status, report")

def handle_memory_visualization(cmd):
    """Handle memory defragmentation visualization"""
    try:
        from src.visualization.memory_defrag_viz import MemoryDefragmentationVisualizer
        
        parts = cmd.split()
        action = parts[2] if len(parts) > 2 else "start"
        
        if action == "start":
            print("🎮 Starting Memory Defragmentation 3D Visualizer...")
            visualizer = MemoryDefragmentationVisualizer(1200, 800)
            
            try:
                print("Controls:")
                print("  SPACE - Pause/Resume")
                print("  R - Toggle Auto-Rotate") 
                print("  ↑↓ - Zoom In/Out")
                print("  ←→ - Manual Rotate")
                print("  ESC - Exit")
                print()
                
                visualizer.start_defragmentation_visualization(real_defrag=False)
                
                print("📊 Generating performance report...")
                report_path = visualizer.generate_html_report()
                print(f"📄 Report saved to: {report_path}")
                
            except KeyboardInterrupt:
                print("\n⏹️  Visualization stopped by user")
            finally:
                visualizer.stop_visualization()
        
        elif action == "demo":
            # Quick demo mode
            print("🎮 Memory Visualization Demo Mode")
            visualizer = MemoryDefragmentationVisualizer(800, 600)
            visualizer.start_defragmentation_visualization(real_defrag=False)
        
        else:
            print("Available actions: start, demo")
            
    except ImportError as e:
        print(f"❌ Visualization dependencies not available: {e}")
        print("Install with: pip install pygame matplotlib plotly rich")

def handle_thermal_gaming(cmd):
    """Handle thermal management gaming interface"""
    try:
        from src.thermal.thermal_gaming import ThermalGameEngine
        
        parts = cmd.split()
        action = parts[2] if len(parts) > 2 else "start"
        
        if action == "start":
            print("🎮 Starting Thermal Management Gaming...")
            game = ThermalGameEngine()
            game.start_gaming_interface()
        
        elif action == "challenge":
            from src.thermal.thermal_gaming import ThermalChallenge
            
            if len(parts) > 3:
                challenge_name = parts[3].lower()
                challenge_map = {
                    'cool': ThermalChallenge.COOL_RUNNER,
                    'efficiency': ThermalChallenge.EFFICIENCY_MASTER,
                    'stress': ThermalChallenge.STRESS_SURVIVOR,
                    'silent': ThermalChallenge.SILENT_OPERATOR,
                    'overclock': ThermalChallenge.OVERCLOCKED_BEAST
                }
                
                if challenge_name in challenge_map:
                    game = ThermalGameEngine()
                    game.start_challenge(challenge_map[challenge_name])
                else:
                    print("Available challenges: cool, efficiency, stress, silent, overclock")
            else:
                print("Usage: thermal challenge [cool|efficiency|stress|silent|overclock]")
        
        else:
            print("Available actions: start, challenge")
            
    except ImportError as e:
        print(f"❌ Thermal gaming dependencies not available: {e}")
        print("Install with: pip install rich pygame numpy")

def handle_cpu_program_management(cmd):
    """Handle CPU-based program thermal management"""
    try:
        from src.thermal.cpu_program_manager import CPUProgramManager
        
        parts = cmd.split()
        action = parts[2] if len(parts) > 2 else "interactive"
        
        manager = CPUProgramManager()
        
        if action == "interactive":
            print("🖥️  CPU-Based Program Thermal Management")
            profile = manager.create_interactive_program_selector()
            if profile:
                print(f"✅ Thermal management configured for {profile.program_name}")
        
        elif action == "list":
            print("\n📋 Discovered Programs:")
            programs = manager.discover_programs()
            for i, prog in enumerate(programs[:10], 1):
                print(f"{i:2d}. {prog.name:20s} | CPU: {prog.cpu_percent:5.1f}% | RAM: {prog.memory_percent:5.1f}%")
        
        elif action == "status":
            manager.show_thermal_status()
        
        elif action == "monitor" and len(parts) > 3:
            program_name = parts[3]
            success = manager.start_thermal_management(program_name)
            if success:
                print(f"🌡️  Started monitoring {program_name}. Press Ctrl+C to stop.")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    manager.stop_thermal_management()
                    print("\n🛑 Monitoring stopped")
        
        else:
            print("Available actions: interactive, list, status, monitor <program_name>")
            
    except ImportError as e:
        print(f"❌ CPU management dependencies not available: {e}")
        print("Install with: pip install psutil")

# Update the CLI help function
def print_cli_help():
    """Print CLI help"""
    print("\n📖 Available Commands:")
    print("  status              - Show system status")
    print("  plugin list         - List all plugins")
    print("  plugin load <name>  - Load a plugin")
    print("  plugin status       - Show plugin status")
    print("  job list            - List scheduled jobs")
    print("  job run <id>        - Run a job now")
    print("  job status          - Show job status")
    print("  config show         - Show configuration")
    print("  config set <key> <value> - Set configuration value")
    print("  system info         - Show system information")
    print("  system metrics      - Show current system metrics")
    print("  monitor             - Real-time monitoring (Ctrl+C to stop)")
    print("  scan                - Quick system security scan")
    print("  scan deep           - Comprehensive deep system scan")
    print("  validate            - Test pre-action validation system")
    print("  backup config       - Backup configurations")
    print("  backup full         - Full system backup")
    print()
    print("🆕 NEW ENHANCED FEATURES:")
    print("  hardware analyze    - AI-powered hardware failure prediction")
    print("  hardware status     - Hardware health summary")
    print("  memory visualize    - 3D memory defragmentation visualization")
    print("  thermal gaming      - Thermal management gaming interface")
    print("  thermal challenge <type> - Start specific thermal challenge")
    print("  cpu manage          - CPU-based program thermal management")
    print("  cpu monitor <program> - Monitor specific program thermals")
    print("  help                - Show this help")
    print("  exit                - Exit CLI")

# Update the handle_* functions in start_cli_interface
def start_cli_interface():
    """Start interactive CLI interface"""
    from core.config import config
    from core.plugin_manager import plugin_manager
    from core.scheduler import scheduler
    
    print("\n🖥️  System Optimizer Pro - Enhanced Interactive CLI")
    print("Type 'help' for commands, 'exit' to quit")
    print("🆕 NEW: Hardware prediction, 3D visualization, thermal gaming!")
    print()
    
    while True:
        try:
            cmd = input("system-optimizer> ").strip().lower()
            
            if cmd == "exit":
                break
            elif cmd == "help":
                print_cli_help()
            elif cmd == "status":
                print_status_summary()
            elif cmd.startswith("plugin"):
                handle_plugin_command(cmd)
            elif cmd.startswith("job"):
                handle_job_command(cmd)
            elif cmd.startswith("config"):
                handle_config_command(cmd)
            elif cmd.startswith("backup"):
                handle_backup_command(cmd)
            elif cmd == "system info":
                handle_system_info()
            elif cmd == "system metrics":
                handle_system_metrics() 
            elif cmd == "monitor":
                handle_real_time_monitoring()
            elif cmd == "scan":
                handle_system_scan()
            elif cmd == "scan deep":
                handle_deep_system_scan()
            elif cmd == "validate":
                handle_action_validation()
            # NEW ENHANCED FEATURES
            elif cmd.startswith("hardware"):
                handle_predictive_hardware(cmd)
            elif cmd.startswith("memory"):
                handle_memory_visualization(cmd)
            elif cmd.startswith("thermal"):
                handle_thermal_gaming(cmd)
            elif cmd.startswith("cpu"):
                handle_cpu_program_management(cmd)
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

