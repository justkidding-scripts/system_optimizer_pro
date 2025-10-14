#!/usr/bin/env python3
"""
Memory Defragmentation 3D Visualization Module
Real-time 3D visualization of memory optimization processes with interactive controls
"""

import time
import psutil
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import threading
import queue
import json
import random

try:
    import pygame
    from pygame import gfxdraw
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False

class MemoryBlockState(Enum):
    FREE = "free"
    ALLOCATED = "allocated"
    FRAGMENTED = "fragmented"
    BEING_MOVED = "being_moved"
    OPTIMIZED = "optimized"

class DefragmentationPhase(Enum):
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    MOVING = "moving"
    COMPACTING = "compacting"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"

@dataclass
class MemoryBlock:
    address: int
    size: int
    state: MemoryBlockState
    process_id: Optional[int] = None
    process_name: str = ""
    age: float = 0.0
    fragmentation_score: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    color: Tuple[int, int, int] = (128, 128, 128)

@dataclass
class DefragmentationStats:
    total_memory: int
    free_memory: int
    fragmented_memory: int
    largest_free_block: int
    fragmentation_percentage: float
    blocks_moved: int
    time_elapsed: float
    performance_gain: float

class MemoryDefragmentationVisualizer:
    def __init__(self, width: int = 1200, height: int = 800):
        self.width = width
        self.height = height
        self.running = False
        self.paused = False
        
        # Memory simulation
        self.memory_blocks: List[MemoryBlock] = []
        self.total_memory = psutil.virtual_memory().total
        self.block_size = 1024 * 1024  # 1MB blocks
        self.num_blocks = self.total_memory // self.block_size
        
        # Visualization state
        self.current_phase = DefragmentationPhase.SCANNING
        self.progress = 0.0
        self.stats = DefragmentationStats(0, 0, 0, 0, 0.0, 0, 0.0, 0.0)
        
        # 3D visualization parameters
        self.camera_angle = 0.0
        self.zoom = 1.0
        self.auto_rotate = True
        
        # Animation queues
        self.animation_queue = queue.Queue()
        self.stats_queue = queue.Queue()
        
        # Performance tracking
        self.fps = 60
        self.frame_time = 0.0
        
        # Initialize memory blocks
        self._initialize_memory_blocks()
        
        if VISUALIZATION_AVAILABLE:
            self._initialize_pygame()

    def _initialize_pygame(self):
        """Initialize pygame for 3D visualization"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.DOUBLEBUF)
        pygame.display.set_caption("Memory Defragmentation 3D Visualizer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 16)

    def _initialize_memory_blocks(self):
        """Initialize memory blocks with realistic distribution"""
        self.memory_blocks.clear()
        
        # Create a grid of memory blocks
        grid_size = int(np.sqrt(self.num_blocks // 100))  # Reduce complexity
        block_count = 0
        
        for x in range(grid_size):
            for y in range(grid_size):
                for z in range(10):  # 10 layers
                    if block_count >= self.num_blocks // 100:
                        break
                    
                    # Simulate realistic memory allocation patterns
                    if random.random() < 0.7:  # 70% allocated
                        state = MemoryBlockState.ALLOCATED
                        if random.random() < 0.3:  # 30% of allocated are fragmented
                            state = MemoryBlockState.FRAGMENTED
                    else:
                        state = MemoryBlockState.FREE
                    
                    block = MemoryBlock(
                        address=block_count * self.block_size,
                        size=self.block_size,
                        state=state,
                        process_id=random.randint(1000, 9999) if state != MemoryBlockState.FREE else None,
                        process_name=f"process_{random.randint(1, 20)}" if state != MemoryBlockState.FREE else "",
                        age=random.uniform(0, 100),
                        fragmentation_score=random.uniform(0, 1) if state == MemoryBlockState.FRAGMENTED else 0.0,
                        x=x * 20,
                        y=y * 20,
                        z=z * 10,
                        color=self._get_block_color(state)
                    )
                    
                    self.memory_blocks.append(block)
                    block_count += 1

    def _get_block_color(self, state: MemoryBlockState) -> Tuple[int, int, int]:
        """Get color for memory block based on state"""
        color_map = {
            MemoryBlockState.FREE: (50, 205, 50),      # Lime Green
            MemoryBlockState.ALLOCATED: (70, 130, 180), # Steel Blue
            MemoryBlockState.FRAGMENTED: (255, 69, 0),  # Red Orange
            MemoryBlockState.BEING_MOVED: (255, 215, 0), # Gold
            MemoryBlockState.OPTIMIZED: (148, 0, 211)   # Dark Violet
        }
        return color_map.get(state, (128, 128, 128))

    def start_defragmentation_visualization(self, real_defrag: bool = False):
        """Start the defragmentation visualization"""
        self.running = True
        self.start_time = time.time()
        
        # Start background defragmentation simulation
        defrag_thread = threading.Thread(target=self._run_defragmentation, args=(real_defrag,))
        defrag_thread.daemon = True
        defrag_thread.start()
        
        if VISUALIZATION_AVAILABLE:
            self._run_pygame_visualization()
        else:
            self._run_terminal_visualization()

    def _run_defragmentation(self, real_defrag: bool):
        """Run the actual defragmentation process"""
        phases = [
            DefragmentationPhase.SCANNING,
            DefragmentationPhase.ANALYZING,
            DefragmentationPhase.MOVING,
            DefragmentationPhase.COMPACTING,
            DefragmentationPhase.OPTIMIZING,
            DefragmentationPhase.COMPLETED
        ]
        
        total_steps = len(phases) * 100
        current_step = 0
        
        for phase in phases:
            self.current_phase = phase
            
            if phase == DefragmentationPhase.SCANNING:
                # Simulate scanning phase
                for i in range(100):
                    if not self.running:
                        break
                    time.sleep(0.05)
                    current_step += 1
                    self.progress = (current_step / total_steps) * 100
                    self._update_stats()
                    
            elif phase == DefragmentationPhase.ANALYZING:
                # Analyze fragmentation
                fragmented_blocks = [b for b in self.memory_blocks if b.state == MemoryBlockState.FRAGMENTED]
                for i, block in enumerate(fragmented_blocks[:50]):  # Limit for performance
                    if not self.running:
                        break
                    block.fragmentation_score = random.uniform(0.5, 1.0)
                    time.sleep(0.02)
                    current_step += 2
                    self.progress = (current_step / total_steps) * 100
                    self._update_stats()
                    
            elif phase == DefragmentationPhase.MOVING:
                # Move fragmented blocks
                fragmented_blocks = [b for b in self.memory_blocks if b.state == MemoryBlockState.FRAGMENTED]
                for i, block in enumerate(fragmented_blocks):
                    if not self.running:
                        break
                    
                    # Animate block movement
                    block.state = MemoryBlockState.BEING_MOVED
                    block.color = self._get_block_color(block.state)
                    
                    # Simulate movement animation
                    for step in range(20):
                        if not self.running:
                            break
                        # Update position for animation
                        block.x += random.uniform(-2, 2)
                        block.y += random.uniform(-2, 2)
                        time.sleep(0.01)
                    
                    # Find new optimal position
                    free_blocks = [b for b in self.memory_blocks if b.state == MemoryBlockState.FREE]
                    if free_blocks:
                        target = random.choice(free_blocks)
                        block.x, block.y, block.z = target.x, target.y, target.z
                        target.state = MemoryBlockState.ALLOCATED
                        target.color = self._get_block_color(target.state)
                    
                    block.state = MemoryBlockState.OPTIMIZED
                    block.color = self._get_block_color(block.state)
                    self.stats.blocks_moved += 1
                    
                    current_step += 1
                    self.progress = (current_step / total_steps) * 100
                    self._update_stats()
                    
            elif phase == DefragmentationPhase.COMPACTING:
                # Compact free space
                for i in range(50):
                    if not self.running:
                        break
                    time.sleep(0.03)
                    current_step += 2
                    self.progress = (current_step / total_steps) * 100
                    self._update_stats()
                    
            elif phase == DefragmentationPhase.OPTIMIZING:
                # Final optimization
                for i in range(30):
                    if not self.running:
                        break
                    time.sleep(0.05)
                    current_step += 3
                    self.progress = (current_step / total_steps) * 100
                    self._update_stats()
        
        self.current_phase = DefragmentationPhase.COMPLETED
        self.progress = 100.0
        self._calculate_final_stats()

    def _update_stats(self):
        """Update defragmentation statistics"""
        allocated_blocks = len([b for b in self.memory_blocks if b.state == MemoryBlockState.ALLOCATED])
        free_blocks = len([b for b in self.memory_blocks if b.state == MemoryBlockState.FREE])
        fragmented_blocks = len([b for b in self.memory_blocks if b.state == MemoryBlockState.FRAGMENTED])
        optimized_blocks = len([b for b in self.memory_blocks if b.state == MemoryBlockState.OPTIMIZED])
        
        total_blocks = len(self.memory_blocks)
        
        self.stats = DefragmentationStats(
            total_memory=total_blocks * self.block_size,
            free_memory=free_blocks * self.block_size,
            fragmented_memory=fragmented_blocks * self.block_size,
            largest_free_block=max([1] + [self.block_size] * free_blocks) if free_blocks > 0 else 0,
            fragmentation_percentage=(fragmented_blocks / max(total_blocks, 1)) * 100,
            blocks_moved=self.stats.blocks_moved,
            time_elapsed=time.time() - self.start_time,
            performance_gain=((optimized_blocks + allocated_blocks) / max(total_blocks, 1)) * 100
        )

    def _calculate_final_stats(self):
        """Calculate final performance statistics"""
        original_fragmentation = 30.0  # Assume 30% initial fragmentation
        current_fragmentation = self.stats.fragmentation_percentage
        
        improvement = max(0, original_fragmentation - current_fragmentation)
        self.stats.performance_gain = (improvement / original_fragmentation) * 100 if original_fragmentation > 0 else 0

    def _run_pygame_visualization(self):
        """Run the main pygame visualization loop"""
        while self.running:
            frame_start = time.time()
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keypress(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_click(event.pos, event.button)
            
            if not self.paused:
                self._update_camera()
            
            self._render_3d_scene()
            self._render_ui_overlay()
            
            pygame.display.flip()
            self.clock.tick(self.fps)
            
            self.frame_time = time.time() - frame_start

        pygame.quit()

    def _handle_keypress(self, key):
        """Handle keyboard input"""
        if key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key == pygame.K_r:
            self.auto_rotate = not self.auto_rotate
        elif key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_UP:
            self.zoom = min(3.0, self.zoom + 0.1)
        elif key == pygame.K_DOWN:
            self.zoom = max(0.1, self.zoom - 0.1)
        elif key == pygame.K_LEFT:
            self.camera_angle -= 5
        elif key == pygame.K_RIGHT:
            self.camera_angle += 5

    def _handle_mouse_click(self, pos, button):
        """Handle mouse clicks for interaction"""
        # Convert screen coordinates to 3D coordinates for block selection
        # This is a simplified version - full 3D picking would be more complex
        pass

    def _update_camera(self):
        """Update camera position and rotation"""
        if self.auto_rotate:
            self.camera_angle += 0.5
            if self.camera_angle >= 360:
                self.camera_angle = 0

    def _render_3d_scene(self):
        """Render the 3D memory visualization"""
        self.screen.fill((20, 20, 30))  # Dark background
        
        # Calculate 3D projection parameters
        center_x, center_y = self.width // 2, self.height // 2
        focal_length = 400 * self.zoom
        
        # Render memory blocks
        for block in self.memory_blocks:
            if block.state == MemoryBlockState.FREE and random.random() > 0.3:
                continue  # Skip some free blocks for performance
            
            # Apply 3D rotation
            angle_rad = np.radians(self.camera_angle)
            rotated_x = block.x * np.cos(angle_rad) - block.z * np.sin(angle_rad)
            rotated_z = block.x * np.sin(angle_rad) + block.z * np.cos(angle_rad)
            
            # 3D to 2D projection
            if rotated_z + 200 != 0:  # Avoid division by zero
                screen_x = int(center_x + (rotated_x * focal_length) / (rotated_z + 200))
                screen_y = int(center_y + (block.y * focal_length) / (rotated_z + 200))
                
                # Calculate block size based on distance
                size = max(1, int(10 * focal_length / (rotated_z + 200)))
                
                if 0 <= screen_x < self.width and 0 <= screen_y < self.height:
                    # Add some visual effects
                    color = block.color
                    if block.state == MemoryBlockState.BEING_MOVED:
                        # Pulsing effect for moving blocks
                        pulse = int(30 * np.sin(time.time() * 10))
                        color = tuple(min(255, c + pulse) for c in color)
                    
                    # Draw the block
                    pygame.draw.circle(self.screen, color, (screen_x, screen_y), size)
                    
                    # Add glow effect for special states
                    if block.state in [MemoryBlockState.BEING_MOVED, MemoryBlockState.OPTIMIZED]:
                        glow_color = tuple(c // 3 for c in color)
                        pygame.draw.circle(self.screen, glow_color, (screen_x, screen_y), size + 2, 1)

    def _render_ui_overlay(self):
        """Render UI overlay with statistics and controls"""
        # Phase indicator
        phase_text = f"Phase: {self.current_phase.value.upper()}"
        phase_surface = self.font.render(phase_text, True, (255, 255, 255))
        self.screen.blit(phase_surface, (10, 10))
        
        # Progress bar
        progress_rect = pygame.Rect(10, 40, 300, 20)
        pygame.draw.rect(self.screen, (50, 50, 50), progress_rect)
        progress_fill = pygame.Rect(10, 40, int(300 * self.progress / 100), 20)
        
        # Progress bar color based on phase
        progress_color = {
            DefragmentationPhase.SCANNING: (255, 165, 0),      # Orange
            DefragmentationPhase.ANALYZING: (255, 255, 0),     # Yellow
            DefragmentationPhase.MOVING: (0, 191, 255),        # Deep Sky Blue
            DefragmentationPhase.COMPACTING: (50, 205, 50),    # Lime Green
            DefragmentationPhase.OPTIMIZING: (148, 0, 211),    # Dark Violet
            DefragmentationPhase.COMPLETED: (0, 255, 0)        # Green
        }.get(self.current_phase, (128, 128, 128))
        
        pygame.draw.rect(self.screen, progress_color, progress_fill)
        pygame.draw.rect(self.screen, (255, 255, 255), progress_rect, 1)
        
        # Progress percentage
        progress_text = f"{self.progress:.1f}%"
        progress_surface = self.small_font.render(progress_text, True, (255, 255, 255))
        self.screen.blit(progress_surface, (320, 42))
        
        # Statistics panel
        stats_y = 80
        stats = [
            f"Total Memory: {self.stats.total_memory // (1024*1024):.0f} MB",
            f"Free Memory: {self.stats.free_memory // (1024*1024):.0f} MB",
            f"Fragmentation: {self.stats.fragmentation_percentage:.1f}%",
            f"Blocks Moved: {self.stats.blocks_moved}",
            f"Time Elapsed: {self.stats.time_elapsed:.1f}s",
            f"Performance Gain: {self.stats.performance_gain:.1f}%",
            f"FPS: {self.clock.get_fps():.0f}"
        ]
        
        for stat in stats:
            stat_surface = self.small_font.render(stat, True, (200, 200, 200))
            self.screen.blit(stat_surface, (10, stats_y))
            stats_y += 18
        
        # Controls help
        controls = [
            "Controls:",
            "SPACE - Pause/Resume",
            "R - Toggle Auto-Rotate",
            "↑↓ - Zoom In/Out",
            "←→ - Manual Rotate",
            "ESC - Exit"
        ]
        
        controls_y = self.height - 120
        for control in controls:
            control_surface = self.small_font.render(control, True, (150, 150, 150))
            self.screen.blit(control_surface, (10, controls_y))
            controls_y += 16
        
        # Legend
        legend_x = self.width - 200
        legend_items = [
            ("Free", MemoryBlockState.FREE),
            ("Allocated", MemoryBlockState.ALLOCATED),
            ("Fragmented", MemoryBlockState.FRAGMENTED),
            ("Being Moved", MemoryBlockState.BEING_MOVED),
            ("Optimized", MemoryBlockState.OPTIMIZED)
        ]
        
        legend_surface = self.font.render("Legend:", True, (255, 255, 255))
        self.screen.blit(legend_surface, (legend_x, 10))
        
        for i, (name, state) in enumerate(legend_items):
            y = 40 + i * 25
            color = self._get_block_color(state)
            pygame.draw.circle(self.screen, color, (legend_x + 10, y), 8)
            name_surface = self.small_font.render(name, True, (200, 200, 200))
            self.screen.blit(name_surface, (legend_x + 25, y - 8))

    def _run_terminal_visualization(self):
        """Run terminal-based visualization when GUI is not available"""
        if not RICH_AVAILABLE:
            self._run_simple_terminal_visualization()
            return
        
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="visualization", ratio=2)
        )
        
        with Live(layout, refresh_per_second=10, screen=True):
            while self.running:
                # Update header
                layout["header"].update(Panel(
                    f"Memory Defragmentation Visualizer - Phase: {self.current_phase.value.upper()}",
                    style="bold blue"
                ))
                
                # Update stats panel
                stats_table = Table(title="Statistics")
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", style="yellow")
                
                stats_table.add_row("Total Memory", f"{self.stats.total_memory // (1024*1024)} MB")
                stats_table.add_row("Free Memory", f"{self.stats.free_memory // (1024*1024)} MB")
                stats_table.add_row("Fragmentation", f"{self.stats.fragmentation_percentage:.1f}%")
                stats_table.add_row("Blocks Moved", str(self.stats.blocks_moved))
                stats_table.add_row("Time Elapsed", f"{self.stats.time_elapsed:.1f}s")
                stats_table.add_row("Performance Gain", f"{self.stats.performance_gain:.1f}%")
                
                layout["stats"].update(stats_table)
                
                # Update visualization (ASCII art representation)
                viz_text = self._generate_ascii_visualization()
                layout["visualization"].update(Panel(viz_text, title="Memory Map"))
                
                # Update footer
                progress_bar = "█" * int(self.progress // 2) + "░" * (50 - int(self.progress // 2))
                layout["footer"].update(Panel(
                    f"Progress: [{progress_bar}] {self.progress:.1f}%",
                    style="green"
                ))
                
                time.sleep(0.1)

    def _generate_ascii_visualization(self) -> str:
        """Generate ASCII art visualization of memory"""
        grid_width = 40
        grid_height = 20
        
        # Create a 2D grid representation
        grid = [['.' for _ in range(grid_width)] for _ in range(grid_height)]
        
        # Map memory blocks to grid
        for i, block in enumerate(self.memory_blocks[:grid_width * grid_height]):
            x = i % grid_width
            y = i // grid_width
            
            if y >= grid_height:
                break
            
            symbol_map = {
                MemoryBlockState.FREE: '.',
                MemoryBlockState.ALLOCATED: '▓',
                MemoryBlockState.FRAGMENTED: '▒',
                MemoryBlockState.BEING_MOVED: '◆',
                MemoryBlockState.OPTIMIZED: '█'
            }
            
            grid[y][x] = symbol_map.get(block.state, '?')
        
        # Convert grid to string
        lines = []
        for row in grid:
            lines.append(''.join(row))
        
        # Add legend
        lines.append("")
        lines.append("Legend: . Free  ▓ Allocated  ▒ Fragmented  ◆ Moving  █ Optimized")
        
        return '\n'.join(lines)

    def _run_simple_terminal_visualization(self):
        """Simple terminal visualization without rich library"""
        while self.running:
            # Clear screen
            print("\033[2J\033[H")
            
            print("=" * 60)
            print(f"Memory Defragmentation Visualizer")
            print(f"Phase: {self.current_phase.value.upper()}")
            print("=" * 60)
            
            # Progress bar
            progress_chars = int(self.progress // 2)
            progress_bar = "█" * progress_chars + "░" * (50 - progress_chars)
            print(f"Progress: [{progress_bar}] {self.progress:.1f}%")
            print()
            
            # Statistics
            print(f"Total Memory:     {self.stats.total_memory // (1024*1024):8.0f} MB")
            print(f"Free Memory:      {self.stats.free_memory // (1024*1024):8.0f} MB")
            print(f"Fragmentation:    {self.stats.fragmentation_percentage:8.1f}%")
            print(f"Blocks Moved:     {self.stats.blocks_moved:8d}")
            print(f"Time Elapsed:     {self.stats.time_elapsed:8.1f}s")
            print(f"Performance Gain: {self.stats.performance_gain:8.1f}%")
            print()
            
            # Simple memory visualization
            print("Memory Map:")
            viz = self._generate_ascii_visualization()
            print(viz)
            
            time.sleep(0.5)

    def stop_visualization(self):
        """Stop the visualization"""
        self.running = False

    def generate_html_report(self) -> str:
        """Generate HTML report with interactive plots"""
        if not VISUALIZATION_AVAILABLE:
            return "Visualization libraries not available for HTML report generation"
        
        # Create interactive plots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Memory Usage Over Time', 'Fragmentation Analysis', 
                          'Block Movement Timeline', 'Performance Metrics'),
            specs=[[{"secondary_y": True}, {"type": "pie"}],
                   [{"colspan": 2}, None]]
        )
        
        # Generate sample data for demonstration
        time_points = np.linspace(0, self.stats.time_elapsed, 100)
        memory_usage = 70 + 20 * np.sin(time_points) + np.random.normal(0, 2, 100)
        fragmentation = 30 * np.exp(-time_points / 10) + np.random.normal(0, 1, 100)
        
        # Memory usage plot
        fig.add_trace(
            go.Scatter(x=time_points, y=memory_usage, name="Memory Usage %"),
            row=1, col=1
        )
        
        # Fragmentation pie chart
        fig.add_trace(
            go.Pie(labels=['Optimized', 'Fragmented', 'Free'], 
                  values=[60, 25, 15], name="Memory Distribution"),
            row=1, col=2
        )
        
        # Performance timeline
        performance_data = np.cumsum(np.random.exponential(2, 50))
        fig.add_trace(
            go.Scatter(x=time_points[:50], y=performance_data, 
                      name="Cumulative Performance Gain", mode='lines+markers'),
            row=2, col=1
        )
        
        fig.update_layout(height=800, showlegend=True, 
                         title_text="Memory Defragmentation Analysis Report")
        
        html_content = fig.to_html(include_plotlyjs='cdn')
        
        # Save report
        report_path = Path.home() / ".system_optimizer_pro" / "defrag_report.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)

def main():
    """Test the memory defragmentation visualizer"""
    print("🎮 Memory Defragmentation 3D Visualizer")
    print("=" * 50)
    
    if not VISUALIZATION_AVAILABLE:
        print("⚠️  Warning: Visualization libraries not fully available")
        print("Installing dependencies for full 3D visualization...")
    
    visualizer = MemoryDefragmentationVisualizer(1200, 800)
    
    try:
        print("🚀 Starting defragmentation visualization...")
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
    except Exception as e:
        print(f"❌ Error during visualization: {e}")
    finally:
        visualizer.stop_visualization()

if __name__ == "__main__":
    main()
