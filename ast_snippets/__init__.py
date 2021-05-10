import ast
import inspect
import time
from ast import AST
from itertools import chain
from os import PathLike
from pathlib import Path
from typing import Optional
from collections import deque

import attr


def get_timestamp_for_new_file(full_datetime=False):
    """This method returns the current datetime timestamp as a str.

    :param full_datetime: A flag to determine if we want to return the full datetime str %Y%m%d-%H%M%S.
    :type full_datetime: bool
    :returns: A datetime timestamp
    :rtype: str
    """
    if full_datetime:
        return time.strftime("%Y%m%d-%H%M%S")
    else:
        return time.strftime("%Y%m%d")


def get_filepath_to_new_file(path: str) -> Path:
    path_to_pdf = Path(path)
    fname = path_to_pdf.stem
    fname_ext = path_to_pdf.suffix
    ts = get_timestamp_for_new_file(True)
    new_name = f"{ts} - {fname}{fname_ext}"
    if not path_to_pdf.parent.exists():
        try:
            path_to_pdf.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(e)
    new_path = path_to_pdf.with_name(new_name)
    return new_path


class ASTExtractor:
    """
    See
    https://docs.python.org/3/library/ast.html
    and
    https://docs.python.org/3/library/inspect.html
    for definitions!
    """

    @staticmethod
    def parse_py_script(fp):
        with open(fp, 'r', encoding="utf-8") as f:
            text = f.read()
        p = ast.parse(text)
        return p

    @staticmethod
    def get_node_name_and_location(ast_obj, ast_type):
        class_type = getattr(ast, ast_type, None)
        if not class_type:
            print("Not a valid ast type!")
            raise Exception
        # visitor = ast.NodeVisitor()
        node_info = {}
        for node in ast.walk(ast_obj):
            if isinstance(node, class_type):
                node_name = getattr(node, "name", None)
                if not (node_name is None):
                    starting_line = node.lineno
                    ending_line = node.end_lineno
                    unparsed_tree = ast.unparse(node)
                    node_info[(node_name, starting_line, ending_line)] = unparsed_tree
                else:
                    unparsed_tree = ast.unparse(node)
                    first_line = unparsed_tree.splitlines()[0]
                    if ("__name__" in first_line) or ("__main__" in first_line):
                        node_name = "__name__ == __main__"
                        starting_line = node.lineno
                        ending_line = node.end_lineno
                        node_info[(node_name, starting_line, ending_line)] = unparsed_tree
        return node_info

    @staticmethod
    def extract_classes(ast_obj: AST):
        ast_type = "ClassDef"
        node_info = ASTExtractor.get_node_name_and_location(ast_obj, ast_type)
        return node_info

    @staticmethod
    def extract_methods(ast_obj: AST):
        ast_type = "FunctionDef"
        node_info = ASTExtractor.get_node_name_and_location(ast_obj, ast_type)
        return node_info

    @staticmethod
    def extract_if_equals_main_statement(ast_obj: AST):
        ast_type = "If"
        node_info = ASTExtractor.get_node_name_and_location(ast_obj, ast_type)
        # TODO: Refactor later
        return node_info


@attr.s
class PyFile(ASTExtractor):
    filepath = attr.ib(type=PathLike, init=True)
    classes = attr.ib(default=None)
    methods = attr.ib(default=None)
    methods_not_found_in_classes = attr.ib(default=None)
    if_statements = attr.ib(default=None)
    lines_of_code = attr.ib(default="")

    @staticmethod
    def get_orig_lines_per_obj_found(py_file_obj_dict, src_lines_of_text):
        new_dict = {}
        for k, v in py_file_obj_dict.items():
            obj_name, lineno, endlineno = k
            lines_to_get = "".join(src_lines_of_text[lineno - 1:endlineno].copy())
            new_dict[k] = lines_to_get
        return new_dict

    @staticmethod
    def get_source(obj_to_lookup):
        source_lines = inspect.getsource(obj_to_lookup)
        return source_lines

    def __attrs_post_init__(self):
        ast_obj = self.parse_py_script(self.filepath)
        classes_found = self.extract_classes(ast_obj)
        lines_belonging_to_classes = list(chain(*[list(range(k[1], k[2] + 1)) for k, v in classes_found.items()]))

        all_methods_found = self.extract_methods(ast_obj)
        methods_not_found_in_classes = {k: v for k, v in all_methods_found.items() if
                                        (k[1] not in lines_belonging_to_classes)}

        if_statements = self.extract_if_equals_main_statement(ast_obj)
        with open(self.filepath, 'r', encoding="utf-8") as f:
            lines_of_code = f.readlines()
        self.lines_of_code = lines_of_code

        self.classes = PyFile.get_orig_lines_per_obj_found(classes_found, lines_of_code)
        self.methods = PyFile.get_orig_lines_per_obj_found(all_methods_found, lines_of_code)
        self.methods_not_found_in_classes = PyFile.get_orig_lines_per_obj_found(methods_not_found_in_classes,
                                                                                lines_of_code)
        self.if_statements = PyFile.get_orig_lines_per_obj_found(if_statements, lines_of_code)


