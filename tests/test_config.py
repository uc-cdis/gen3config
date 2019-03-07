import os

import pytest
from yaml import safe_load as yaml_load

from gen3config import Config

CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))


def _assert_expected_cfg(config):
    assert config["TEST_VALUE"] == "some-config"
    assert config["DEFAULT_VALUE_NOT_IN_ACTUAL"] == "DEFAULT_VALUE_NOT_IN_ACTUAL"
    assert not config.get("UNKNOWN_CFG_NOT_IN_DEFAULT")


def test_actual_overrides_default_ignores_unknown():
    """
    Test that the actual config overrides the default values and test that default
    values NOT in the actual config exist.
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    actual_cfg_path = os.path.join(CURRENT_PATH, "actual_cfg/some-config.yaml")
    config = Config(default_cfg_path).load(actual_cfg_path)

    _assert_expected_cfg(config)


def test_search_paths():
    """
    Test that we find the same actual config when providing search paths
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    search_folders = [
        os.path.join(CURRENT_PATH, "no_cfg_folder"),
        os.path.join(CURRENT_PATH, "actual_cfg"),
    ]
    config = Config(default_cfg_path).load(search_folders=search_folders)

    _assert_expected_cfg(config)


def test_search_paths_if_mult_configs():
    """
    Test that we raise exception if there are multiple cfg files in provided folders
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    search_folders = [
        os.path.join(CURRENT_PATH, "no_cfg_folder"),
        os.path.join(CURRENT_PATH, "folder_with_multiple_cfg"),
    ]
    with pytest.raises(Exception):
        Config(default_cfg_path).load(search_folders=search_folders)


def test_search_paths_if_no_config():
    """
    Test that we raise exception if we can't find config in provided folders
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    search_folders = [os.path.join(CURRENT_PATH, "no_cfg_folder")]
    with pytest.raises(Exception):
        Config(default_cfg_path).load(search_folders=search_folders)


@pytest.mark.parametrize("default_cfg_method", ["path", "loaded_yaml"])
def test_force_default_when_not_none(default_cfg_method):
    """
    Test trying to set default value on a key that already has a valid value.
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    actual_cfg_path = os.path.join(CURRENT_PATH, "actual_cfg/some-config.yaml")
    config = Config(default_cfg_path).load(actual_cfg_path)

    if default_cfg_method == "path":
        config.force_default_if_none("TEST_VALUE", default_cfg_path=default_cfg_path)
    elif default_cfg_method == "loaded_yaml":
        default_cfg = yaml_load(open(default_cfg_path))
        config.force_default_if_none("TEST_VALUE", default_cfg=default_cfg)

    # should not have changed anything
    _assert_expected_cfg(config)


@pytest.mark.parametrize("default_cfg_method", ["path", "loaded_yaml"])
def test_force_default_when_none(default_cfg_method):
    """
    Test setting default value on a key that is none
    """
    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    actual_cfg_path = os.path.join(CURRENT_PATH, "actual_cfg/some-config.yaml")
    config = Config(default_cfg_path).load(actual_cfg_path)

    if default_cfg_method == "path":
        config.force_default_if_none(
            "THIS_SHOULD_NOT_BE_NONE", default_cfg_path=default_cfg_path
        )
    elif default_cfg_method == "loaded_yaml":
        default_cfg = yaml_load(open(default_cfg_path))
        config.force_default_if_none("THIS_SHOULD_NOT_BE_NONE", default_cfg=default_cfg)

    assert config["THIS_SHOULD_NOT_BE_NONE"] == "THIS_SHOULD_NOT_BE_NONE"

    _assert_expected_cfg(config)


def test_template_replace():
    """
    Test that the template replace does what it says it does
    """
    default_cfg_path = os.path.join(
        CURRENT_PATH, "default_cfgs/default-template-config.yaml"
    )
    actual_cfg_path = os.path.join(CURRENT_PATH, "template_cfg/template-config.yaml")
    config = Config(default_cfg_path).load(actual_cfg_path)

    # template-config.yaml
    # ---
    # BASE_URL: 'http://localhost/user'
    # OPENID_CONNECT:
    #   fence:
    #     api_base_url: 'http://other_fence/user'
    #     client_kwargs:
    #       redirect_uri: '{{BASE_URL}}/login/fence/login'
    #     authorize_url: '{{api_base_url}}/oauth2/authorize'

    assert (
        config["OPENID_CONNECT"]["fence"]["client_kwargs"]["redirect_uri"]
        == config["BASE_URL"] + "/login/fence/login"
    )

    assert (
        config["OPENID_CONNECT"]["fence"]["authorize_url"]
        == config["OPENID_CONNECT"]["fence"]["api_base_url"] + "/oauth2/authorize"
    )


def test_invalid_template_replace():
    """
    Test that the template replace does what it says it does
    """
    default_cfg_path = os.path.join(
        CURRENT_PATH, "default_cfgs/default-template-config.yaml"
    )
    actual_cfg_path = os.path.join(
        CURRENT_PATH, "invalid_template_cfg/template-config.yaml"
    )
    config = Config(default_cfg_path).load(actual_cfg_path)

    # template-config.yaml
    # ---
    # BASE_URL: 'http://localhost/user'
    # OPENID_CONNECT:
    #   fence:
    #     api_base_url: 'http://other_fence/user'
    #     client_kwargs:
    #       redirect_uri: '{{BASE_URL}}/login/fence/login'
    #     authorize_url: '{{api_base_url}}/oauth2/authorize'
    # THIS_WONT_WORK: '{{api_base_url}}/test'

    assert (
        config["OPENID_CONNECT"]["fence"]["client_kwargs"]["redirect_uri"]
        == config["BASE_URL"] + "/login/fence/login"
    )

    assert (
        config["OPENID_CONNECT"]["fence"]["authorize_url"]
        == config["OPENID_CONNECT"]["fence"]["api_base_url"] + "/oauth2/authorize"
    )

    assert (
        config["THIS_WONT_WORK"]
        != config["OPENID_CONNECT"]["fence"]["api_base_url"] + "/test"
    )


def test_custom_class_with_post_process():
    """
    Test that by inheriting the class and implementing a post process, it actually
    happens
    """

    class CustomConfig(Config):
        def __init__(self, *args, **kwargs):
            super(CustomConfig, self).__init__(*args, **kwargs)
            self.post_process_called = False

        def post_process(self):
            self.post_process_called = True

    default_cfg_path = os.path.join(CURRENT_PATH, "default_cfgs/default-config.yaml")
    actual_cfg_path = os.path.join(CURRENT_PATH, "actual_cfg/some-config.yaml")
    config = CustomConfig(default_cfg_path).load(actual_cfg_path)

    _assert_expected_cfg(config)
    assert config.post_process_called
