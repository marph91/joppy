"""
Analyze all joplin notes.
Requirements: pip install joppy markdown beautifulsoup4 nltk
Usage: API_TOKEN=XYZ python note_stats.py
"""

import re
import string
import os

from bs4 import BeautifulSoup
from joppy.api import Api
from markdown import Markdown
import nltk
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from nltk.tokenize import word_tokenize


def markdown_to_text(markdown_string: str) -> str:

    # convert markdown to html
    md = Markdown(extensions=["nl2br", "sane_lists", "tables"])
    html = md.convert(markdown_string)
    exclude_patterns_html = (
        r"<pre>.*?<\/pre>",  # code
        r"<code>.*?<\/code>",  # code
        r"\$.*?\$",  # formulas (https://meta.stackexchange.com/a/263344)
    )
    for pattern in exclude_patterns_html:
        html = re.sub(pattern, " ", html, flags=re.DOTALL)

    # convert html to text
    text = BeautifulSoup(html, "html.parser").get_text()
    exclude_patterns_text = (r"http[A-Za-z0-9-._~:/?#\[\]@!$&'\(\)\*+,;=]*",)  # links
    for pattern in exclude_patterns_text:
        text = re.sub(pattern, " ", text, flags=re.DOTALL)

    return text


def analyze_text(text: str):

    tokens = word_tokenize(text)
    tokens = [
        # normalize to lower case
        word.lower()
        for word in tokens
        if word not in ("...", "''", "``", "--", "++") and
        # punctuation
        word not in string.punctuation and
        # single character words
        len(word) > 1 and
        # words containing at least one digit
        not any(character.isdigit() for character in word)
    ]
    print("Words:", len(tokens))
    # filter most common words
    tokens = [
        word
        for word in tokens
        if word not in set(stopwords.words("english") + stopwords.words("german"))
    ]

    fdist = FreqDist(tokens)
    # fdist.plot(50)
    print("Most common words:")
    for word, count in fdist.most_common(10):
        print(f"- {word}: {count}")


def main():

    # download nltk data at the first start
    if False:
        nltk.download()

    # get all notes from joplin
    api = Api(token=os.getenv("API_TOKEN"))
    notes = api.get_all_notes(fields="id,title,body")
    print("Notes:", len(notes))

    # concatenate and convert them to text
    text = markdown_to_text("\n".join(note["body"] for note in notes))

    # analyze them
    analyze_text(text)


if __name__ == "__main__":
    main()
