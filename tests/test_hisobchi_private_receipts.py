from src.services.core.finance.handlers import should_process_private_receipt_photo


def test_owner_private_photo_without_finance_marker_is_ignored():
    assert not should_process_private_receipt_photo(is_owner=True, has_photo=True, text="")
    assert not should_process_private_receipt_photo(is_owner=True, has_photo=True, text="Oilaviy rasm")
    assert not should_process_private_receipt_photo(is_owner=True, has_photo=True, text="saqlab qo'y")


def test_owner_private_photo_with_finance_marker_is_processed():
    assert should_process_private_receipt_photo(is_owner=True, has_photo=True, text="/kirim 100000 mijoz")
    assert should_process_private_receipt_photo(is_owner=True, has_photo=True, text="/chiqim 50000 reklama")
    assert should_process_private_receipt_photo(is_owner=True, has_photo=True, text="/chek")
    assert should_process_private_receipt_photo(is_owner=True, has_photo=True, text="#kirim")


def test_non_owner_or_non_photo_is_ignored():
    assert not should_process_private_receipt_photo(is_owner=False, has_photo=True, text="/kirim 100000")
    assert not should_process_private_receipt_photo(is_owner=True, has_photo=False, text="/kirim 100000")
