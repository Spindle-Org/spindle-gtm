"""Configuration-driven qualification & policy engine.

Deterministic scoring/classification first (config/*.yaml validated by schemas.py);
an LLM is consulted only for genuinely ambiguous titles and must explain its decision.
No protected characteristics or sensitive personal information are used anywhere.
"""
