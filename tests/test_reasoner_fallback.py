from taxagent.agent.reasoner import Reasoner


class BrokenAgent:
    def run_sync(self, *args, **kwargs):
        raise ConnectionError("model endpoint is down")


def test_reasoner_uses_local_fallback_when_model_is_down():
    reasoner = Reasoner()
    reasoner.agent = BrokenAgent()

    rec, cards = reasoner.answer("I have tuition carryforward. Why is my refund not huge?", tax_year=2025)

    assert cards
    assert rec.answer
    assert rec.required_evidence
    assert rec.source_card_ids
    assert rec.confidence in {"low", "medium"}
    assert "external API" in rec.rationale
