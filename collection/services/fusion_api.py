from .http import configured, post_json


def score_fusion(features):
    return post_json(
        configured("FUSION_SCORE_URL"),
        configured("FUSION_API_KEY"),
        {"features": features},
        "Multimodal fusion",
    )