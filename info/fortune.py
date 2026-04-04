"""
fortune.py -- Fortune sub-service for the packet node INFO menu.

Tries /usr/games/fortune first. Falls back to a built-in list of
ham radio, computing, and engineering quotes if fortune is unavailable.
No interaction -- displays a quote and returns immediately.
"""

import subprocess
import random

# Built-in fallback quotes: ham radio, computing, and engineering themes.
FORTUNES = [
    "73 de the universe -- the best DX is always the next contact.",
    "The ionosphere is not a bug; it's an undocumented feature.",
    "A radio amateur's antenna is always too short and never high enough.",
    "Any sufficiently advanced packet node is indistinguishable from magic.",
    "The manual is always the last resort of a true amateur.",
    "If it works, don't touch it. If it doesn't work, wiggle the coax.",
    "The strength of a signal is inversely proportional to the importance "
    "of the message.",
    "We do precision guesswork. -- Engineering motto",
    "All parts fall out of a bag at the same speed, regardless of value.",
    "The best antenna is the one you actually put up.",
    "There are two types of RF connectors: the ones that have failed, "
    "and the ones that will.",
    "A clear frequency is one that only you can hear the interference on.",
    "QRM: Quantum Randomness of Mysteriously arriving signals.",
    "The difference between a ham and a lid is about 10 dB.",
    "Ohm's Law: the three equations every engineer memorises and every "
    "student forgets.",
    "The nice thing about standards is that there are so many to choose from."
    " -- Andrew Tanenbaum",
    "640K ought to be enough for anybody. -- Attribution disputed",
    "UNIX is basically a simple operating system, but you have to be a "
    "genius to understand the simplicity. -- Dennis Ritchie",
    "Any fool can write code that a computer can understand. Good "
    "programmers write code that humans can understand. -- Martin Fowler",
    "First, solve the problem. Then, write the code. -- John Johnson",
    "It's not a bug; it's an undocumented feature.",
    "The most effective debugging tool is still careful thought, coupled "
    "with judiciously placed print statements. -- Brian Kernighan",
    "Beware of bugs in the above code; I have only proved it correct, "
    "not tried it. -- Donald Knuth",
    "Talk is cheap. Show me the code. -- Linus Torvalds",
    "Real programmers don't comment their code. If it was hard to write, "
    "it should be hard to read.",
    "To iterate is human; to recurse, divine. -- L. Peter Deutsch",
    "In theory, theory and practice are the same. In practice, they are "
    "not. -- Yogi Berra",
    "The goal of Computer Science is to build something that will last at "
    "least until we've finished building it.",
    "A computer lets you make more mistakes faster than any other invention "
    "in human history, with the possible exception of handguns and tequila."
    " -- Mitch Ratcliffe",
    "There are only two hard things in Computer Science: cache invalidation "
    "and naming things. -- Phil Karlton",
]


def run(writeln, read_line, write):
    """Entry point called from the main INFO menu."""
    writeln()
    writeln("=== Fortune ===")
    writeln()

    quote = _get_fortune()
    for line in _wrap(quote, 78):
        writeln(line)

    writeln()


def _get_fortune():
    """Return a fortune string from /usr/games/fortune or the built-in list."""
    try:
        r = subprocess.run(
            ["/usr/games/fortune"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return random.choice(FORTUNES)


def _wrap(text, width):
    """
    Simple word-wrap. Returns a list of lines, each at most `width` chars.
    Preserves existing newlines in the input.
    """
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines
