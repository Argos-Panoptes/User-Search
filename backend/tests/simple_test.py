import sys
import os


def simple_debug():
    with open("simple_python_test.txt", "w") as f:
        f.write(f"Python: {sys.version}\n")
        f.write(f"CWD: {os.getcwd()}\n")


if __name__ == "__main__":
    simple_debug()
