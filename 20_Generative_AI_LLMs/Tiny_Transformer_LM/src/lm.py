"""Tiny character-level Transformer language model - offline.

Loads a local text corpus, trains a miniature causal (decoder-only) GPT
with hand-built masked multi-head self-attention and learned positional
embeddings, then samples text with temperature / top-k decoding. Local
files only - no network, no tokenizers, no pretrained weights fetched.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch import nn

LOG = logging.getLogger("lm")

MIN_CORPUS_CHARS = 500
MIN_BLOCK = 8
MIN_STEPS = 1


class LmError(RuntimeError):
    """Raised for missing corpora, bad hyperparameters, and sampling errors."""


# --------------------------------------------------------------------------- #
# Character tokenizer
# --------------------------------------------------------------------------- #
class CharTokenizer:
    """Character-level vocabulary built from the corpus itself."""

    def __init__(self, text: str) -> None:
        if not text:
            raise LmError("corpus text is empty")
        self.chars = sorted(set(text))
        self.stoi = {ch: i for i, ch in enumerate(self.chars)}
        self.itos = {i: ch for i, ch in enumerate(self.chars)}

    @property
    def vocab_size(self) -> int:
        return len(self.chars)

    def encode(self, text: str) -> list[int]:
        """Text -> token ids; unknown characters raise LmError."""
        unknown = sorted({ch for ch in text if ch not in self.stoi})
        if unknown:
            raise LmError(
                "character(s) not in vocabulary: "
                + ", ".join(repr(ch) for ch in unknown[:4])
                + (" ..." if len(unknown) > 4 else ""))
        return [self.stoi[ch] for ch in text]

    def decode(self, ids: list[int]) -> str:
        try:
            return "".join(self.itos[int(i)] for i in ids)
        except KeyError as exc:
            raise LmError(f"unknown token id: {exc.args[0]}") from exc


# --------------------------------------------------------------------------- #
# The model: masked self-attention blocks + learned positional encoding
# --------------------------------------------------------------------------- #
class CausalSelfAttention(nn.Module):
    """Multi-head self-attention restricted to earlier positions."""

    def __init__(self, d_model: int, n_head: int, block_size: int) -> None:
        super().__init__()
        if d_model % n_head != 0:
            raise LmError(f"d_model ({d_model}) must be divisible by "
                          f"n_head ({n_head})")
        self.n_head = n_head
        self.d_head = d_model // n_head
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        mask = torch.tril(torch.ones(block_size, block_size, dtype=torch.bool))
        self.register_buffer("mask", mask.view(1, 1, block_size, block_size),
                             persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, steps, channels = x.shape
        q, k, v = self.qkv(x).split(channels, dim=2)
        q = q.view(batch, steps, self.n_head, self.d_head).transpose(1, 2)
        k = k.view(batch, steps, self.n_head, self.d_head).transpose(1, 2)
        v = v.view(batch, steps, self.n_head, self.d_head).transpose(1, 2)

        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.d_head)
        scores = scores.masked_fill(
            ~self.mask[:, :, :steps, :steps], float("-inf"))
        weights = torch.softmax(scores, dim=-1)
        out = (weights @ v).transpose(1, 2).contiguous()
        return self.proj(out.view(batch, steps, channels))


class Block(nn.Module):
    """Pre-norm transformer block: attention + feed-forward, both residual."""

    def __init__(self, d_model: int, n_head: int, block_size: int,
                 dropout: float) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_head, block_size)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model),
            nn.Dropout(dropout),
        )
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.drop(self.attn(self.ln1(x)))
        x = x + self.mlp(self.ln2(x))
        return x


class TinyGPT(nn.Module):
    """Decoder-only mini-GPT: token + positional embeddings, N blocks, logits."""

    def __init__(self, vocab_size: int, block_size: int = 64,
                 d_model: int = 64, n_head: int = 2, n_layer: int = 2,
                 dropout: float = 0.0) -> None:
        super().__init__()
        if vocab_size < 2:
            raise LmError(f"vocab_size must be >= 2, got {vocab_size}")
        if block_size < MIN_BLOCK:
            raise LmError(f"block_size must be >= {MIN_BLOCK}, "
                          f"got {block_size}")
        if n_head < 1:
            raise LmError(f"n_head must be >= 1, got {n_head}")
        if d_model % n_head != 0:
            raise LmError(f"d_model ({d_model}) must be divisible by "
                          f"n_head ({n_head})")
        if n_layer < 1:
            raise LmError(f"n_layer must be >= 1, got {n_layer}")
        if not 0.0 <= dropout < 1.0:
            raise LmError(f"dropout must be in [0, 1), got {dropout}")

        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(block_size, d_model)
        self.blocks = nn.ModuleList(
            [Block(d_model, n_head, block_size, dropout)
             for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        batch, steps = idx.shape
        if steps > self.block_size:
            raise LmError(f"sequence length {steps} exceeds block size "
                          f"{self.block_size}")
        positions = torch.arange(steps, device=idx.device)
        x = self.tok_emb(idx) + self.pos_emb(positions)
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def build_model(vocab_size: int, block_size: int = 64, d_model: int = 64,
                n_head: int = 2, n_layer: int = 2, seed: int = 42,
                dropout: float = 0.0) -> TinyGPT:
    """Seeded construction so initial weights are reproducible."""
    torch.manual_seed(seed)
    return TinyGPT(vocab_size, block_size, d_model, n_head, n_layer, dropout)


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
def load_corpus(path: str | Path) -> str:
    """Read a local corpus file and validate it."""
    source = Path(path)
    if not source.is_file():
        raise LmError(f"file not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LmError(f"could not read {source.name}: {exc}") from exc
    if not text.strip():
        raise LmError(f"corpus is empty: {source.name}")
    if len(text) < MIN_CORPUS_CHARS:
        raise LmError(f"corpus too small: need at least {MIN_CORPUS_CHARS} "
                      f"characters, got {len(text)}")
    LOG.info("loaded %d characters from %s", len(text), source.name)
    return text


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
@dataclass
class LmResult:
    """Trained model plus training history and configuration."""

    model: TinyGPT
    tokenizer: CharTokenizer
    history: list[float]
    steps: int
    block_size: int
    d_model: int
    n_head: int
    n_layer: int
    corpus_chars: int

    @property
    def initial_loss(self) -> float:
        return self.history[0]

    @property
    def final_loss(self) -> float:
        return self.history[-1]

    def sample(self, prompt: str = "", length: int = 200,
               temperature: float = 1.0, top_k: int = 8,
               seed: int = 0) -> str:
        """Autoregressively sample `length` new characters (prompt included)."""
        if length < 1:
            raise LmError(f"length must be >= 1, got {length}")
        if not math.isfinite(temperature) or temperature <= 0:
            raise LmError(f"temperature must be > 0, got {temperature}")
        if top_k < 1:
            raise LmError(f"top_k must be >= 1, got {top_k}")

        ids = self.tokenizer.encode(prompt)          # validates OOV chars
        if len(ids) > self.model.block_size:
            raise LmError(f"prompt of {len(ids)} tokens exceeds block size "
                          f"{self.model.block_size}")
        seeded = not ids
        if seeded:
            # an empty prompt needs one seed character, which counts towards
            # the requested output length
            ids = [0]
            steps = max(0, length - 1)
        else:
            steps = length

        idx = torch.tensor([ids], dtype=torch.long)
        generator = torch.Generator().manual_seed(seed)
        self.model.eval()
        with torch.no_grad():
            for _ in range(steps):
                context = idx[:, -self.model.block_size:]
                logits = self.model(context)[0, -1] / temperature
                k = min(top_k, logits.numel())
                cutoff = torch.topk(logits, k).values[-1]
                logits = logits.masked_fill(logits < cutoff, float("-inf"))
                probs = F.softmax(logits, dim=-1)
                nxt = torch.multinomial(probs, 1,
                                        generator=generator).view(1, 1)
                idx = torch.cat([idx, nxt], dim=1)
        return self.tokenizer.decode(idx[0].tolist())

    def to_dict(self) -> dict[str, Any]:
        tail = self.history[-min(10, len(self.history)):]
        return {
            "corpus_chars": self.corpus_chars,
            "vocab_size": self.tokenizer.vocab_size,
            "steps": self.steps,
            "block_size": self.block_size,
            "d_model": self.d_model,
            "n_head": self.n_head,
            "n_layer": self.n_layer,
            "initial_loss": round(self.initial_loss, 4),
            "final_loss": round(self.final_loss, 4),
            "mean_tail_loss": round(sum(tail) / len(tail), 4),
        }


def train_lm(text: str, steps: int = 300, batch_size: int = 32,
             block_size: int = 32, lr: float = 3e-3, d_model: int = 64,
             n_head: int = 2, n_layer: int = 2, seed: int = 42) -> LmResult:
    """Train the mini-GPT on a raw text corpus (fully seeded, CPU only)."""
    if steps < MIN_STEPS:
        raise LmError(f"steps must be >= {MIN_STEPS}, got {steps}")
    if batch_size < 1:
        raise LmError(f"batch_size must be >= 1, got {batch_size}")
    if block_size < MIN_BLOCK:
        raise LmError(f"block_size must be >= {MIN_BLOCK}, got {block_size}")
    if not math.isfinite(lr) or lr <= 0:
        raise LmError(f"lr must be > 0, got {lr}")
    if not text or len(text) < MIN_CORPUS_CHARS:
        raise LmError(f"corpus must have at least {MIN_CORPUS_CHARS} "
                      f"characters, got {len(text or '')}")
    if len(text) <= block_size + 1:
        raise LmError(f"corpus of {len(text)} characters is too short for "
                      f"block_size {block_size}")

    tokenizer = CharTokenizer(text)
    data = torch.tensor(tokenizer.encode(text), dtype=torch.long)

    model = build_model(tokenizer.vocab_size, block_size=block_size,
                        d_model=d_model, n_head=n_head, n_layer=n_layer,
                        seed=seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    generator = torch.Generator().manual_seed(seed)

    history: list[float] = []
    model.train()
    for _ in range(steps):
        starts = torch.randint(len(data) - block_size - 1,
                               (batch_size,), generator=generator)
        x = torch.stack([data[i:i + block_size] for i in starts])
        y = torch.stack([data[i + 1:i + 1 + block_size] for i in starts])
        optimizer.zero_grad()
        loss = F.cross_entropy(model(x).reshape(-1, tokenizer.vocab_size),
                               y.reshape(-1))
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))

    model.eval()
    result = LmResult(model=model, tokenizer=tokenizer, history=history,
                      steps=steps, block_size=block_size, d_model=d_model,
                      n_head=n_head, n_layer=n_layer,
                      corpus_chars=len(text))
    LOG.info("trained %d steps, loss %.3f -> %.3f",
             steps, result.initial_loss, result.final_loss)
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: LmResult) -> str:
    """Human-readable training report used by the CLI and the demo."""
    head = result.history[:5]
    tail = result.history[-5:]
    lines = [
        "TINY TRANSFORMER LM (character-level mini-GPT)",
        "=" * 68,
        f"Corpus      : {result.corpus_chars} characters, "
        f"vocab {result.tokenizer.vocab_size} (character-level)",
        f"Model       : d_model {result.d_model}, {result.n_head} heads, "
        f"{result.n_layer} layers, block {result.block_size}",
        f"Training    : {result.steps} steps, AdamW, batch sampling",
        f"Loss head   : " + " ".join(f"{v:.3f}" for v in head),
        f"Loss tail   : " + " ".join(f"{v:.3f}" for v in tail),
        f"Final loss  : {result.final_loss:.3f} "
        f"(initial {result.initial_loss:.3f}, "
        f"drop {result.initial_loss - result.final_loss:.3f})",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus.txt"
DEMO_PROMPT = "The "
DEMO_STEPS = 150
DEMO_LENGTH = 160


def run_demo(corpus_path: Path | None = None) -> int:
    """Train the mini-GPT on the bundled corpus and sample text - offline."""
    print("=" * 68)
    print(" TINY TRANSFORMER LM - offline demo")
    print(" Bundled corpus, CPU training, no downloads, no network.")
    print("=" * 68)

    source = corpus_path or DEMO_CORPUS
    text = load_corpus(source)
    print(f"\nLoaded {len(text)} characters from {source.name}")

    result = train_lm(text, steps=DEMO_STEPS, batch_size=32,
                      block_size=32, lr=3e-3, d_model=64, n_head=2,
                      n_layer=2, seed=42)
    print()
    print(render_report(result))

    generated = result.sample(DEMO_PROMPT, length=DEMO_LENGTH,
                              temperature=0.8, top_k=8, seed=7)
    print(f"\nGenerated from prompt {DEMO_PROMPT!r}:")
    for line in _wrap(generated, 64):
        print(f"  {line}")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert generated.startswith(DEMO_PROMPT), "must start with the prompt"
    assert len(generated) == len(DEMO_PROMPT) + DEMO_LENGTH, \
        "wrong generated length"
    assert set(generated) <= set(result.tokenizer.chars), \
        "generated text left the vocabulary"
    assert result.final_loss < result.initial_loss - 0.05, \
        "loss did not fall"
    assert result.final_loss < 2.5, "final loss too high"
    assert len(result.history) == DEMO_STEPS

    # deterministic re-run: identical losses and identical samples
    again = train_lm(text, steps=DEMO_STEPS, batch_size=32, block_size=32,
                     lr=3e-3, d_model=64, n_head=2, n_layer=2, seed=42)
    assert again.history == result.history, "training is not deterministic"
    assert again.sample(DEMO_PROMPT, length=DEMO_LENGTH, temperature=0.8,
                        top_k=8, seed=7) == generated, \
        "sampling is not deterministic"

    # seed sensitivity: a different sampling seed changes the text
    other = result.sample(DEMO_PROMPT, length=DEMO_LENGTH, temperature=0.8,
                          top_k=8, seed=8)
    assert other != generated, "sampling seed had no effect"

    print(f"\nCross-checks OK: loss {result.initial_loss:.3f} -> "
          f"{result.final_loss:.3f}, {len(generated)} chars in-vocab, "
          f"deterministic re-run, seed-sensitive sampling")
    print("\nDemo completed successfully.")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap for demo output (no textwrap dependency quirks)."""
    lines, current = [], ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
