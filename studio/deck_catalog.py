"""Named artwork collections sharing the same canonical tarot meanings."""
from dataclasses import replace
from pathlib import Path

from .tarot_rules import MAJORS, RANKS, SUITS, load_deck


DECKS = {
    'celebrity': {'label': 'StarPower Celebrity', 'count': 78},
    'esoteric-minimal': {'label': 'Esoteric Minimal', 'count': 78},
    'storybook-cartoon': {'label': 'Storybook Cartoon', 'count': 78},
}

CARD_IDS = tuple(f'major-{n}' for n in MAJORS) + tuple(f'{suit}-{rank}' for suit in SUITS for rank in RANKS)


def variant_path(root: Path, key: str, number: str) -> Path:
    if not isinstance(key, str) or key not in DECKS or key == 'celebrity':
        raise ValueError('Unknown artwork collection or card.')
    card_id = f'major-{number}' if number in MAJORS else number
    if card_id not in CARD_IDS:
        raise ValueError('Unknown artwork collection or card.')
    suit, rank = card_id.split('-')
    base = root / 'assets' / 'cards' / 'variants' / key
    return base / f'{rank}.png' if suit == 'major' else base / suit / f'{rank}.png'


def deck_options(root: Path) -> list[dict]:
    return [dict(id=key, **info,
                 ready=key == 'celebrity' or all(variant_path(root, key, card_id).is_file() for card_id in CARD_IDS))
            for key, info in DECKS.items()]


def get_deck(root: Path, key: str = 'celebrity', original=None):
    if not isinstance(key, str) or key not in DECKS:
        raise ValueError('Unknown deck.')
    original = load_deck(root) if original is None else original
    if key == 'celebrity':
        return original
    cards = {card.id: card for card in original}
    if any(card_id not in cards or not variant_path(root, key, card_id).is_file() for card_id in CARD_IDS):
        raise ValueError('This deck is still being prepared.')
    return [replace(cards[card_id], image_path=variant_path(root, key, card_id), celebrity=None) for card_id in CARD_IDS]


def artwork_url(card_id: str, key: str = 'celebrity') -> str:
    if key not in DECKS:
        raise ValueError('Unknown deck.')
    return f'/cards/{card_id}' + (f'?deck={key}' if key != 'celebrity' else '')
