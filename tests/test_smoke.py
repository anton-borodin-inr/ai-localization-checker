import l10n_checker


def test_package_imports():
    assert isinstance(l10n_checker.__version__, str)
