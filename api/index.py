import os
import sys

# Ensure current directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Expose handler for Vercel serverless function
app.debug = False
