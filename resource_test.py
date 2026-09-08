import csv
import time
from datetime import datetime
from pathlib import Path

import psutil


LOGGER_PID = 10448
INTERVAL = 2

OUTPUT = Path("resource_usage_test.csv")


def main():

    try:
        logger = psutil.Process(LOGGER_PID)

        print(f"Monitoring logger.py")
        print(f"PID: {LOGGER_PID}")
        print(f"Process: {logger.name()}")
        print()

    except psutil.NoSuchProcess:
        print(f"ERROR: Process {LOGGER_PID} was not found.")
        return

    print("Starting resource measurement...")
    print("Press Ctrl+C to stop.")
    print()

    # Prime CPU measurement
    logger.cpu_percent(interval=None)

    file_exists = OUTPUT.exists()

    with OUTPUT.open("a", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "Timestamp",
                "PID",
                "CPU_Percent",
                "Memory_MB",
                "Memory_Percent",
                "Threads"
            ])

        try:

            while True:

                try:

                    cpu = logger.cpu_percent(interval=None)

                    memory = logger.memory_info()
                    memory_mb = memory.rss / (1024 * 1024)

                    memory_percent = logger.memory_percent()

                    threads = logger.num_threads()

                    timestamp = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    writer.writerow([
                        timestamp,
                        LOGGER_PID,
                        round(cpu, 2),
                        round(memory_mb, 2),
                        round(memory_percent, 4),
                        threads
                    ])

                    file.flush()

                    print(
                        f"{timestamp} | "
                        f"CPU: {cpu:6.2f}% | "
                        f"RAM: {memory_mb:8.2f} MB | "
                        f"Threads: {threads}"
                    )

                    time.sleep(INTERVAL)

                except psutil.NoSuchProcess:
                    print("\nlogger.py has stopped.")
                    break

        except KeyboardInterrupt:
            print("\nResource measurement stopped.")


if __name__ == "__main__":
    main()