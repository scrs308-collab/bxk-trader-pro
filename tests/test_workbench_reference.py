from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from bxk_app.routes.workbench_preview import spx_reference


def test_current_spx_reference_preserves_source_and_timestamp():
    stamp = datetime.now(timezone.utc).isoformat()
    broker = Mock()
    broker.get_index_quote.return_value = {'symbol': 'SPX', 'last': '7741.25', 'updated-at': stamp}
    result = spx_reference(broker)
    assert result['price'] == 7741.25
    assert result['timestamp'] == stamp
    assert result['price_field'] == 'last'
    assert result['user_scoped'] is True
    assert result['order_submission_available'] is False
    broker.get_index_quote.assert_called_once_with('SPX')


@pytest.mark.parametrize('change', [
    {'symbol': 'SPY'}, {'last': 'nan'}, {'last': 'inf'},
    {'last': None, 'close': '7700'}, {'updated-at': None},
    {'updated-at': 'not-a-date'},
    {'updated-at': (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()},
    {'updated-at': (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()},
])
def test_unusable_spx_reference_blocks_instead_of_using_close(change):
    broker = Mock()
    broker.get_index_quote.return_value = {
        'symbol': 'SPX', 'last': '7741.25',
        'updated-at': datetime.now(timezone.utc).isoformat(),
    } | change
    with pytest.raises(HTTPException) as error:
        spx_reference(broker)
    assert error.value.status_code == 503
