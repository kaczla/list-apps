#!/usr/bin/env python3

import json
import logging
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Counter as CounterType
from typing import Dict, List, Optional, Tuple

from loguru import logger

HEADER_LIST_OF_APPS = "List of application"

RGX_SPACES_CLEAN = re.compile(r"\s+")

DATA_PATH = Path("data")
JSON_DATA = DATA_PATH / "json"


@dataclass
class ParsedApplication:
    name: str
    name_text: str
    text: List[str]

    def text_to_line(self) -> str:
        return "\n".join(self.text)

    def to_text(self) -> str:
        return f"- {self.name} {self.name_text}\n{self.text_to_line()}"

    def get_tags(self) -> Optional[List[str]]:
        tags_lines_text_with_index: List[Tuple[int, str]] = [
            (i, text.strip()[7:].strip())
            for i, text in enumerate(self.text)
            if text[:10].strip().lower().startswith("- tags:")
        ]
        if not tags_lines_text_with_index:
            return None

        tags_text = ", ".join([text for _, text in tags_lines_text_with_index]).strip().strip(",")
        tags = [tag_name.strip() for tag_name in tags_text.split(", ")]

        # Remove other tag text lines
        if len(tags_lines_text_with_index) > 1:
            for index, _ in reversed(tags_lines_text_with_index[1:]):
                del self.text[index]

        # Skip duplicates tags
        uniq_tags = set(tags)
        if len(uniq_tags) != len(tags):
            uniq_tags_list = []
            for tag_name in tags:
                if tag_name in uniq_tags:
                    uniq_tags_list.append(tag_name)
                    uniq_tags.discard(tag_name)
                else:
                    continue
            tags = uniq_tags_list

        # Update tag text
        self.set_tags(self._sort_tags(tags))

        return tags

    def set_tags(self, tag_names: List[str]) -> None:
        tag_text_indexes = [i for i, text in enumerate(self.text) if text[:10].strip().lower().startswith("- tags:")]
        if tag_text_indexes:
            self.text[tag_text_indexes[0]] = "  - Tags: " + ", ".join(tag_names)
        else:
            self.text.append("  - Tags: " + ", ".join(tag_names))

    @staticmethod
    def _sort_tags(tags: List[str]) -> List[str]:
        source_tags = []
        command_line_tags = []
        tags_copy = deepcopy(tags)
        tags_to_remove = []
        for tag in tags_copy:
            if tag.lower().startswith("source: "):
                source_tags.append(tag)
                tags_to_remove.append(tag)

            elif tag.lower().startswith("command line: "):
                command_line_tags.append(tag)
                tags_to_remove.append(tag)

        for tag_to_remove in tags_to_remove:
            tags_copy.remove(tag_to_remove)

        return tags_copy + command_line_tags + source_tags


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


@dataclass
class Tag:
    name: str
    occurrence: int


def init_logs(debug: bool = False, warning: bool = False) -> None:
    if debug:
        level = logging.DEBUG
    elif warning:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if debug:
        logging.getLogger("urllib3").setLevel(logging.INFO)


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
        logger.error(f"Empty text in section: {section_name}")
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
    sections: List[Section] = []
    text_lines: List[str] = []

    for line in text:
        if line.startswith("# ") and text_lines:
            sections.append(parse_section(text_lines))
            text_lines = []

        text_lines.append(line.rstrip())

    if text_lines:
        sections.append(parse_section(text_lines))

    logger.info(f"Found {len(sections)} sections")
    logger.info(f"Sections: {[s.name for s in sections]}")
    return sections


def remove_section(section_name: str, sections: List[Section]) -> List[Section]:
    indexes = [i for i, section in enumerate(sections) if section.name == section_name]
    for index in reversed(indexes):
        del sections[index]
    return sections


def read_readme(file_path: Path) -> Tuple[List[Section], List[Section], Section]:
    logger.info(f"Reading from: {file_path}")

    sections = parse_sections(file_path.read_text().split("\n"))

    indexes_list_applications = [index for index, s in enumerate(sections) if s.name == HEADER_LIST_OF_APPS]
    assert len(indexes_list_applications), (
        f"Expecting one section with applications, got {len(indexes_list_applications)} sections"
    )
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
    logger.info(f"Writing into: {save_path}")
    text_to_save = ""

    text_to_save += "\n".join([s.to_text(extra_new_line=True) for s in text_before])

    text_to_save += f"# {HEADER_LIST_OF_APPS}\n\n"
    text_to_save += "\n".join([e.to_text() for e in parsed_applications]) + "\n\n"

    text_to_save += "\n".join([s.to_text() for s in text_after])

    save_path.write_text(text_to_save)


def clean_whitespaces(text: str) -> str:
    lines = text.split("\n")
    lines_cleaned = []

    for line in lines:
        line_clean = line.strip()

        line_clean_index = line.find(line_clean)
        if line_clean_index < 0:
            logger.warning(f"Cannot clean text: {line!r}")
            lines_cleaned.append(line)
            continue
        prefix = line[:line_clean_index]

        line_clean = RGX_SPACES_CLEAN.sub(" ", line_clean)
        lines_cleaned.append(prefix + line_clean)

    return "\n".join(lines_cleaned)


def parse_application_text_lines(text: List[str]) -> ParsedApplication:
    line_with_name = text.pop(0).lstrip("-").strip()
    application_name, application_name_text = line_with_name.split(maxsplit=1)

    # Check empty link
    if "[]" in application_name_text or "()" in application_name_text:
        logger.error(f"Found empty link in {application_name}")

    application_name_text = clean_whitespaces(application_name_text)
    text = [clean_whitespaces(single_text) for single_text in text]
    return ParsedApplication(name=application_name, name_text=application_name_text.strip(), text=text)


