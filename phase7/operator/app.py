"""Main application entry point for Phase 7 Offline Operator Application.

Milestone 4.12: Unified launcher that activates network quarantine, acquires
single-instance lock, and launches either the standard-library CLI/TUI or Tkinter GUI.
"""

import argparse
import sys
import tkinter as tk
from typing import List, Optional

from phase7.operator.constants import MANDATORY_BANNERS
from phase7.operator.network_quarantine import NetworkQuarantineManager
from phase7.operator.single_instance import (
    SingleInstanceLock,
    SingleInstanceLockError,
)
from phase7.operator.cli import OperatorCLI, print_banner_header
from phase7.operator.core import OperatorCore
from phase7.operator.gui import OperatorGUI


def run_operator_application(argv: Optional[List[str]] = None) -> int:
    """Launch operator application with network quarantine and single-instance locking."""
    parser = argparse.ArgumentParser(
        description="Phase 7 Internal Offline Operator Application [Milestone 4.12]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Mandatory Banners:\n" + "\n".join(f" - {b}" for b in MANDATORY_BANNERS),
    )
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter desktop GUI")
    parser.add_argument("--screen", type=int, choices=range(1, 11), default=1, help="Screen number to display in CLI (1-10)")
    parser.add_argument("--all", action="store_true", help="Display all 10 screens in CLI")
    parser.add_argument("--demo", action="store_true", help="Execute Synthetic Demonstration Mode (Screen 10)")
    parser.add_argument("--export", action="store_true", help="Generate Metadata-Only Audit Export (Screen 9)")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI text menu")
    args = parser.parse_args(argv)

    # 1. Activate Network Quarantine (Zero outbound sockets/HTTP)
    quarantine = NetworkQuarantineManager()
    quarantine.activate()

    # 2. Acquire Single-Instance Lock
    lock = SingleInstanceLock()
    try:
        lock.acquire()
    except SingleInstanceLockError as e:
        quarantine.deactivate()
        sys.stderr.write(f"ERROR: {e}\n")
        return 1

    try:
        core = OperatorCore()

        if args.gui:
            # Launch Tkinter GUI
            root = tk.Tk()
            gui = OperatorGUI(root, core=core)
            root.mainloop()
            return 0
        else:
            # Launch CLI
            cli = OperatorCLI(core=core)
            if args.demo:
                print(cli.render_screen(10))
            elif args.export:
                print(cli.render_screen(9))
            elif args.all:
                for s in range(1, 11):
                    print(cli.render_screen(s))
                    print("\n")
            elif args.interactive:
                while True:
                    print_banner_header()
                    print("Select Screen to View (1-10) or 'q' to quit:")
                    print(" 1. Readiness Dashboard       2. Evidence Inventory")
                    print(" 3. Manifest Verifier         4. Batch-State Viewer")
                    print(" 5. Operational-Drill Viewer  6. Backup and Restore Verifier")
                    print(" 7. Governance & Blockers     8. Authorization Registry")
                    print(" 9. Metadata Audit Export    10. Synthetic Demonstration")
                    try:
                        choice = input("Enter selection [1-10, q]: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        break
                    if choice.lower() in ("q", "quit", "exit"):
                        break
                    try:
                        sn = int(choice)
                        if 1 <= sn <= 10:
                            print(cli.render_screen(sn))
                        else:
                            print("Invalid selection. Must be 1 to 10.")
                    except ValueError:
                        print("Invalid input.")
                    try:
                        input("\nPress Enter to return to menu...")
                    except (EOFError, KeyboardInterrupt):
                        break
            else:
                print(cli.render_screen(args.screen))
            return 0

    finally:
        lock.release()
        quarantine.deactivate()


def main() -> None:
    sys.exit(run_operator_application())


if __name__ == "__main__":
    main()
