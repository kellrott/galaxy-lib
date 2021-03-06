import fnmatch
import glob
import os
import re
from ..tools import loader

import yaml

from galaxy.util import checkers

import sys

import logging
log = logging.getLogger(__name__)

PATH_DOES_NOT_EXIST_ERROR = "Could not load tools from path [%s] - this path does not exist."
PATH_AND_RECURSIVE_ERROR = "Cannot specify a single file and recursive."
LOAD_FAILURE_ERROR = "Failed to load tool with path %s."
TOOL_LOAD_ERROR = object()
TOOL_REGEX = re.compile(r"<tool\s")


def load_exception_handler(path, exc_info):
    log.warn(LOAD_FAILURE_ERROR % path, exc_info=exc_info)


def load_tool_elements_from_path(
    path,
    load_exception_handler=load_exception_handler,
    recursive=False,
    register_load_errors=False,
):
    tool_elements = []
    for file in __find_tool_files(path, recursive=recursive):
        try:
            does_look_like_a_tool = looks_like_a_tool(file)
        except IOError:
            # Some problem reading the tool file, skip.
            continue

        if does_look_like_a_tool:
            try:
                tool_elements.append((file, loader.load_tool(file)))
            except Exception:
                exc_info = sys.exc_info()
                load_exception_handler(file, exc_info)
                if register_load_errors:
                    tool_elements.append((file, TOOL_LOAD_ERROR))
    return tool_elements


def is_tool_load_error(obj):
    return obj is TOOL_LOAD_ERROR


def looks_like_a_tool(path, invalid_names=[], enable_beta_formats=False):
    """ Whether true in a strict sense or not, lets say the intention and
    purpose of this procedure is to serve as a filter - all valid tools must
    "looks_like_a_tool" but not everything that looks like a tool is actually
    a valid tool.

    invalid_names may be supplid in the context of the tool shed to quickly
    rule common tool shed XML files.
    """
    looks = False

    if os.path.basename(path) in invalid_names:
        return False

    if looks_like_a_tool_xml(path):
        looks = True

    if not looks and enable_beta_formats:
        for tool_checker in BETA_TOOL_CHECKERS.values():
            if tool_checker(path):
                looks = True
                break

    return looks


def looks_like_a_tool_xml(path):
    full_path = os.path.abspath(path)

    if not full_path.endswith(".xml"):
        return False

    if not os.path.getsize(full_path):
        return False

    if(checkers.check_binary(full_path) or
       checkers.check_image(full_path) or
       checkers.check_gzip(full_path)[0] or
       checkers.check_bz2(full_path)[0] or
       checkers.check_zip(full_path)):
        return False

    with open(path, "r") as f:
        start_contents = f.read(5 * 1024)
        if TOOL_REGEX.search(start_contents):
            return True

    return False


def looks_like_a_tool_yaml(path):
    if not path.endswith(".yml") and not path.endswith(".json"):
        return False

    with open(path, "r") as f:
        try:
            as_dict = yaml.safe_load(f)
        except Exception:
            return False

    if not isinstance(as_dict, dict):
        return False

    file_class = as_dict.get("class", None)
    return file_class == "GalaxyTool"


def __find_tool_files(path, recursive):
    is_file = not os.path.isdir(path)
    if not os.path.exists(path):
        raise Exception(PATH_DOES_NOT_EXIST_ERROR)
    elif is_file and recursive:
        raise Exception(PATH_AND_RECURSIVE_ERROR)
    elif is_file:
        return [os.path.abspath(path)]
    else:
        if not recursive:
            files = glob.glob(path + "/*.xml")
        else:
            files = _find_files(path, "*.xml")
        return map(os.path.abspath, files)


def _find_files(directory, pattern='*'):
    if not os.path.exists(directory):
        raise ValueError("Directory not found {}".format(directory))

    matches = []
    for root, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            if fnmatch.filter([full_path], pattern):
                matches.append(os.path.join(root, filename))
    return matches


BETA_TOOL_CHECKERS = {
    'yaml': looks_like_a_tool_yaml,
}
