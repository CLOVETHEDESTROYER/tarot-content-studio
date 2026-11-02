from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


RANKS = {
    "01": ("Ace", "seed, new beginning, raw potential", "blocked beginning, hesitation, unused gift"),
    "02": ("Two", "choice, partnership, balance", "imbalance, avoidance, tension"),
    "03": ("Three", "growth, collaboration, first results", "scattered effort, delay, mixed signals"),
    "04": ("Four", "structure, pause, stability", "stagnation, rigidity, restlessness"),
    "05": ("Five", "conflict, loss, pressure, lesson", "recovery, release, learning from friction"),
    "06": ("Six", "repair, generosity, memory, harmony", "uneven exchange, nostalgia trap, strings attached"),
    "07": ("Seven", "assessment, challenge, strategy", "confusion, impatience, self-doubt"),
    "08": ("Eight", "movement, discipline, momentum", "delay, burnout, misdirected force"),
    "09": ("Nine", "culmination, solitude, personal truth", "overindulgence, anxiety, guardedness"),
    "10": ("Ten", "completion, burden or fulfillment", "release, unfinished business, too much weight"),
    "11": ("Page", "message, beginner energy, curiosity", "immaturity, missed message, nervous start"),
    "12": ("Knight", "pursuit, motion, mission", "recklessness, delay, one-track thinking"),
    "13": ("Queen", "maturity, inner mastery, receptive power", "insecurity, overcontrol, emotional drain"),
    "14": ("King", "authority, command, public mastery", "misuse of power, rigidity, performative control"),
}

SUITS = {
    "cups": {
        "domain": "emotion, love, intuition, memory, relationships",
        "prediction": "the emotional weather is the lever that changes the outcome",
    },
    "pentacles": {
        "domain": "money, work, body, status, resources, practical reality",
        "prediction": "material choices and consistent effort shape what happens next",
    },
    "swords": {
        "domain": "thought, truth, conflict, communication, decisions",
        "prediction": "clarity, language, and hard choices drive the next turn",
    },
    "wands": {
        "domain": "ambition, creativity, public heat, desire, momentum",
        "prediction": "energy and timing matter more than perfect certainty",
    },
}

MAJORS = {
    "00": ("The Fool", "beginnings, risk, innocence, a leap into the unknown", "naivete, poor timing, avoidable risk"),
    "01": ("The Magician", "will, skill, manifestation, using every tool available", "manipulation, scattered force, unused talent"),
    "02": ("The High Priestess", "intuition, secrets, hidden knowledge, sacred restraint", "confusion, silence, ignoring the inner voice"),
    "03": ("The Empress", "abundance, beauty, care, creation, sensual power", "creative block, dependence, overindulgence"),
    "04": ("The Emperor", "authority, boundaries, command, structure", "domination, rigidity, control issues"),
    "05": ("The Hierophant", "tradition, institutions, mentorship, belief systems", "rebellion, stale doctrine, bad advice"),
    "06": ("The Lovers", "choice, union, values, intimate alignment", "misalignment, temptation, divided loyalty"),
    "07": ("The Chariot", "victory, discipline, directed will, public momentum", "loss of control, ego, stalled progress"),
    "08": ("Strength", "courage, restraint, grace under pressure", "self-doubt, forcefulness, drained courage"),
    "09": ("The Hermit", "solitude, wisdom, retreat, inner guidance", "isolation, withdrawal, refusing counsel"),
    "10": ("Wheel of Fortune", "cycles, fate, luck, timing, reversal", "bad timing, resistance to change, repeated pattern"),
    "11": ("Justice", "truth, balance, accountability, consequences", "bias, imbalance, evasion of responsibility"),
    "12": ("The Hanged Man", "pause, surrender, changed perspective, sacrifice", "stalling, martyrdom, refusal to release"),
    "13": ("Death", "ending, transformation, irreversible change", "clinging, delayed ending, fear of renewal"),
    "14": ("Temperance", "integration, patience, moderation, alchemy", "imbalance, excess, impatience"),
    "15": ("The Devil", "attachment, temptation, appetite, power, shadow", "breaking chains, seeing the trap, detox"),
    "16": ("The Tower", "shock, collapse, revelation, false structure falling", "avoided disaster, slow breakdown, denial"),
    "17": ("The Star", "hope, healing, renewal, future vision", "discouragement, dimmed faith, delayed healing"),
    "18": ("The Moon", "uncertainty, dreams, fear, illusion, hidden motives", "truth emerging, fear named, deception clearing"),
    "19": ("The Sun", "success, joy, vitality, visibility", "temporary cloud, ego glare, delayed celebration"),
    "20": ("Judgement", "reckoning, awakening, verdict, second chance", "avoidance, self-judgment, unfinished call"),
    "21": ("The World", "completion, integration, achievement, full circle", "loose end, incomplete lesson, delayed arrival"),
}

SPREADS = {
    "one": ["Signal"],
    "three": ["Past", "Present", "Future"],
    "cross": ["Heart of the Matter", "Challenge", "Hidden Influence", "Advice", "Likely Outcome"],
    "relationship": ["You", "The Other Side", "The Bond", "Shadow", "Next Step"],
    "celtic": [
        "Present Situation",
        "Crossing Challenge",
        "Root Cause",
        "Recent Past",
        "Conscious Aim",
        "Near Future",
        "Your Power",
        "Outside Influence",
        "Hope or Fear",
        "Likely Outcome",
    ],
}


