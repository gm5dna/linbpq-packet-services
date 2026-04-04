"""
eliza.py -- ELIZA chatbot sub-service for the packet node INFO menu.

Classic Rogerian psychotherapist pattern-matching chatbot, faithful to
Weizenbaum's 1966 design. No external dependencies.

Type BYE (or a blank line) to return to the main menu.
"""

import re
import random

# ---------------------------------------------------------------------------
# Reflection table: first-person input -> second-person reply
# ---------------------------------------------------------------------------
REFLECTIONS = {
    "i am":     "you are",
    "i was":    "you were",
    "i":        "you",
    "i'm":      "you're",
    "i've":     "you've",
    "i'll":     "you'll",
    "i'd":      "you'd",
    "my":       "your",
    "myself":   "yourself",
    "me":       "you",
    "am":       "are",
    "was":      "were",
    "you are":  "I am",
    "you were": "I was",
    "you":      "me",
    "your":     "my",
    "yourself": "myself",
    "you've":   "I've",
    "you'll":   "I'll",
    "you'd":    "I'd",
    "you're":   "I'm",
}

# ---------------------------------------------------------------------------
# Patterns: list of (compiled_regex, [response_templates])
# %1 in a response is replaced by the reflected remainder of the match.
# Ordered from most to least specific.
# ---------------------------------------------------------------------------
PATTERNS = [
    (re.compile(r"\bI need (.*)", re.I),
     [
         "Why do you need %1?",
         "Would it really help you if you got %1?",
         "Are you sure you need %1?",
         "What would it mean to you to have %1?",
     ]),

    (re.compile(r"\bI am (.*)", re.I),
     [
         "How long have you been %1?",
         "Do you believe it is normal to be %1?",
         "How do you feel about being %1?",
         "Why do you tell me you are %1?",
     ]),

    (re.compile(r"\bI'm (.*)", re.I),
     [
         "How long have you been %1?",
         "Do you feel strongly about being %1?",
         "How does being %1 make you feel?",
     ]),

    (re.compile(r"\bI feel (.*)", re.I),
     [
         "Tell me more about feeling %1.",
         "Do you often feel %1?",
         "When do you usually feel %1?",
         "What makes you feel %1?",
     ]),

    (re.compile(r"\bI have (.*)", re.I),
     [
         "Why do you tell me that you have %1?",
         "Have you had %1 for a long time?",
         "How does having %1 make you feel?",
     ]),

    (re.compile(r"\bI (.*) you\b", re.I),
     [
         "Why do you %1 me?",
         "Perhaps in your fantasies we %1 each other.",
         "Do you wish to %1 me?",
     ]),

    (re.compile(r"\bwhy (.*)\?*", re.I),
     [
         "Why do you think %1?",
         "What makes you ask that?",
         "Does that question interest you?",
     ]),

    (re.compile(r"\bhow (.*)\?*", re.I),
     [
         "How do you suppose?",
         "Perhaps you can answer your own question.",
         "What is it you are really asking?",
     ]),

    (re.compile(r"\byes\b", re.I),
     [
         "You seem very certain.",
         "Of course. But can you elaborate?",
         "I see. Please go on.",
     ]),

    (re.compile(r"\bno\b", re.I),
     [
         "Are you saying NO just to be negative?",
         "You are being a bit negative.",
         "Why not?",
         "Are you sure?",
     ]),

    (re.compile(r"\bsorry\b", re.I),
     [
         "Please do not apologise.",
         "Apologies are not necessary.",
         "What feelings do you have when you apologise?",
     ]),

    (re.compile(r"\bcomputer(s)?\b", re.I),
     [
         "Do computers worry you?",
         "What do you think about machines?",
         "Why do you mention computers?",
         "What do you think machines have to do with your problem?",
     ]),

    (re.compile(r"\bfriend(s)?\b", re.I),
     [
         "Tell me more about your friends.",
         "When you think of a friend, what comes to mind?",
         "Why do you bring up the subject of friends?",
     ]),

    (re.compile(r"\bfamily\b|\bmother\b|\bfather\b|\bsister\b|\bbrother\b",
                re.I),
     [
         "Tell me more about your family.",
         "Who else in your family do you think of?",
         "How does your family make you feel?",
     ]),

    (re.compile(r"\bI want (.*)", re.I),
     [
         "What would it mean if you got %1?",
         "Why do you want %1?",
         "Suppose you got %1 -- what then?",
         "What does wanting %1 mean to you?",
     ]),

    (re.compile(r"\bI think (.*)", re.I),
     [
         "Do you really think %1?",
         "But you are not sure %1?",
         "Do you doubt %1?",
         "What makes you think %1?",
     ]),

    (re.compile(r"\bI know (.*)", re.I),
     [
         "How do you know %1?",
         "Are you very sure you know %1?",
         "What makes you certain about %1?",
     ]),

    (re.compile(r"\bbecause\b(.*)", re.I),
     [
         "Is that the real reason?",
         "What other reasons might there be?",
         "Does that reason seem to explain anything else?",
     ]),

    (re.compile(r"\balways\b", re.I),
     [
         "Can you think of a specific example?",
         "Really, always?",
         "When in particular?",
     ]),

    (re.compile(r"\bnever\b", re.I),
     [
         "Never?",
         "Surely there must be some occasions.",
         "Can you think of any exceptions?",
     ]),

    (re.compile(r"\b(perhaps|maybe)\b", re.I),
     [
         "You do not seem very certain.",
         "Can you be more definitive?",
         "Why the hesitation?",
     ]),

    (re.compile(r"\b(sad|unhappy|depressed|upset)\b", re.I),
     [
         "I am sorry to hear you are %1.",
         "Do you think coming here will help you not to be %1?",
         "Can you explain what made you %1?",
     ]),

    (re.compile(r"\b(happy|glad|elated|good)\b", re.I),
     [
         "How have I helped you to be %1?",
         "Has your being %1 anything to do with me?",
         "What makes you %1?",
     ]),

    (re.compile(r"\b(hello|hi|greetings|howdy)\b", re.I),
     [
         "Hello. How are you feeling today?",
         "Hi there. What is on your mind?",
         "Greetings. Please tell me what is troubling you.",
     ]),

    (re.compile(r"\b(radio|amateur|ham|packet)\b", re.I),
     [
         "Tell me more about your interest in %1.",
         "How does %1 make you feel?",
         "That is interesting. Please go on.",
     ]),
]

