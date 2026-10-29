import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.core.brain.client_qa import ClientQAError, answer_client_question


@pytest.mark.parametrize('answer', ['', 'Shaxboz aka bilan qayta gaplasha oldingizmi? ' * 8])
def test_invalid_qa_reply_is_rejected(answer):
    context = SimpleNamespace(display_name='Synthetic client', format_prompt_block=lambda: 'Synthetic context')
    aggregate = SimpleNamespace(gather=AsyncMock(return_value=context))
    router = SimpleNamespace(generate_text=AsyncMock(return_value=SimpleNamespace(text=answer)))
    with patch('src.services.core.brain.client_qa.ClientContextAggregator', return_value=aggregate), patch('src.services.utils.free_ai_router.get_free_ai_router', return_value=router):
        with pytest.raises(ClientQAError):
            asyncio.run(answer_client_question('Synthetic question?', amocrm=object(), lead_id=1))
