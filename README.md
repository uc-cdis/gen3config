# gen3config

Handle YAML configurations with a given default/expected configuration.
Library will overlay a provided configration over the default and ignore unknown values.

## Quickstart

Example `config-default.yaml` for your application:

```
---
SOME_VALUE: 'default'

EXAMPLE:
    nested:
        key: 'value'
        is_boolean: true
```

Example `config.py` in your application:

```
from gen3config import Config

class AppConfig(Config):
    def __init__(self, *args, **kwargs):
        super(AppConfig, self).__init__(*args, **kwargs)

    def post_process(self):
        # do custom stuff here after parsing config
        pass

default_cfg_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config-default.yaml"
)

config = AppConfig(default_cfg_path)
```

---

Now we want to get a specific configuration.

Example file `~/path/to/app-config.yaml`:

```
SOME_VALUE: 'app-specific configuration'

EXAMPLE:
    nested:
        is_boolean: true
```

Example initialization function in your application:

```
from app.config import config

config.load('~/path/to/app-config.yaml')
```

Then from other files:
```
from app.config import config

print(config["SOME_VALUE"])  # 'app-specific configuration'
print(config["EXAMPLE"]["nested"]["key"])  # 'value'
```

> NOTE: `config["EXAMPLE"]["nested"]["key"]` does not exist in the provided configuration, but it does exist in the default configuration. Therefore, the default value, `'value'` is retrieved.

## Details:

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
    - Example: `nested_value = config["TOP_LEVEL"]["nested"]`
- And of course you can import that into any file you want and will have access to
  keys/values
    - Example: `from fence.config import config`
