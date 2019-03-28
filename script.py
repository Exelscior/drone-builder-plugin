#!/usr/local/bin/python

import re
import sys
import hashlib
import subprocess
from os import getenv, system
from typing import Any
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


def convert_to_iterable(arg: Any, split: str = ",") -> tuple:
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
        self.image_hash = self.get_files_hash()

    @property
    def pull_tag(self) -> str:
        return self.force_tag or self.image_hash

    @property
    def full_repository(self) -> str:
        if self.registry == "docker.io" or self.registry in self.repository:
            return self.repository
        return f"{self.registry}/{self.repository}"

    def get_hash(self, file: Path) -> str:
        if self.debug:
            print(f"get_hash : {file}")
        return hashlib.sha256(file.read_bytes()).hexdigest()

    def run_cmd(
            self, command: str,
            expected_returncode: int = 0, no_raise: bool = False,
            capture_output: bool = True
    ) -> int:
        if self.debug:
            print(f"current path: {Path().absolute().as_posix()}")
            print(f"run_cmd: {command}")
        if command and command[0] in ("'", '"'):
            command = command.strip('"\'')
        command_as_list = [elem for elem in command.split(' ') if elem]
        response = subprocess.run(command_as_list, capture_output=capture_output)
        if self.debug:
            if capture_output:
                print(f"stdout: '{response.stdout.decode('utf8')}'")
                print(f"stderr: '{response.stderr.decode('utf8')}'")
            print(f"returncode: {response.returncode}")
            print(f"expected_returncode: {expected_returncode}")
        if not no_raise and response.returncode != expected_returncode:
            raise SystemError(response.stdout.decode("utf8").strip("\n").split("\n")[-1])
        return response.returncode

    def resolve_from_env(self, string: str) -> str:
        new_string = string
        if new_string and new_string[0] in ("'", '"') and new_string[0] == new_string[-1]:
            new_string = new_string.strip(new_string[0])
        match = True
        while match:
            match = re.match(ManagementUtility.RESOLVE_REGEX, new_string)
            if match:
                for group in match.groups():
                    if hasattr(self, group.lower()):
                        resolved_value = getattr(self, group.lower())
                    else:
                        resolved_value = getenv(group, "None")
                    new_string = new_string.replace(f"%{group}%", resolved_value)
        if self.debug and new_string != string:
            print(f"resolved string from '{string}' to '{new_string}'")
        return new_string

    def docker_login(self):
        self.run_cmd(f"docker login -u {self.username} -p {self.password} {self.registry}")

    def docker_pull_image(self) -> int:
        return self.run_cmd(f"docker pull {self.full_repository}:{self.pull_tag}", no_raise=True)

    def docker_build_image(self):
        parsed_build_args = list()
        if self.build_args:
            for arg in self.build_args:
                parsed_build_args.append(f"--build-arg {self.resolve_from_env(arg)}")
        all_tags = [f"-t {self.full_repository}:{self.pull_tag}"]
        for tag in self.tags:
            all_tags.append(f"-t {self.full_repository}:{self.resolve_from_env(tag)}")
        self.run_cmd(
            "docker build --no-cache "
            f"{' '.join(parsed_build_args)} {' '.join(all_tags)} "
            f"-f {self.dockerfile} {self.context}",
            no_raise=True,
            capture_output=False,
        )

    def docker_push_all_tags(self):
        self.run_cmd(f"docker push {self.full_repository}:{self.pull_tag}")
        for tag in self.tags:
            self.run_cmd(f"docker push {self.full_repository}:{self.resolve_from_env(tag)}")

    def get_files_hash(self, split: int = 7) -> str:
        if not self.files_to_hash:
            return self.commit_id
        full_hash = ""
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
        if pull_response == 0:
            print("Image already exists and has been pulled.")
            for cmd in self.commands:
                self.run_cmd(self.resolve_from_env(cmd))
            return 0
        if self.debug:
            self.run_cmd("docker images", capture_output=False)
        print(f"Image '{self.repository}:{self.pull_tag}' not found. Building..")
        self.docker_build_image()
        print("Image built.")
        if self.push_tags:
            print(f"Pushing all tags for image '{self.repository}'")
            self.docker_push_all_tags()
        for cmd in self.commands:
            self.run_cmd(self.resolve_from_env(cmd))
        return 0


if __name__ == "__main__":
    main = ManagementUtility()
    try:
        ret = main.execute()
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        ret = 1
    raise SystemExit(ret)
