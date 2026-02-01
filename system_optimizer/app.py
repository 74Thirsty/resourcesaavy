"""PyQt application for the System Optimizer."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Iterable, List

try:
    from PyQt5 import QtChart
except Exception as _err:  # pragma: no cover - environment specific
    raise ImportError(
        "PyQt5.QtChart (PyQtChart) is not installed or not available in this environment.\n"
        "Install it with: pip install PyQtChart\n"
        "Or on Debian/Ubuntu/Parrot: sudo apt install python3-pyqt5.qtchart"
    ) from _err

from PyQt5 import QtCore, QtGui, QtWidgets

from .file_manager import DiskScanner, FileInfo, FileSearch, delete_files
from .logging_config import configure_logging, get_logger
from .logs import clear_logs, export_logs, generate_performance_report, read_logs
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
        self.cpu_chart.legend().hide()
        self.cpu_chart_view = QtChart.QChartView(self.cpu_chart)
        stats_layout.addWidget(self.cpu_chart_view, 1)

        # Memory Chart
        self.memory_chart = QtChart.QChart()
        self.memory_series = QtChart.QLineSeries()
        self.memory_chart.addSeries(self.memory_series)
        self.memory_chart.createDefaultAxes()
        self.memory_chart.setTitle("Memory Usage (%)")
        self.memory_chart.axisX().setRange(0, 60)
        self.memory_chart.axisY().setRange(0, 100)
        self.memory_chart.legend().hide()
        self.memory_chart_view = QtChart.QChartView(self.memory_chart)
        stats_layout.addWidget(self.memory_chart_view, 1)

        # Network Chart
        self.network_chart = QtChart.QChart()
        self.network_series = QtChart.QLineSeries()
        self.network_chart.addSeries(self.network_series)
        self.network_chart.createDefaultAxes()
        self.network_chart.setTitle("Network Activity (bytes/s)")
        self.network_chart.axisX().setRange(0, 60)
        self.network_chart.legend().hide()
        self.network_chart_view = QtChart.QChartView(self.network_chart)
        stats_layout.addWidget(self.network_chart_view, 1)

        # CPU Info
        self.cpu_info_label = QtWidgets.QLabel("CPU Info")
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

    # ------------------ Optimization Tab ------------------
    def _build_optimization_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        self.optimization_tab.setLayout(layout)

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
        service_layout.addWidget(self.service_table)
        refresh_services_btn = QtWidgets.QPushButton("Refresh Services")
        refresh_services_btn.clicked.connect(self.refresh_services)
        service_layout.addWidget(refresh_services_btn)
        service_group.setLayout(service_layout)
        layout.addWidget(service_group)

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
        schedule_layout.addWidget(QtWidgets.QLabel("minutes"))
        save_schedule_btn = QtWidgets.QPushButton("Save Schedule")
        save_schedule_btn.clicked.connect(self.save_schedule)
        schedule_layout.addWidget(save_schedule_btn)
        schedule_group.setLayout(schedule_layout)
        layout.addWidget(schedule_group)

        layout.addStretch(1)

    # ------------------ Timers ------------------
    def _init_timers(self) -> None:
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.refresh_dashboard)
        self.update_timer.start(1000)

        self.schedule_timer = QtCore.QTimer(self)
        self.schedule_timer.timeout.connect(self.execute_scheduled_tasks)
        self._reset_schedule_timer()

    def _reset_schedule_timer(self) -> None:
        interval = int(self.schedule_config.get("tuneup_interval", 0))
        if interval > 0:
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
            disable_btn = QtWidgets.QPushButton("Disable")
            enable_btn.clicked.connect(lambda _, name=service["name"]: self._service_action(name, "enable"))
            disable_btn.clicked.connect(lambda _, name=service["name"]: self._service_action(name, "disable"))
            enable_disable_layout.addWidget(enable_btn)
            enable_disable_layout.addWidget(disable_btn)
            enable_disable_layout.setContentsMargins(0, 0, 0, 0)
            enable_disable_widget.setLayout(enable_disable_layout)
            self.service_table.setCellWidget(row, 5, enable_disable_widget)

        self.refresh_recommendations()

    def _service_action(self, service: str, action: str) -> None:
        mapping = {
            "start": self.service_manager.start_service,
            "stop": self.service_manager.stop_service,
            "enable": self.service_manager.enable_service,
            "disable": self.service_manager.disable_service,
        }
        fn = mapping[action]
        if fn(service):
            self.statusBar().showMessage(f"{action.title()}ed {service}", 2000)
        else:
            self.statusBar().showMessage(f"Failed to {action} {service}", 2000)
        self.refresh_services()

    def update_cpu_governor_ui(self) -> None:
        current = self.cpu_tuner.current_governor() or "Unknown"
        self.current_governor_label.setText(f"Current: {current}")
        if current and current not in [self.governor_combo.itemText(i) for i in range(self.governor_combo.count())]:
            self.governor_combo.addItem(current)

    def change_governor(self, governor: str) -> None:
        if not governor:
            return
        if self.cpu_tuner.set_governor(governor):
            self.statusBar().showMessage(f"CPU governor changed to {governor}", 2000)
        else:
            self.statusBar().showMessage(f"Failed to set governor {governor}", 2000)
        self.update_cpu_governor_ui()

    def update_swappiness_label(self, value: int) -> None:
        self.swappiness_label.setText(str(value))

    def apply_swappiness(self) -> None:
        value = self.swappiness_slider.value()
        if self.memory_tuner.set_swappiness(value):
            self.statusBar().showMessage(f"Swappiness set to {value}", 2000)
        else:
            self.statusBar().showMessage("Failed to set swappiness", 2000)

    def clear_cache(self) -> None:
        if self.memory_tuner.clear_cache():
            self.statusBar().showMessage("Cleared cache", 2000)
        else:
            self.statusBar().showMessage("Failed to clear cache", 2000)

    def clean_temp_files(self) -> None:
        removed = self.disk_cleaner.clean_temp_files()
        self.statusBar().showMessage(f"Removed {len(removed)} temporary entries", 2000)

    def clean_package_cache(self) -> None:
        if self.disk_cleaner.clean_package_cache():
            self.statusBar().showMessage("Cleaned package cache", 2000)
        else:
            self.statusBar().showMessage("Failed to clean package cache", 2000)

    def refresh_recommendations(self) -> None:
        services = self.service_manager.list_services()
        recs = self.system_tuner.recommendations(services)
        self.recommendations_list.clear()
        for rec in recs:
            self.recommendations_list.addItem(rec)

    def apply_recommendations(self) -> None:
        services = self.service_manager.list_services()
        results = self.system_tuner.apply_recommendations(services)
        if results:
            self.statusBar().showMessage("; ".join(results), 4000)
        else:
            self.statusBar().showMessage("No recommendations applied", 2000)
        self.refresh_services()

    # ------------------ File management ------------------
    def _selected_file_paths(self) -> List[Path]:
        paths: List[Path] = []
        for idx in self.file_table.selectionModel().selectedRows():
            item = self.file_table.item(idx.row(), 0)
            if item:
                paths.append(Path(item.text()))
        return paths

    def delete_selected_files(self) -> None:
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
        }
        save_schedule_config(self.schedule_config, SCHEDULE_PATH)
        self._reset_schedule_timer()
        self.statusBar().showMessage("Schedule saved", 2000)

    def execute_scheduled_tasks(self) -> None:
        if self.schedule_config.get("auto_cleanup"):
            self.clean_temp_files()
        self.refresh_dashboard()
        ui_logger.info("Executed scheduled tasks")


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    if window.dark_mode_checkbox.isChecked():
        window.toggle_theme(QtCore.Qt.Checked)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
