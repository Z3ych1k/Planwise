"""Launch the Planwise coursework demo on this computer."""

import argparse
from pathlib import Path

from nas.application import create_app


DEMO_DATABASE = Path(__file__).resolve().parent / "data" / "planwise-demo.sqlite3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    app = create_app({
        "DATABASE": str(DEMO_DATABASE),
        "COOKIE_SECURE": False,
        "PUBLIC_ORIGIN": "",
        "TRUSTED_PROXY_IPS": "",
    })
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
