import os
import sys
import json
import subprocess
from pathlib import Path
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

    contributors_list = subprocess.getoutput(
        f'git log "--pretty=format:%an <%ae>"'
    ).splitlines()
    formatted_contributors = format_contributors(contributors_list=contributors_list)
    acknowledgements = Acknowledgements(
        packages=packages, contributors=formatted_contributors
    )

    with open(os.path.join(arguments["output"], "Acknowledgements.json"), "w") as file:
        file.write(acknowledgements.to_json(indent=2))

    print("done writing acknowledgements ✨")


def format_contributors(contributors_list: List[str]):
    """Returns formatted contributors

    >>> format_contributors({'John <john@email.com>', 'Kamaal <kamaal@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>'})
    [Contributor(name='John Smith', email=None, contributions=2), Contributor(name='Kamaal Farah', email=None, contributions=2)]

    >>> format_contributors({'John <john@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>', 'Kamaal <kamaal@email.com>'})
    [Contributor(name='John Smith', email=None, contributions=2), Contributor(name='Kamaal Farah', email=None, contributions=2)]

    >>> format_contributors({'Kent Clark <kent.clark@email.com>', 'John <john@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>', 'Kamaal <kamaal@email.com>'})
    [Contributor(name='John Smith', email=None, contributions=2), Contributor(name='Kamaal Farah', email=None, contributions=2), Contributor(name='Kent Clark', email=None, contributions=1)]
    """

    contributor_names_mapped_by_emails: Dict[str, List[str]] = {}
    for contributor_entry in contributors_list:
        splitted_contributor_entry = contributor_entry.split("<")
        contributor_name = (
            "".join(splitted_contributor_entry[:-1])
            .strip()
            .replace("<", "")
            .replace(">", "")
        )
        email = splitted_contributor_entry[-1].strip().replace("<", "").replace(">", "")

        contributor_names_mapped_by_emails[
            email
        ] = contributor_names_mapped_by_emails.get(email, []) + [contributor_name]

    contributors: List[Contributor] = []
    for (email, contributor_names) in contributor_names_mapped_by_emails.items():
        longest_contributor_name = ""

        for contributor_name in contributor_names:
            if contributor_name == "kamaal111":
                contributor_name = "Kamaal Farah"
            if len(contributor_name) > len(longest_contributor_name):
                longest_contributor_name = contributor_name

        contributors.append(
            Contributor(
                name=longest_contributor_name,
                email=email,
                contributions=len(contributor_names),
            )
        )

    merged_contributors: List[Contributor] = []
    for contributor in contributors:
        contributor_first_names_names = map(
            lambda contributor: contributor.first_name, merged_contributors
        )
        if contributor.first_name in contributor_first_names_names:
            for (index, merged_author) in enumerate(merged_contributors):
                first_name_is_the_same = (
                    contributor.first_name == merged_author.first_name
                )
                name_is_the_same = contributor.name == merged_author.name

                one_of_authors_has_just_a_single_name = (
                    contributor.has_just_a_single_name
                    or merged_author.has_just_a_single_name
                ) and len(contributor.name_components) != len(
                    merged_author.name_components
                )

                if first_name_is_the_same and (
                    one_of_authors_has_just_a_single_name or name_is_the_same
                ):
                    if len(contributor.name) > len(merged_author.name):
                        longest_author_name = contributor.name
                    else:
                        longest_author_name = merged_author.name

                    merged_contributors[index] = Contributor(
                        name=longest_author_name,
                        email=None,
                        contributions=contributor.contributions
                        + merged_author.contributions,
                    )
        else:
            contributor.email = None
            merged_contributors.append(contributor)

    return sorted(
        sorted(merged_contributors, key=lambda contributor: contributor.name),
        key=lambda contributor: contributor.contributions,
        reverse=True,
    )


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
        if arg == "--output" and (output := get_next_value()):
            arguments["output"] = output

    if arguments.get("scheme") is None:
        raise Exception("Please provide a scheme with the --scheme flag")

    if arguments.get("output") is None:
        raise Exception("Please provide a output path with the --output flag")

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
    if package_object := package_file_content.get("object"):
        for pin in package_object["pins"]:
            package_name = pin["package"]
            url = pin["repositoryURL"]
            if url.endswith(".git"):
                url = url[:-4]

            author = url.split("/")[-2]

            acknowledgement = AcknowledgementPackage(
                name=package_name,
                url=url,
                author=author,
                license=packages_licenses.get(package_name),
            )
            packages.append(acknowledgement)
    else:
        for pin in package_file_content["pins"]:
            url = pin["location"]
            if url.endswith(".git"):
                url = url[:-4]

            url_split_by_separator = url.split("/")
            package_name = url_split_by_separator[-1]
            author = url_split_by_separator[-2]
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
        path = Path(workspace_path) / "xcshareddata" / "swiftpm" / "Package.resolved"
        with path.open(mode="r") as file:
            return json.loads(file.read())

    raise Exception("Workspace not found at root")


def get_packages_directory(scheme: str):
    project_path = get_path_from_root_ending_with(search_string=".xcodeproj")
    if project_path is None:
        raise Exception("Project not found at root")

    output = subprocess.getoutput(
        f'xcodebuild -project {project_path} -target "{scheme}" -showBuildSettings'
    )

    output_search_line = "    BUILD_DIR = "
    for line in output.splitlines():
        if output_search_line in line:
            return line.replace(output_search_line, "").replace(
                "Build/Products", "SourcePackages/checkouts"
            )

    raise Exception(f"Build directory not found from {output=}")


@dataclass
class Acknowledgements:
    packages: List["AcknowledgementPackage"]
    contributors: List["Contributor"]

    def to_dict(self):
        dictionary_to_return = {}
        for key, value in asdict(self).items():
            dictionary_to_return[key] = value
        return dictionary_to_return

    def to_json(self, indent: Optional[int] = None):
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class Contributor:
    name: str
    email: Optional[str]
    contributions: int

    @property
    def first_name(self):
        return self.name_components[0]

    @property
    def name_components(self):
        return self.name.split(" ")

    @property
    def has_just_a_single_name(self):
        return len(self.name_components) == 1


@dataclass
class AcknowledgementPackage:
    name: str
    url: str
    author: Optional[str]
    license: Optional[str]


class Arguments(TypedDict):
    scheme: str
    output: str


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


class PackageFileContentPin(TypedDict):
    identity: str
    kind: str
    location: str
    state: PackageFileContentObjectPinState


class PackageFileContent(TypedDict):
    version: int
    object: Optional[PackageFileContentObject]
    pins: Optional[List[PackageFileContentPin]]


main()
