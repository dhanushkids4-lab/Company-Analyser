#!/usr/bin/env python
import sys
import os

# Ensure package can be imported directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from company_analyzer.cli import main

if __name__ == "__main__":
    main()
