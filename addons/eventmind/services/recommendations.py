from datetime import datetime
import math
import re

from odoo import fields


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_MODEL = None
_MODEL_LOAD_FAILED = False


def _split_csv(value):
    return [item.strip() for item in (value or "").split(",") if item and item.strip()]


def _event_text(event):
    parts = [
        event.name or "",
        event.category or "",
        event.description or "",
        event.location or "",
        event.price or "",
        event.age_limit or "",
    ]
    return ". ".join(part for part in parts if part)


def _tokenize(text):
    return set(re.findall(r"[\w]+", (text or "").lower(), flags=re.UNICODE))


def _cosine(left, right):
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    common = set(left) & set(right)
    return sum(left[key] * right[key] for key in common) / (left_norm * right_norm)


def _weighted_bow(texts_with_weights):
    vector = {}
    for text, weight in texts_with_weights:
        for token in _tokenize(text):
            vector[token] = vector.get(token, 0.0) + weight
    return vector


def _try_get_model():
    global _MODEL, _MODEL_LOAD_FAILED
    if _MODEL or _MODEL_LOAD_FAILED:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        _MODEL_LOAD_FAILED = True
        return None

    try:
        _MODEL = SentenceTransformer(MODEL_NAME)
    except Exception:
        _MODEL_LOAD_FAILED = True
        return None
    return _MODEL


class EventRecommendationEngine:
    def __init__(self, top_k=6):
        self.top_k = top_k

    def recommend_for_user(self, user, events):
        events = events.exists()
        candidates = events.filtered(lambda event: event.status != "cancelled" and self._is_upcoming(event))
        if not candidates:
            return []

        profile_items = self._build_profile_items(user)
        if not profile_items:
            return []

        selected_ids = set(user.sudo().personal_event_ids.ids)
        candidates = candidates.filtered(lambda event: event.id not in selected_ids)
        if not candidates:
            return []

        model = _try_get_model()
        if model:
            try:
                scored = self._rank_with_embeddings(model, profile_items, candidates)
            except Exception:
                scored = self._rank_with_keywords(profile_items, candidates)
        else:
            scored = self._rank_with_keywords(profile_items, candidates)

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: self.top_k]

    def _build_profile_items(self, user):
        profile = user.sudo().partner_id
        items = [(interest, 2.0) for interest in _split_csv(profile.em_interests)]

        for event in user.sudo().personal_event_ids:
            items.append((_event_text(event), 3.0))

        return items

    def _rank_with_embeddings(self, model, profile_items, events):
        import numpy as np

        profile_texts = [text for text, _weight in profile_items]
        profile_weights = np.array([weight for _text, weight in profile_items], dtype=np.float32)
        profile_embeddings = model.encode(
            profile_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        user_vector = np.average(profile_embeddings, axis=0, weights=profile_weights)
        user_norm = np.linalg.norm(user_vector)
        if user_norm:
            user_vector = user_vector / user_norm

        event_texts = [_event_text(event) for event in events]
        event_embeddings = model.encode(
            event_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        similarities = np.dot(event_embeddings, user_vector)

        result = []
        for index, event in enumerate(events):
            semantic_score = float(similarities[index])
            result.append(self._build_item(event, semantic_score))
        return result

    def _rank_with_keywords(self, profile_items, events):
        profile_vector = _weighted_bow(profile_items)
        return [
            self._build_item(event, _cosine(profile_vector, _weighted_bow([(_event_text(event), 1.0)])))
            for event in events
        ]

    def _build_item(self, event, relevance):
        freshness = self._freshness_score(event)
        popularity = min((event.attendee_count or 0) / 20.0, 1.0)
        final_score = 0.78 * relevance + 0.14 * freshness + 0.08 * popularity
        return {
            "event": event,
            "score": round(max(final_score, 0.0), 4),
            "relevance": round(max(relevance, 0.0), 4),
            "freshness": round(freshness, 4),
            "popularity": round(popularity, 4),
            "reason": self._reason(event, relevance, freshness),
        }

    @staticmethod
    def _is_upcoming(event):
        start = fields.Datetime.to_datetime(event.date_start)
        if not start:
            return False
        return start >= datetime.utcnow()

    @staticmethod
    def _freshness_score(event):
        start = fields.Datetime.to_datetime(event.date_start)
        if not start:
            return 0.0

        now = datetime.utcnow()
        days = (start - now).days
        if days < 0:
            return 0.0
        if days <= 7:
            return 1.0
        if days <= 30:
            return 0.75
        if days <= 90:
            return 0.45
        return 0.2

    @staticmethod
    def _reason(event, relevance, freshness):
        reasons = []
        if relevance >= 0.65:
            reasons.append("matches your interests")
        elif relevance >= 0.35:
            reasons.append("close to your profile")
        else:
            reasons.append("potentially relevant")

        if event.category:
            reasons.append(event.category)
        if freshness >= 0.75:
            reasons.append("soon")
        if event.location:
            reasons.append(event.location)
        return ", ".join(reasons)
