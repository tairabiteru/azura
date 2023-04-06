import os
import pathlib
import sys

if __name__ == "__main__":
    os.chdir(pathlib.Path(__file__).parent.resolve())
    os.system(f"python3.11 azura/ {' '.join(sys.argv[1:])}")