@attr.s
class PyFileMutator:

    @staticmethod
    def get_lines_after_filtering(py_file_obj_dict, names_to_filter_by):
        filtered_objs = PyFileMutator.filter_by_first_key(py_file_obj_dict, names_to_filter_by)
        lines_code_found_in = list(chain(*[list(range(k[1], k[2] + 1)) for k in filtered_objs.keys()]))
        return lines_code_found_in

    @staticmethod
    def filter_by_first_key(py_file_obj_dict, names_to_filter_by):
        return {k: v for k, v in py_file_obj_dict.items() if (k[0] in names_to_filter_by)}

    @staticmethod
    def get_py_with_replacements_made(dest_filepath, dest_method_names, src_filepath, src_method_names,
                                      replacement_type):

        src_file = PyFile(src_filepath)
        src_file_objs_to_copy_from = getattr(src_file, replacement_type)

        dest_file = PyFile(dest_filepath)
        dest_file_obj_replacements = getattr(dest_file, replacement_type)
        dest_lines = dest_file.lines_of_code.copy()

        lines_w_obj_found_in_list_dest = PyFileMutator.get_lines_after_filtering(dest_file_obj_replacements,
                                                                                 dest_method_names)
        lines_w_obj_found_in_list_src = PyFileMutator.get_lines_after_filtering(dest_file_obj_replacements,
                                                                                src_method_names)
        lines_to_overwrite = sorted(
            list(set(lines_w_obj_found_in_list_dest).intersection(set(lines_w_obj_found_in_list_src))))
        try:
            assert lines_to_overwrite
        except Exception as e:
            print("There aren't any similar objects found!")
            raise Exception
        all_lines_to_write_back = deque()

        for i, l in enumerate(dest_lines):
            cur_line = i + 1
            if cur_line in lines_to_overwrite:
                key_to_occurance = [k for k in dest_file_obj_replacements.keys() if k[1] == cur_line]
                if key_to_occurance:
                    # start of replacement
                    key_to_occurance = key_to_occurance[0]
                    obj_name, _lineno, _endlineno = key_to_occurance
                    key_to_src_replacement = [k for k in src_file_objs_to_copy_from.keys() if k[0] == obj_name]
                    if key_to_src_replacement:
                        key_to_src_replacement = key_to_src_replacement[0]
                        src_replacement_val = src_file_objs_to_copy_from[key_to_src_replacement]
                        all_lines_to_write_back.append(src_replacement_val)
            else:
                all_lines_to_write_back.append(l)
        all_lines_to_write_back_str = "".join(all_lines_to_write_back)
        return all_lines_to_write_back_str

    @staticmethod
    def get_updated_code(src_filepath: PathLike = None, src_method_names=None,
                         dest_filepath: PathLike = __file__,
                         dest_method_names=None, replacement_type: str = "classes",
                         output_path: Optional[PathLike] = None):
        src_filepath, dest_filepath, output_path = PyFileMutator.verify_paths_and_objs_to_search_for(src_filepath,
                                                                                                     src_method_names,
                                                                                                     dest_filepath,
                                                                                                     dest_method_names,
                                                                                                     output_path)

        mutated_script = PyFileMutator.get_py_with_replacements_made(dest_filepath, dest_method_names, src_filepath,
                                                                     src_method_names, replacement_type)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(mutated_script)
        print(f"Successfully wrote to {output_path}")

    @staticmethod
    def get_code_from_module(src_filepath: PathLike = None, src_method_names=None, obj_type: str = "classes",
                             assume_unique: bool = True):
        assert src_filepath and src_method_names
        src_filepath = Path(src_filepath)
        assert src_filepath.exists()
        parsed_module = PyFile(filepath=src_filepath)
        dict_to_filter = getattr(parsed_module, obj_type, None)
        if dict_to_filter:
            module_objs_read = PyFileMutator.filter_by_first_key(dict_to_filter, src_method_names)
            return module_objs_read
        else:
            print(f"{obj_type} is not a PyFile type")
            raise Exception

    @staticmethod
    def verify_paths_and_objs_to_search_for(src_filepath, src_method_names, dest_filepath, dest_method_names,
                                            output_path: Optional[PathLike] = None):
        if src_filepath is None:
            print("Provide a source to read from")
            raise Exception
        if src_method_names is None:
            print("Provide methods to copy!")
            raise Exception
        src_filepath = Path(src_filepath)
        dest_filepath = Path(dest_filepath)
        if output_path is None:
            output_path = get_filepath_to_new_file(dest_filepath.as_posix())
        else:
            output_path = Path(output_path)
        assert src_filepath.exists() and dest_filepath.exists()
        if dest_method_names is None:
            print("Provide methods to overwrite!")
            raise Exception
        return src_filepath, dest_filepath, output_path
