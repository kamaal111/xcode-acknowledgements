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

    authors_list = subprocess.getoutput(
        f'git log "--pretty=format:%an <%ae>"'
    ).splitlines()
    formatted_authors = format_authors(authors_list=authors_list)
    acknowledgements = Acknowledgements(packages=packages, authors=formatted_authors)

    with open(os.path.join(arguments["output"], "Acknowledgements.json"), "w") as file:
        file.write(acknowledgements.to_json(indent=2))

    print("done writing acknowledgements ✨")


def format_authors(authors_list: List[str]):
    """Returns formatted authors

    >>> format_authors({'John <john@email.com>', 'Kamaal <kamaal@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>'})
    [Author(name='John Smith', email=None, contributions=2), Author(name='Kamaal Farah', email=None, contributions=2)]

    >>> format_authors({'John <john@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>', 'Kamaal <kamaal@email.com>'})
    [Author(name='John Smith', email=None, contributions=2), Author(name='Kamaal Farah', email=None, contributions=2)]

    >>> format_authors({'Kent Clark <kent.clark@email.com>', 'John <john@email.com>', 'John Smith <john.smith@email.com>', 'Kamaal Farah <kamaal.farah@email.com>', 'Kamaal <kamaal@email.com>'})
    [Author(name='John Smith', email=None, contributions=2), Author(name='Kamaal Farah', email=None, contributions=2), Author(name='Kent Clark', email=None, contributions=1)]
    """

    author_names_mapped_by_emails: Dict[str, List[str]] = {}
    for author_entry in authors_list:
        splitted_author_entry = author_entry.split("<")
        author_name = (
            "".join(splitted_author_entry[:-1])
            .strip()
            .replace("<", "")
            .replace(">", "")
        )
        email = splitted_author_entry[-1].strip().replace("<", "").replace(">", "")

        author_names_mapped_by_emails[email] = author_names_mapped_by_emails.get(
            email, []
        ) + [author_name]

    authors: List[Author] = []
    for (email, author_names) in author_names_mapped_by_emails.items():
        longest_author_name = ""

        for author_name in author_names:
            if len(author_name) > len(longest_author_name):
                longest_author_name = author_name

        authors.append(
            Author(
                name=longest_author_name, email=email, contributions=len(author_names)
            )
        )

    ultimate_authors: List[Author] = []
    for author in authors:
        author_first_names_names = map(
            lambda author: author.first_name, ultimate_authors
        )
        if author.first_name in author_first_names_names:
            for (index, ultimate_author) in enumerate(ultimate_authors):
                first_name_is_the_same = author.first_name == ultimate_author.first_name
                name_is_the_same = author.name == ultimate_author.name

                one_of_authors_has_just_a_single_name = (
                    author.has_just_a_single_name
                    or ultimate_author.has_just_a_single_name
                ) and len(author.name_components) != len(
                    ultimate_author.name_components
                )

                if first_name_is_the_same and (
                    one_of_authors_has_just_a_single_name or name_is_the_same
                ):
                    if len(author.name) > len(ultimate_author.name):
                        longest_author_name = author.name
                    else:
                        longest_author_name = ultimate_author.name

                    ultimate_authors[index] = Author(
                        name=longest_author_name,
                        email=None,
                        contributions=author.contributions
                        + ultimate_author.contributions,
                    )
        else:
            author.email = None
            ultimate_authors.append(author)

    return sorted(ultimate_authors, key=lambda x: x.contributions, reverse=True)


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
    authors: List["Author"]

    def to_dict(self):
        dictionary_to_return = {}
        for key, value in asdict(self).items():
            dictionary_to_return[key] = value
        return dictionary_to_return

    def to_json(self, indent: Optional[int] = None):
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class Author:
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


class PackageFileContent(TypedDict):
    version: int
    object: PackageFileContentObject


main()
