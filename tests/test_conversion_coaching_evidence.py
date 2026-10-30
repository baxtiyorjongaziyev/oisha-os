"""Synthetic evidence validation cases; no real customer data."""
from src.services.call_analytics.conversion_coaching import validated_coaching, transcript_quality


def sample(quote):
    return {'coaching_evidence': [{'skill': 'next_step', 'quote': quote,
            'advice': 'Aniq vaqtni kelishing.', 'better_phrase': 'Qachon qulay?'}]}


def test_invented_or_short_quote_rejected():
    assert validated_coaching(sample('Bu gap transkriptda yoq'), 'Boshqa suhbat') == []
    assert validated_coaching(sample('Alo'), 'Alo') == []


def test_supported_coaching_survives():
    text = 'Menejer: Men sizga keyinroq chiqaman.'
    result = validated_coaching(sample('Men sizga keyinroq chiqaman.'), text)
    assert len(result) == 1
    assert result[0]['skill'] == 'next_step'


def test_malformed_model_data_does_not_crash():
    for raw in (None, 'text', [None, 3, {}], [{'skill': []}]):
        assert validated_coaching({'coaching_evidence': raw}, 'Suhbat') == []


def test_transcript_limitations_are_explicit():
    assert transcript_quality('Suhbat\n...[qisqartirildi]')['truncated']
    assert transcript_quality('No audio file was provided')['status'] == 'unusable'
    assert not transcript_quality('Menejer: Assalomu alaykum')['speaker_identity_verified']


def test_exact_quote_does_not_authorize_unverified_guarantee():
    text = 'Men sizga keyinroq chiqaman.'
    data = sample(text)
    data['coaching_evidence'][0]['better_phrase'] = 'Xarajat ikki barobar oshadi, biz kafolat beramiz.'
    assert validated_coaching(data, text) == []
