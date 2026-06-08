"""Launch the stats dashboard at http://127.0.0.1:8787"""

from tjrbot.dashboard.app import create_app

if __name__ == "__main__":
    print("Dashboard running at http://127.0.0.1:8787  (Ctrl-C to stop)")
    create_app().run(host="127.0.0.1", port=8787, debug=False)
