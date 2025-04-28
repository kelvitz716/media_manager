#!/usr/bin/env python3
"""
main.py - Main entry point for the Media Manager application.

This script launches and manages the Telegram Downloader and File Watcher
as separate processes. It handles graceful shutdown on receiving signals
like Ctrl+C (SIGINT) or SIGTERM.
"""

import subprocess
import time
import signal
import sys
import os
import logging

# Assume common modules are available in the 'common' directory
# In a real setup, you might need to adjust sys.path or use package structure
try:
    # If running from the root media_manager directory
    from common.logger_setup import setup_logging
    from common.config_manager import ConfigManager # Assuming ConfigManager is in common
except ImportError:
    # If running main.py directly, adjust path (less ideal for production)
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from common.logger_setup import setup_logging
        from common.config_manager import ConfigManager
    except ImportError as e:
        print(f"Error importing common modules: {e}")
        print("Please ensure main.py is run from the project root or adjust PYTHONPATH.")
        sys.exit(1)

# --- Configuration ---
CONFIG_FILE = "config.json"
PYTHON_EXECUTABLE = sys.executable # Use the same python interpreter that runs main.py

# --- Global Variables ---
downloader_process = None
watcher_process = None
shutting_down = False
logger = None # Global logger instance

# --- Signal Handling ---
def signal_handler(signum, frame):
    """Handles SIGINT and SIGTERM signals for graceful shutdown."""
    global shutting_down, logger
    if shutting_down:
        # Already handling shutdown, maybe force exit if called again?
        if logger:
            logger.warning("Shutdown already in progress. Force exiting if needed.")
        return
    shutting_down = True

    signal_name = signal.Signals(signum).name
    if logger:
        logger.info(f"Received signal {signal_name} ({signum}). Initiating shutdown...")
    else:
        print(f"\nReceived signal {signal_name} ({signum}). Initiating shutdown...")

    # Terminate child processes gracefully
    terminate_process(downloader_process, "Downloader")
    terminate_process(watcher_process, "Watcher")

    # Wait for processes to exit (optional, with timeout)
    wait_for_processes(timeout=10)

    if logger:
        logger.info("Media Manager shutdown complete.")
    else:
        print("Media Manager shutdown complete.")
    sys.exit(0) # Exit cleanly

def terminate_process(process, name):
    """Sends SIGTERM to a process."""
    global logger
    if process and process.poll() is None: # Check if process exists and is running
        if logger:
            logger.info(f"Sending SIGTERM to {name} process (PID: {process.pid})...")
        else:
            print(f"Sending SIGTERM to {name} process (PID: {process.pid})...")
        try:
            # On Windows, terminate() is equivalent to TerminateProcess()
            # On Unix, it sends SIGTERM
            process.terminate()
        except ProcessLookupError:
             if logger:
                logger.warning(f"{name} process (PID: {process.pid}) not found.")
             else:
                 print(f"{name} process (PID: {process.pid}) not found.")
        except Exception as e:
            if logger:
                logger.error(f"Error terminating {name} process: {e}")
            else:
                print(f"Error terminating {name} process: {e}")

def wait_for_processes(timeout=10):
    """Waits for child processes to exit with a timeout."""
    global logger
    processes = [p for p in [downloader_process, watcher_process] if p]
    start_time = time.time()

    for process in processes:
        if process.poll() is None: # If still running
            try:
                remaining_time = max(0, timeout - (time.time() - start_time))
                process.wait(timeout=remaining_time)
                if logger:
                    logger.info(f"Process {process.pid} exited.")
                else:
                    print(f"Process {process.pid} exited.")
            except subprocess.TimeoutExpired:
                if logger:
                    logger.warning(f"Process {process.pid} did not exit within {timeout}s. Killing...")
                else:
                    print(f"Process {process.pid} did not exit within {timeout}s. Killing...")
                process.kill() # Force kill if timeout expires
            except Exception as e:
                 if logger:
                    logger.error(f"Error waiting for process {process.pid}: {e}")
                 else:
                    print(f"Error waiting for process {process.pid}: {e}")


