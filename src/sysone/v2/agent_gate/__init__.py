"""Software go/no-go for an inline AI-agent command gate (Modbus pumping station).

plant.py     -- true plant dynamics with hidden per-episode parameters + hazard labeler
policies.py  -- gate policies (none, static allow-lists, stateful rules, stateful predictive)
sources.py   -- command proposers (competent operator, fault/attack families, LLM agent)
"""
