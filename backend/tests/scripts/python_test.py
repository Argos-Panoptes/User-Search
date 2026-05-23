
import os

path = r"d:\auto-backup\colin\projects\user-search\user-search-code-here\test_output.txt"
try:
    with open(path, 'w') as f:
        f.write("Python is running!")
except Exception as e:
    pass
