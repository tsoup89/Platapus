"""CLI entry point: python platapicker.py <command>"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.__main__ import cli

if __name__ == "__main__":
    cli()
