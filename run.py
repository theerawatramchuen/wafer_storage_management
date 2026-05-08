#!/usr/bin/env python3
"""
Wafer Box Storage Management System
Run this file to start the web server.

Usage:
  python run.py              → http://localhost:5050
  python run.py --port 8080  → http://localhost:8080
"""

import sys
import os

# Add app directory to path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from app import app

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5050)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    print(f"\n{'='*50}")
    print(f"  Wafer Storage Management System")
    print(f"  Open: http://localhost:{args.port}")
    print(f"{'='*50}\n")
    app.run(debug=False, port=args.port, host=args.host)
