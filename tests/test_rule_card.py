from taxagent.knowledge import load_default_store


def test_default_rule_cards_load_as_utf8():
    store = load_default_store()

    ids = {card.id for card in store.cards}

    assert "qc_ramq_drug_premium_v1" in ids
    assert "ca_tuition_carryforward_v1" in ids


def test_rule_card_retrieval_ignores_low_signal_words():
    store = load_default_store()

    cards = store.retrieve("I have tuition carryforward. Why is my refund not huge?", tax_year=2025)

    assert cards
    assert cards[0].id == "ca_tuition_carryforward_v1"
    assert "qc_ramq_drug_premium_v1" not in {card.id for card in cards}
