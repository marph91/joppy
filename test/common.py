import itertools
import logging
import os
import random
import string
import tempfile
from typing import Iterable, Tuple
import unittest

from joppy.client_api import ClientApi
from joppy.server_api import ServerApi


os.makedirs("test_output", exist_ok=True)
logging.basicConfig(
    filename="test_output/test.log",
    filemode="w",
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.DEBUG,
)
LOGGER = logging.getLogger("joppy")

SLOW_TESTS = bool(os.getenv("SLOW_TESTS", ""))


def with_resource(func):
    """Create a dummy resource and return its filename."""

    def inner_decorator(self, *args, **kwargs):
        # TODO: Check why TemporaryFile() doesn't work.
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = f"{tmpdirname}/dummy.raw"
            open(filename, "w").close()

            return func(self, *args, **kwargs, filename=filename)

    return inner_decorator


class Base(unittest.TestCase):
    api: ClientApi | ServerApi

    def setUp(self) -> None:
        super().setUp()

        LOGGER.debug("Test: %s", self.id())

        self.api.delete_all_notebooks()
        self.api.delete_all_notes()
        self.api.delete_all_resources()
        self.api.delete_all_tags()
        # Delete revisions last to cover all previous deletions.
        self.api.delete_all_revisions()

    @staticmethod
    def get_random_id() -> str:
        """Return a random, valid ID."""
        # https://stackoverflow.com/a/2782859/7410886
        return f"{random.randrange(16**32):032x}"

    @staticmethod
    def get_random_string(length: int = 8, exclude: str = "") -> str:
        """Return a random string."""
        characters = string.printable
        for character in exclude:
            characters = characters.replace(character, "")
        random_string = "".join(random.choice(characters) for _ in range(length))
        LOGGER.debug("Test: random string: %s", random_string)
        return random_string

    @staticmethod
    def get_combinations(
        iterable: Iterable[str], max_combinations: int = 100
    ) -> Iterable[Tuple[str, ...]]:
        """Get some combinations of an iterable."""
        # https://stackoverflow.com/a/10465588
        # TODO: Randomize fully. For now the combinations are sorted by length.
        list_ = list(iterable)
        lengths = list(range(1, len(list_) + 1))
        random.shuffle(lengths)
        combinations = itertools.chain.from_iterable(
            itertools.combinations(list_, r)
            for r in lengths
            # shuffle each iteration
            if random.shuffle(list_) is None
        )
        return itertools.islice(combinations, max_combinations)
