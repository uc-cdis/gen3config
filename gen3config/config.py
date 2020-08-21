"""
Configuration class for handling configs with a given default.

If you need custom functionality or need to apply post_processing to parsed config,
simply extend this class.

Example:

```
class FenceConfig(Config):
    def __init__(self, *args, **kwargs):
        super(FenceConfig, self).__init__(*args, **kwargs)

    def post_process(self):
        # allow authlib traffic on http for development if enabled. By default
        # it requires https.
        #
        # NOTE: use when fence will be deployed in such a way that fence will
        #       only receive traffic from internal clients, and can safely use HTTP
        if (
            self._configs.get("AUTHLIB_INSECURE_TRANSPORT")
            and "AUTHLIB_INSECURE_TRANSPORT" not in os.environ
        ):
            os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "true"

        # if we're mocking storage, ignore the storage backends provided
        # since they'll cause errors if misconfigured
        if self._configs.get("MOCK_STORAGE", False):
            self._configs["STORAGE_CREDENTIALS"] = {}

        cirrus.config.config.update(**self._configs.get("CIRRUS_CFG", {}))
```


Recommended use:

- Create a `config-default.yaml` and `config.py` in the top-level folder your app
- Inside `config-default.yaml` add keys and reasonable default values
- Inside `config.py`, create a class that inherits from this Config class
    - See above example
- Add a final line to your `config.py` that instantiates your custom class:
    - Ensure that you provide the default config path
        - If placed in same directory as `config.py` you can use something like:
            ```
            default_cfg_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config-default.yaml"
            )
            config = FenceConfig(default_cfg_path)
            ```
- Import your instaniated object whenever you need to get configuration
    - Example: `from fence.config import config`
- Load in application configuration during init of your app
    - Example: `config.load('path/to/fence-config.yaml')`
- Now you can safely access anything that was in your `config-default.yaml` from this
  object as if it were a dictionary
    - Example: `storage_creds = config["STORAGE_CREDENTIALS"]`
    - Example: `if config["SOME_BOOLEAN"]: ...`
    - Example: `nested_value = config["TOP_LEVEL"]["nested"]
- And of course you can import that into any file you want and will have access to
  keys/values
    - Example: `from fence.config import config`

"""
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import glob
from yaml import safe_load as yaml_load
from yaml.scanner import ScannerError
from jinja2 import Template, TemplateSyntaxError
import six

from cdislogging import get_logger

from gen3config.errors import NotFoundError, ParsingError

logger = get_logger(__name__, log_level="info")


class Config(dict):
    """
    Configuration singleton that's instantiated on module load.
    Allows updating from a config file by using .update()
    """

    def __init__(self, default_cfg_path):
        self._configs = {}
        self.default_cfg_path = default_cfg_path

        logger.debug("Checking if provided cfg path is an actual file...")
        if not os.path.isfile(default_cfg_path):
            raise FileNotFoundError(
                "Default configuration file provided {} does not exist.".format(
                    default_cfg_path
                )
            )

        logger.debug("Attempting to parse provided cfg as yaml file...")
        try:
            yaml_load(open(self.default_cfg_path))
        except Exception as exc:
            logger.exception(exc)
            raise ParsingError(
                "Could not parse provided file {} as YAML. See logs for details.".format(
                    default_cfg_path
                )
            )

    def get(self, key, default=None):
        return self._configs.get(key, default)

    def set(self, key, value):
        self._configs.__setitem__(key, value)

    def setdefault(self, key, default=None):
        self._configs.setdefault(key, default)

    def __setitem__(self, key, value):
        self._configs.__setitem__(key, value)

    def __contains__(self, key):
        return key in self._configs

    def __iter__(self):
        for key, value in six.iteritems(self._configs):
            yield key, value

    def __getitem__(self, key):
        return self._configs[key]

    def __delitem__(self, key):
        del self._configs[key]

    def __len__(self):
        return len(self._configs)

    def __str__(self):
        return str(self._configs)

    def update(self, *args, **kwargs):
        """
        update configuration properties

        support passing dictionary or keyword args
        """
        if len(args) > 1:
            raise TypeError(
                "update expected at most 1 arguments, got {}".format(len(args))
            )

        if args:
            self._configs.update(dict(args[0]))

        self._configs.update(kwargs)

    def load(self, config_path=None, search_folders=None, file_name=None):
        if not config_path and not search_folders:
            raise AttributeError(
                "Cannot find configuration with given information. "
                "You must either provide `search_folders` arg so load knows where to "
                "look OR provide `config_path` as full path to config."
            )

        config_path = config_path or get_config_path(search_folders, file_name)

        if config_path:
            self.load_configuration_file(config_path)

        self.post_process()

        return self

    def load_configuration_file(self, provided_cfg_path):
        logger.info("Opening default configuration...")
        config = yaml_load(open(self.default_cfg_path))

        logger.info("Applying configuration: {}".format(provided_cfg_path))

        # treat cfg as template and replace vars, returning an updated dict
        provided_configurations = nested_render(
            yaml_load(open(provided_cfg_path)), {}, {}
        )

        # only update known configuration values. In the situation
        # where the provided config does not have a certain value,
        # the default will be used.
        common_keys = {
            key: value
            for (key, value) in six.iteritems(config)
            if key in provided_configurations
        }
        keys_not_provided = {
            key: value
            for (key, value) in six.iteritems(config)
            if key not in provided_configurations
        }
        keys_to_update = {
            key: value
            for (key, value) in six.iteritems(provided_configurations)
            if key in common_keys
        }
        unknown_keys = {
            key: value
            for (key, value) in six.iteritems(provided_configurations)
            if key not in common_keys
        }

        config.update(keys_to_update)

        if keys_not_provided:
            logger.warning(
                "Did not provide key(s) {} in {}. Will be set to default value(s) from {}.".format(
                    keys_not_provided.keys(), provided_cfg_path, self.default_cfg_path
                )
            )

        if unknown_keys:
            logger.warning(
                "Unknown key(s) {} found in {}. Will be ignored.".format(
                    unknown_keys.keys(), provided_cfg_path
                )
            )

        self._configs.update(config)

    def post_process(self):
        """
        Do some post processing to the configuration (set env vars if necessary,
        do more complex modifications/changes to vars, etc.)

        Called after loading the configuration and doing the template-replace.
        """
        pass

    def force_default_if_none(self, key, default_cfg=None, default_cfg_path=None):
        """
        Set the key in the configuration to the default value if it either
            1) doesn't exist (this is mostly for backwards-compatibility with previous
               configuration methods)
            2) is None
        """
        default_cfg = default_cfg or yaml_load(open(default_cfg_path))

        if key not in self._configs or self._configs[key] is None:
            self._configs[key] = default_cfg.get(key)