# Fallback responses when no pattern matches.
FALLBACKS = [
    "Please go on.",
    "Tell me more.",
    "I see. Can you elaborate?",
    "That is very interesting. Please continue.",
    "Why do you say that?",
    "How does that make you feel?",
    "Very interesting. Please tell me more.",
    "I am not sure I understand you fully. Can you say more?",
    "Can you elaborate on that?",
    "Let us explore that further.",
]

GOODBYE_WORDS = {"bye", "goodbye", "quit", "exit", "q"}


def _reflect(text):
    """Apply reflection table to swap first/second person in a phrase."""
    tokens = text.lower().split()
    result = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            pair = tokens[i] + " " + tokens[i + 1]
            if pair in REFLECTIONS:
                result.append(REFLECTIONS[pair])
                i += 2
                continue
        word = tokens[i]
        result.append(REFLECTIONS.get(word, word))
        i += 1
    return " ".join(result)


def _respond(user_input):
    """Generate ELIZA's response to user_input."""
    text = user_input.strip()
    for pattern, responses in PATTERNS:
        m = pattern.search(text)
        if m:
            response = random.choice(responses)
            if "%1" in response:
                try:
                    tail = m.group(1).strip()
                except IndexError:
                    tail = m.group(0).strip()
                reflected = _reflect(tail)
                response = response.replace("%1", reflected)
            return response
    return random.choice(FALLBACKS)


def run(writeln, read_line, write):
    """Entry point called from the main INFO menu."""
    writeln()
    writeln("=== ELIZA - Rogerian Psychotherapist ===")
    writeln()
    writeln("Hello. I am ELIZA. How are you feeling today?")
    writeln("(Type BYE or leave a blank line to return to the menu.)")
    writeln()

    while True:
        write("> ")
        line = read_line()

        if line is None:
            return

        stripped = line.strip()

        if stripped == "":
            return

        if stripped.lower() in GOODBYE_WORDS:
            writeln()
            writeln("Goodbye. It was good talking with you.")
            writeln()
            return

        response = _respond(stripped)
        writeln()
        writeln(response)
        writeln()
