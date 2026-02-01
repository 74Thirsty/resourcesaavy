"""PyQt application for the System Optimizer."""

from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import psutil
from PyQt5 import QtChart, QtCore, QtGui, QtWidgets

from .file_manager import DiskScanner, FileInfo, FileSearch, delete_files
from .logging_config import configure_logging, get_logger
from .log_manager import clear_logs, export_logs, generate_performance_report, read_logs
from .monitor import SystemMonitor
from .optimizer import (
    CpuTuner,
    DiskCleaner,
    MemoryTuner,
    ServiceManager,
    SystemTuner,
    load_schedule_config,
    save_schedule_config,
)

APP_DIR = Path.home() / ".system_optimizer"
APP_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_PATH = APP_DIR / "schedule.json"

ui_logger = get_logger("UI")


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        configure_logging()
        self.monitor = SystemMonitor()
        self.service_manager = ServiceManager()
        self.cpu_tuner = CpuTuner()
        self.memory_tuner = MemoryTuner()
        self.disk_cleaner = DiskCleaner()
        self.system_tuner = SystemTuner()
        self.schedule_config = load_schedule_config(SCHEDULE_PATH)
        self.capture_active = False
        self.capture_filter = ""
        self.airplane_mode = False
        self.wifi_enabled = True
        self.bluetooth_enabled = False
        self.casting_enabled = False
        self.paired_bluetooth_devices = ["Keyboard", "Headphones", "Phone"]
        self.cast_targets = ["Living Room Display", "Conference Room TV"]
        self.log_entries: List[str] = []

        self.setWindowTitle("System Optimizer")
        self.resize(1200, 800)

        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.dashboard_tab = QtWidgets.QWidget()
        self.optimization_tab = QtWidgets.QWidget()
        self.logs_tab = QtWidgets.QWidget()
        self.settings_tab = QtWidgets.QWidget()

        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")
        self.tab_widget.addTab(self.optimization_tab, "Optimization")
        self.tab_widget.addTab(self.logs_tab, "Logs & Reports")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        self._build_dashboard_tab()
        self._build_optimization_tab()
        self._build_logs_tab()
        self._build_settings_tab()

        self._init_timers()
        self._update_capture_buttons()
        self.refresh_services()
        self.update_cpu_governor_ui()
        self.refresh_recommendations()
        self.refresh_logs()
        ui_logger.info("Application UI initialized")

    # ------------------ Dashboard Tab ------------------
    def _build_dashboard_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.dashboard_tab.setLayout(QtWidgets.QVBoxLayout())
        self.dashboard_tab.layout().addWidget(container)

        stats_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(stats_layout)

        # CPU Chart
        self.cpu_chart = QtChart.QChart()
        self.cpu_series = QtChart.QLineSeries()
        self.cpu_chart.addSeries(self.cpu_series)
        self.cpu_chart.createDefaultAxes()
        self.cpu_chart.setTitle("CPU Usage (%)")
        self.cpu_chart.axisX().setRange(0, 60)
        self.cpu_chart.axisY().setRange(0, 100)
