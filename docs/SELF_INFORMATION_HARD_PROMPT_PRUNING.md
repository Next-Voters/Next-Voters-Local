# Static Self-Information

## Overview

Static self-information is a scoring mechanism used in **hard prompt compression** to decide which tokens in a prompt are worth keeping and which can be dropped. Each token receives a numerical score representing how informative it is. A compression algorithm then ranks tokens by score and keeps only the top-performing ones, producing a shorter prompt that preserves the most important content.

## Foundations: Claude Shannon and Information Theory

The method is built directly on **Claude Shannon's 1948 paper, *A Mathematical Theory of Communication***, which established the field of information theory. The core idea from that work: **information equals surprise**. A token is "informative" to the extent that observing it was unexpected.

Shannon formalized this with the self-information formula:

```
I(t) = -log₂ p(t)
```

- `p(t)` is the probability of the token.
- The logarithm converts a probability into an additive surprise score (so information from independent tokens can be summed).
- The negative sign flips the output so rare tokens get high scores and common tokens get low scores.
- Base 2 means the score is measured in **bits**.

This formula is not specific to prompt compression. It is the standard definition of information content used across information theory, data compression, and communication systems. Static self-information applies this formula to a particular kind of probability estimate (see below).

## How Static Self-Information Works

The pipeline has two steps.

### Step 1: Unigram Frequency

Build a large offline reference corpus. In the paper this documentation is based on, the corpus comprises Wikipedia, ShareGPT conversations, and arXiv articles. Then compute the unigram frequency of every token:

```
f(t) = count of t in corpus / total tokens in corpus
```

This produces a proportion between 0 and 1 representing how often token `t` appears in the reference corpus. The reference corpus — not the prompt itself — is the yardstick against which rarity is measured.

### Step 2: Self-Information Score

Feed the frequency into Shannon's formula:

```
I(t) = -log₂ f(t)
```

Rare tokens (small `f(t)`) produce large scores. Common tokens produce small scores. The score is **static** in that it is a fixed property of the token relative to the corpus — the same token gets the same score regardless of where it appears or what surrounds it.

## Compression via Top-k Selection

Once every token in a prompt has a self-information score, the compression step is straightforward:

1. Sort tokens by score, highest to lowest.
2. Apply a **top-k cutoff**, where `k` is the compression budget (how many tokens to keep).
3. Retain the top `k` scoring tokens. Everything below the cutoff is dropped.
4. Reassemble the surviving tokens in their original order to form the compressed prompt.

The compression budget controls the cutoff:

- **Larger budget** → higher `k` → more low-score tokens survive.
- **Smaller budget** → lower `k` → only the highest-scoring tokens remain.

The scoring mechanism itself does not remove tokens. Removal is a consequence of ranking combined with the budget.

## Why It Works: The LM Reconstruction Argument

The compressed prompt is consumed by a downstream language model, not a human. This matters because **LMs can reconstruct predictable tokens from context.** Common words like articles, prepositions, and conjunctions are so thoroughly represented in LM training data that the model can mentally fill them back in when they are missing.

Rare tokens — proper nouns, technical terms, specific numbers — cannot be reconstructed this way. Once dropped, they are gone. Static self-information preserves exactly these high-value tokens while discarding the ones the LM can recover on its own.

## Advantages

- **Computationally cheap.** Token frequencies are computed once from the offline corpus and stored in a lookup table. Scoring any future prompt is an O(1) operation per token — no model inference required.
- **Easy to implement.** The entire method is a frequency count plus a logarithm.
- **Protects rare content.** Named entities, technical vocabulary, and domain-specific terms reliably score high and survive compression.
- **Standard units.** Scores are in bits, making them directly comparable to other information-theoretic methods.

## Limitations

The central weakness of static self-information is that **it is context-blind.** The score for a token depends only on its corpus-wide frequency, not on its role in the sentence it appears in. This produces two failure modes:

1. **Common tokens that carry structural meaning get culled.** Articles, prepositions, and pronouns often score low but may be doing real grammatical or semantic work in a specific sentence. Removing them can degrade tightly-worded or precise text (legal phrasing, instructions, contracts).

2. **The same token gets the same score in every context.** A polysemous word like "bank" receives identical scores whether the prompt is about rivers or finance. The method cannot distinguish between contexts where a token is redundant and contexts where it is essential.

These limitations are addressed by **dynamic self-information**, which uses a language model to compute context-aware probabilities. That is a separate method documented elsewhere.

## Summary

Static self-information applies Shannon's surprise formula (`I(t) = -log₂ p(t)`) to unigram frequencies computed from a fixed reference corpus. It scores tokens by how rare they are in general, then uses a top-k cutoff to keep the most informative ones. It is cheap, easy, and effective for protecting rare content — but it cannot see context, so it sometimes drops tokens that are common in general but important in the specific sentence they appear in.
