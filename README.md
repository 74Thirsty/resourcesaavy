# System Optimizer

System Optimizer is a PyQt5 desktop application that monitors system resources, manages services, and helps keep your machine tidy. It provides a dashboard for CPU, memory, disk, and network activity, tools for tuning and cleaning the system, and utilities for browsing logs and generating performance reports.

## Features

- Real-time CPU, memory, disk, and network monitoring with charts and tables.
- Service management for starting, stopping, enabling, or disabling systemd services.
- CPU governor selection, swappiness tuning, and cache clearing controls.
- Disk cleanup helpers for temporary files, package caches, and large-file discovery.
- File search utilities to locate files by name, extension, and size.
- Log viewer with export and clear functions, plus performance report generation.
- Optional dark mode, automatic cleanup scheduling, and notifications for high resource usage.

## Requirements

- Python 3.11
- PyQt5
- psutil

Additional features rely on optional tools such as `systemd`, `apt`, and `journalctl` when available on the system.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py
```

## Notes

Administrative privileges may be required for some optimization tasks (service management, cache cleaning, CPU governor changes). The application logs actions using the format `{timestamp} - {log_level} - {component} - {message}`.
