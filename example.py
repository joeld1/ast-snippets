import sys
from pathlib import Path

from ast_snippets import PyFileMutator

if __name__ == "__main__":
    src_filepath = Path("file_to_get_code_from.py")
    classes_to_get = ["ThisAwesomeClass"]
    objs_to_get = PyFileMutator.get_code_from_module(src_filepath, classes_to_get, "classes")
    print("done")
    sys.exit()