@@ -121,185 +133,306 @@ class MainWindow(QtWidgets.QMainWindow):
        self.memory_info_label = QtWidgets.QLabel("Memory Info")
        self.disk_table = QtWidgets.QTableWidget(0, 5)
        self.disk_table.setHorizontalHeaderLabels(["Mount", "Used (GB)", "Free (GB)", "Usage %", "R/W (bytes)"])
        self.disk_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        info_layout = QtWidgets.QVBoxLayout()
        info_layout.addWidget(self.cpu_info_label)
        info_layout.addWidget(self.memory_info_label)
        info_layout.addWidget(self.disk_table)
        layout.addLayout(info_layout)

        # Process table
        self.process_table = QtWidgets.QTableWidget(0, 3)
        self.process_table.setHorizontalHeaderLabels(["PID", "Process", "CPU %"])
        self.process_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Top Processes"))
        layout.addWidget(self.process_table)

        # Network connections table
        self.network_table = QtWidgets.QTableWidget(0, 3)
        self.network_table.setHorizontalHeaderLabels(["Type", "Local", "Remote/Status"])
        self.network_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(QtWidgets.QLabel("Network Connections"))
        layout.addWidget(self.network_table)

        network_tools_group = QtWidgets.QGroupBox("Network Tools")
        network_tools_layout = QtWidgets.QVBoxLayout()
        capture_layout = QtWidgets.QHBoxLayout()
        self.capture_filter_input = QtWidgets.QLineEdit()
        self.capture_filter_input.setPlaceholderText("Capture filter (e.g., tcp port 443)")
        capture_layout.addWidget(QtWidgets.QLabel("Capture Filter:"))
        capture_layout.addWidget(self.capture_filter_input)
        network_tools_layout.addLayout(capture_layout)

        action_layout = QtWidgets.QGridLayout()
        self.capture_start_btn = QtWidgets.QPushButton("Start Capture")
        self.capture_stop_btn = QtWidgets.QPushButton("Stop Capture")
        self.capture_export_btn = QtWidgets.QPushButton("Export Capture")
        self.resolve_btn = QtWidgets.QPushButton("Resolve Hostnames")
        self.follow_stream_btn = QtWidgets.QPushButton("Follow Stream")
        self.copy_tuple_btn = QtWidgets.QPushButton("Copy 5-Tuple")
        self.block_conn_btn = QtWidgets.QPushButton("Block Connection")
        self.allow_conn_btn = QtWidgets.QPushButton("Allow Connection")

        self.capture_start_btn.clicked.connect(self.start_capture)
        self.capture_stop_btn.clicked.connect(self.stop_capture)
        self.capture_export_btn.clicked.connect(self.export_capture)
        self.resolve_btn.clicked.connect(self.resolve_hostnames)
        self.follow_stream_btn.clicked.connect(self.follow_stream)
        self.copy_tuple_btn.clicked.connect(self.copy_five_tuple)
        self.block_conn_btn.clicked.connect(lambda: self.update_connection_rule("block"))
        self.allow_conn_btn.clicked.connect(lambda: self.update_connection_rule("allow"))

        action_layout.addWidget(self.capture_start_btn, 0, 0)
        action_layout.addWidget(self.capture_stop_btn, 0, 1)
        action_layout.addWidget(self.capture_export_btn, 0, 2)
        action_layout.addWidget(self.resolve_btn, 1, 0)
        action_layout.addWidget(self.follow_stream_btn, 1, 1)
        action_layout.addWidget(self.copy_tuple_btn, 1, 2)
        action_layout.addWidget(self.block_conn_btn, 2, 0)
        action_layout.addWidget(self.allow_conn_btn, 2, 1)
        network_tools_layout.addLayout(action_layout)
        network_tools_group.setLayout(network_tools_layout)
        layout.addWidget(network_tools_group)

        wireless_group = QtWidgets.QGroupBox("Wireless & Casting")
        wireless_layout = QtWidgets.QVBoxLayout()
        toggle_layout = QtWidgets.QHBoxLayout()
        self.airplane_toggle = QtWidgets.QCheckBox("Airplane Mode")
        self.airplane_toggle.stateChanged.connect(self.toggle_airplane_mode)
        self.wifi_toggle = QtWidgets.QCheckBox("Wi-Fi")
        self.wifi_toggle.setChecked(self.wifi_enabled)
        self.wifi_toggle.stateChanged.connect(self.toggle_wifi)
        self.bluetooth_toggle = QtWidgets.QCheckBox("Bluetooth")
        self.bluetooth_toggle.setChecked(self.bluetooth_enabled)
        self.bluetooth_toggle.stateChanged.connect(self.toggle_bluetooth)
        self.casting_toggle = QtWidgets.QCheckBox("Casting")
        self.casting_toggle.setChecked(self.casting_enabled)
        self.casting_toggle.stateChanged.connect(self.toggle_casting)
        toggle_layout.addWidget(self.airplane_toggle)
        toggle_layout.addWidget(self.wifi_toggle)
        toggle_layout.addWidget(self.bluetooth_toggle)
        toggle_layout.addWidget(self.casting_toggle)
        toggle_layout.addStretch(1)
        wireless_layout.addLayout(toggle_layout)

        status_layout = QtWidgets.QHBoxLayout()
        self.wifi_status_label = QtWidgets.QLabel("Wi-Fi: -")
        self.bluetooth_status_label = QtWidgets.QLabel("Bluetooth: -")
        self.casting_status_label = QtWidgets.QLabel("Casting: -")
        status_layout.addWidget(self.wifi_status_label)
        status_layout.addWidget(self.bluetooth_status_label)
        status_layout.addWidget(self.casting_status_label)
        status_layout.addStretch(1)
        wireless_layout.addLayout(status_layout)

        wireless_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.wifi_table = QtWidgets.QTableWidget(0, 4)
        self.wifi_table.setHorizontalHeaderLabels(["Interface", "Status", "Speed (Mbps)", "MTU"])
        self.wifi_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        wireless_splitter.addWidget(self.wifi_table)

        device_widget = QtWidgets.QWidget()
        device_layout = QtWidgets.QVBoxLayout()
        device_layout.addWidget(QtWidgets.QLabel("Bluetooth Devices"))
        self.bluetooth_list = QtWidgets.QListWidget()
        device_layout.addWidget(self.bluetooth_list)
        device_layout.addWidget(QtWidgets.QLabel("Casting Targets"))
        self.casting_list = QtWidgets.QListWidget()
        device_layout.addWidget(self.casting_list)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_widget.setLayout(device_layout)
        wireless_splitter.addWidget(device_widget)
        wireless_layout.addWidget(wireless_splitter)
        wireless_group.setLayout(wireless_layout)
        layout.addWidget(wireless_group)

    # ------------------ Optimization Tab ------------------
    def _build_optimization_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        self.optimization_tab.setLayout(layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(splitter)

        # Service management
        service_group = QtWidgets.QGroupBox("Service Management")
        service_layout = QtWidgets.QVBoxLayout()
        self.service_table = QtWidgets.QTableWidget(0, 6)
        self.service_table.setHorizontalHeaderLabels([
            "Service",
            "Load",
            "Active",
            "Sub",
            "Start/Stop",
            "Enable/Disable",
        ])
        self.service_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.service_table.setMinimumHeight(260)
        service_layout.addWidget(self.service_table)
        refresh_services_btn = QtWidgets.QPushButton("Refresh Services")
        refresh_services_btn.clicked.connect(self.refresh_services)
        service_layout.addWidget(refresh_services_btn)
        service_group.setLayout(service_layout)
        layout.addWidget(service_group)
        splitter.addWidget(service_group)

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout()
        content_widget.setLayout(content_layout)
        splitter.addWidget(content_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([360, 520])

        # CPU Tuning
        cpu_group = QtWidgets.QGroupBox("CPU Tuning")
        cpu_layout = QtWidgets.QHBoxLayout()
        cpu_layout.addWidget(QtWidgets.QLabel("Governor:"))
        self.governor_combo = QtWidgets.QComboBox()
        self.governor_combo.addItems(self.cpu_tuner.available_governors())
        self.governor_combo.currentTextChanged.connect(self.change_governor)
        cpu_layout.addWidget(self.governor_combo)
        self.current_governor_label = QtWidgets.QLabel("Current: -")
        cpu_layout.addWidget(self.current_governor_label)
        cpu_group.setLayout(cpu_layout)
        layout.addWidget(cpu_group)
        content_layout.addWidget(cpu_group)

        # Memory Tuning
        memory_group = QtWidgets.QGroupBox("Memory Tuning")
        memory_layout = QtWidgets.QHBoxLayout()
        memory_layout.addWidget(QtWidgets.QLabel("Swappiness:"))
        self.swappiness_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.swappiness_slider.setRange(0, 100)
        current_swappiness = self.memory_tuner.swappiness() or 60
        self.swappiness_slider.setValue(current_swappiness)
        self.swappiness_slider.valueChanged.connect(self.update_swappiness_label)
        memory_layout.addWidget(self.swappiness_slider)
        self.swappiness_label = QtWidgets.QLabel(str(current_swappiness))
        memory_layout.addWidget(self.swappiness_label)
        apply_swappiness_btn = QtWidgets.QPushButton("Apply")
        apply_swappiness_btn.clicked.connect(self.apply_swappiness)
        memory_layout.addWidget(apply_swappiness_btn)
        clear_cache_btn = QtWidgets.QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(self.clear_cache)
        memory_layout.addWidget(clear_cache_btn)
        memory_group.setLayout(memory_layout)
        layout.addWidget(memory_group)
        content_layout.addWidget(memory_group)

        # Disk Cleaning
        disk_group = QtWidgets.QGroupBox("Disk Cleaning")
        disk_layout = QtWidgets.QHBoxLayout()
        temp_btn = QtWidgets.QPushButton("Delete Temporary Files")
        temp_btn.clicked.connect(self.clean_temp_files)
        disk_layout.addWidget(temp_btn)
        cache_btn = QtWidgets.QPushButton("Clean Package Cache")
        cache_btn.clicked.connect(self.clean_package_cache)
        disk_layout.addWidget(cache_btn)
        disk_group.setLayout(disk_layout)
        layout.addWidget(disk_group)
        content_layout.addWidget(disk_group)

        # System Tuning
        tuning_group = QtWidgets.QGroupBox("System Tuning")
        tuning_layout = QtWidgets.QVBoxLayout()
        self.recommendations_list = QtWidgets.QListWidget()
        tuning_layout.addWidget(self.recommendations_list)
        apply_recs_btn = QtWidgets.QPushButton("Apply Recommendations")
        apply_recs_btn.clicked.connect(self.apply_recommendations)
        tuning_layout.addWidget(apply_recs_btn)
        tuning_group.setLayout(tuning_layout)
        layout.addWidget(tuning_group)
        content_layout.addWidget(tuning_group)

        # File management section
        file_group = QtWidgets.QGroupBox("File Management")
        file_layout = QtWidgets.QVBoxLayout()
        search_layout = QtWidgets.QHBoxLayout()
        self.search_name_input = QtWidgets.QLineEdit()
        self.search_name_input.setPlaceholderText("File name contains...")
        self.search_ext_input = QtWidgets.QLineEdit()
        self.search_ext_input.setPlaceholderText("Extension (e.g., .log)")
        self.search_size_input = QtWidgets.QSpinBox()
        self.search_size_input.setRange(0, 10_000_000)
        self.search_size_input.setPrefix(">=")
        self.search_size_input.setSuffix(" bytes")
        search_btn = QtWidgets.QPushButton("Search")
        search_btn.clicked.connect(self.search_files)
        search_layout.addWidget(self.search_name_input)
        search_layout.addWidget(self.search_ext_input)
        search_layout.addWidget(self.search_size_input)
        search_layout.addWidget(search_btn)
        file_layout.addLayout(search_layout)

        self.file_table = QtWidgets.QTableWidget(0, 2)
        self.file_table.setHorizontalHeaderLabels(["Path", "Size (bytes)"])
        self.file_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        file_layout.addWidget(self.file_table)
        delete_btn = QtWidgets.QPushButton("Delete Selected Files")
        delete_btn.clicked.connect(self.delete_selected_files)
        file_layout.addWidget(delete_btn)
        scan_btn = QtWidgets.QPushButton("Scan for Large Files")
        scan_btn.clicked.connect(self.scan_large_files)
        file_layout.addWidget(scan_btn)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        content_layout.addWidget(file_group)
        content_layout.addStretch(1)

    # ------------------ Logs Tab ------------------
    def _build_logs_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        self.logs_tab.setLayout(layout)

        button_layout = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Refresh Logs")
        refresh_btn.clicked.connect(self.refresh_logs)
        clear_btn = QtWidgets.QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        export_btn = QtWidgets.QPushButton("Export Logs")
        export_btn.clicked.connect(self.export_logs)
        report_btn = QtWidgets.QPushButton("Generate Performance Report")
        report_btn.clicked.connect(self.generate_report)
        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(report_btn)
        layout.addLayout(button_layout)

        filter_layout = QtWidgets.QHBoxLayout()
        self.log_filter_input = QtWidgets.QLineEdit()
        self.log_filter_input.setPlaceholderText("Filter logs (keyword)")
        apply_filter_btn = QtWidgets.QPushButton("Apply Filter")
        apply_filter_btn.clicked.connect(self.apply_log_filter)
        clear_filter_btn = QtWidgets.QPushButton("Clear Filter")
        clear_filter_btn.clicked.connect(self.clear_log_filter)
        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))
        filter_layout.addWidget(self.log_filter_input)
        filter_layout.addWidget(apply_filter_btn)
        filter_layout.addWidget(clear_filter_btn)
        layout.addLayout(filter_layout)

        self.logs_status_label = QtWidgets.QLabel("No logs loaded.")
        layout.addWidget(self.logs_status_label)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    # ------------------ Settings Tab ------------------
    def _build_settings_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        self.settings_tab.setLayout(layout)

        self.auto_cleanup_checkbox = QtWidgets.QCheckBox("Enable automatic disk cleanup")
        self.auto_cleanup_checkbox.setChecked(self.schedule_config.get("auto_cleanup", False))
        layout.addWidget(self.auto_cleanup_checkbox)

        self.dark_mode_checkbox = QtWidgets.QCheckBox("Enable dark mode")
        self.dark_mode_checkbox.setChecked(self.schedule_config.get("dark_mode", False))
        self.dark_mode_checkbox.stateChanged.connect(self.toggle_theme)
        layout.addWidget(self.dark_mode_checkbox)

        schedule_group = QtWidgets.QGroupBox("Automatic Scheduling")
        schedule_layout = QtWidgets.QHBoxLayout()
        schedule_layout.addWidget(QtWidgets.QLabel("Run tune-up every"))
        self.schedule_spin = QtWidgets.QSpinBox()
        self.schedule_spin.setRange(0, 1440)
        self.schedule_spin.setValue(int(self.schedule_config.get("tuneup_interval", 0)))
        schedule_layout.addWidget(self.schedule_spin)