# --- Main Application Logic ---
def run_manager():
    """Loads config, sets up logging, and launches child processes."""
    global downloader_process, watcher_process, logger

    print("--- Media Manager Starting ---")

    # 1. Load Configuration
    try:
        config_manager = ConfigManager(CONFIG_FILE)
        config = config_manager.config # Get the loaded config dictionary
        print("Configuration loaded successfully.")
    except FileNotFoundError:
        print(f"ERROR: Configuration file '{CONFIG_FILE}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        sys.exit(1)

    # 2. Setup Logging
    # Note: Child processes will also call this, but setting it up here
    # allows the main manager process to log as well.
    try:
        setup_logging(config)
        logger = logging.getLogger("MediaManagerMain")
        logger.info("Logging configured.")
    except Exception as e:
        print(f"ERROR: Failed to set up logging: {e}")
        # Continue without logging for the main process if setup fails
        logger = None

    # 3. Define script paths (relative to this main.py)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    downloader_script = os.path.join(base_dir, "downloader", "run_downloader.py")
    watcher_script = os.path.join(base_dir, "watcher", "run_watcher.py")

    # Check if scripts exist
    if not os.path.exists(downloader_script):
        message = f"ERROR: Downloader script not found at {downloader_script}"
        if logger: logger.critical(message)
        else: print(message)
        sys.exit(1)
    if not os.path.exists(watcher_script):
        message = f"ERROR: Watcher script not found at {watcher_script}"
        if logger: logger.critical(message)
        else: print(message)
        sys.exit(1)

    # 4. Register Signal Handlers
    signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Handle termination signals

    if logger:
        logger.info("Signal handlers registered.")
    else:
        print("Signal handlers registered.")

    # 5. Launch Child Processes
    try:
        if logger: logger.info(f"Launching Downloader: {PYTHON_EXECUTABLE} {downloader_script}")
        else: print(f"Launching Downloader: {PYTHON_EXECUTABLE} {downloader_script}")
        # Use Popen for non-blocking execution.
        # Capture stdout/stderr if needed for logging or debugging:
        # stdout=subprocess.PIPE, stderr=subprocess.PIPE
        downloader_process = subprocess.Popen([PYTHON_EXECUTABLE, downloader_script])
        if logger: logger.info(f"Downloader process started with PID: {downloader_process.pid}")
        else: print(f"Downloader process started with PID: {downloader_process.pid}")

        # Add a small delay between starting processes (optional)
        time.sleep(1)

        if logger: logger.info(f"Launching Watcher: {PYTHON_EXECUTABLE} {watcher_script}")
        else: print(f"Launching Watcher: {PYTHON_EXECUTABLE} {watcher_script}")
        watcher_process = subprocess.Popen([PYTHON_EXECUTABLE, watcher_script])
        if logger: logger.info(f"Watcher process started with PID: {watcher_process.pid}")
        else: print(f"Watcher process started with PID: {watcher_process.pid}")

    except Exception as e:
        message = f"ERROR: Failed to launch child process: {e}"
        if logger: logger.critical(message)
        else: print(message)
        # Attempt to clean up any process that might have started
        terminate_process(downloader_process, "Downloader")
        terminate_process(watcher_process, "Watcher")
        sys.exit(1)

    # 6. Monitor Processes (Main Loop)
    if logger: logger.info("Media Manager running. Monitoring child processes...")
    else: print("\nMedia Manager running. Monitoring child processes... (Press Ctrl+C to exit)")

    while not shutting_down:
        try:
            # Check downloader status
            if downloader_process and downloader_process.poll() is not None:
                retcode = downloader_process.returncode
                message = f"Downloader process (PID: {downloader_process.pid}) exited unexpectedly with code {retcode}. Shutting down."
                if logger: logger.error(message)
                else: print(message)
                signal_handler(signal.SIGTERM, None) # Trigger shutdown

            # Check watcher status
            if watcher_process and watcher_process.poll() is not None:
                retcode = watcher_process.returncode
                message = f"Watcher process (PID: {watcher_process.pid}) exited unexpectedly with code {retcode}. Shutting down."
                if logger: logger.error(message)
                else: print(message)
                signal_handler(signal.SIGTERM, None) # Trigger shutdown

            # Sleep briefly to avoid busy-waiting
            time.sleep(1)

        except KeyboardInterrupt:
            # This might be caught if the signal handler hasn't fully executed yet
            # The signal handler should take precedence.
            if not shutting_down:
                 signal_handler(signal.SIGINT, None)
            time.sleep(0.1) # Short sleep to allow handler to run
        except Exception as e:
            # Log unexpected errors in the monitoring loop
            if logger: logger.error(f"Error in monitoring loop: {e}")
            else: print(f"Error in monitoring loop: {e}")
            # Consider if shutdown is needed on monitoring errors
            if not shutting_down:
                signal_handler(signal.SIGTERM, None)


# --- Script Entry Point ---
if __name__ == "__main__":
    run_manager()