def parse_list_applications(section: Section) -> List[ParsedApplication]:
    parsed_applications: List[ParsedApplication] = []
    data_application_lines: List[str] = []
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

    logger.info(f"Parsed {len(parsed_applications)} applications")
    parsed_applications.sort(key=lambda x: x.name.lower())
    return parsed_applications


def get_tags(parsed_applications: List[ParsedApplication]) -> List[Tag]:
    tags_counter: CounterType = Counter()
    for parsed_application in parsed_applications:
        tag_names = parsed_application.get_tags()
        if tag_names is None:
            logger.error(f"Not found tags in: {parsed_application}")
            continue

        application_tags = list(filter(lambda x: x, tag_names))
        tags_counter.update(application_tags)

    logger.info(f"Found {len(tags_counter)} tags")
    tags = [Tag(name=name, occurrence=occ) for name, occ in sorted(tags_counter.items(), key=lambda x: x[0].lower())]
    logger.debug(f"Tags with occurrences: {tags}")
    return tags


def get_tag_mapper(tags: List[Tag]) -> Dict[str, str]:
    normalized_tags_dict: Dict[str, List[Tag]] = {}
    for tag in tags:
        tag_name = tag.name.lower()
        if tag_name in normalized_tags_dict:
            normalized_tags_dict[tag_name].append(tag)
        else:
            normalized_tags_dict[tag_name] = [tag]

    tag_mapper = {}
    for _, original_tags in normalized_tags_dict.items():
        if len(original_tags) < 2:
            continue

        sorted_tags_by_occ = sorted(original_tags, key=lambda x: x.occurrence, reverse=True)
        most_popular_tag = sorted_tags_by_occ.pop(0)
        # If tags are with equal occurrences, use tag with first uppercase letter
        if most_popular_tag.occurrence == sorted_tags_by_occ[0].occurrence and not most_popular_tag.name[0].isupper():
            index_to_remove = None
            for tag_index, tag in enumerate(sorted_tags_by_occ):
                # Use tag with first uppercase letter
                if tag.name[0].isupper():
                    sorted_tags_by_occ.append(most_popular_tag)
                    most_popular_tag = tag
                    index_to_remove = tag_index
                    break

            if index_to_remove is not None:
                del sorted_tags_by_occ[index_to_remove]
            else:
                logger.warning(f"Cannot find tag to normalization for: {original_tags}")
                continue

        for tag in sorted_tags_by_occ:
            logger.debug(f"Found tag normalization from: {tag.name!r} to {most_popular_tag.name!r}")
            tag_mapper[tag.name] = most_popular_tag.name

    return tag_mapper


def fix_tags(tags: List[Tag], applications: List[ParsedApplication], tag_mapper: Dict[str, str]) -> List[Tag]:
    logger.info(f"Normalizing tags with mapping: {tag_mapper}")
    tag_name_to_index: Dict[str, int] = {tag.name: i for i, tag in enumerate(tags)}

    # Merge tag occurrences
    tag_indexes_to_remove = []
    for tag_name, target_tag_name in tag_mapper.items():
        idx = tag_name_to_index[tag_name]
        idx_target = tag_name_to_index[target_tag_name]
        logger.debug(f"Merging tag: {tags[idx]} with {tags[idx_target]}")
        tags[idx_target].occurrence += tags[idx].occurrence
        tag_indexes_to_remove.append(idx)

    # Remove merged tags
    for idx in reversed(tag_indexes_to_remove):
        del tags[idx]

    # Fix tags in applications
    for application in applications:
        original_tag_names = application.get_tags()
        if original_tag_names is None:
            continue

        original_tag_names = [tag_name.strip() for tag_name in original_tag_names]

        tag_names = []
        for tag_name in original_tag_names:
            if tag_name in tag_mapper:
                tag_name = tag_mapper[tag_name]
            tag_names.append(tag_name)

        if original_tag_names != tag_names:
            application.set_tags(tag_names)

    return tags


def main() -> None:
    init_logs(debug=False)
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md does not exist!"

    text_before, text_after, application_text = read_readme(readme_path)
    parsed_applications = parse_list_applications(application_text)

    remove_section("Tags", text_after)
    tags = get_tags(parsed_applications)
    tag_mapper = get_tag_mapper(tags)
    if tag_mapper:
        fix_tags(tags, parsed_applications, tag_mapper)

    dump_data_from_parsed_applications(parsed_applications, tags)

    text_after.append(
        Section(
            name="Tags",
            text=["List of tags with occurrences in the brackets:\n"]
            + [f"- {tag.name} ({tag.occurrence})" for tag in tags],
        )
    )

    write_readme(text_before, text_after, parsed_applications, readme_path)


def dump_data_from_parsed_applications(parsed_applications: list[ParsedApplication], tags: list[Tag]) -> None:
    file_tags = JSON_DATA / "tags.json"
    file_applications = JSON_DATA / "applications.json"

    tag_names = [tag.name for tag in tags]
    tag_names.sort(key=lambda x: x.lower())
    file_tags.write_text(json.dumps(tag_names, indent=4, ensure_ascii=False))

    application_data = []
    for parsed_application in parsed_applications:
        url = parsed_application.name_text.strip("[🛈]()")
        description = next(text for text in parsed_application.text if "- Tags:" not in text)
        description = description.strip().lstrip("-").strip()
        json_data = {
            "name": parsed_application.name,
            "url": url,
            "description": description,
            "tags": parsed_application.get_tags() or [],
        }
        application_data.append(json_data)
    file_applications.write_text(json.dumps(application_data, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
