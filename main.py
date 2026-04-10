"""Application entry point."""

from __future__ import annotations

from b8085.ui import EmulatorApp


def main() -> None:
    app = EmulatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()

