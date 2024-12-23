from __future__ import annotations as _annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from typing import Any, Literal, cast, final, override

from pydantic import BaseModel

__all__ = (
    'format_tag',
    'Dialect',
)

Dialect = Literal['xml']
BasicType = str | int | float | bool


def format_tag(tag: str, content: Any, dialect: Dialect = 'xml') -> str:
    """Format content into a tagged string representation using the specified dialect.

    Args:
        tag: The tag name to wrap the content with.
        content: The content to be formatted. Can be:
            - Basic types (str, int, float, bool)
            - Dictionaries
            - Lists, tuples, or other iterables
            - Pydantic models
            - Dataclasses
        dialect: The formatting dialect to use. Currently supports:
            - 'xml': XML format

    Returns:
        A string representation of the tagged content in the specified dialect.

    Raises:
        ValueError: If an unsupported dialect is specified.
        TypeError: If content is of an unsupported type.

    Examples:
        >>> format_tag('user', {'name': 'John', 'age': 30})
        '<user><name>John</name><age>30</age></user>'

        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class User:
        ...     name: str
        ...     age: int
        >>> user = User('John', 30)
        >>> format_tag('user', user)
        '<user><name>John</name><age>30</age></user>'
    """
    try:
        builder = {
            'xml': XMLTagBuilder,
        }[dialect](tag, content)
    except KeyError:
        raise ValueError(f'Unsupported dialect: {dialect}')

    return builder.build()


def _normalize_type(content: Any) -> dict[str, Any] | list[Any] | BasicType:
    match content:
        case BaseModel():
            return content.model_dump()

        case _ if is_dataclass(content):
            return asdict(cast(Any, content))

        case _ if isinstance(content, Iterable) and not isinstance(content, (str, dict)):
            return list(cast(Iterable[Any], content))

        case str() | int() | float() | bool() | dict():
            return cast(BasicType | dict[str, Any], content)

        case _:
            raise TypeError(f'Unsupported content type: {type(content)}')


class TagBuilder(ABC):
    """Abstract base class for building tagged string representations of content.

    This class provides the base functionality for converting various Python data types
    into a tagged string format. It handles normalization and formatting of content
    while leaving the specific string building implementation to subclasses.

    Args:
        tag: The root tag name to wrap the content with.
        content: The content to be formatted. Supported types include:
            - Basic types (str, int, float, bool)
            - Dictionaries
            - Lists, tuples, or other iterables
            - Pydantic models
            - Dataclasses

    Attributes:
        _content: Normalized and formatted content as a dictionary structure.

    Raises:
        TypeError: If content is of an unsupported type.
    """

    def __init__(self, tag: str, content: Any) -> None:
        self._content: dict[str, Any] = self._format_content(tag, content)

    @abstractmethod
    def build(self) -> str: ...

    def _format_content(self, tag: str, content: Any) -> dict[str, Any]:
        root: dict[str, Any] = {}
        normalized = _normalize_type(content)

        match normalized:
            case dict():
                root[tag] = {}

                for key, value in normalized.items():
                    root[tag][key] = self._format_content(key, value)[key]

            case list():
                assert isinstance(normalized, list)
                root[tag] = [self._format_content(tag, item)[tag] for item in normalized]

            case _:
                root[tag] = normalized

        return root


@final
class XMLTagBuilder(TagBuilder):
    """Concrete implementation of TagBuilder that produces XML formatted output.

    This class converts the normalized content into valid XML string representation.
    It handles nested structures, lists, and basic types while ensuring proper XML formatting.

    Examples:
        >>> builder = XMLTagBuilder('user', {'name': 'John', 'age': 30})
        >>> builder.build()
        '<user><name>John</name><age>30</age></user>'

        >>> builder = XMLTagBuilder('flags', [True, False])
        >>> builder.build()
        '<flags>true</flags><flags>false</flags>'

        >>> builder = XMLTagBuilder('nested', {'user': {'details': {'active': True}}})
        >>> builder.build()
        '<nested><user><details><active>true</active></details></user></nested>'
    """

    @override
    def build(self) -> str:
        return self._build_element(self._content)

    def _build_element(self, content: dict[str, Any]) -> str:
        result: list[str] = []

        for tag, value in content.items():
            match value:
                case dict():
                    nested_content = ''

                    for k, v in cast(dict[str, Any], value).items():
                        nested_content += self._build_element({k: v})

                    result.append(f'<{tag}>{nested_content}</{tag}>')

                case list():
                    nested_content = ''.join(
                        f'<{tag}>{self._format_value(item)}</{tag}>' for item in cast(list[str], value)
                    )
                    result.append(nested_content)

                case _:
                    result.append(f'<{tag}>{self._format_value(value)}</{tag}>')

        return ''.join(result)

    def _format_value(self, value: Any) -> str:
        match value:
            case bool():
                return str(value).lower()

            case dict():
                return self._build_element(cast(dict[str, Any], value))

            case list():
                return ''.join(f'{self._format_value(item)}' for item in cast(list[Any], value))

            case _:
                return str(value)
