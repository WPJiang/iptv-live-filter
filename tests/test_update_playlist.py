from scripts import update_playlist


def test_main_returns_success_for_empty_placeholder():
    assert update_playlist.main() == 0
