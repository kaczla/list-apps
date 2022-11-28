#!/usr/bin/env python3

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

HEADER_LIST_OF_APPS = "List of application"

LOGGER = logging.getLogger(__name__)


@dataclass
class ParsedApplication:
    name: str
    name_text: str
    text: List[str]

    def text_to_line(self) -> str:
        return "\n".join(self.text)

    def to_text(self) -> str:
        return f"- {self.name} {self.name_text}\n{self.text_to_line()}"


@dataclass
class Section:
    name: str
    text: List[str]

    def text_to_line(self) -> str:
        return "\n".join(self.text)

    def to_text(self, extra_new_line: bool = False) -> str:
        text = f"# {self.name}\n\n{self.text_to_line()}\n"
        if extra_new_line:
            text += "\n"
        return text


def parse_section(text: List[str]) -> Section:
    section_name = text.pop(0)[1:].strip()

    # Find empty lines at the beginning
    indexes_to_remove = []
    for index, text_line in enumerate(text):
        if not text_line.strip():
            indexes_to_remove.append(index)
            continue

        break

    # Return empty text if it is
    if len(indexes_to_remove) == len(text):
        LOGGER.error(f"Empty text in section: {section_name}")
        return Section(name=section_name, text=[])

    # Find empty lines at the end
    for index, text_line in enumerate(reversed(text)):
        if not text_line.strip():
            indexes_to_remove.append(len(text) - 1 - index)
            continue

        break

    # Remove empty lines
    for index in sorted(indexes_to_remove, reverse=True):
        del text[index]

    return Section(name=section_name, text=text)


def parse_sections(text: List[str]) -> List[Section]:
    sections, text_lines = [], []

    for line in text:
        if line.startswith("# ") and text_lines:
            sections.append(parse_section(text_lines))
            text_lines = []

        text_lines.append(line.rstrip())

    if text_lines:
        sections.append(parse_section(text_lines))

    LOGGER.info(f"Found {len(sections)} sections")
    LOGGER.info(f"Sections: {[s.name for s in sections]}")
    return sections


def remove_section(section_name: str, sections: List[Section]) -> List[Section]:
    indexes = [i for i, section in enumerate(sections) if section.name == section_name]
    for index in reversed(indexes):
        del sections[index]
    return sections


def read_readme(file_path: Path) -> Tuple[List[Section], List[Section], Section]:
    LOGGER.info(f"Reading from: {file_path}")

    sections = parse_sections(file_path.read_text().split("\n"))

    indexes_list_applications = [index for index, s in enumerate(sections) if s.name == HEADER_LIST_OF_APPS]
    assert len(
        indexes_list_applications
    ), f"Expecting one section with applications, got {len(indexes_list_applications)} sections"
    index_list_applications = indexes_list_applications[0]
    del indexes_list_applications

    sections_before_applications = sections[:index_list_applications]
    sections_after_applications = sections[index_list_applications + 1 :]
    application_section = sections[index_list_applications]

    return (
        sections_before_applications,
        sections_after_applications,
        application_section,
    )


def write_readme(
    text_before: List[Section],
    text_after: List[Section],
    parsed_applications: List[ParsedApplication],
    save_path: Path,
) -> None:
    LOGGER.info(f"Writing into: {save_path}")
    text_to_save = ""

    text_to_save += "\n".join([s.to_text(extra_new_line=True) for s in text_before])

    text_to_save += f"# {HEADER_LIST_OF_APPS}\n\n"
    text_to_save += "\n".join([e.to_text() for e in parsed_applications]) + "\n\n"

    text_to_save += "\n".join([s.to_text() for s in text_after])

    save_path.write_text(text_to_save)


def parse_application_text_lines(text: List[str]) -> ParsedApplication:
    line_with_name = text.pop(0).lstrip("-").strip()
    application_name, application_name_text = line_with_name.split(maxsplit=1)

    # Check empty link
    if "[]" in application_name_text or "()" in application_name_text:
        LOGGER.error(f"Found empty link in {application_name}")

    return ParsedApplication(name=application_name, name_text=application_name_text.strip(), text=text)


def parse_list_applications(section: Section) -> List[ParsedApplication]:
    parsed_applications = []
    data_application_lines = []
    for line in section.text:
        if line.startswith("-"):
            if data_application_lines:
                parsed_applications.append(parse_application_text_lines(data_application_lines))
                data_application_lines = []

            data_application_lines.append(line.rstrip())

        else:
            data_application_lines.append(line.rstrip())

    if data_application_lines:
        parsed_applications.append(parse_application_text_lines(data_application_lines))

    LOGGER.info(f"Parsed {len(parsed_applications)} applications")
    parsed_applications.sort(key=lambda x: x.name.lower())
    return parsed_applications


def get_tags(parsed_applications: List[ParsedApplication]) -> List[Tuple[str, int]]:
    tags = Counter()
    for parsed_application in parsed_applications:
        tags_lines_text = [
            text.strip()[7:].strip()
            for text in parsed_application.text
            if text[:10].strip().lower().startswith("- tags:")
        ]
        if not tags_lines_text:
            LOGGER.error(f"Cannot find TAGS for application: {parsed_application.name}")
            continue

        tags_text = ", ".join(tags_lines_text).strip().strip(",")
        application_tags = list(filter(lambda x: x, [tag.strip() for tag in tags_text.strip(",").split(",")]))
        tags.update(application_tags)

    LOGGER.info(f"Found {len(tags)} tags")
    LOGGER.debug(f"Tags with occurrences: {sorted(tags.items(), key=lambda x: x[0])}")
    return sorted(tags.items(), key=lambda x: x[0].lower())


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md does not exist!"

    text_before, text_after, application_text = read_readme(readme_path)
    parsed_applications = parse_list_applications(application_text)

    remove_section("Tags", text_after)
    tags = get_tags(parsed_applications)
    text_after.append(
        Section(
            name="Tags",
            text=["List of tags with occurrences in the brackets:\n"]
            + [f"- {tag} ({tag_occurrence})" for tag, tag_occurrence in tags],
        )
    )

    write_readme(text_before, text_after, parsed_applications, readme_path)


if __name__ == "__main__":
    main()
