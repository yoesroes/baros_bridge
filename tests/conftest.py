"""
Konfigurasi pytest: tambahkan root repo ke sys.path agar `import core` dan
`import project` bekerja bila pytest dijalankan dari direktori mana pun
(tests/ tidak berisi __init__.py). Tidak ada fixture di sini.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
