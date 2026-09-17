"""Framework tests — testing Monid, Paper2Agent, RSIAgent, Seesaw patterns against Muse.

These tests import the wire layer from qprivately and test each adapter
against the live LLM (Muse on OpenCode Go). Every test logs to runs/.

Code flows: qpbot -> pq. pq never edits qpbot.
"""
