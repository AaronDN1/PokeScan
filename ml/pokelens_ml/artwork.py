"""Replaceable artwork embedding network used for metric learning."""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torchvision.models import ResNet18_Weights, resnet18


class ArtworkEmbeddingModel(nn.Module):
    """Produce L2-normalized embeddings rather than fixed card classes."""

    def __init__(self, embedding_size: int = 256, *, pretrained: bool = True) -> None:
        super().__init__()
        backbone = resnet18(weights=ResNet18_Weights.DEFAULT if pretrained else None)
        input_features = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.projection = nn.Linear(input_features, embedding_size)

    def forward(self, images: Tensor) -> Tensor:
        """Return normalized embeddings compatible with cosine similarity."""
        features = self.backbone(images)
        return nn.functional.normalize(self.projection(features), dim=-1)


def batch_hard_triplet_loss(embeddings: Tensor, labels: Tensor, margin: float = 0.2) -> Tensor:
    """Optimize same-card captures together while separating different cards."""
    distances = torch.cdist(embeddings, embeddings)
    same = labels[:, None].eq(labels[None, :])
    different = ~same
    same.fill_diagonal_(False)
    hardest_positive = distances.masked_fill(~same, float("-inf")).max(dim=1).values
    hardest_negative = distances.masked_fill(~different, float("inf")).min(dim=1).values
    valid = torch.isfinite(hardest_positive) & torch.isfinite(hardest_negative)
    return nn.functional.relu(hardest_positive[valid] - hardest_negative[valid] + margin).mean()