@dataclass(frozen=True)
class TarotCard:
    id: str
    name: str
    arcana: str
    suit: str | None
    image_path: Path
    upright: str
    reversed: str
    domain: str
    prediction_hint: str
    celebrity: str | None = None


def title_from_file(path: Path) -> str:
    stem = re.sub(r"^\d+-", "", path.stem)
    stem = stem.replace("-existing", "").replace("-", " ")
    return stem.title()


def celebrity_from_major_name(path: Path) -> str | None:
    stem = re.sub(r"^\d+-", "", path.stem)
    parts = stem.split("-")
    known_titles = {"the", "fool", "magician", "high", "priestess", "empress", "emperor", "hierophant",
                    "lovers", "chariot", "strength", "hermit", "wheel", "of", "fortune", "justice",
                    "hanged", "man", "death", "temperance", "devil", "tower", "star", "moon", "sun",
                    "judgement", "world"}
    celeb = [p for p in parts if p not in known_titles]
    return " ".join(celeb).title() if celeb else None


def load_deck(project_root: Path) -> list[TarotCard]:
    bundled_cards = project_root / "assets" / "cards"
    major_dir = bundled_cards / "major"
    minor_dir = bundled_cards / "minor"
    if not major_dir.exists() or not minor_dir.exists():
        raise ValueError('Bundled deck files are missing. Restore the assets/cards folder to use this standalone studio.')
    cards: list[TarotCard] = []

    for path in sorted(major_dir.iterdir()):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or path.name.startswith("_"):
            continue
        number = path.name[:2]
        name, upright, reversed = MAJORS.get(number, (title_from_file(path), "major life theme", "blocked major life theme"))
        cards.append(
            TarotCard(
                id=f"major-{number}",
                name=name,
                arcana="Major",
                suit=None,
                image_path=path,
                upright=upright,
                reversed=reversed,
                domain="fate, identity, major turning points, archetypal pressure",
                prediction_hint="this card sets the spiritual headline for the reading",
                celebrity=celebrity_from_major_name(path),
            )
        )

    for suit_dir in sorted(p for p in minor_dir.iterdir() if p.is_dir()):
        suit = suit_dir.name
        if suit not in SUITS:
            continue
        for path in sorted(suit_dir.iterdir()):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or path.name.startswith("_"):
                continue
            rank_code = path.name[:2]
            rank_name, upright, reversed = RANKS.get(rank_code, (title_from_file(path), "minor theme", "blocked minor theme"))
            suit_title = suit.title()
            cards.append(
                TarotCard(
                    id=f"{suit}-{rank_code}",
                    name=f"{rank_name} of {suit_title}",
                    arcana="Minor",
                    suit=suit_title,
                    image_path=path,
                    upright=f"{upright} through {SUITS[suit]['domain']}",
                    reversed=f"{reversed} around {SUITS[suit]['domain']}",
                    domain=SUITS[suit]["domain"],
                    prediction_hint=SUITS[suit]["prediction"],
                )
            )

    return cards


def local_interpretation(question: str, spread_name: str, dealt_cards: list[dict]) -> str:
    focus = question.strip() or "the querent's current path"
    lines = [
        f"Reading focus: {focus}.",
        f"This {spread_name} spread suggests a symbolic forecast, not a fixed fate.",
        "",
    ]
    upright_count = sum(1 for c in dealt_cards if c["orientation"] == "Upright")
    reversed_count = len(dealt_cards) - upright_count
    if reversed_count > upright_count:
        lines.append("The spread leans reversed, so the message is about blocks, delays, and energy that wants to be turned right-side up.")
    elif upright_count > reversed_count:
        lines.append("The spread leans upright, so the story has momentum and visible paths of action.")
    else:
        lines.append("The spread is evenly split, which points to a choice point: part of the answer is external action, part is inner correction.")
    lines.append("")

    for card in dealt_cards:
        meaning = card["meaning"]
        celeb = f" ({card['celebrity']})" if card.get("celebrity") else ""
        lines.append(f"{card['position']}: {card['name']}{celeb}, {card['orientation']}. {meaning}.")
        lines.append(f"Prediction thread: {card['prediction_hint']}.")

    final_card = dealt_cards[-1]
    lines.extend([
        "",
        f"Overall prediction: the next chapter is shaped most by {final_card['name']} in the {final_card['position']} position. "
        "Expect the situation to reveal its real pattern soon; the best move is to respond to the symbol of the card rather than forcing the outcome.",
    ])
    return "\n".join(lines)


def card_seed_text(card: TarotCard) -> str:
    celeb = f" In this deck, the public figure energy is {card.celebrity}." if card.celebrity else ""
    suit_line = f"The {card.suit} suit points to {card.domain}." if card.suit else f"As a Major Arcana card, it points to {card.domain}."
    return (
        f"{card.name}.{celeb} Upright, it speaks to {card.upright}. "
        f"Reversed, it can show {card.reversed}. {suit_line} "
        f"For a prediction, {card.prediction_hint}."
    )
