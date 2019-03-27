#!/usr/local/bin/python

import re
import sys
import hashlib
import subprocess
from os import getenv
from typing import Any, Tuple
from pathlib import Path


def convert_to_bool(arg: Any):
    if isinstance(arg, (bool, int)):
        return bool(arg)
    if not arg:
        return False
    arg = arg.strip().lower()
    if arg in ("false", "no"):
        return False
    return True


def convert_to_iterable(arg: Any[str, list, tuple], split: str = ",") -> Tuple[str]:
    if isinstance(arg, (list, tuple)):
        return arg
    if not arg or not isinstance(arg, str):
        return tuple()
    arg = arg.strip(f' \n\t\r{split}').split(split)
    return arg


class ManagementUtility(object):
    RESOLVE_REGEX = r'.*%(.*?)%.*'

    def __init__(self):
        self.context = getenv("PLUGIN_CONTEXT", ".")
        self.debug = convert_to_bool(getenv("PLUGIN_DEBUG", False))
        self.push_tags = convert_to_bool(getenv("PLUGIN_PUSHTAGS", True))
        self.commit_tag = convert_to_bool(getenv("PLUGIN_COMMITTAG", True))
        self.tags = convert_to_iterable(getenv("PLUGIN_TAGS", []))
        self.files_to_hash = convert_to_iterable(getenv("PLUGIN_FILES", []))
        self.commands = convert_to_iterable(getenv("PLUGIN_COMMANDS", []))
        self.build_args = convert_to_iterable(getenv("PLUGIN_ARGS", []))
        self.commit_id = getenv("DRONE_COMMIT_AFTER")
        self.commit_branch = getenv("DRONE_BRANCH")
        self.login = convert_to_bool(getenv("PLUGIN_LOGIN", False))
        self.username = getenv("PLUGIN_USERNAME", "")
        self.password = getenv("PLUGIN_PASSWORD", "")
        self.repository = getenv("PLUGIN_REPO")
        self.registry = getenv("PLUGIN_REGISTRY", "docker.io")
        self.dockerfile = Path(getenv("PLUGIN_DOCKERFILE", ""))
        self.force_tag = getenv("PLUGIN_FORCETAG")
        self.image_hash = self.force_tag or self.get_files_hash()

    @property
    def full_repository(self):
        if self.registry == "docker.io" or self.registry in self.repository:
            return self.repository
        return f"{self.registry}/{self.repository}"

    def get_hash(self, file: Path):
        if self.debug:
            print(f"get_hash : {file}")
        return hashlib.sha256(file.read_bytes()).hexdigest()

    def run_cmd(self, command):
        if self.debug:
            print(f"run_cmd : {command}")
        if command and command[0] in ("'", '"'):
            command = command.strip('"\'')
        command_as_list = command.split(' ')
        response = subprocess.run(command_as_list, capture_output=True)
        return response.returncode

    def resolve_from_env(self, string: str):
        new_string = string
        match = re.match(ManagementUtility.RESOLVE_REGEX, new_string)
        if match:
            for group in match.groups():
                if hasattr(self, group.lower()):
                    resolved_value = getattr(self, group.upper())
                else:
                    resolved_value = getenv(group, "None")
                new_string = new_string.replace(f"%{group}%", resolved_value)
            if self.debug:
                print(f"resolved string from '{string}' to '{new_string}'")
        return new_string

    def docker_login(self):
        return self.run_cmd(f"docker login -u {self.username} -p {self.password} {self.registry}")

    def docker_pull_image(self):
        return self.run_cmd(f"docker pull {self.full_repository}:{self.image_hash}")

    def docker_build_image(self):
        parsed_build_args = list()
        if self.build_args:
            for arg in self.build_args:
                parsed_build_args.append(f"--build-arg {self.resolve_from_env(arg)}")
        all_tags = [f"-t {self.repository}:{self.image_hash}"]
        for tag in self.tags:
            all_tags.append(f"-t {self.full_repository}:{self.resolve_from_env(tag)}")
        return self.run_cmd(
            "docker build --no-cache --force-rm "
            f"{' '.join(parsed_build_args)} {' '.join(all_tags)} "
            f"-f {self.dockerfile} {self.context}"
        )

    def docker_push_all_tags(self):
        resp = self.run_cmd(f"docker push {self.full_repository}:{self.image_hash}")
        for tag in self.tags:
            resp += self.run_cmd(f"docker push {self.full_repository}:{self.resolve_from_env(tag)}")
        return resp

    def get_files_hash(self, split: int = 7):
        if not self.files_to_hash:
            return self.commit_id
        full_hash = self.get_hash(self.dockerfile)[:split]
        for path in self.files_to_hash:
            file = Path(path)
            full_hash += self.get_hash(file)[:split]
        if self.debug:
            print(f"get_full_hash : {full_hash}")
        return full_hash

    def execute(self):
        if self.login:
            self.docker_login()
        pull_response = self.docker_pull_image()
        if not pull_response:
            for cmd in self.commands:
                self.run_cmd(self.resolve_from_env(cmd))
            return 0
        print(f"Image '{self.repository}:{self.image_hash}' not found. Building..")
        self.docker_build_image()
        if self.push_tags:
            print(f"Pushing all tags for image '{self.repository}'")
            self.docker_push_all_tags()
        for cmd in self.commands:
            self.run_cmd(self.resolve_from_env(cmd))
        return 0


if __name__ == "__main__":
    command = ManagementUtility()
    try:
        ret = command.execute()
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        ret = 1
    raise SystemExit(ret)