def nested_render(cfg, fully_rendered_cfgs, replacements):
    """
    Template render the provided cfg by recurisevly replacing {{var}}'s which values
    from the current "namespace".

    The nested config is treated like nested namespaces where the inner variables
    are only available in current block and further nested blocks.

    Said the opposite way: the namespace with available vars that can be used
    includes the current block's vars and parent block vars.

    This means that you can do replacements for top-level
    (global namespaced) config vars anywhere, but you can only use inner configs within
    that block or further nested blocks.

    An example is worth a thousand words:

        ---------------------------------------------------------------------------------
        fence-config.yaml
        --------------------------------------------------------------------------------
        BASE_URL: 'http://localhost/user'
        OPENID_CONNECT:
          fence:
            api_base_url: 'http://other_fence/user'
            client_kwargs:
              redirect_uri: '{{BASE_URL}}/login/fence/login'
            authorize_url: '{{api_base_url}}/oauth2/authorize'
        THIS_WONT_WORK: '{{api_base_url}}/test'
        --------------------------------------------------------------------------------

    "redirect_uri" will become "http://localhost/user/login/fence/login"
        - BASE_URL is in the global namespace so it can be used in this nested cfg

    "authorize_url" will become "http://other_fence/user/oauth2/authorize"
        - api_base_url is in the current namespace, so it is available

    "THIS_WONT_WORK" will become "/test"
        - Why? api_base_url is not in the current namespace and so we cannot use that
          as a replacement. the configuration (instead of failing) will replace with
          an empty string

    Args:
        cfg (TYPE): Description
        fully_rendered_cfgs (TYPE): Description
        replacements (TYPE): Description

    Returns:
        dict: Configurations with template vars replaced
    """
    if isinstance(cfg, dict):
        for key, value in six.iteritems(cfg):
            replacements.update(cfg)
            fully_rendered_cfgs[key] = {}
            fully_rendered_cfgs[key] = nested_render(
                value,
                fully_rendered_cfgs=fully_rendered_cfgs[key],
                replacements=replacements,
            )
            # new namespace, remove current vars (no longer available as replacements)
            for old_cfg, value in six.iteritems(cfg):
                replacements.pop(old_cfg, None)

        return fully_rendered_cfgs
    else:
        # it's not a dict, so lets try to render it. But only if it's
        # truthy (which means there's actually something to replace)
        if cfg:
            try:
                t = Template(str(cfg))
                rendered_value = t.render(**replacements)
            except TemplateSyntaxError:
                rendered_value = cfg

            try:
                cfg = yaml_load(rendered_value)
            except ScannerError:
                # it's not loading into yaml, so let's assume it's a string with special
                # chars such as: {}[],&*#?|:-<>=!%@\)
                #
                # in YAML, we have to "quote" a string with special chars.
                #
                # since yaml_load isn't loading from a file, we need to wrap the Python
                # str in actual quotes.
                cfg = yaml_load('"{}"'.format(rendered_value))

        return cfg


def get_config_path(search_folders, file_name="*config.yaml"):
    """
    Return the path of a single configuration file ending in config.yaml
    from one of the search folders.

    NOTE: Will return the first match it finds. If multiple are found,
    this will error out.
    """
    possible_configs = []
    file_name = file_name or "*config.yaml"

    for folder in search_folders:
        config_path = os.path.join(folder, file_name)
        possible_files = glob.glob(config_path)
        possible_configs.extend(possible_files)

    if len(possible_configs) == 1:
        return possible_configs[0]
    elif len(possible_configs) > 1:
        raise IOError(
            "Multiple config.yaml files found: {}. Please specify which "
            "configuration to use by providing `config_path` instead of "
            "`search_folders` to Config.load(). Alternatively, ensure that only a "
            "single valid *config.yaml exists in the search folders: {}.".format(
                str(possible_configs), search_folders
            )
        )
    else:
        raise NotFoundError(
            "Could not find config file {}. Searched in the following locations: "
            "{}".format(file_name, str(search_folders))
        )
