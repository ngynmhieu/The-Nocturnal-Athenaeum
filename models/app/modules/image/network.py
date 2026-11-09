"""SRVGGNetCompact — the compact VGG-style SR net behind Real-ESRGAN anime-video.

The layer layout (a single `body` ModuleList) matches the upstream implementation
exactly so the published `params` state dict loads without remapping.
"""
import torch
import torch.nn.functional as F
from torch import nn


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_feat: int = 64, num_conv: int = 16, upscale: int = 4):
        super().__init__()
        self.upscale = upscale
        body = [nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        # Residual: the net only learns detail on top of a nearest-neighbour upscale.
        return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")