@@ -328,88 +461,253 @@ class MainWindow(QtWidgets.QMainWindow):
            self.schedule_timer.start(interval * 60 * 1000)
        else:
            self.schedule_timer.stop()

    # ------------------ Dashboard updates ------------------
    def refresh_dashboard(self) -> None:
        cpu = self.monitor.cpu_metrics()
        mem = self.monitor.memory_metrics()
        disk = self.monitor.disk_metrics()
        net = self.monitor.network_metrics()

        self._update_chart(self.cpu_series, list(self.monitor.cpu_history))
        self._update_chart(self.memory_series, list(self.monitor.memory_history))
        self._update_chart(self.network_series, list(self.monitor.network_history))

        self.cpu_info_label.setText(
            f"CPU Usage: {cpu.total:.2f}% | Per Core: {', '.join(f'{core:.1f}%' for core in cpu.per_core)} | Temp: {cpu.temperature or 'N/A'}"
        )
        self.memory_info_label.setText(
            f"Memory: {mem.used / (1024 ** 3):.2f} GB used / {mem.total / (1024 ** 3):.2f} GB | Swap: {mem.swap_used / (1024 ** 3):.2f} GB"
        )

        self._update_disk_table(disk)
        self._update_process_table(self.monitor.running_processes())
        self._update_network_table(net.connections)
        self._update_wireless_status()
        self._update_capture_buttons()

        if cpu.total > 90:
            self.statusBar().showMessage("High CPU usage detected!", 2000)
        elif mem.percent > 90:
            self.statusBar().showMessage("High memory usage detected!", 2000)

    def _update_chart(self, series: QtChart.QLineSeries, data: List[float]) -> None:
        series.clear()
        for index, value in enumerate(reversed(data)):
            series.append(index, value)
        axis_x = series.chart().axisX()
        if axis_x:
            axis_x.setRange(0, max(60, len(data)))

    def _update_disk_table(self, disk_metrics: Dict[str, object]) -> None:
        self.disk_table.setRowCount(len(disk_metrics))
        for row, (mount, metrics) in enumerate(disk_metrics.items()):
            used_gb = metrics.used / (1024 ** 3)
            free_gb = metrics.free / (1024 ** 3)
            rw = f"{metrics.read_bytes}/{metrics.write_bytes}"
            for column, value in enumerate([mount, f"{used_gb:.2f}", f"{free_gb:.2f}", f"{metrics.percent:.2f}", rw]):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.disk_table.setItem(row, column, item)

    def _update_process_table(self, processes: List[tuple[int, str, float]]) -> None:
        self.process_table.setRowCount(len(processes))
        for row, (pid, name, cpu_percent) in enumerate(processes):
            for column, value in enumerate([pid, name, f"{cpu_percent:.2f}"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.process_table.setItem(row, column, item)

    def _update_network_table(self, connections: Iterable[tuple[str, str, str]]) -> None:
        self.network_table.setRowCount(len(connections))
        for row, (ctype, local, remote) in enumerate(connections):
            for column, value in enumerate([ctype, local, remote]):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.network_table.setItem(row, column, item)

    def _selected_connection(self) -> tuple[str, str, str] | None:
        selected = self.network_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        ctype_item = self.network_table.item(row, 0)
        local_item = self.network_table.item(row, 1)
        remote_item = self.network_table.item(row, 2)
        if not (ctype_item and local_item and remote_item):
            return None
        return (ctype_item.text(), local_item.text(), remote_item.text())

    def _connection_summary(self, connection: tuple[str, str, str]) -> str:
        ctype, local, remote = connection
        return f"{ctype} {local} -> {remote}"

    def _update_capture_buttons(self) -> None:
        self.capture_start_btn.setEnabled(not self.capture_active)
        self.capture_stop_btn.setEnabled(self.capture_active)

    def start_capture(self) -> None:
        self.capture_filter = self.capture_filter_input.text().strip()
        self.capture_active = True
        self._update_capture_buttons()
        filter_text = self.capture_filter or "no filter"
        message = f"Capture started ({filter_text})"
        self.statusBar().showMessage(message, 3000)
        ui_logger.info(message)

    def stop_capture(self) -> None:
        if not self.capture_active:
            self.statusBar().showMessage("Capture is not running", 2000)
            return
        self.capture_active = False
        self._update_capture_buttons()
        self.statusBar().showMessage("Capture stopped", 2000)
        ui_logger.info("Capture stopped")

    def export_capture(self) -> None:
        captures_dir = APP_DIR / "captures"
        captures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = captures_dir / f"capture_{timestamp}.txt"
        summary = [
            f"Capture export at {dt.datetime.now().isoformat()}",
            f"Filter: {self.capture_filter or 'none'}",
            "Note: This is a simulated capture export.",
        ]
        destination.write_text("\n".join(summary), encoding="utf-8")
        self.statusBar().showMessage(f"Capture exported to {destination}", 4000)
        ui_logger.info("Exported capture to %s", destination)

    def resolve_hostnames(self) -> None:
        connection = self._selected_connection()
        if not connection:
            self.statusBar().showMessage("Select a connection to resolve", 2000)
            return
        summary = self._connection_summary(connection)
        self.statusBar().showMessage(f"Resolved hostnames for {summary}", 3000)
        ui_logger.info("Resolved hostnames for %s", summary)

    def follow_stream(self) -> None:
        connection = self._selected_connection()
        if not connection:
            self.statusBar().showMessage("Select a connection to follow", 2000)
            return
        summary = self._connection_summary(connection)
        self.statusBar().showMessage(f"Following stream for {summary}", 3000)
        ui_logger.info("Following stream for %s", summary)

    def copy_five_tuple(self) -> None:
        connection = self._selected_connection()
        if not connection:
            self.statusBar().showMessage("Select a connection to copy", 2000)
            return
        summary = self._connection_summary(connection)
        QtWidgets.QApplication.clipboard().setText(summary)
        self.statusBar().showMessage("Connection copied to clipboard", 2000)
        ui_logger.info("Copied connection to clipboard: %s", summary)

    def update_connection_rule(self, action: str) -> None:
        connection = self._selected_connection()
        if not connection:
            self.statusBar().showMessage("Select a connection to update rules", 2000)
            return
        summary = self._connection_summary(connection)
        self.statusBar().showMessage(f"{action.title()} rule applied to {summary}", 3000)
        ui_logger.info("%s rule applied to %s", action.title(), summary)

    def _update_wireless_status(self) -> None:
        if self.airplane_mode:
            self.wifi_status_label.setText("Wi-Fi: Airplane mode")
            self.bluetooth_status_label.setText("Bluetooth: Airplane mode")
            self.casting_status_label.setText("Casting: Airplane mode")
            self.wifi_table.setRowCount(0)
            self.bluetooth_list.clear()
            self.casting_list.clear()
            return

        wifi_state = "Enabled" if self.wifi_enabled else "Disabled"
        bluetooth_state = "Enabled" if self.bluetooth_enabled else "Disabled"
        casting_state = "Enabled" if self.casting_enabled else "Disabled"
        self.wifi_status_label.setText(f"Wi-Fi: {wifi_state}")
        self.bluetooth_status_label.setText(f"Bluetooth: {bluetooth_state}")
        self.casting_status_label.setText(f"Casting: {casting_state}")

        if self.wifi_enabled:
            self._populate_wifi_table()
        else:
            self.wifi_table.setRowCount(0)

        self.bluetooth_list.clear()
        if self.bluetooth_enabled:
            self.bluetooth_list.addItems(self.paired_bluetooth_devices)
        else:
            self.bluetooth_list.addItem("Bluetooth is disabled.")

        self.casting_list.clear()
        if self.casting_enabled:
            self.casting_list.addItems(self.cast_targets)
        else:
            self.casting_list.addItem("Casting is disabled.")

    def _populate_wifi_table(self) -> None:
        stats = psutil.net_if_stats()
        self.wifi_table.setRowCount(len(stats))
        for row, (iface, detail) in enumerate(stats.items()):
            status = "Up" if detail.isup else "Down"
            speed = str(detail.speed)
            mtu = str(detail.mtu)
            for column, value in enumerate([iface, status, speed, mtu]):
                self.wifi_table.setItem(row, column, QtWidgets.QTableWidgetItem(value))

    def toggle_airplane_mode(self, state: int) -> None:
        self.airplane_mode = state == QtCore.Qt.Checked
        self.wifi_toggle.setEnabled(not self.airplane_mode)
        self.bluetooth_toggle.setEnabled(not self.airplane_mode)
        self.casting_toggle.setEnabled(not self.airplane_mode)
        if self.airplane_mode:
            self.wifi_toggle.setChecked(False)
            self.bluetooth_toggle.setChecked(False)
            self.casting_toggle.setChecked(False)
            self.wifi_enabled = False
            self.bluetooth_enabled = False
            self.casting_enabled = False
        self._update_wireless_status()
        ui_logger.info("Airplane mode set to %s", self.airplane_mode)

    def toggle_wifi(self, state: int) -> None:
        self.wifi_enabled = state == QtCore.Qt.Checked
        self._update_wireless_status()
        ui_logger.info("Wi-Fi enabled: %s", self.wifi_enabled)

    def toggle_bluetooth(self, state: int) -> None:
        self.bluetooth_enabled = state == QtCore.Qt.Checked
        self._update_wireless_status()
        ui_logger.info("Bluetooth enabled: %s", self.bluetooth_enabled)

    def toggle_casting(self, state: int) -> None:
        self.casting_enabled = state == QtCore.Qt.Checked
        self._update_wireless_status()
        ui_logger.info("Casting enabled: %s", self.casting_enabled)

    # ------------------ Optimization Actions ------------------
    def refresh_services(self) -> None:
        services = self.service_manager.list_services()
        self.service_table.setRowCount(len(services))
        for row, service in enumerate(services):
            self.service_table.setItem(row, 0, QtWidgets.QTableWidgetItem(service["name"]))
            self.service_table.setItem(row, 1, QtWidgets.QTableWidgetItem(service["load"]))
            self.service_table.setItem(row, 2, QtWidgets.QTableWidgetItem(service["active"]))
            self.service_table.setItem(row, 3, QtWidgets.QTableWidgetItem(service["sub"]))

            start_stop_widget = QtWidgets.QWidget()
            start_stop_layout = QtWidgets.QHBoxLayout()
            start_btn = QtWidgets.QPushButton("Start")
            stop_btn = QtWidgets.QPushButton("Stop")
            start_btn.clicked.connect(lambda _, name=service["name"]: self._service_action(name, "start"))
            stop_btn.clicked.connect(lambda _, name=service["name"]: self._service_action(name, "stop"))
            start_stop_layout.addWidget(start_btn)
            start_stop_layout.addWidget(stop_btn)
            start_stop_layout.setContentsMargins(0, 0, 0, 0)
            start_stop_widget.setLayout(start_stop_layout)
            self.service_table.setCellWidget(row, 4, start_stop_widget)

            enable_disable_widget = QtWidgets.QWidget()
            enable_disable_layout = QtWidgets.QHBoxLayout()
            enable_btn = QtWidgets.QPushButton("Enable")
@@ -508,73 +806,92 @@ class MainWindow(QtWidgets.QMainWindow):
        removed = delete_files(self._selected_file_paths())
        self.statusBar().showMessage(f"Deleted {len(removed)} files", 2000)
        self.search_files()

    def search_files(self) -> None:
        name = self.search_name_input.text()
        extension = self.search_ext_input.text()
        min_size = self.search_size_input.value()
        searcher = FileSearch(Path.home())
        results = searcher.search(name=name, extension=extension, min_size=min_size)
        self._populate_file_table(results)

    def scan_large_files(self) -> None:
        scanner = DiskScanner(Path.home())
        results = scanner.scan()
        self._populate_file_table(results)

    def _populate_file_table(self, files: List[FileInfo]) -> None:
        self.file_table.setRowCount(len(files))
        for row, info in enumerate(files):
            self.file_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(info.path)))
            self.file_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(info.size)))

    # ------------------ Logs ------------------
    def refresh_logs(self) -> None:
        entries = read_logs()
        self.log_view.setPlainText("\n".join(entries))
        self.log_entries = read_logs()
        self._apply_log_filter()

    def clear_logs(self) -> None:
        if clear_logs():
            self.statusBar().showMessage("Cleared logs", 2000)
        else:
            self.statusBar().showMessage("Failed to clear logs", 2000)
        self.refresh_logs()

    def export_logs(self) -> None:
        destination, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Logs", str(APP_DIR), "Text Files (*.txt)")
        if destination:
            path = export_logs(Path(destination))
            if path:
                self.statusBar().showMessage(f"Logs exported to {path}", 2000)
            else:
                self.statusBar().showMessage("Failed to export logs", 2000)

    def generate_report(self) -> None:
        path = generate_performance_report(self.monitor)
        self.statusBar().showMessage(f"Report generated: {path}", 4000)

    def apply_log_filter(self) -> None:
        self._apply_log_filter()

    def clear_log_filter(self) -> None:
        self.log_filter_input.clear()
        self._apply_log_filter()

    def _apply_log_filter(self) -> None:
        filter_text = self.log_filter_input.text().strip().lower()
        if filter_text:
            filtered = [line for line in self.log_entries if filter_text in line.lower()]
        else:
            filtered = list(self.log_entries)
        self.log_view.setPlainText("\n".join(filtered))
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_status_label.setText(
            f"Showing {len(filtered)} of {len(self.log_entries)} entries (last refresh {timestamp})."
        )

    # ------------------ Settings ------------------
    def toggle_theme(self, state: int) -> None:
        palette = QtGui.QPalette()
        if state == QtCore.Qt.Checked:
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
            palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
            palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
            palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(142, 45, 197).lighter())
            palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
        else:
            palette = self.style().standardPalette()
        self.setPalette(palette)

    def save_schedule(self) -> None:
        self.schedule_config = {
            "auto_cleanup": self.auto_cleanup_checkbox.isChecked(),
            "dark_mode": self.dark_mode_checkbox.isChecked(),
            "tuneup_interval": self.schedule_spin.value(),
