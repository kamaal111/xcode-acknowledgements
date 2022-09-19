import os
import sys
import json
import subprocess
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, TypedDict


def main():
    arguments = parse_arguments()

    packages_directory = get_packages_directory(scheme=arguments["scheme"])
    packages_licenses = get_packages_licenses(packages_directory=packages_directory)

    package_file_content = decode_package_file()
    packages = package_file_content_to_acknowledgments(
        package_file_content=package_file_content, packages_licenses=packages_licenses
    )
    acknowledgements = Acknowledgements(packages=packages)

    with open("acknowledgements.json", "w") as file:
        file.write(acknowledgements.to_json(indent=2))

    print("done writing acknowledgements ✨")


def parse_arguments():
    arguments: Arguments = {}

    skip_next_value = False
    for index, arg in enumerate(sys.argv[1:]):
        if skip_next_value:
            skip_next_value = False
            continue

        def get_next_value():
            if index + 1 < len(sys.argv):
                nonlocal skip_next_value
                skip_next_value = True

                return sys.argv[index + 2]

        if arg == "--scheme" and (scheme := get_next_value()):
            arguments["scheme"] = scheme

    if arguments.get("scheme") is None:
        raise Exception("Please provide a scheme with the --scheme flag")

    return arguments


def get_path_from_root_ending_with(search_string: str) -> Optional[str]:
    current_work_directory = os.getcwd()
    root_files = os.listdir(current_work_directory)

    for file in root_files:
        if file.endswith(search_string):
            return file


def get_packages_licenses(packages_directory: str):
    licenses: Dict[str, str] = {}
    for root, _, files in os.walk(packages_directory):
        if "LICENSE" not in files:
            continue

        package_name = root.split("/")[-1]

        license_path = os.path.join(root, "LICENSE")
        with open(license_path, "r") as file:
            licenses[package_name] = file.read()

    return licenses


def package_file_content_to_acknowledgments(
    package_file_content: "PackageFileContent", packages_licenses: Dict[str, str]
):
    packages: List[AcknowledgementPackage] = []
    for pin in package_file_content["object"]["pins"]:
        package_name = pin["package"]
        url = pin["repositoryURL"]
        if url.endswith(".git"):
            url = url[:-4]

        try:
            author = url.split("/")[-2]
        except IndexError:
            pass

        acknowledgement = AcknowledgementPackage(
            name=package_name,
            url=url,
            author=author,
            license=packages_licenses.get(package_name),
        )
        packages.append(acknowledgement)

    return packages


def decode_package_file() -> "PackageFileContent":
    if workspace_path := get_path_from_root_ending_with(search_string=".xcworkspace"):
        path_string = f"{workspace_path}/xcshareddata/swiftpm/Package.resolved"
        with open(path_string, "r") as file:
            return json.loads(file.read())

    raise Exception("Workspace not found at root")


def get_packages_directory(scheme: str):
    if project_path := get_path_from_root_ending_with(search_string=".xcodeproj"):
        output = subprocess.getoutput(
            f"xcodebuild -project {project_path} -target {scheme} -showBuildSettings"
        )

        output_search_line = "    BUILD_DIR = "
        for line in output.splitlines():
            if output_search_line in line:
                return line.replace(output_search_line, "").replace(
                    "Build/Products", "SourcePackages/checkouts"
                )
    else:
        raise Exception("Project not found at root")

    raise Exception("Build directory not found")


@dataclass
class Acknowledgements:
    packages: List["AcknowledgementPackage"]

    def to_dict(self):
        dictionary_to_return = {}
        for key, value in asdict(self).items():
            dictionary_to_return[key] = value
        return dictionary_to_return

    def to_json(self, indent: Optional[int] = None):
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class AcknowledgementPackage:
    name: str
    url: str
    author: Optional[str]
    license: Optional[str]


class Arguments(TypedDict):
    scheme: Optional[str]


class PackageFileContentObjectPinState(TypedDict):
    branch: Optional[str]
    revision: str
    version: Optional[str]


class PackageFileContentObjectPin(TypedDict):
    package: str
    repositoryURL: str
    state: PackageFileContentObjectPinState


class PackageFileContentObject(TypedDict):
    pins: List[PackageFileContentObjectPin]


class PackageFileContent(TypedDict):
    version: int
    object: PackageFileContentObject


main()
